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
CLEANER_DB = {
    'alkaline_mild': {
        'name': '弱鹼性清潔劑（pH 9-10）',
        'ph': 9.5,
        'type': 'alkaline',
        'active_ingredient': '碳酸鈉 / 椰子油皂基',
        'surface_tension_reduction': 28,   # mN/m（相對純水 72.8 mN/m）
        'contact_angle_water_deg': 15,
        'solubility_boost': {'grease_light': 3.0, 'grease_heavy': 5.0, 'dust_general': 2.0},
        'safe_on_aluminum': True,
        'safe_on_copper': True,
        'rinse_required': True,
        'recommended_conc_pct': (1.0, 3.0),   # % v/v
        'contact_time_min': (3, 10),
        'cost_level': 1,  # 1=低, 2=中, 3=高
    },
    'alkaline_strong': {
        'name': '強鹼清潔劑（pH 12-13）',
        'ph': 12.5,
        'type': 'alkaline',
        'active_ingredient': '氫氧化鉀 / 界面活性劑',
        'surface_tension_reduction': 35,
        'contact_angle_water_deg': 8,
        'solubility_boost': {'grease_light': 8.0, 'grease_heavy': 15.0, 'dust_general': 3.0},
        'safe_on_aluminum': False,  # 強鹼會腐蝕鋁
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
        'solubility_boost': {'mineral_scale': 20.0, 'dust_general': 1.5},
        'safe_on_aluminum': True,
        'safe_on_copper': False,  # 弱酸會氧化銅
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


def noyes_whitney_dissolution(
    contamination_key: str,
    contact_time_min: float,
    cleaner_key: str = 'alkaline_mild',
    concentration_pct: float = 2.0,
    temperature_C: float = 25.0,
) -> DissolutionResult:
    """
    Noyes-Whitney 方程式計算溶解分率。
    dC/dt = (D·A) / (h·V) · (Cs - C)

    溶解分率隨時間：f(t) = 1 - exp(-k·t)
    其中 k 受溫度（Arrhenius）、清潔劑濃度、界面活性劑增效影響。
    """
    cont = CONTAMINATION_DB[contamination_key]
    cleaner = CLEANER_DB[cleaner_key]

    D = cont['diffusion_coeff']  # 擴散係數
    h = cont['layer_thickness_um'] * 1e-6  # 擴散層厚度 m

    # 基礎速率常數 k = D / h² （量綱：1/s）
    k_base = D / (h ** 2)

    # 溫度修正（Arrhenius，Ea ≈ 40 kJ/mol）
    Ea = 40000  # J/mol
    R = 8.314
    T_ref = 298.15
    T = temperature_C + 273.15
    k_temp = k_base * math.exp(-Ea / R * (1/T - 1/T_ref))

    # 清潔劑增效（濃度效應 + 種類效應）
    boost = cleaner['solubility_boost'].get(contamination_key, 1.0)
    conc_factor = math.log1p(concentration_pct) / math.log1p(2.0)  # 以 2% 為基準歸一
    k_effective = k_temp * boost * conc_factor

    # 溶解分率 f = soluble_fraction × (1 - exp(-k·t))
    t_s = contact_time_min * 60
    f = cont['soluble_fraction'] * (1 - math.exp(-k_effective * t_s))

    return DissolutionResult(
        contamination_type=cont['name'],
        cleaner_name=cleaner['name'],
        concentration_pct=concentration_pct,
        contact_time_min=contact_time_min,
        dissolved_fraction=f,
        remaining_mass_pct=(1 - f) * 100,
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
    water_surface_tension = 72.8  # mN/m @ 20°C

    # 表面張力（隨濃度對數下降，達 CMC 後趨於平坦）
    cmc_pct = 0.3  # 假設 CMC 約 0.3%
    if concentration_pct <= cmc_pct:
        reduction = cleaner['surface_tension_reduction'] * (concentration_pct / cmc_pct)
    else:
        reduction = cleaner['surface_tension_reduction']
    gamma_liquid = max(water_surface_tension - reduction, 25.0)  # 最低 25 mN/m

    # 接觸角（加入濃度影響）
    contact_angle = cleaner['contact_angle_water_deg'] * math.sqrt(cmc_pct / max(concentration_pct, cmc_pct))
    contact_angle = max(contact_angle, 2.0)

    # 鋪展係數 S（正值代表可自發鋪展）
    gamma_solid_air = 45.0  # 鋁翅片 mN/m（典型值）
    gamma_solid_liquid = gamma_liquid * math.cos(math.radians(contact_angle))
    spreading = gamma_solid_air - gamma_liquid - (gamma_solid_liquid * 0.1)

    # 剪切應力（翅片縫隙 Couette 流：τ = μ·V/d）
    mu_water = 1.0e-3   # Pa·s（近似，清潔液黏度略高但忽略）
    gap = fin_spacing_mm / 1000
    shear_stress = mu_water * shear_velocity / gap

    # 滑動力（單位面積）= 剪切應力 + 浮力輔助（簡化）
    sliding_force = shear_stress * 1.2  # 1.2 倍修正（表面張力梯度貢獻）

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
