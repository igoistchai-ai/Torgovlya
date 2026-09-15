from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

def render(df, analysis, path: str):
    d=df.tail(120).reset_index(drop=True)
    fig,ax=plt.subplots(figsize=(14,7))
    width=.65
    for i,r in d.iterrows():
        up=r.close>=r.open
        lo=min(r.open,r.close); h=abs(r.close-r.open)
        ax.vlines(i,r.low,r.high,linewidth=1)
        ax.add_patch(Rectangle((i-width/2,lo),width,max(h,1e-12),fill=up,alpha=.8))
    levels=[]
    for key,label in [("entry_zone","ENTRY"),("stop_reference","STOP"),("tp1","TP1"),("tp2","TP2"),("tp3","TP3")]:
        v=analysis.get(key)
        if isinstance(v,(int,float)):
            ax.axhline(v,linestyle="--",linewidth=1,label=f"{label} {v:g}"); levels.append(v)
    ax.set_title(f"{analysis.get('symbol','')} — {analysis.get('timeframe','')} — {analysis.get('bias','WAIT')}")
    ax.grid(alpha=.15); ax.legend(loc="upper left",fontsize=8)
    fig.tight_layout(); fig.savefig(path,dpi=150); plt.close(fig)
