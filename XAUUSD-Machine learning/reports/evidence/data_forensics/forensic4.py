import numpy as np, polars as pl
from datetime import datetime
pl.Config.set_tbl_formatting("ASCII_FULL"); pl.Config.set_tbl_rows(30); pl.Config.set_tbl_cols(12); pl.Config.set_tbl_width_chars(200)
root="Z:/Coding/Projects/AI-Harness/xau-edge/data/market/XAUUSD/M5/"
def show(mon,day):
    d=pl.read_parquet(root+f"{mon}.parquet").sort("timestamp")
    ts=d["timestamp"].dt.epoch("s").to_numpy(); step=np.diff(ts)
    gi=np.where((step>=1800)&(step<=3*3600))[0]
    # first daily break in the month after `day`
    for i in gi:
        t=datetime.utcfromtimestamp(int(ts[i]))
        if t.day>=day:
            sub=d[max(0,i-3):i+7].select("timestamp","open","high","low","close","spread","tick_volume")
            print(mon,"break after",t,"gap min",int(step[i]//60)); print(sub); return
for mon,day in (("2011-05",10),("2013-05",14),("2019-05",14),("2024-05",14)): show(mon,day)
# hour-of-day histogram of >8 sigma M5 returns by era
for lab,mons in (("2011-01..2012-05",[f"{y}-{m:02d}" for y in (2011,) for m in range(1,13)]+["2012-01","2012-02","2012-03","2012-04","2012-05"]),("2013..2015",[f"{y}-{m:02d}" for y in (2013,2014,2015) for m in range(1,13)]),("2022..2023",[f"{y}-{m:02d}" for y in (2022,2023) for m in range(1,13)])):
    H=np.zeros(24); tot=0; revs=[]
    for mon in mons:
        d=pl.read_parquet(root+f"{mon}.parquet").sort("timestamp")
        ts=d["timestamp"].dt.epoch("s").to_numpy(); c=d["close"].to_numpy(); r=np.diff(np.log(c)); sd=r[np.diff(ts)==300].std()
        idx=np.where(np.abs(r)>8*sd)[0]
        for i in idx:
            H[(ts[i+1]%86400)//3600]+=1; tot+=1
            if i+1<len(r): revs.append(-np.sign(r[i])*r[i+1]/abs(r[i]))
    print(lab,"n>8sigma",tot,"by hour of the bar:",{h:int(H[h]) for h in range(24) if H[h]>0},"mean reversal ratio",round(float(np.mean(revs)),2) if revs else None)
