"""由 docs/flywheel_design.json 產生 2D 製造工程圖（平面圖 + 剖面 A-A + 尺寸 + GD&T 註記 +
BOM/成本 + 標題欄）。輸出 docs/flywheel_drawing.png / .pdf。

用法：python scripts/cad_drawing_flywheel.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import Rectangle, Circle, Wedge, FancyArrowPatch

for fname in ["PingFang TC", "Heiti TC", "Arial Unicode MS", "STHeiti"]:
    if any(fname in f.name for f in fm.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [fname]; break
plt.rcParams["axes.unicode_minus"] = False

D = json.loads(Path("docs/flywheel_design.json").read_text())
dim, perf = D["dims"], D["perf"]
OD, HUB, BORE = dim["wheel_OD_mm"], dim["hub_OD_mm"], dim["shaft_bore_mm"]
H, PLATE, NSEG = dim["stack_height_mm"], dim["plate_thickness_mm"], dim["n_segments"]
GAP, SPAN, NZ = dim["gap_mm"], dim["field_span_deg"], dim["n_field_zones"]
MAGL = dim.get("magnet_length_mm") or 6.0
mc = perf["magnet_circuit"]

# 銅線圈估算
rho_cu, rho_steel, rho_alloy = 8960.0, 7850.0, perf["material"]["rho"]
wire_d = 0.8e-3
mean_turn = math.pi * (OD * 0.5e-3)            # 粗估每匝平均周長
n_turns = 400
m_coil = n_turns * mean_turn * (math.pi/4*wire_d**2) * rho_cu
PRICE = dict(alloy=30.0, steel=3.0, copper=12.0)
m_mat = perf["m_material_kg"]; m_mag = perf["m_magnet_kg"]
m_struct = perf["m_total_kg"] - m_mat - m_mag
cost = dict(
    alloy=m_mat*PRICE["alloy"], magnet=mc["magnet_cost_usd"],
    steel=m_struct*PRICE["steel"], copper=m_coil*PRICE["copper"], bearings=40.0, misc=30.0)
cost_total = sum(cost.values())

fig = plt.figure(figsize=(15.5, 10.5)); fig.patch.set_facecolor("white")
GS = fig.add_gridspec(2, 2, height_ratios=[2.05, 1], width_ratios=[1, 1],
                      hspace=0.16, wspace=0.12, left=0.04, right=0.97, top=0.95, bottom=0.04)

STEEL = "#b9bfc7"; ALLOYC = "#8a9099"; MAGT = "#d65a5a"; MAGB = "#4a6fb0"; SHAFTC = "#5b626b"


def dim_line(ax, x1, y1, x2, y2, text, off=0, va="bottom", ha="center", color="#16407a"):
    ax.annotate("", (x2, y2), (x1, y1), arrowprops=dict(arrowstyle="<->", color=color, lw=1))
    ax.text((x1+x2)/2, (y1+y2)/2+off, text, color=color, fontsize=8.5, va=va, ha=ha,
            bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))


# ── 平面圖 (PLAN) ──
axp = fig.add_subplot(GS[0, 0]); axp.set_aspect("equal"); axp.axis("off")
axp.set_title("PLAN VIEW  (俯視)", fontsize=11, weight="bold")
R = OD/2
axp.add_patch(Circle((0, 0), OD/2, fill=False, ec="k", lw=1.6))
axp.add_patch(Circle((0, 0), HUB/2, fill=False, ec="k", lw=1.2))
axp.add_patch(Circle((0, 0), BORE/2, fc=SHAFTC, ec="k", lw=1))
for i in range(NSEG):
    a = math.radians(i*360/NSEG)
    axp.plot([HUB/2*math.cos(a), OD/2*math.cos(a)], [HUB/2*math.sin(a), OD/2*math.sin(a)], color=ALLOYC, lw=0.6)
for k in range(NZ):
    axp.add_patch(Wedge((0, 0), OD/2, k*360/NZ-SPAN/2, k*360/NZ+SPAN/2, width=(OD-HUB)/2,
                        fc=MAGT, alpha=0.32, ec=MAGT, lw=1.2))
axp.add_patch(FancyArrowPatch((-R*0.5, R*0.78), (R*0.5, R*0.78), connectionstyle="arc3,rad=-0.32",
                              arrowstyle="-|>", mutation_scale=14, color="#16407a"))
axp.text(0, R*1.02, "ω", color="#16407a", fontsize=12, ha="center")
dim_line(axp, -OD/2, -OD/2-22, OD/2, -OD/2-22, f"Ø{OD:.0f}", off=-9, va="top")
dim_line(axp, -HUB/2, OD/2+14, HUB/2, OD/2+14, f"Ø{HUB:.0f} (active ID)", off=3)
axp.text(0, -OD/2-40, f"{NSEG}× lamination sectors · magnet zones {NZ}×{SPAN:.0f}°", ha="center", fontsize=8, color="#444")
axp.set_xlim(-OD/2-55, OD/2+55); axp.set_ylim(-OD/2-55, OD/2+60)

# ── 剖面 A-A (SECTION) ──
axs = fig.add_subplot(GS[0, 1]); axs.set_aspect("equal"); axs.axis("off")
axs.set_title("SECTION A–A  (剖面)", fontsize=11, weight="bold")
half = OD/2
axs.add_patch(Rectangle((-half, -H/2), OD, H, fc=ALLOYC, ec="k", lw=1.2))            # active ring (both sides)
axs.add_patch(Rectangle((half-(OD-HUB)/2, -H/2), 0, H, fill=False))
axs.add_patch(Rectangle((-HUB/2, -H/2), HUB, H, fc=STEEL, ec="k", lw=1))             # hub region
axs.add_patch(Rectangle((-BORE/2, -H), BORE, 2.0*H, fc=SHAFTC, ec="k", lw=1))        # shaft
for sgn, col in [(1, MAGT), (-1, MAGB)]:
    for xc in [-(half+HUB/2)/2, (half+HUB/2)/2]:
        y0 = sgn*(H/2+GAP)
        axs.add_patch(Rectangle((xc-(OD-HUB)/4, y0 if sgn > 0 else y0-MAGL), (OD-HUB)/2, MAGL, fc=col, ec="k", lw=1))
dim_line(axs, -half, -H/2-30, half, -H/2-30, f"Ø{OD:.0f}", off=-9, va="top")
dim_line(axs, half+18, -H/2, half+18, H/2, f"{H:.0f}", off=0, ha="left")
dim_line(axs, -half-18, H/2, -half-18, H/2+GAP, f"gap {GAP:.1f}", off=0, ha="right")
dim_line(axs, half+18, H/2+GAP, half+18, H/2+GAP+MAGL, f"mag {MAGL:.1f}", off=0, ha="left")
axs.text(0, -H-14, f"plate t={PLATE} mm · {dim['n_plates_total']} laminations · fill {dim['fill']}", ha="center", fontsize=8, color="#444")
axs.text(0, H/2+GAP+MAGL+10, f"PM {mc['grade']} (top N / bot S)", ha="center", fontsize=8, color=MAGT)
axs.set_xlim(-half-70, half+70); axs.set_ylim(-H-30, H/2+GAP+MAGL+25)

# ── BOM + 成本 ──
axb = fig.add_subplot(GS[1, 0]); axb.axis("off")
axb.set_title("BILL OF MATERIALS / 成本估算", fontsize=10.5, weight="bold", loc="left")
rows = [
    ["#", "Part", "Material", "Qty", "Mass kg", "Cost $"],
    ["1", "Active ring (laminations)", "Fe-Co-Ni-Al 0.2mm", f"{dim['n_plates_total']}", f"{m_mat:.1f}", f"{cost['alloy']:.0f}"],
    ["2", "Permanent magnets", mc["grade"], f"{NZ*2}", f"{m_mag:.2f}", f"{cost['magnet']:.0f}"],
    ["3", "Rotor hub + disc", "Steel (M270)", "1", f"{m_struct:.1f}", f"{cost['steel']:.0f}"],
    ["4", "Stator coil", "Cu Ø0.8mm ×400t", "1", f"{m_coil:.2f}", f"{cost['copper']:.0f}"],
    ["5", "Bearings / seals", "—", "2", "—", f"{cost['bearings']:.0f}"],
    ["6", "Fasteners / misc", "—", "—", "—", f"{cost['misc']:.0f}"],
    ["", "TOTAL", "", "", f"{perf['m_total_kg']+m_coil:.1f}", f"{cost_total:.0f}"],
]
tab = axb.table(cellText=rows, loc="center", cellLoc="left",
                colWidths=[0.05, 0.30, 0.27, 0.10, 0.13, 0.13])
tab.auto_set_font_size(False); tab.set_fontsize(8.6); tab.scale(1, 1.42)
for (r, c), cell in tab.get_celld().items():
    cell.set_edgecolor("#ccc")
    if r == 0: cell.set_facecolor("#1f3a5f"); cell.set_text_props(color="white", weight="bold")
    elif r == len(rows)-1: cell.set_facecolor("#eef1f6"); cell.set_text_props(weight="bold")

# ── 註記 + 標題欄 ──
axn = fig.add_subplot(GS[1, 1]); axn.axis("off")
notes = [
    "NOTES / GD&T:",
    "1. 疊片：0.2 mm 矽鋼/Fe-Co 軟磁箔，層間絕緣，疊壓係數 ≥0.95。",
    "2. 動平衡 G2.5 @ %d rpm；轉子同軸度 Ø0.02 A｜軸承位 Ø0.01。" % round(perf["rpm"]),
    "3. 氣隙 %.1f±0.05 mm（含板）；磁體面平行度 0.02。" % GAP,
    "4. 磁體 %s，工作溫 ≤300°C（需熱隔離/冷側）；退磁裕度 %.0f°C。" % (mc["grade"], mc["demag_margin_C"]),
    "5. 表面：軸承位 Ra0.8，其餘 Ra3.2。未注公差 ISO 2768-m。",
    "6. 回熱器（逆流，ε≈0.95）與熱/冷流道介面另見組裝圖。",
]
y = 0.98
for i, t in enumerate(notes):
    axn.text(0.0, y, t, fontsize=8.4 if i else 9.2, weight="bold" if i == 0 else "normal",
             va="top", ha="left", color="#222", transform=axn.transAxes)
    y -= 0.082 if i == 0 else 0.072
# 標題欄
tb = [["PROJECT", "alloy_engine Thermomagnetic Generator"],
      ["PART", "Flywheel TMG rotor assembly (Curie wheel)"],
      ["DESIGN PT", f"{dim['meta']['target_tc_C']:.0f}°C · {dim['meta']['formula']}"],
      ["PERF", f"P≈{perf['P_total_W']:.0f}W(ceiling) · η {perf['eta_material_pct']}% · {perf['rpm']:.0f}rpm · {perf['V_rms']}Vrms"],
      ["MASS / COST", f"{perf['m_total_kg']+m_coil:.1f} kg · ~${cost_total:.0f}"],
      ["UNITS / SCALE", "mm · NTS"]]
yt = 0.30
ttab = axn.table(cellText=tb, loc="lower left", cellLoc="left", colWidths=[0.24, 0.76], bbox=[0, -0.02, 1, 0.34])
ttab.auto_set_font_size(False); ttab.set_fontsize(8.2)
for (r, c), cell in ttab.get_celld().items():
    cell.set_edgecolor("#999")
    if c == 0: cell.set_facecolor("#1f3a5f"); cell.set_text_props(color="white", weight="bold")

fig.suptitle("Flywheel Thermomagnetic Generator — Manufacturing Drawing (estimates; FEM/DFM review required)",
             fontsize=12.5, weight="bold", y=0.99)
plt.savefig("docs/flywheel_drawing.png", dpi=150, bbox_inches="tight")
plt.savefig("docs/flywheel_drawing.pdf", bbox_inches="tight")
print("saved docs/flywheel_drawing.png / .pdf")
print(f"BOM total ≈ ${cost_total:.0f}  mass ≈ {perf['m_total_kg']+m_coil:.1f} kg")
