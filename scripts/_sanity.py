import sys, torch, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from alloy_engine.config import CHECKPOINT_DIR, DEFAULT_DEVICE
from alloy_engine.models.surrogate import SurrogateBundle
from alloy_engine.data.elements import ELEMENTS

device = DEFAULT_DEVICE
bundle = SurrogateBundle.load(CHECKPOINT_DIR / "bundle.pt", device=device)
elem_idx = {e: i for i, e in enumerate(ELEMENTS)}

alloys = {
    "Permalloy (Ni80Fe20)":           {"Ni": 0.80, "Fe": 0.20},
    "Sendust (Fe85Si9Al6)":           {"Fe": 0.85, "Si": 0.09, "Al": 0.06},
    "Hiperco50 (Fe50Co50)":           {"Fe": 0.50, "Co": 0.50},
    "Fe65Ni35 (Invar)":               {"Fe": 0.65, "Ni": 0.35},
    "Alnico5 (Fe51Co24Ni14Al8Cu3)":   {"Fe": 0.51, "Co": 0.24, "Ni": 0.14, "Al": 0.08, "Cu": 0.03},
    "5-elem HEA (Fe30Co30Ni20Cr10Si10)": {"Fe": 0.30, "Co": 0.30, "Ni": 0.20, "Cr": 0.10, "Si": 0.10},
}

print("Sanity check — famous alloys, new 36-dim model (output in K):")
print(f"  {'Alloy':<42}  {'Pred Tc (K)':>12}  {'Pred Tc (C)':>12}")
for name, comp in alloys.items():
    vec = np.zeros((1, len(ELEMENTS)), dtype=np.float32)
    for e, f in comp.items():
        vec[0, elem_idx[e]] = f
    comp_t = torch.from_numpy(vec).to(device)
    with torch.no_grad():
        props = bundle.predict_properties(comp_t)
    tc_K = props["Tc"].cpu().item()
    tc_C = tc_K - 273.15
    print(f"  {name:<42}  {tc_K:>12.1f}  {tc_C:>12.1f}")
