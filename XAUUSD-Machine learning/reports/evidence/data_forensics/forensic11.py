import numpy as np, polars as pl
root="Z:/Coding/Projects/AI-Harness/xau-edge/data/market/XAUUSD/"
def pseudo(d):
    vol=d["tick_volume"].to_numpy(); mv=max(np.median(vol),1)
    hr=d["timestamp"].dt.hour().to_numpy(); mi=d["timestamp"].dt.minute().to_numpy(); sp=d["spread"].to_numpy()
    return ((hr==21)|(hr==22))&(mi==0)&(sp==0)&(vol>=50*mv)
def naive(c): 
    r=np.diff(np.log(c)); return float(np.corrcoef(r[:-1],r[1:])[0,1])
for mon in ("2012-06","2013-05","2016-05","2019-05","2020-12","2021-01","2021-06","2021-08","2011-05","2024-05"):
    m1=pl.read_parquet(root+f"M1/{mon}.parquet").sort("timestamp"); m5=pl.read_parquet(root+f"M5/{mon}.parquet").sort("timestamp"); h1=pl.read_parquet(root+f"H1/{mon}.parquet").sort("timestamp")
    p=pseudo(m1); clean=m1.filter(pl.Series(~p))
    agg=clean.with_columns(pl.col("timestamp").dt.truncate("5m").alias("b")).group_by("b").agg(pl.col("open").first(),pl.col("high").max(),pl.col("low").min(),pl.col("close").last()).sort("b")
    m5p=pseudo(m5); m5c=m5.filter(pl.Series(~m5p))
    j=agg.join(m5c.select(pl.col("timestamp").alias("b"),pl.col("close").alias("c5"),pl.col("high").alias("h5")),on="b",how="inner")
    eq=float((np.abs(j["close"].to_numpy()-j["c5"].to_numpy())<1e-9).mean())
    h1p=pseudo(h1)  # H1 may have different volume scale; use spread==0 and range
    print(mon,"pseudo M1:",int(p.sum()),"M5:",int(m5p.sum()),"| M5 naive ac stored",round(naive(m5["close"].to_numpy()),3),"-> without pseudo bars",round(naive(m5c["close"].to_numpy()),3),"| cleaned-M1 agg==stored M5 closes:",round(eq,4),"| H1 naive",round(naive(h1["close"].to_numpy()),3),"H1 spread0&vol>20xmed",int(((h1["spread"].to_numpy()==0)&(h1["tick_volume"].to_numpy()>20*np.median(h1["tick_volume"].to_numpy()))).sum()))
