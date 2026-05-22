"""
冷氣化學清潔計算模組
涵蓋：溶解動力學（Noyes-Whitney）、界面活性劑表面張力、接觸角、剪切力
"""
import math
from dataclasses import dataclass, field
from typing import List, Optional


# ─── 污垢類型資料庫 ──────────────────────────────────────────
CONTAMINATION_DB = {
    'dust_general': {
        'name': '一般灰塵',
        'density': 1200,           # kg/m³
        'diffusion_coeff': 8e-10,  # m²/s
        'saturation_conc': 0.05,   # kg/m³
        'layer_thickness_um': 50,  # 微米
        'soluble_fraction': 0.6,   # 可溶比例
    },
    'grease_light': {
        'name': '輕度油污',
        'density': 900,
        'diffusion_coeff': 3e-10,
        'saturation_conc': 0.01,
        'layer_thickness_um': 30,
        'soluble_fraction': 0.85,
    },
    'grease_heavy': {
        'name': '重度油污/廚房油垢',
        'density': 920,
        'diffusion_coeff': 1e-10,
        'saturation_conc': 0.005,
        'layer_thickness_um': 200,
        'soluble_fraction': 0.9,
    },
    'biofilm': {
        'name': '生物膜/黴菌',
        'density': 1050,
        'diffusion_coeff': 5e-11,
        'saturation_conc': 0.02,
        'layer_thickness_um': 100,
        'soluble_fraction': 0.7,
    },
    'mineral_scale': {
        'name': '水垢/礦物質沉積',
        'density': 2700,
        'diffusion_coeff': 2e-11,
        'saturation_conc': 0.002,
        'layer_thickness_um': 80,
        'soluble_fraction': 0.95,
    },
}

# ─── 清潔劑資料庫 ──────────────────────────────────────────
# cmc_pct: 臨界微胞濃度 (% v/v)，各界面活性劑差異極大，不可共用單一值
CLEANER_DB = {
    'alkaline_mild': {
        'name': '弱鹼性清潔劑（pH 9-10）',
        'ph': 9.5,
        'type': 'alkaline',
        'active_ingredient': '碳酸鈉 / 椰子油皂基',
        'surface_tension_reduction': 28,   # mN/m（相對純水 72.8 mN/m，在 CMC 以上）
        'contact_angle_water_deg': 15,
        'cmc_pct': 0.25,                   # 皂基類 CMC 約 0.2~0.4%
        'solubility_boost': {'grease_light': 3.0, 'grease_heavy': 5.0, 'dust_general': 2.0},
        'safe_on_aluminum': True,
        'safe_on_copper': True,
        'rinse_required': True,
        'recommended_conc_pct': (1.0, 3.0),
        'contact_time_min': (3, 10),
        'cost_level': 1,
    },
    'alkaline_strong': {
        'name': '強鹼清潔劑（pH 12-13）',
        'ph': 12.5,
        'type': 'alkaline',
        'active_ingredient': '氫氧化鉀 / 界面活性劑',
        'surface_tension_reduction': 35,
        'contact_angle_water_deg': 8,
        'cmc_pct': 0.15,
        'solubility_boost': {'grease_light': 8.0, 'grease_heavy': 15.0, 'dust_general': 3.0},
        'safe_on_aluminum': False,
        'safe_on_copper': True,
        'rinse_required': True,
        'recommended_conc_pct': (0.5, 2.0),
        'contact_time_min': (2, 5),
        'cost_level': 2,
    },
    'surfactant_neutral': {
        'name': '中性界面活性劑（pH 6-8）',
        'ph': 7.0,
        'type': 'neutral_surfactant',
        'active_ingredient': '非離子界面活性劑 (APG / AEO)',
        'surface_tension_reduction': 40,
        'contact_angle_water_deg': 5,
        'cmc_pct': 0.05,                   # 非離子界面活性劑 CMC 較低，約 0.01~0.1%
        'solubility_boost': {'dust_general': 4.0, 'biofilm': 3.0, 'grease_light': 2.5},
        'safe_on_aluminum': True,
        'safe_on_copper': True,
        'rinse_required': True,
        'recommended_conc_pct': (0.5, 2.0),
        'contact_time_min': (5, 15),
        'cost_level': 2,
    },
    'acid_mild': {
        'name': '弱酸性除垢劑（pH 3-5）',
        'ph': 4.0,
        'type': 'acid',
        'active_ingredient': '檸檬酸 / 草酸',
        'surface_tension_reduction': 15,
        'contact_angle_water_deg': 20,
        'cmc_pct': 0.5,                    # 有機酸本身無明顯 CMC，設較大值使線性段延伸
        'solubility_boost': {'mineral_scale': 20.0, 'dust_general': 1.5},
        'safe_on_aluminum': True,
        'safe_on_copper': False,
        'rinse_required': True,
        'recommended_conc_pct': (2.0, 5.0),
        'contact_time_min': (5, 20),
        'cost_level': 1,
    },
    'disinfectant': {
        'name': '消毒除菌劑',
        'ph': 7.5,
        'type': 'disinfectant',
        'active_ingredient': '季銨鹽 / 過氧化氫',
        'surface_tension_reduction': 20,
        'contact_angle_water_deg': 18,
        'cmc_pct': 0.20,                   # 季銨鹽 CMC 約 0.1~0.3%
        'solubility_boost': {'biofilm': 10.0, 'dust_general': 1.5},
        'safe_on_aluminum': True,
        'safe_on_copper': True,
        'rinse_required': True,
        'recommended_conc_pct': (0.5, 1.5),
        'contact_time_min': (10, 30),
        'cost_level': 2,
    },
}


