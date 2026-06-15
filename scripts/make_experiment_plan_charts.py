"""為實驗執行計畫產生圖表（中文字型 WQY）。輸出 docs/plan_assets/。"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.patches as mpatches
import numpy as np

FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
fm.fontManager.addfont(FONT)
plt.rcParams["font.family"] = fm.FontProperties(fname=FONT).get_name()
plt.rcParams["axes.unicode_minus"] = False
OUT = Path("docs/plan_assets"); OUT.mkdir(parents=True, exist_ok=True)

NAVY="#1f3a5f"; TEAL="#2a9d8f"; ORANGE="#e76f51"; GOLD="#e9c46a"; GREY="#8d99ae"; PURPLE="#6a4c93"

def save(fig,n): fig.savefig(OUT/n,dpi=150,bbox_inches="tight",facecolor="white"); plt.close(fig); print("wrote",OUT/n)

def gantt():
    fig,ax=plt.subplots(figsize=(11,4.2))
    # (label, start_month, duration, color)
    rows=[
        ("Phase 0 先導：純 Gd 全流程打通",0,2,TEAL),
        ("  ├ 製樣/採購 + 成分相確認",0,1,GREY),
        ("  ├ VSM M-H + DSC（ΔM/ΔS/w）",0.7,1,GREY),
        ("  └ 決策門 G0（流程是否可信）",1.7,0.3,GOLD),
        ("Phase 1 一階材料：La-Fe-Si / Mn-Fe-P",2,3,NAVY),
        ("  └ 氫化 Tc 上修驗證（D8）",3.5,1.5,GREY),
        ("Phase 2 GA 候選 + 複合 connectivity",5,3,ORANGE),
        ("  └ SEM 微結構回填（D6）",6,1.5,GREY),
        ("Phase 3 整機 TMG 原型（發電側絕對校準 D12）",8,4,PURPLE),
    ]
    for i,(lab,s,d,c) in enumerate(rows):
        y=len(rows)-i
        ax.barh(y,d,left=s,height=0.6,color=c,alpha=0.92)
        ax.text(s+0.05,y,lab,va="center",ha="left",fontsize=10,
                color="white" if d>1.2 else "black",fontweight="bold" if not lab.startswith("  ") else "normal")
    ax.set_xlim(0,12.5); ax.set_ylim(0,len(rows)+1)
    ax.set_xlabel("月")
    ax.set_xticks(range(0,13))
    ax.set_yticks([])
    ax.set_title("階段化時程（小規模先導 → 逐步擴張）",fontsize=14,fontweight="bold")
    for m in [2,5,8]: ax.axvline(m,ls="--",color=GREY,lw=0.8,alpha=0.6)
    save(fig,"gantt.png")

def derisk():
    fig,ax=plt.subplots(figsize=(11,3.4)); ax.axis("off")
    boxes=[("Phase 0\n純 Gd 先導\n（最易、商購）",TEAL),
           ("決策門 G0\nM-H/DSC 與模型\n量級吻合？",GOLD),
           ("Phase 1–2\n一階材料 +\nGA 候選 + 複合",NAVY),
           ("決策門 G1\n端到端\nsim-to-real 收斂？",GOLD),
           ("Phase 3\n整機原型\n絕對校準",PURPLE)]
    x=0.02
    for i,(t,c) in enumerate(boxes):
        w=0.165 if i%2==0 else 0.15
        ax.add_patch(mpatches.FancyBboxPatch((x,0.35),w,0.42,
            boxstyle="round,pad=0.01",fc=c,ec="none"))
        ax.text(x+w/2,0.56,t,ha="center",va="center",color="white",fontsize=9.5,fontweight="bold")
        if i<len(boxes)-1:
            ax.annotate("",xy=(x+w+0.035,0.56),xytext=(x+w+0.005,0.56),
                        arrowprops=dict(arrowstyle="-|>",lw=2,color="#333"))
        x+=w+0.04
    ax.text(0.5,0.12,"任一決策門未過 → 回到上一階段修模型/製程，不貿然擴張（避免重蹈覆轍）",
            ha="center",fontsize=11,color=ORANGE,fontweight="bold")
    ax.set_xlim(0,1); ax.set_ylim(0,1)
    ax.set_title("先導—決策門—擴張：階段閘控的去風險邏輯",fontsize=14,fontweight="bold")
    save(fig,"derisk.png")

def scale_ramp():
    fig,ax=plt.subplots(figsize=(9,4))
    phases=["Phase 0\n先導","Phase 1\n一階","Phase 2\nGA+複合","Phase 3\n原型"]
    samples=[1,3,6,2]; cost=[0.5,3,8,20]
    x=np.arange(4)
    ax.bar(x-0.2,samples,0.4,color=TEAL,label="樣品數")
    ax.set_ylabel("樣品數",color=TEAL); ax.tick_params(axis='y',labelcolor=TEAL)
    ax2=ax.twinx()
    ax2.plot(x,cost,"-o",color=ORANGE,lw=2.5,label="相對成本/工作量")
    ax2.set_ylabel("相對成本/工作量（任意單位）",color=ORANGE); ax2.tick_params(axis='y',labelcolor=ORANGE)
    ax.set_xticks(x); ax.set_xticklabels(phases)
    ax.set_title("規模化路徑：先小（1 樣）驗流程，逐步放大投入",fontsize=13,fontweight="bold")
    save(fig,"scale_ramp.png")

def backfill():
    fig,ax=plt.subplots(figsize=(10,4.6)); ax.axis("off")
    pairs=[("VSM M-H 迴線（工作溫度）","→ ΔJ 取代平均場估計 / 磁滯損耗"),
           ("M(T) 斜率擬合","→ D5 logistic 寬度 w"),
           ("DSC（ΔS_M、Cp、相變峰）","→ properties / reference_materials"),
           ("雷射閃光 κ","→ generator_design 熱擴散頻率"),
           ("SEM 相連通度 / φ","→ D6 composite connectivity（最敏感）"),
           ("氫化前後 Tc","→ D8 hydrogenation_tc_shift_K 校準"),
           ("整機 W/η/P","→ D12 reference_devices 新增『本工作』錨點")]
    ax.text(0.02,0.95,"量測值",fontsize=12,fontweight="bold",color=NAVY)
    ax.text(0.55,0.95,"回填模型位置",fontsize=12,fontweight="bold",color=TEAL)
    for i,(m,t) in enumerate(pairs):
        y=0.85-i*0.115
        ax.add_patch(mpatches.FancyBboxPatch((0.02,y-0.04),0.46,0.08,
            boxstyle="round,pad=0.005",fc="#eef2f6",ec=NAVY,lw=0.8))
        ax.text(0.04,y,m,fontsize=9.5,va="center")
        ax.annotate("",xy=(0.54,y),xytext=(0.49,y),arrowprops=dict(arrowstyle="-|>",color=GREY,lw=1.5))
        ax.text(0.55,y,t,fontsize=9.5,va="center",color=TEAL)
    ax.set_xlim(0,1); ax.set_ylim(0,1)
    ax.set_title("量到什麼 → 回填模型哪裡（閉環校準）",fontsize=14,fontweight="bold")
    save(fig,"backfill.png")

def funnel():
    fig,ax=plt.subplots(figsize=(9,3.8)); ax.axis("off")
    stages=[("模型預測\n相對可信、絕對待測\n(Tc R²0.78, 功率上界)",NAVY,1.0),
            ("小規模實測\nGd→一階→GA候選\n(M-H/DSC/SEM)",TEAL,0.72),
            ("回填校準\nΔM/w/connectivity\n絕對值收斂",ORANGE,0.48),
            ("可信整機設計\n相對+絕對皆可預測",PURPLE,0.28)]
    y=0.8
    for t,c,w in stages:
        ax.add_patch(mpatches.FancyBboxPatch(((1-w)/2,y-0.09),w,0.16,
            boxstyle="round,pad=0.005",fc=c,ec="none"))
        ax.text(0.5,y,t,ha="center",va="center",color="white",fontsize=9,fontweight="bold")
        y-=0.22
    ax.set_xlim(0,1); ax.set_ylim(0,1)
    ax.set_title("實驗的角色：把『相對可信』收斂成『絕對可信』",fontsize=13,fontweight="bold")
    save(fig,"funnel.png")

if __name__=="__main__":
    gantt(); derisk(); scale_ramp(); backfill(); funnel()
    print("done")
