"""
PyTorch MLP 代理模型：訓練、推論、checkpoint 存取。

四個獨立模型：Tc, Hc (log-space), Br, σy。
選用輕量 MLP（input → 128 → 128 → 64 → 1）：
  - GA 評估時不需在 CPU/GPU 之間搬資料
  - 推論延遲低（<1 ms / 100K 樣本）
  - 相容後續 ONNX export
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score

from alloy_engine.features.engineering import composition_to_features_torch

logger = logging.getLogger(__name__)

# ── 型別別名 ──────────────────────────────────────────────────────────────────
Scaler = tuple[np.ndarray, np.ndarray, float, float, bool]
GpuScaler = tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, bool]


# ── 模型架構 ──────────────────────────────────────────────────────────────────
class PropertyMLP(nn.Module):
    def __init__(self, in_dim: int, hidden: int = 128, dropout_rate: float = 0.10) -> None:
        super().__init__()
        self.dropout_rate = dropout_rate
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden),      nn.GELU(),
            nn.Dropout(dropout_rate),
            nn.Linear(hidden, hidden),      nn.GELU(),
            nn.Dropout(dropout_rate),
            nn.Linear(hidden, hidden // 2), nn.GELU(),
            nn.Dropout(dropout_rate),
            nn.Linear(hidden // 2, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


# ── 訓練 ──────────────────────────────────────────────────────────────────────
def train_mlp(
    X: np.ndarray,
    y: np.ndarray,
    label: str,
    device: torch.device,
    epochs: int = 300,
    batch_size: int = 256,
    hidden: int = 128,
    lr: float = 1.5e-3,
    target_log: bool = False,
) -> tuple[PropertyMLP, Scaler]:
    """
    訓練單個 MLP，回傳最佳模型與標準化參數。

    Args:
        target_log: 若 True，對 y 取 log1p 後訓練（適用 Hc 等偏態分佈）
    """
    y_t = np.log1p(y) if target_log else y.copy()
    x_mean, x_std = X.mean(0), X.std(0) + 1e-6
    y_mean, y_std = float(y_t.mean()), float(y_t.std() + 1e-6)

    Xn = ((X - x_mean) / x_std).astype(np.float32)
    yn = ((y_t - y_mean) / y_std).astype(np.float32)

    X_tr, X_te, y_tr, y_te = train_test_split(Xn, yn, test_size=0.15, random_state=42)
    Xtr = torch.from_numpy(X_tr).to(device)
    ytr = torch.from_numpy(y_tr).to(device)
    Xte = torch.from_numpy(X_te).to(device)
    y_te_np = y_te * y_std + y_mean  # 原始尺度，供 R² 計算

    model = PropertyMLP(X.shape[1], hidden=hidden).to(device)
    opt   = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-5)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)

    best_r2, best_state = -np.inf, None
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(Xtr.size(0), device=device)
        for i in range(0, Xtr.size(0), batch_size):
            idx  = perm[i : i + batch_size]
            loss = F.smooth_l1_loss(model(Xtr[idx]), ytr[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
        sched.step()

        if (ep + 1) % 30 == 0:
            model.eval()
            with torch.no_grad():
                pred_norm = model(Xte).cpu().numpy()
            pred_real = pred_norm * y_std + y_mean
            if target_log:
                pred_real = np.expm1(pred_real)
                y_real    = np.expm1(y_te_np)
            else:
                y_real = y_te_np
            r2 = r2_score(y_real, pred_real)
            if r2 > best_r2:
                best_r2    = r2
                best_state = {k: v.clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    logger.info("  %-15s: best R² = %.4f", label, best_r2)
    scaler: Scaler = (x_mean.astype(np.float32), x_std.astype(np.float32),
                      y_mean, y_std, target_log)
    return model, scaler


# ── GPU scaler ────────────────────────────────────────────────────────────────
def _to_gpu_scaler(scaler: Scaler, device: torch.device) -> GpuScaler:
    x_mean, x_std, y_mean, y_std, log_t = scaler
    return (
        torch.from_numpy(x_mean).to(device),
        torch.from_numpy(x_std).to(device),
        torch.tensor(y_mean, dtype=torch.float32, device=device),
        torch.tensor(y_std,  dtype=torch.float32, device=device),
        log_t,
    )


# ── 推論包裝 ──────────────────────────────────────────────────────────────────
@dataclass
class SurrogateBundle:
    """封裝 4 個 MLP + scaler，提供統一推論介面。"""

    mlp_tc:       PropertyMLP
    mlp_hc:       PropertyMLP
    mlp_br:       PropertyMLP
    mlp_strength: PropertyMLP

    sc_tc:       Scaler
    sc_hc:       Scaler
    sc_br:       Scaler
    sc_strength: Scaler

    device: torch.device
    element_matrix_t: torch.Tensor = field(repr=False)

    # GPU scaler（lazy init）
    _sc_tc_g:       GpuScaler | None = field(default=None, init=False, repr=False)
    _sc_hc_g:       GpuScaler | None = field(default=None, init=False, repr=False)
    _sc_br_g:       GpuScaler | None = field(default=None, init=False, repr=False)
    _sc_strength_g: GpuScaler | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        for m in [self.mlp_tc, self.mlp_hc, self.mlp_br, self.mlp_strength]:
            m.eval()
        self._sc_tc_g       = _to_gpu_scaler(self.sc_tc,       self.device)
        self._sc_hc_g       = _to_gpu_scaler(self.sc_hc,       self.device)
        self._sc_br_g       = _to_gpu_scaler(self.sc_br,       self.device)
        self._sc_strength_g = _to_gpu_scaler(self.sc_strength, self.device)

    # ── 訓練入口 ──────────────────────────────────────────────────────────────
    @classmethod
    def from_trained(
        cls,
        X_features:    np.ndarray,
        tc_data:       np.ndarray,
        hc_data:       np.ndarray,
        br_data:       np.ndarray,
        strength_data: np.ndarray,
        device:        torch.device,
        epochs:        int = 300,
        batch_size:    int = 256,
        hidden:        int = 128,
        lr:            float = 1.5e-3,
    ) -> "SurrogateBundle":
        logger.info("訓練 4 個 MLP 代理模型…")
        from alloy_engine.data.elements import get_element_matrix
        element_matrix_t = torch.from_numpy(get_element_matrix()).to(device)

        common = dict(device=device, epochs=epochs, batch_size=batch_size,
                      hidden=hidden, lr=lr)
        mlp_tc,       sc_tc       = train_mlp(X_features, tc_data,       "Tc (K)",    **common)
        mlp_hc,       sc_hc       = train_mlp(X_features, hc_data,       "Hc (A/m)",  target_log=True, **common)
        mlp_br,       sc_br       = train_mlp(X_features, br_data,       "Br (T)",    **common)
        mlp_strength, sc_strength = train_mlp(X_features, strength_data, "σy (MPa)",  **common)

        return cls(
            mlp_tc=mlp_tc, mlp_hc=mlp_hc, mlp_br=mlp_br, mlp_strength=mlp_strength,
            sc_tc=sc_tc,   sc_hc=sc_hc,   sc_br=sc_br,   sc_strength=sc_strength,
            device=device, element_matrix_t=element_matrix_t,
        )

    # ── Checkpoint I/O ────────────────────────────────────────────────────────
    def replace_tc_head(self, tc_model: PropertyMLP, tc_scaler: Scaler) -> "SurrogateBundle":
        """
        以另一個（通常是真實資料訓練的）Tc 模型就地替換 Tc 頭（D2）。

        前提：tc_model 的特徵管線與本 bundle 相同（36 維 Oliynyk），
        scaler 為 (x_mean, x_std, y_mean, y_std, log_t)。其餘三頭不動。
        替換後可 save() 成「單一 checkpoint、真實 Tc + 合成 Hc/Br/σy」的統一 bundle，
        下游以標準 SurrogateBundle.load 取用，無需 HybridBundle 包裝或 --hybrid-tc 旗標。
        """
        self.mlp_tc = tc_model.to(self.device).eval()
        self.sc_tc = tc_scaler
        self._sc_tc_g = _to_gpu_scaler(tc_scaler, self.device)
        return self

    def save(self, path: Path | str) -> None:
        path = Path(path)
        payload: dict[str, Any] = {
            "mlp_tc":       self.mlp_tc.state_dict(),
            "mlp_hc":       self.mlp_hc.state_dict(),
            "mlp_br":       self.mlp_br.state_dict(),
            "mlp_strength": self.mlp_strength.state_dict(),
            "sc_tc":        self.sc_tc,
            "sc_hc":        self.sc_hc,
            "sc_br":        self.sc_br,
            "sc_strength":  self.sc_strength,
            "in_dim":       next(iter(self.mlp_tc.parameters())).shape[1],
            "hidden":       self.mlp_tc.net[0].out_features,
            "dropout_rate": self.mlp_tc.dropout_rate,
        }
        torch.save(payload, path)
        logger.info("Checkpoint 已儲存至 %s", path)

    @classmethod
    def load(cls, path: Path | str, device: torch.device) -> "SurrogateBundle":
        from alloy_engine.data.elements import get_element_matrix
        path = Path(path)
        payload = torch.load(path, map_location=device, weights_only=False)

        in_dim       = payload["in_dim"]
        hidden       = payload["hidden"]
        dropout_rate = payload.get("dropout_rate", 0.0)  # backwards-compatible

        def _build(key: str) -> PropertyMLP:
            m = PropertyMLP(in_dim, hidden, dropout_rate).to(device)
            m.load_state_dict(payload[key])
            return m

        element_matrix_t = torch.from_numpy(get_element_matrix()).to(device)
        return cls(
            mlp_tc=_build("mlp_tc"), mlp_hc=_build("mlp_hc"),
            mlp_br=_build("mlp_br"), mlp_strength=_build("mlp_strength"),
            sc_tc=payload["sc_tc"],   sc_hc=payload["sc_hc"],
            sc_br=payload["sc_br"],   sc_strength=payload["sc_strength"],
            device=device, element_matrix_t=element_matrix_t,
        )

    # ── 推論 ──────────────────────────────────────────────────────────────────
    @torch.no_grad()
    def predict_properties(
        self, compositions: torch.Tensor
    ) -> dict[str, torch.Tensor]:
        """
        Args:
            compositions: (N, NUM_ELEMENTS) on self.device

        Returns:
            dict with keys: "Tc", "Hc", "Br", "strength"  — each (N,) tensor
        """
        feats = composition_to_features_torch(compositions, self.element_matrix_t)

        def _pred(model: PropertyMLP, sc: GpuScaler) -> torch.Tensor:
            xm, xs, ym, ys, log_t = sc
            out = model((feats - xm) / xs) * ys + ym
            return torch.expm1(out) if log_t else out

        return {
            "Tc":       _pred(self.mlp_tc,       self._sc_tc_g),
            "Hc":       _pred(self.mlp_hc,       self._sc_hc_g),
            "Br":       _pred(self.mlp_br,       self._sc_br_g),
            "strength": _pred(self.mlp_strength, self._sc_strength_g),
        }

    def predict_properties_with_uncertainty(
        self,
        compositions: torch.Tensor,
        n_samples: int = 30,
    ) -> dict[str, torch.Tensor]:
        """
        MC Dropout 推論：n_samples 次 forward pass with Dropout active。

        Args:
            compositions: (N, NUM_ELEMENTS) on self.device
            n_samples: Monte-Carlo samples (default 30)

        Returns:
            dict with 8 keys: Tc_mean, Tc_std, Hc_mean, Hc_std,
                               Br_mean, Br_std, strength_mean, strength_std
        """
        models = [self.mlp_tc, self.mlp_hc, self.mlp_br, self.mlp_strength]
        for m in models:
            m.train()  # enables Dropout at inference time

        keys = ["Tc", "Hc", "Br", "strength"]
        samples: dict[str, list[torch.Tensor]] = {k: [] for k in keys}

        with torch.no_grad():
            for _ in range(n_samples):
                preds = self.predict_properties(compositions)
                for k in keys:
                    samples[k].append(preds[k])

        for m in models:
            m.eval()

        result: dict[str, torch.Tensor] = {}
        for k in keys:
            stacked = torch.stack(samples[k])   # (n_samples, N)
            result[f"{k}_mean"] = stacked.mean(dim=0)
            result[f"{k}_std"]  = stacked.std(dim=0)
        return result
