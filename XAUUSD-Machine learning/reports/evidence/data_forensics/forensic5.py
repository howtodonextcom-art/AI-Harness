import numpy as np, polars as pl
from datetime import datetime, UTC, timedelta
root="Z:/Coding/Projects/AI-Harness/xau-edge/data/market/XAUUSD/"
m5=pl.read_parquet(root+"M5/2013-05.parquet").sort("timestamp")
prev=pl.read_parquet(root+"M5/2013-04.parquet").sort("timestamp"); nxt=pl.read_parquet(root+"M5/2013-06.parquet").sort("timestamp")
allm=pl.concat([prev,m5,nxt]).sort("timestamp")
ts=allm["timestamp"].dt.epoch("s").to_numpy()
spec=allm.filter((pl.col("timestamp").dt.hour()==21)&(pl.col("timestamp").dt.minute()==0)&(pl.col("spread")==0))
print("anomalous 21:00 bars with spread 0 in 2013-05:",spec.filter(pl.col("timestamp").dt.month()==5).height)
def agg(t0,t1):
    m=(ts>=t0)&(ts<t1)
    sub=allm.filter(pl.Series(m))
    # exclude the anomalous bars themselves
    sub=sub.filter(pl.col("spread")>0)
    return (sub["open"][0],sub["high"].max(),sub["low"].min(),sub["close"][-1],int(sub["tick_volume"].sum())) if sub.height else None
for r in spec.filter((pl.col("timestamp").dt.month()==5)).head(6).iter_rows(named=True):
    t=int(r["timestamp"].timestamp())
    print("\nanomalous bar",r["timestamp"],"O H L C vol:",r["open"],r["high"],r["low"],r["close"],r["tick_volume"])
    for lab,a,b in (("prev 24h (D-1 21:05..D 20:55)",t-86400+300,t),("next 24h (D 22:05..D+1 20:55)",t+3900,t+86400),("same-day 00:00..20:55",t-21*3600,t),("next-day 00:00..20:55",t+3*3600,t+24*3600-300)):
        print("  ",lab,agg(a,b))
