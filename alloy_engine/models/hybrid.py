"""
HybridBundle：真實 NEMAD Tc 模型 + 合成 Hc/Br/強度。

動機：NEMAD 真實資料只有 Tc（baseline R²=0.88，遠勝合成的 −0.17），但沒有
Hc/Br/σy。本類別把「真實 Tc 模型」與既有合成 SurrogateBundle 組合，對外提供
與 SurrogateBundle 完全相同的 `predict_properties` 介面，故 GA 無需改動即可
用**真實居禮溫度**搜尋。

Br/Hc/σy 仍為合成（待 MP 校準，見 docs/DATA_SOURCING_ASSESSMENT.md）。
"""
from __future__ import annotations

from pathlib import Path

import torch

from alloy_engine.features.engineering import composition_to_features_torch
from alloy_engine.models.surrogate import (
    SurrogateBundle, PropertyMLP, _to_gpu_scaler,
)


class HybridBundle:
    """介面相容 SurrogateBundle：Tc 來自真實模型，其餘來自合成 bundle。"""

    def __init__(
        self,
        synthetic: SurrogateBundle,
        tc_model: PropertyMLP,
        tc_scaler,
        device: torch.device,
    ) -> None:
        self.synthetic = synthetic
        self.tc_model = tc_model.to(device).eval()
        self.device = device
        self.element_matrix_t = synthetic.element_matrix_t
        self._tc_sc_g = _to_gpu_scaler(tc_scaler, device)

    @torch.no_grad()
    def _real_tc(self, compositions: torch.Tensor) -> torch.Tensor:
        feats = composition_to_features_torch(compositions, self.element_matrix_t)
        xm, xs, ym, ys, log_t = self._tc_sc_g
        out = self.tc_model((feats - xm) / xs) * ys + ym
        return torch.expm1(out) if log_t else out

    @torch.no_grad()
    def predict_properties(self, compositions: torch.Tensor) -> dict[str, torch.Tensor]:
        """回傳 {Tc(真實), Hc, Br, strength(合成)}，每個 (N,) tensor。"""
        out = self.synthetic.predict_properties(compositions)
        out["Tc"] = self._real_tc(compositions)
        return out

    @torch.no_grad()
    def predict_properties_with_uncertainty(
        self, compositions: torch.Tensor, n_samples: int = 30
    ) -> dict[str, torch.Tensor]:
        """合成端走 MC Dropout；真實 Tc 為確定值（std=0）。"""
        res = self.synthetic.predict_properties_with_uncertainty(compositions, n_samples)
        tc = self._real_tc(compositions)
        res["Tc_mean"] = tc
        res["Tc_std"] = torch.zeros_like(tc)
        return res

    @classmethod
    def load(
        cls,
        synthetic_path: Path | str,
        tc_path: Path | str,
        device: torch.device,
    ) -> "HybridBundle":
        synth = SurrogateBundle.load(synthetic_path, device=device)
        payload = torch.load(tc_path, map_location=device, weights_only=False)
        m = PropertyMLP(payload["in_dim"], payload["hidden"]).to(device)
        m.load_state_dict(payload["model_state"])
        return cls(synth, m, payload["scaler"], device)
