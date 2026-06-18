"""由 design_flywheel_tmg.py 的尺寸 JSON 產生飛輪式 TMG 參數化 CAD。

讀 docs/flywheel_design.json → 建轉子活性環（分扇槽）、中央輪轂、軸、飛輪、
上下夾的兩組磁體（場區）→ 匯出：
  docs/flywheel_tmg.step  (帶顏色組件，可在 CAD 編輯)
  docs/flywheel_tmg.stl   (合併實體，可 3D 列印/檢視)
  docs/flywheel_tmg.svg   (等角投影預覽)

用法：python scripts/cad_flywheel_tmg.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import cadquery as cq
from cadquery import exporters

DIM_PATHS = [Path("docs/flywheel_design.json"), Path("/tmp/flywheel_design.json")]
src = next((p for p in DIM_PATHS if p.exists()), None)
if src is None:
    raise SystemExit("找不到 flywheel_design.json，請先跑 design_flywheel_tmg.py")
D = json.loads(src.read_text())["dims"]


def sector(r_in: float, r_out: float, span_deg: float, h: float, n: int = 24) -> cq.Workplane:
    """環狀扇區實體（中心在原點，沿 +Z 擠出 h）。"""
    a0, a1 = -math.radians(span_deg) / 2, math.radians(span_deg) / 2
    out = [(r_out * math.cos(a0 + (a1 - a0) * i / n), r_out * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
    inn = [(r_in * math.cos(a1 - (a1 - a0) * i / n), r_in * math.sin(a1 - (a1 - a0) * i / n)) for i in range(n + 1)]
    return cq.Workplane("XY").polyline(out + inn).close().extrude(h)


# 尺寸 (mm)
Rw, Rh, Rs = D["wheel_OD_mm"] / 2, D["hub_OD_mm"] / 2, D["shaft_bore_mm"] / 2
H = D["stack_height_mm"]
nseg = int(D["n_segments"])
gap = D["gap_mm"]
span = D["field_span_deg"]
nzone = int(D["n_field_zones"])
fw_R, fw_t = D["flywheel_OD_mm"] / 2, D["flywheel_thickness_mm"]
shaft_len = D["shaft_len_mm"]
mag_h = 20.0   # 磁體軸向厚 mm

# 1) 轉子活性環（OD..hub），中心於 z=0
ring = cq.Workplane("XY").workplane(offset=-H / 2).circle(Rw).circle(Rh).extrude(H)
# 切 nseg 條徑向窄槽（顯示分扇疊片 + 回熱流道）
slot = 1.6  # 槽角寬近似（用薄扇區）
cutters = None
for i in range(nseg):
    c = sector(Rh - 1, Rw + 1, slot, H + 2, n=4).translate((0, 0, -(H / 2) - 1)).rotate((0, 0, 0), (0, 0, 1), i * 360.0 / nseg)
    cutters = c if cutters is None else cutters.union(c)
ring = ring.cut(cutters)

# 2) 中央輪轂盤（hub..shaft），較薄
hub_t = 14.0
hub = cq.Workplane("XY").workplane(offset=-hub_t / 2).circle(Rh + 2).circle(Rs).extrude(hub_t)

# 3) 軸
shaft = cq.Workplane("XY").workplane(offset=-shaft_len * 0.5).circle(Rs).extrude(shaft_len)

# 4) 飛輪環（軸下端）
flywheel = cq.Workplane("XY").workplane(offset=-shaft_len * 0.5 + 10).circle(fw_R).circle(Rs).extrude(fw_t)

# 5) 磁體：每個場區上下各一片扇區，夾住活性環（軸向氣隙場）
mag_top, mag_bot = [], []
z_top = H / 2 + gap
z_bot = -H / 2 - gap - mag_h
for k in range(nzone):
    ang = k * 360.0 / nzone
    mt = sector(Rh, Rw, span, mag_h, n=24).translate((0, 0, z_top)).rotate((0, 0, 0), (0, 0, 1), ang)
    mb = sector(Rh, Rw, span, mag_h, n=24).translate((0, 0, z_bot)).rotate((0, 0, 0), (0, 0, 1), ang)
    mag_top.append(mt); mag_bot.append(mb)

# 組件（帶顏色，STEP 用）
asm = (cq.Assembly(name="flywheel_TMG")
       .add(ring, name="rotor_active_ring", color=cq.Color(0.55, 0.57, 0.60))
       .add(hub, name="hub_web", color=cq.Color(0.45, 0.47, 0.50))
       .add(shaft, name="shaft", color=cq.Color(0.30, 0.32, 0.35))
       .add(flywheel, name="flywheel", color=cq.Color(0.40, 0.42, 0.45)))
for i, m in enumerate(mag_top):
    asm.add(m, name=f"magnet_top_{i}", color=cq.Color(0.80, 0.20, 0.20))
for i, m in enumerate(mag_bot):
    asm.add(m, name=f"magnet_bot_{i}", color=cq.Color(0.20, 0.35, 0.80))

out_step = Path("docs/flywheel_tmg.step")
out_stl = Path("docs/flywheel_tmg.stl")
out_svg = Path("docs/flywheel_tmg.svg")

asm.save(str(out_step))
print("saved", out_step)

# 合併實體供 STL / SVG
combined = ring
for s in [hub, shaft, flywheel] + mag_top + mag_bot:
    combined = combined.union(s)
exporters.export(combined, str(out_stl))
print("saved", out_stl)

exporters.export(
    combined, str(out_svg),
    opt={"projectionDir": (1.0, -1.0, 0.6), "showAxes": False,
         "strokeWidth": 0.4, "width": 900, "height": 640},
)
print("saved", out_svg)
print("OK — CAD generated.")
