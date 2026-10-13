import numpy as np, polars as pl, glob, json
from datetime import datetime, UTC, timedelta
root="Z:/Coding/Projects/AI-Harness/xau-edge/data/market/XAUUSD/M1/"
def load(y):
    return pl.concat([pl.read_parquet(f).select("timestamp","open","high","low","close","spread","tick_volume") for f in sorted(glob.glob(root+f"{y}-*.parquet"))]+[pl.read_parquet(root+f"{y+1}-01.parquet").select("timestamp","open","high","low","close","spread","tick_volume")]).sort("timestamp")
summ={}
for y in (2013,2016,2019):
    d=load(y)
    ts=d["timestamp"].dt.epoch("s").to_numpy(); hr=d["timestamp"].dt.hour().to_numpy(); mi=d["timestamp"].dt.minute().to_numpy()
    sp=d["spread"].to_numpy(); vol=d["tick_volume"].to_numpy(); mv=np.median(vol)
    O,H,L,C=[d[k].to_numpy() for k in ("open","high","low","close")]
    bog=((hr==21)|(hr==22))&(mi==0)&(sp==0)&(vol>=50*mv)
    idx=np.where(bog)[0]
    ok=~bog
    m_next={"H":0,"L":0,"C":0,"O":0}; m_prev={"H":0,"L":0,"C":0,"O":0}; n=0; vols=[]
    errs=[]
    for i in idx:
        t=ts[i]
        if datetime.fromtimestamp(t,UTC).year!=y: continue
        for lab,(a,b),acc in (("next",(t+60,t+86400),m_next),("prev",(t-86400+60,t),m_prev)):
            sel=ok&(ts>=a)&(ts<b)
            if sel.sum()<200: break
            h,l,c,o=H[sel].max(),L[sel].min(),C[sel][-1],O[sel][0]
            acc["H"]+=abs(H[i]-h)<=1.0; acc["L"]+=abs(L[i]-l)<=1.0; acc["C"]+=abs(C[i]-c)<=1.0; acc["O"]+=abs(O[i]-o)<=1.0
            if lab=="next": errs.append((H[i]-h, L[i]-l, C[i]-c))
        else:
            n+=1
    e=np.array(errs)
    summ[y]={"days":n,"match_next_day_within_$1":m_next,"match_prev_day_within_$1":m_prev,"median_abs_err_next(H,L,C)":[round(float(np.median(np.abs(e[:,k]))),2) for k in range(3)]}
    print(y,summ[y])
