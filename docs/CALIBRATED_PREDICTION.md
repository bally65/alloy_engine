# 校準後整機效能預估（帶不確定度）

> Direction #1+#2：把文獻值正式回填進模型（`reference_materials` ΔS_M 已校準至
> 文獻 @2T），並把文獻 ±12% 散布以 Monte Carlo 傳過整機 `design_tmg` →
> **預測帶誤差條，而非單點值**，再套 D12 量化的現實折減。
> 程式：`alloy_engine/thermomagnetic/uncertainty.py`、`scripts/calibrated_device_report.py`。

---

## 1. 校準動作（已落地）

- `reference_materials.py` 的 `delta_S_M` 已由舊的 ~1.5T 粗值改為**文獻 @2T 值**
  （單一真實來源 = `literature_mce`，引用見 `LITERATURE_CALIBRATION.md`）：
  Gd 3→5、Gd₅Si₂Ge₂ 9→14、La-Fe-Si 11→19、Mn-Fe-P 14（已一致）。
- 一階材料的相變銳度 **w 由文獻 ΔS_M 峰 FWHM 校準**（D5），用於 **GA 材料評分**
  （`magnetic_thermodynamic_score`）。註：本節整機路徑以 `delta_M_T`（循環淨極化
  擺幅，已含相變）為輸入，不另取 w；w 影響的是材料篩選排序，非此整機數字。

## 2. 整機預估（Monte Carlo，n=2000，±12% 文獻散布）

| 材料 | 工作°C | P/V 理想 (kW/m³) | 現實 ÷10 (kW/m³) | η/η_C (%) |
|---|---|---|---|---|
| La(Fe,Si)₁₃H | 47 | 1110 ± 134 | 111 | 0.56 ± 0.07 |
| (Mn,Fe)₂(P,Si) | 27 | 608 ± 73 | 61 | 0.74 ± 0.09 |
| Gd（基準）| 21 | 1844 ± 222 | 184 | 0.88 ± 0.11 |

## 3. 解讀

- **誤差條 ~±12%** 直接來自文獻多篇量測的散布——是**統計可辯護的不確定度**，
  不是單點臆測。精確說：**P/V 的擺幅來自 ΔM**（功率 = 磁功×頻率，僅依 ΔM）；
  **η 的擺幅來自 ΔM 與 ΔS**（ΔS 進入熱輸入 q_in）。兩者皆用同一 ±12%。
- **「理想」是 design_tmg 上界；「現實」套 D12 量化的 ~10× 折減**（發電側絕對功率
  為理想化上界，見 `KNOWN_DEFECTS` D12）。
- 反直覺但正確：**Gd 的 P/V 高於 La-Fe-Si**——因 Gd 的 κ 高、Cp 低 → 循環頻率高 →
  功率密度高，即使 ΔS/ΔM 較小。一階材料 ΔS 大但 κ 極低（限頻率），這正是
  「複合材料（高 κ 基底）」存在的理由（見 `COMPOSITE_MATERIALS`）。

## 4. 復現

```bash
python scripts/calibrated_device_report.py            # 帶誤差條的整機預估
python scripts/recommend_material.py --temp 47        # 材料推薦
```

> 一句話：模型現在不只「相對可信」，其輸出也帶上**來自文獻的誠實誤差條**，
> 並明確標出絕對值的現實折減——這是把研究從「點估計」升級為「可辯護的區間估計」。
