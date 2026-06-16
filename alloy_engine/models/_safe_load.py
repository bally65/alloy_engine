"""安全的 checkpoint 載入工具（P0-2 / F-DES-01~04, F-SCI-06）。

問題
----
原程式以 ``torch.load(..., weights_only=False)`` 與裸 ``pickle.loads`` 載入
checkpoint。兩者都會執行檔案中內嵌的任意 Python（pickle ``__reduce__`` / GLOBAL），
故載入「他人提供／被竄改」的 ``.pt`` / ``.pkl`` 即等同遠端程式碼執行 (RCE)。

對策
----
* ``safe_torch_load``：以 ``weights_only=True`` 載入 torch checkpoint（預設不執行任意
  程式碼），並僅把「numpy 陣列重建函式」加入安全白名單——這些函式只重建陣列，
  無法執行任意程式碼，故仍阻擋 RCE，同時讓含 numpy scaler 的既有 checkpoint 可載入。
* ``restricted_pickle_load``：sklearn 模型無 ``weights_only`` 等價物，改用限制式
  Unpickler，只允許 ``numpy`` / ``sklearn`` / ``scipy`` 與少數安全 builtins，
  阻擋 ``os`` / ``subprocess`` / ``builtins.eval`` 等 RCE 載具。
* 兩者皆支援可選的 SHA-256 完整性驗證（``expected_sha256``）。

逃生口
------
完全信任、且確定未被竄改的「你自己產生」的本地 checkpoint，可設環境變數
``ALLOY_ALLOW_UNSAFE_LOAD=1`` 走舊版完整 pickle，但這會重新開啟 RCE 風險。

最佳長期解
----------
surrogate 改用 safetensors 序列化；sklearn 改用 ``skops.io``（白名單）或 ONNX；
所有 checkpoint 附 SHA-256/簽章並於載入時驗證。
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
import pickle
from pathlib import Path
from typing import Any

import torch

logger = logging.getLogger(__name__)

_UNSAFE_ENV = "ALLOY_ALLOW_UNSAFE_LOAD"


# ── 完整性 ────────────────────────────────────────────────────────────────────
def sha256_file(path: str | Path) -> str:
    """回傳檔案的 SHA-256 十六進位摘要（分塊讀取，支援大檔）。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_sha256(path: str | Path, expected: str | None) -> None:
    if not expected:
        return
    actual = sha256_file(path)
    if actual.lower() != expected.lower():
        raise RuntimeError(
            f"Checkpoint SHA-256 不符，拒絕載入（可能被竄改）：{path}\n"
            f"  期望 {expected}\n  實得 {actual}"
        )


def _allow_unsafe() -> bool:
    return os.environ.get(_UNSAFE_ENV) == "1"


# ── torch checkpoint ──────────────────────────────────────────────────────────
def _register_numpy_safe_globals() -> None:
    """把 numpy 陣列重建所需的全域加入 torch 安全白名單（跨 numpy 1.x / 2.x）。

    這些只重建陣列／純量，不能執行任意程式碼，故 weights_only=True + 此白名單
    仍會阻擋任何非白名單 GLOBAL（如 os.system / builtins.eval）→ 不會 RCE。
    """
    add = getattr(torch.serialization, "add_safe_globals", None)
    if add is None:          # 舊版 torch 無此 API（其 weights_only 本就更嚴格）
        return
    globs: list[Any] = []
    try:
        import numpy as np
        globs += [np.ndarray, np.dtype]
        for name in ("float16", "float32", "float64", "int8", "int16",
                     "int32", "int64", "uint8", "bool_", "longlong"):
            t = getattr(np, name, None)
            if t is not None:
                globs.append(t)
        # numpy 2.0 把 dtype 實例類別搬到 numpy.dtypes（Float32DType 等）；
        # checkpoint 內 numpy 陣列的序列化會引用這些類別，需一併白名單。
        try:
            import numpy.dtypes as _npd
            globs += [getattr(_npd, n) for n in dir(_npd) if n.endswith("DType")]
        except Exception:
            pass
    except Exception:        # numpy 不可用時略過——torch 仍可載入純 tensor payload
        pass
    for modname in ("numpy.core.multiarray", "numpy._core.multiarray"):
        try:
            mod = __import__(modname, fromlist=["_reconstruct", "scalar"])
            for fn in ("_reconstruct", "scalar"):
                obj = getattr(mod, fn, None)
                if obj is not None:
                    globs.append(obj)
        except Exception:
            pass
    if globs:
        try:
            add(globs)
        except Exception:
            pass


