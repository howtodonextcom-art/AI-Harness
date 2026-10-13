import numpy as np, polars as pl, glob, json
root="Z:/Coding/Projects/AI-Harness/xau-edge/data/market/XAUUSD/M5/"
rows=[]
for f in sorted(glob.glob(root+"*.parquet")):
    mon=f[-15:-8]
    d=pl.read_parquet(f).sort("timestamp")
    ts=d["timestamp"].dt.epoch("s").to_numpy(); c=d["close"].to_numpy()
    r=np.diff(np.log(c)); step=np.diff(ts)
    sess=step==300
    naive=float(np.corrcoef(r[:-1],r[1:])[0,1])
    pair=sess[:-1]&sess[1:]
    session=float(np.corrcoef(r[:-1][pair],r[1:][pair])[0,1])
    # contribution of gap-adjacent pairs to sum(a*b) and to variance
    ab=r[:-1]*r[1:]
    tot=ab.sum(); gapc=ab[~pair].sum()
    big=np.abs(r)>8*np.median(np.abs(r))*1.4826 if len(r) else None
    nbig=int((np.abs(r)>8*r[sess].std()).sum())
    # daily break: most common start-of-gap hour (UTC) among gaps between 30 min and 3 h
    gi=np.where((step>=1800)&(step<=3*3600))[0]
    hrs=((ts[gi]%86400)//3600) if len(gi) else np.array([])
    brk=int(np.bincount(hrs.astype(int)).argmax()) if len(hrs) else -1
    rows.append((mon,naive,session,gapc/tot if tot else np.nan,nbig,brk,len(gi)))
print("month naive session gapShareOfCov >8sigma breakHourUTC nBreaks")
last=None
for mon,n,s,g,nb,b,ng in rows:
    y=mon[:4]
    if mon[5:] in ("01","05","09") or mon in ("2012-05","2012-06","2021-01","2021-02","2021-08"):
        print(mon,f"{n:+.2f} {s:+.2f} {g:+.2f} {nb:3d} {b:2d} {ng}")
