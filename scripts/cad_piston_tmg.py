"""活塞/共振懸臂式熱磁發電機 CAD（飛輪式的對照變體）。

懸臂樑（彈簧）末端帶熱磁元件，在熱板/冷板間往復；偏壓磁體提供場，線性線圈取電。
拓撲對標 Ujihara 2007 / EPJ 2019 共振懸臂原型（見架構研究）。

輸出 docs/piston_tmg.step / .stl / .svg。用法：python scripts/cad_piston_tmg.py
"""
from __future__ import annotations

from pathlib import Path

import cadquery as cq
from cadquery import exporters

# 參數 (mm)
BASE = (120, 60, 20)
RISER = (24, 24, 60)
BEAM = (90, 24, 3)          # 懸臂樑（彈簧）
TIP = (30, 24, 8)           # 熱磁元件（往復）
PLATE = (36, 30, 6)         # 熱板 / 冷板
MAG = (20, 24, 42)          # 偏壓磁體
GAPv = 8.0                  # 元件與熱/冷板的單側間隙
COIL_R, COIL_r = 22.0, 4.0  # 線圈環

z_base = BASE[2] / 2
z_beam = BASE[2] + RISER[2]                       # 樑中心高
x_tip = BEAM[0] - TIP[0] / 2                      # 末端
z_tip = z_beam - BEAM[2] / 2 - TIP[2] / 2

base = cq.Workplane("XY").box(*BASE).translate((BASE[0] / 2 - 10, 0, z_base))
riser = cq.Workplane("XY").box(*RISER).translate((RISER[0] / 2 - 10, 0, BASE[2] + RISER[2] / 2))
beam = cq.Workplane("XY").box(*BEAM).translate((BEAM[0] / 2 - 10 + RISER[0] / 2, 0, z_beam))
tip = cq.Workplane("XY").box(*TIP).translate((x_tip, 0, z_tip))
hot = cq.Workplane("XY").box(*PLATE).translate((x_tip, 0, z_tip + TIP[2] / 2 + GAPv + PLATE[2] / 2))
cold = cq.Workplane("XY").box(*PLATE).translate((x_tip, 0, z_tip - TIP[2] / 2 - GAPv - PLATE[2] / 2))
mag = cq.Workplane("XY").box(*MAG).translate((x_tip + TIP[0] / 2 + MAG[0] / 2 + 4, 0, z_tip))
coil = (cq.Workplane("XZ").workplane(offset=-COIL_R)
        .center(x_tip, z_tip).circle(COIL_R).circle(COIL_R - COIL_r).extrude(COIL_r * 2))

asm = (cq.Assembly(name="piston_resonant_TMG")
       .add(base, name="base", color=cq.Color(0.45, 0.47, 0.50))
       .add(riser, name="riser", color=cq.Color(0.45, 0.47, 0.50))
       .add(beam, name="cantilever_spring", color=cq.Color(0.62, 0.66, 0.72))
       .add(tip, name="tm_element", color=cq.Color(0.55, 0.57, 0.60))
       .add(hot, name="hot_plate", color=cq.Color(0.80, 0.20, 0.20))
       .add(cold, name="cold_plate", color=cq.Color(0.20, 0.35, 0.80))
       .add(mag, name="bias_magnet", color=cq.Color(0.42, 0.30, 0.58))
       .add(coil, name="pickup_coil", color=cq.Color(0.85, 0.55, 0.20)))

out_step, out_stl, out_svg = Path("docs/piston_tmg.step"), Path("docs/piston_tmg.stl"), Path("docs/piston_tmg.svg")
asm.save(str(out_step)); print("saved", out_step)

combined = base
for s in [riser, beam, tip, hot, cold, mag, coil]:
    combined = combined.union(s)
exporters.export(combined, str(out_stl)); print("saved", out_stl)
exporters.export(combined, str(out_svg),
                 opt={"projectionDir": (1.0, -1.0, 0.5), "showAxes": False, "strokeWidth": 0.4,
                      "width": 900, "height": 620})
print("saved", out_svg)
print("OK — piston CAD generated.")
