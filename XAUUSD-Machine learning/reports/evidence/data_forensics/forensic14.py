import sys, numpy as np, polars as pl
sys.path.insert(0,"scripts/research")
from datetime import UTC, datetime, timedelta
from data_forensics import pseudo_mask
from funnel_audit import load
from xau_edge_v2.config import Settings
from xau_edge_v2.core.frames import MultiFrames
from xau_edge_v2.core.market_state import SnapshotMemo, build_market_state
from xau_edge_v2.data.bar_store import BarStore
from xau_edge_v2.data.frames import frame_from_polars
from xau_edge_v2.domain.contract import Timeframe
from xau_edge_v2.domain.market import BrokerClock
y,m=int(sys.argv[1]),int(sys.argv[2])
start=datetime(y,m,1,tzinfo=UTC); end=datetime(y+(m==12),m%12+1,1,tzinfo=UTC)
fr=load(BarStore(Settings().data_root,cache_seconds=0.0),start,end)
def mk(clean):
    d={}
    for tf,df in fr.items():
        if clean and tf!=Timeframe.H4:
            df=df.filter(pl.Series(~pseudo_mask(df)))
        f=frame_from_polars(tf,df)
        if f: d[tf]=f
    return MultiFrames(d)
raw,cl=mk(False),mk(True)
clock=BrokerClock(ny_offset_hours=7); memo1,memo2=SnapshotMemo(),SnapshotMemo()
m5=fr[Timeframe.M5]["timestamp"].to_list()
n=0; diff={k:0 for k in ("h1_trend","m15_structure","m15_pullback","m5_momentum","volatility_regime","execution_quality")}; atr=[]; any_diff=0
for t in m5:
    if t<start or t>=end: continue
    at=t+timedelta(minutes=5)
    if not (22<=at.hour or at.hour<4) : continue
    a=build_market_state(raw,at,broker_clock=clock,memo=memo1); b=build_market_state(cl,at,broker_clock=clock,memo=memo2)
    if a.h1_trend=="UNKNOWN": continue
    n+=1; d=False
    for k in diff:
        if getattr(a,k)!=getattr(b,k): diff[k]+=1; d=True
    any_diff+=d
    if a.atr_m15 and b.atr_m15: atr.append(a.atr_m15/b.atr_m15)
print(y,m,"decision times 22-04 UTC:",n,"any of the 6 labels differs:",any_diff,f"({any_diff/n:.1%})",{k:f"{v/n:.1%}" for k,v in diff.items()},"median ATR15 raw/clean",round(float(np.median(atr)),2),"p90",round(float(np.quantile(atr,0.9)),2))