def safe_torch_load(
    path: str | Path,
    map_location: Any = None,
    *,
    expected_sha256: str | None = None,
):
    """以 ``weights_only=True`` 安全載入 torch checkpoint（預設不執行任意程式碼）。

    Args:
        path:            checkpoint 路徑
        map_location:    傳給 ``torch.load``
        expected_sha256: 若提供，載入前驗證檔案摘要，不符即拒載
    """
    path = Path(path)
    _verify_sha256(path, expected_sha256)

    if _allow_unsafe():
        logger.warning("%s=1：以完整 pickle 載入 %s（不安全，僅限你自己且未竄改的檔案）",
                       _UNSAFE_ENV, path)
        return torch.load(path, map_location=map_location, weights_only=False)

    _register_numpy_safe_globals()
    try:
        return torch.load(path, map_location=map_location, weights_only=True)
    except Exception as e:   # noqa: BLE001 — 轉成可操作的錯誤訊息
        raise RuntimeError(
            f"以 weights_only=True 安全載入 {path} 失敗：{e}\n"
            "此檔可能含非白名單物件（或為舊格式）。確認可信後，可設環境變數 "
            f"{_UNSAFE_ENV}=1 走完整 pickle（會重啟 RCE 風險）。"
        ) from e


# ── sklearn pickle：限制式 Unpickler ──────────────────────────────────────────
_SAFE_PICKLE_PREFIXES = ("numpy", "sklearn", "scipy")
_SAFE_PICKLE_GLOBALS = {
    ("copyreg", "_reconstructor"),
    ("collections", "OrderedDict"),
}
# pickle 重建資料結構所需的安全 builtins（皆為資料建構子，無副作用；
# 刻意不含 eval/exec/getattr/__import__/open 等可執行載具）。
_SAFE_BUILTINS = {
    "range", "slice", "complex", "object", "list", "dict", "tuple",
    "set", "frozenset", "int", "float", "bool", "str", "bytes", "bytearray",
}


class _RestrictedUnpickler(pickle.Unpickler):
    """只允許 numpy / sklearn / scipy 與少數安全 builtins 的 Unpickler。"""

    def find_class(self, module: str, name: str):  # type: ignore[override]
        if module == "builtins" and name in _SAFE_BUILTINS:
            return super().find_class(module, name)
        if (module, name) in _SAFE_PICKLE_GLOBALS:
            return super().find_class(module, name)
        if module.split(".")[0] in _SAFE_PICKLE_PREFIXES:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"封鎖不安全的全域 {module}.{name}（限制式 Unpickler 僅允許 "
            f"{_SAFE_PICKLE_PREFIXES} 與安全 builtins）。確認檔案可信後可設 "
            f"{_UNSAFE_ENV}=1。"
        )


def restricted_pickle_load(
    path: str | Path,
    *,
    expected_sha256: str | None = None,
):
    """以限制式 Unpickler 載入 sklearn pickle（阻擋 os/subprocess/builtins 等 RCE 載具）。

    完全信任檔案可設 ``ALLOY_ALLOW_UNSAFE_LOAD=1`` 走標準 pickle。
    """
    path = Path(path)
    _verify_sha256(path, expected_sha256)
    raw = path.read_bytes()

    if _allow_unsafe():
        logger.warning("%s=1：以標準 pickle 載入 %s（不安全）", _UNSAFE_ENV, path)
        return pickle.loads(raw)

    return _RestrictedUnpickler(io.BytesIO(raw)).load()
