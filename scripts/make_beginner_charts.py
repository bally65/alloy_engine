"""初學者向 PPT 的簡易圖（白話、概念導向）。輸出 docs/beginner_assets/。"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.patches as mp
import numpy as np

FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
fm.fontManager.addfont(FONT)
plt.rcParams["font.family"] = fm.FontProperties(fname=FONT).get_name()
plt.rcParams["axes.unicode_minus"] = False
OUT = Path("docs/beginner_assets"); OUT.mkdir(parents=True, exist_ok=True)
NAVY="#1f3a5f"; TEAL="#2a9d8f"; ORANGE="#e76f51"; GOLD="#e9c46a"; GREY="#8d99ae"; RED="#c1121f"

def save(fig,n): fig.savefig(OUT/n,dpi=150,bbox_inches="tight",facecolor="white"); plt.close(fig); print("wrote",n)

def flow():
    fig,ax=plt.subplots(figsize=(10,2.6)); ax.axis("off")
    steps=[("熱","廢熱（如工廠排氣）",ORANGE),
           ("磁性變化","材料一熱，磁性就變",TEAL),
           ("電","磁變→產生電流",NAVY)]
    x=0.04
    for i,(t,d,c) in enumerate(steps):
        ax.add_patch(mp.FancyBboxPatch((x,0.30),0.24,0.5,boxstyle="round,pad=0.02",fc=c,ec="none"))
        ax.text(x+0.12,0.62,t,ha="center",va="center",color="white",fontsize=17,fontweight="bold")
        ax.text(x+0.12,0.42,d,ha="center",va="center",color="white",fontsize=10)
        if i<2:
            ax.annotate("",xy=(x+0.30,0.55),xytext=(x+0.245,0.55),arrowprops=dict(arrowstyle="-|>",lw=3,color="#333"))
        x+=0.32
    ax.set_xlim(0,1); ax.set_ylim(0,1)
    ax.set_title("一句話：把『沒人要的熱』變成『電』",fontsize=15,fontweight="bold")
    save(fig,"flow.png")

def tc_switch():
    fig,ax=plt.subplots(figsize=(8,3.6))
    T=np.linspace(0,400,400); Tc=300
    M=np.where(T<Tc,np.sqrt(np.clip(1-T/Tc,0,None)),0)
    ax.plot(T,M,color=NAVY,lw=3)
    ax.axvline(Tc,ls="--",color=RED,lw=2)
    ax.text(Tc+5,0.8,"居禮溫度 Tc\n（磁性開關）",color=RED,fontsize=12,fontweight="bold")
    ax.fill_between(T,M,where=(T<Tc),alpha=0.15,color=TEAL)
    ax.text(120,0.45,"冷 → 有磁性 🧲",fontsize=13,color=TEAL,fontweight="bold")
    ax.text(330,0.18,"熱 → 沒磁性",fontsize=12,color=GREY,fontweight="bold")
    ax.set_xlabel("溫度（越右越熱）"); ax.set_ylabel("磁性強度")
    ax.set_yticks([]); ax.set_title("關鍵：加熱過某溫度，磁鐵就『失憶』——這個切換能拿來發電",fontsize=12.5,fontweight="bold")
    save(fig,"tc_switch.png")

def sim_real():
    fig,ax=plt.subplots(figsize=(7,3.6))
    bars=ax.bar(["用『假資料』\n(電腦模擬) 訓練","用『真實資料』\n(實驗量測) 訓練"],[-0.17,0.78],
                color=[RED,TEAL])
    ax.axhline(0,color="k",lw=1)
    ax.text(0,-0.27,"比亂猜還差！",ha="center",color=RED,fontsize=13,fontweight="bold")
    ax.text(1,0.84,"準了！",ha="center",color=TEAL,fontsize=13,fontweight="bold")
    ax.set_ylabel("預測準度（越高越好）"); ax.set_ylim(-0.45,1.05)
    ax.set_title("最大教訓：餵『真實資料』，AI 才會準",fontsize=13.5,fontweight="bold")
    save(fig,"sim_real.png")

def pipeline():
    fig,ax=plt.subplots(figsize=(11,2.4)); ax.axis("off")
    steps=[("配方","Fe? Ni? Gd?…",GREY),("AI 預測","這配方好不好？",TEAL),
           ("GA 搜尋","幾萬種裡挑最好",NAVY),("候選名單","最佳幾個配方",GOLD),
           ("做實驗","實際驗證",ORANGE)]
    x=0.01; w=0.165
    for i,(t,d,c) in enumerate(steps):
        ax.add_patch(mp.FancyBboxPatch((x,0.3),w,0.5,boxstyle="round,pad=0.01",fc=c,ec="none"))
        ax.text(x+w/2,0.62,t,ha="center",va="center",color="white",fontsize=13,fontweight="bold")
        ax.text(x+w/2,0.42,d,ha="center",va="center",color="white",fontsize=8.5)
        if i<4: ax.annotate("",xy=(x+w+0.027,0.55),xytext=(x+w+0.003,0.55),arrowprops=dict(arrowstyle="-|>",lw=2.5,color="#333"))
        x+=w+0.04
    ax.set_xlim(0,1); ax.set_ylim(0,1)
    ax.set_title("整個專案的流水線（一張圖看懂）",fontsize=14,fontweight="bold")
    save(fig,"pipeline.png")

if __name__=="__main__":
    flow(); tc_switch(); sim_real(); pipeline(); print("done")