# ─── 計算函數 ──────────────────────────────────────────────

@dataclass
class DissolutionResult:
    contamination_type: str
    cleaner_name: str
    concentration_pct: float
    contact_time_min: float
    dissolved_fraction: float      # 0~1
    remaining_mass_pct: float
    effective: bool


@dataclass
class SurfaceForceResult:
    surface_tension_mN: float      # mN/m（清潔液）
    contact_angle_deg: float       # 接觸角（清潔液在翅片上）
    spreading_coefficient: float   # 鋪展係數 S = γ_solid - γ_liquid - γ_sl
    shear_stress_Pa: float         # 翅片表面剪切應力
    sliding_force_N_per_m2: float  # 單位面積滑動力


@dataclass
class ChemCleaningReport:
    equipment: str
    contamination: str
    recommended_cleaner: str
    concentration_pct: float
    contact_time_min: float
    surface_tension_mN: float
    contact_angle_deg: float
    dissolved_fraction: float
    combined_effectiveness: str    # '優' | '良' | '可' | '差'
    warnings: List[str] = field(default_factory=list)
    procedure: List[str] = field(default_factory=list)
    alternatives: List[str] = field(default_factory=list)


# ─── 各污垢在「無清潔劑純水」下的基礎溶解特徵時間（秒）───────
# 定義：純水接觸下達到 63% 溶解分率所需時間（即 1/k₀）。
# 由此校準的 k₀ 使接觸時間（分鐘量級）對溶解分率有顯著影響。
# 清潔劑的 solubility_boost 倍率會縮短此時間。
_BASE_DISSOLUTION_TIME_S = {
    'dust_general':   600,   # 純水 ~10 min，灰塵主要靠機械力
    'grease_light':  1800,   # 純水 ~30 min，油污疏水不溶於水
    'grease_heavy':  7200,   # 純水 ~120 min，重油脂
    'biofilm':       3600,   # 純水 ~60 min，生物膜結構緊密
    'mineral_scale': 9999,   # 純水幾乎不溶，需酸性清潔劑
}


