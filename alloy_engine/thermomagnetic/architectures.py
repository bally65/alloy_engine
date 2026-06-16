"""熱磁發電機架構預設（飛輪式 vs 活塞式）— 整機級 device_score 參數組。

把兩種能量解構轉成 generator_design / device_score 的整機輸入，供 GA 以
``--w-device`` 對「整機功率密度 × 效率」最佳化時分別代入不同架構假設，
得到「各架構各自的最佳合金 + 預測 P/V·η」（架構 ↔ 材料共同設計）。

數值為工程初估（待 docs 架構研究細化）：
- 飛輪式（旋轉）：冷熱空間分離 → 可逆流回熱（ε 高）；Halbach 氣隙場高；薄箔高頻；穩態耐脆材。
- 活塞式（往復）：冷熱時間交替 → 回熱差（ε 低）；氣隙場較低；共振可掃較滿迴線；往復疲勞。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Architecture:
    name: str
    B_applied_T: float    # 永磁氣隙場 (T)
    regeneration: float   # 回熱器效率 ε ∈ [0,1)
    utilization: float    # M-H 迴線利用率 ∈ (0,1]
    L_meters: float       # 熱磁元件特徵厚度 (m)
    note: str

    def ga_kwargs(self) -> dict:
        """轉成 GPUGeneticAlgorithm 的 device_* 建構參數。"""
        return dict(
            device_B_applied_T=self.B_applied_T,
            device_regeneration=self.regeneration,
            device_utilization=self.utilization,
            device_L_meters=self.L_meters,
        )


FLYWHEEL = Architecture(
    name="飛輪式（旋轉 / Curie-wheel）",
    B_applied_T=1.4, regeneration=0.90, utilization=0.40, L_meters=5.0e-4,
    note="空間分離冷熱→逆流回熱 ε 0.85–0.95（16層AMR→84%Carnot）；"
         "NdFeB Halbach 1.0–1.5T（磁體保持低溫）；0.5mm 體相板；f~1–5Hz；大 ΔT",
)

PISTON = Architecture(
    name="活塞式（往復 / 共振）",
    B_applied_T=1.2, regeneration=0.20, utilization=0.45, L_meters=5.0e-4,
    note="時間交替冷熱→回熱受限（>1Hz 幾乎失效）；磁體近熱端宜 SmCo；"
         "體相往復 0.5–3Hz（薄膜共振可達 84–200Hz 但體積/ΔT 小）；往復疲勞",
)

ARCHITECTURES: dict[str, Architecture] = {"flywheel": FLYWHEEL, "piston": PISTON}
