"""出版級圖表包：把研究線的關鍵結果做成乾淨圖。輸出 docs/figures/。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
fm.fontManager.addfont(FONT)
plt.rcParams["font.family"] = fm.FontProperties(fname=FONT).get_name()
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 160
OUT = Path("docs/figures"); OUT.mkdir(parents=True, exist_ok=True)
NAVY="#1f3a5f"; TEAL="#2a9d8f"; ORANGE="#e76f51"; GOLD="#e9c46a"; GREY="#8d99ae"; RED="#c1121f"

def save(fig,n): fig.savefig(OUT/n,bbox_inches="tight",facecolor="white"); plt.close(fig); print("wrote",OUT/n)

def fig_sim_to_real():
    fig,ax=plt.subplots(figsize=(5,3.6))
    bars=ax.bar(["合成代理\n(評於真實)","真實 NEMAD\n訓練"],[-0.17,0.78],color=[ORANGE,TEAL])
    ax.axhline(0,color="k",lw=0.8); ax.set_ylabel("測試 R²"); ax.set_ylim(-0.4,1.0)
    for b,v in zip(bars,[-0.17,0.78]):
        ax.text(b.get_x()+b.get_width()/2, v+(0.04 if v>0 else -0.09), f"{v:+.2f}",
                ha="center",fontweight="bold")
    ax.set_title("Tc Sim-to-Real：真實資料把 R² 從 −0.17 救到 0.78",fontsize=11)
    save(fig,"fig1_sim_to_real.png")

def fig_cost_landscape():
    from alloy_engine.thermomagnetic import literature_mce as lm
    rows=lm.rank_by_value_per_cost()
    names=[r[0] for r in rows]; fom=[r[3] for r in rows]
    cav=[bool(lm.get(n).caveat) for n in names]
    colors=[RED if c else TEAL for c in cav]
    fig,ax=plt.subplots(figsize=(6.2,3.8))
    y=np.arange(len(names))[::-1]
    ax.barh(y,fom,color=colors)
    ax.set_yticks(y); ax.set_yticklabels(names,fontsize=9)
    ax.set_xscale("symlog",linthresh=0.1)
    ax.set_xlabel("效能/成本  ΔS@2T ÷ ($/kg)  (log)")
    for yi,n,f in zip(y,names,fom):
        cv=lm.get(n).caveat
        ax.text(f*1.1+0.02,yi,("⚠ " if cv else "")+f"{f:.1f}",va="center",fontsize=8,
                color=RED if cv else "k")
    ax.set_title("最低成本材料：La-Fe-Si / Mn-Fe-P 勝出（紅=有實用性警示）",fontsize=10)
    save(fig,"fig2_cost_landscape.png")

def fig_calibrated_prediction():
    from alloy_engine.thermomagnetic.uncertainty import device_performance_with_uncertainty as uq
    mats=[("La(Fe,Si)13H",47),("(Mn,Fe)2(P,Si)",27),("Gd (純釓)",21)]
    res=[uq(m,t,n_samples=1500) for m,t in mats]
    names=[m for m,_ in mats]
    p=[r.power_W_m3_mean/1e3 for r in res]; perr=[r.power_W_m3_std/1e3 for r in res]
    fig,ax=plt.subplots(figsize=(5.5,3.6))
    x=np.arange(len(names))
    ax.bar(x,p,yerr=perr,capsize=6,color=NAVY,alpha=0.85,error_kw=dict(ecolor=ORANGE,lw=2))
    ax.set_xticks(x); ax.set_xticklabels([n.replace(" (純釓)","") for n in names],fontsize=9)
    ax.set_ylabel("整機 P/V（理想，kW/m³）")
    for xi,pv,pe in zip(x,p,perr):
        ax.text(xi,pv+pe+30,f"{pv:.0f}±{pe:.0f}",ha="center",fontsize=9,fontweight="bold")
    ax.set_title("校準後整機預估帶 ±12% 文獻誤差條",fontsize=11)
    save(fig,"fig3_calibrated_prediction.png")

def fig_bottleneck():
    fig,ax=plt.subplots(figsize=(8,1.9)); ax.axis("off")
    steps=["顯熱","磁滯","熱導率 κ","元素空間","真實資料"]
    cols=[NAVY,TEAL,ORANGE,GOLD,"#6a4c93"]
    for i,(s,c) in enumerate(zip(steps,cols)):
        ax.add_patch(plt.Rectangle((i-0.42,-0.3),0.84,0.6,color=c))
        ax.text(i,0,s,ha="center",va="center",color="white",fontsize=11,fontweight="bold")
        if i<len(steps)-1:
            ax.annotate("",xy=(i+0.56,0),xytext=(i+0.42,0),
                        arrowprops=dict(arrowstyle="-|>",lw=2,color="#333"))
    ax.set_xlim(-0.7,len(steps)-0.3); ax.set_ylim(-0.6,0.6)
    ax.set_title("瓶頸演進鏈（逐一識別並處理）",fontsize=11)
    save(fig,"fig4_bottleneck.png")

if __name__=="__main__":
    fig_sim_to_real(); fig_cost_landscape(); fig_calibrated_prediction(); fig_bottleneck()
    print("done")