def noyes_whitney_dissolution(
    contamination_key: str,
    contact_time_min: float,
    cleaner_key: str = 'alkaline_mild',
    concentration_pct: float = 2.0,
    temperature_C: float = 25.0,
) -> DissolutionResult:
    """
    Noyes-Whitney 一階溶解動力學模型。

    df/dt = k_eff × (1 - f)  →  f(t) = soluble_fraction × (1 - exp(-k_eff × t))

    k_eff = k₀ × boost × conc_factor × temp_factor

    其中：
    - k₀ = 1 / BASE_DISSOLUTION_TIME_S  （校準至分鐘量級有意義）
    - boost: 清潔劑對此污垢的增效倍率
    - conc_factor: 濃度對數效應（Hill 型，以推薦濃度中值為基準）
    - temp_factor: Arrhenius 溫度修正（Ea ≈ 50 kJ/mol for emulsification）
    """
    cont = CONTAMINATION_DB[contamination_key]
    cleaner = CLEANER_DB[cleaner_key]

    # 基礎速率常數（已校準至現實清潔時間）
    k0 = 1.0 / _BASE_DISSOLUTION_TIME_S[contamination_key]

    # 溫度修正（Arrhenius）
    Ea = 50000  # J/mol，皂化/乳化反應活化能
    R = 8.314
    T_ref = 298.15  # 25°C
    T_K = temperature_C + 273.15
    temp_factor = math.exp(-Ea / R * (1.0 / T_K - 1.0 / T_ref))

    # 清潔劑種類增效
    boost = cleaner['solubility_boost'].get(contamination_key, 1.0)

    # 濃度效應：對數型（飽和於高濃度），以推薦濃度中值歸一
    conc_ref = sum(cleaner['recommended_conc_pct']) / 2
    conc_factor = math.log1p(concentration_pct) / math.log1p(conc_ref)

    k_eff = k0 * boost * conc_factor * temp_factor

    t_s = contact_time_min * 60
    f = cont['soluble_fraction'] * (1.0 - math.exp(-k_eff * t_s))

    return DissolutionResult(
        contamination_type=cont['name'],
        cleaner_name=cleaner['name'],
        concentration_pct=concentration_pct,
        contact_time_min=contact_time_min,
        dissolved_fraction=f,
        remaining_mass_pct=(1.0 - f) * 100.0,
        effective=f >= 0.7,
    )


def surface_forces(
    cleaner_key: str,
    concentration_pct: float = 2.0,
    shear_velocity: float = 1.0,  # m/s，清潔水流速
    fin_spacing_mm: float = 1.2,  # 翅片間距
) -> SurfaceForceResult:
    """
    計算清潔液的表面力學特性。
    - 表面張力（線性插補，CMC 效應簡化）
    - 接觸角（Young 方程式近似）
    - 剪切應力（Couette 流假設）
    - 滑動力
    """
    cleaner = CLEANER_DB[cleaner_key]
    gamma_water = 72.8  # mN/m @ 20°C

    # 表面張力：使用各清潔劑自身的 CMC（不再共用 0.3%）
    cmc_pct = cleaner['cmc_pct']
    if concentration_pct <= cmc_pct:
        # CMC 以下：線性下降
        reduction = cleaner['surface_tension_reduction'] * (concentration_pct / cmc_pct)
    else:
        # CMC 以上：趨於平坦（對數微調）
        reduction = cleaner['surface_tension_reduction'] * (
            1.0 + 0.05 * math.log(concentration_pct / cmc_pct)
        )
    gamma_liquid = max(gamma_water - reduction, 25.0)

    # 接觸角：CMC 以上幾乎不再降低，與濃度的依賴同樣飽和
    scale = min(concentration_pct / cmc_pct, 1.0) ** 0.5
    contact_angle = max(cleaner['contact_angle_water_deg'] * (1.0 - 0.5 * scale), 2.0)

    # 鋪展係數（Young 方程式）：S = γ_LG × (cos θ − 1)
    # S ≤ 0 恆成立；θ→0 時 S→0（自發鋪展臨界）。
    # 報告 cos θ 作為「可潤濕性指數」（1 = 完全潤濕，-1 = 完全不潤濕）
    spreading = gamma_liquid * (math.cos(math.radians(contact_angle)) - 1.0)

    # 翅片縫隙剪切應力：Couette 流 τ = μ·V/d
    mu_water = 1.0e-3  # Pa·s @ 20°C
    gap = fin_spacing_mm / 1000
    shear_stress = mu_water * shear_velocity / gap

    # 滑動力（剪切應力作用於污垢底面）
    sliding_force = shear_stress

    return SurfaceForceResult(
        surface_tension_mN=gamma_liquid,
        contact_angle_deg=contact_angle,
        spreading_coefficient=spreading,
        shear_stress_Pa=shear_stress,
        sliding_force_N_per_m2=sliding_force,
    )


def recommend_cleaner(
    contamination_key: str,
    fin_material: str = 'aluminum',
    fin_spacing_mm: float = 1.2,
    target_effectiveness: float = 0.80,  # 目標溶解分率
    temperature_C: float = 25.0,
) -> ChemCleaningReport:
    """
    針對污垢類型與翅片材質，自動推薦最佳清潔劑與操作條件。
    """
    cont = CONTAMINATION_DB[contamination_key]
    warnings = []

    # 材質限制篩選
    safe_cleaners = {
        k: v for k, v in CLEANER_DB.items()
        if (fin_material == 'aluminum' and v['safe_on_aluminum']) or
           (fin_material == 'copper' and v['safe_on_copper'])
    }

    # 對每種清潔劑搜尋最短達標時間
    best_key = None
    best_time = None
    best_fraction = 0

    for cleaner_key, cleaner in safe_cleaners.items():
        # 以推薦濃度中值測試
        conc = sum(cleaner['recommended_conc_pct']) / 2
        # 最大接觸時間（推薦範圍上限）
        max_time = cleaner['contact_time_min'][1]
        result = noyes_whitney_dissolution(
            contamination_key, max_time, cleaner_key, conc, temperature_C
        )
        if result.dissolved_fraction >= target_effectiveness:
            # 二分搜尋最短時間
            lo, hi = cleaner['contact_time_min'][0], max_time
            for _ in range(20):
                mid = (lo + hi) / 2
                r = noyes_whitney_dissolution(contamination_key, mid, cleaner_key, conc, temperature_C)
                if r.dissolved_fraction >= target_effectiveness:
                    hi = mid
                else:
                    lo = mid
            t_needed = hi
            if best_time is None or t_needed < best_time:
                best_time = t_needed
                best_key = cleaner_key
                best_fraction = noyes_whitney_dissolution(
                    contamination_key, t_needed, cleaner_key, conc, temperature_C
                ).dissolved_fraction

    # 若無法達標，選效果最好的
    if best_key is None:
        best_key = max(
            safe_cleaners,
            key=lambda k: noyes_whitney_dissolution(
                contamination_key,
                CLEANER_DB[k]['contact_time_min'][1],
                k,
                sum(CLEANER_DB[k]['recommended_conc_pct']) / 2,
                temperature_C,
            ).dissolved_fraction
        )
        best_time = CLEANER_DB[best_key]['contact_time_min'][1]
        conc = sum(CLEANER_DB[best_key]['recommended_conc_pct']) / 2
        best_fraction = noyes_whitney_dissolution(
            contamination_key, best_time, best_key, conc, temperature_C
        ).dissolved_fraction
        warnings.append(f"此污垢類型難以達到 {target_effectiveness*100:.0f}% 效果，建議機械輔助清潔")

    cleaner = CLEANER_DB[best_key]
    conc = sum(cleaner['recommended_conc_pct']) / 2

    # 表面力學
    forces = surface_forces(best_key, conc, shear_velocity=1.5, fin_spacing_mm=fin_spacing_mm)

    # 效果評級
    if best_fraction >= 0.90:
        effectiveness = '優'
    elif best_fraction >= 0.75:
        effectiveness = '良'
    elif best_fraction >= 0.55:
        effectiveness = '可'
    else:
        effectiveness = '差'

    if not cleaner['safe_on_aluminum'] and fin_material == 'aluminum':
        warnings.append("⚠ 所選清潔劑可能腐蝕鋁翅片，請稀釋至建議濃度並縮短接觸時間")
    if forces.contact_angle_deg > 30:
        warnings.append("表面張力偏高，建議提高清潔劑濃度或預濕翅片")

    procedure = [
        f"1. 將清潔劑以 {conc:.1f}% 濃度兌水稀釋",
        f"2. 均勻噴灑於翅片表面，確保完全覆蓋",
        f"3. 靜置 {best_time:.0f} 分鐘（接觸反應時間）",
        f"4. 以清水由上而下沖洗，搭配 $cleaning skill 建議水壓",
        f"5. 確認排水清澈無泡沫後完成",
    ]
    if cleaner['rinse_required']:
        procedure.append("6. 充分清水沖洗，避免殘留清潔劑腐蝕金屬")

    # 替代方案
    alternatives = [
        k for k in safe_cleaners if k != best_key
    ][:2]
    alt_names = [CLEANER_DB[k]['name'] for k in alternatives]

    return ChemCleaningReport(
        equipment=f"{fin_material} 翅片",
        contamination=cont['name'],
        recommended_cleaner=cleaner['name'],
        concentration_pct=conc,
        contact_time_min=best_time,
        surface_tension_mN=forces.surface_tension_mN,
        contact_angle_deg=forces.contact_angle_deg,
        dissolved_fraction=best_fraction,
        combined_effectiveness=effectiveness,
        warnings=warnings,
        procedure=procedure,
        alternatives=alt_names,
    )
