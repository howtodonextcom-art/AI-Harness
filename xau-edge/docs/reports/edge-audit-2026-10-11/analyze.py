# ruff: noqa - one-off Class D measurement script for INDEPENDENT_EDGE_FAILURE_AUDIT.md
import collections
import glob
import json
import math
import os
from statistics import NormalDist

import polars as pl

ROOT = r"z:\Coding\Projects\AI-Harness\xau-edge\data"
T = os.path.join(ROOT, "trade")
out = {}

# A. live forward decisions -------------------------------------------------------------------
rows = []
for f in sorted(glob.glob(os.path.join(T, "decisions-2026*.jsonl"))):
    with open(f, encoding="utf-8") as fh:
        rows += [json.loads(x) for x in fh if x.strip()]
first = collections.Counter((r.get("refusals") or ["<none>"])[0] for r in rows)
dec = collections.Counter(r["decision"] for r in rows)
opened = [r for r in rows if "MARKET_CLOSED" not in (r.get("refusals") or [])]
first_open = collections.Counter((r.get("refusals") or ["<none>"])[0] for r in opened)
allref_open = collections.Counter(x for r in opened for x in (r.get("refusals") or []))
phase = collections.Counter(r.get("setup_phase") for r in opened)
out["live"] = {
    "rows": len(rows),
    "decisions": dict(dec),
    "first_refusal_all": dict(first.most_common()),
    "open_rows": len(opened),
    "first_refusal_open": dict(first_open.most_common()),
    "all_refusals_open": dict(allref_open.most_common()),
    "labels_open": {
        k: dict(collections.Counter(r.get(k) for r in opened).most_common())
        for k in ("h1", "h4", "m15", "m5", "volatility", "spread_state", "news", "m1")
    },
    "first_at": rows[0]["at"] if rows else None,
    "last_at": rows[-1]["at"] if rows else None,
}

# B. acceptance replay trades -----------------------------------------------------------------
trades = []
for rep in glob.glob(os.path.join(T, "acceptance", "*", "report.json")):
    with open(rep, encoding="utf-8") as fh:
        r = json.load(fh)
    for t in r["trades"]:
        t["run"] = os.path.basename(os.path.dirname(rep))
        trades.append(t)
spread_r = []
for jf in glob.glob(os.path.join(T, "acceptance", "*", "paper_journal.jsonl")):
    with open(jf, encoding="utf-8") as fh:
        for line in fh:
            e = json.loads(line)
            if e.get("event") != "paper.close":
                continue
            risk = abs(e["fill_price"] - e["initial_sl"])
            sp = (e.get("quote") or {}).get("spread_points") or e["market"].get("spread_points")
            # round trip: entry pays the spread once, the exit on the other side; 0.01 = point
            spread_r.append((sp * 0.01) / risk if risk else None)
rs = [t["r_multiple"] for t in trades]
wins = [x for x in rs if x > 0]
loss = [x for x in rs if x <= 0]
srt = sorted(rs)
out["acceptance"] = {
    "n": len(rs),
    "by_run": dict(collections.Counter(t["run"] for t in trades)),
    "exit_reasons": dict(collections.Counter(t["exit_reason"] for t in trades)),
    "win_rate": len(wins) / len(rs),
    "avg_win_r": sum(wins) / len(wins) if wins else None,
    "avg_loss_r": sum(loss) / len(loss) if loss else None,
    "mean_r": sum(rs) / len(rs),
    "median_r": srt[len(srt) // 2],
    "sum_r": sum(rs),
    "pf": (sum(wins) / -sum(loss)) if loss and sum(loss) < 0 else None,
    "mean_mfe_r": sum(t["mfe_r"] for t in trades) / len(trades),
    "mean_mae_r": sum(t["mae_r"] for t in trades) / len(trades),
    "share_mfe_ge_1r": sum(t["mfe_r"] >= 1 for t in trades) / len(trades),
    "mean_duration_min": sum(t["duration_minutes"] for t in trades) / len(trades),
    "spread_drag_r_mean": sum(x for x in spread_r if x) / len([x for x in spread_r if x]),
    "trades": [
        {
            k: t[k]
            for k in (
                "run",
                "side",
                "exit_reason",
                "r_multiple",
                "mfe_r",
                "mae_r",
                "duration_minutes",
            )
        }
        for t in trades
    ],
}

# C. entry geometry on the funnel windows (Class D, burned windows) ----------------------------
m5_files = glob.glob(os.path.join(ROOT, "market", "XAUUSD", "M5", "*.parquet"))
m5 = (
    pl.concat([pl.read_parquet(f) for f in m5_files], how="diagonal_relaxed")
    .unique(subset=["timestamp"])
    .sort("timestamp")
    .select("timestamp", "open", "high", "low", "close")
)
geo = {
    "episodes": 0,
    "triggered": 0,
    "delays": [],
    "drift_atr": [],
    "fwd_from_setup": [],
    "fwd_from_trigger": [],
    "mfe_before_trigger": [],
}
H = 24  # 2h of M5 bars, the paper desk's max hold
for fw in sorted(glob.glob(os.path.join(T, "reports", "funnel", "v1.1_*.jsonl"))):
    recs = []
    with open(fw, encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            g, f = d["gates"], d["f"]
            h1 = f["labels"]["h1"]
            direction = 1 if h1 == "BULLISH" else -1 if h1 == "BEARISH" else 0
            # the M5 bar that just closed at decision time `at`
            recs.append(
                (
                    d["at"],
                    direction,
                    bool(g.get("m15_setup")),
                    bool(g.get("m5_trigger")),
                    f.get("atr_m15"),
                )
            )
    df = pl.DataFrame(recs, schema=["at", "dir", "setup", "trig", "atr"], orient="row")
    df = df.with_columns(pl.col("at").str.to_datetime(time_zone="UTC"))
    df = df.with_columns((pl.col("at") - pl.duration(minutes=5)).alias("bar"))
    j = df.join(m5, left_on="bar", right_on="timestamp", how="left")
    close = j["close"].to_list()
    high = j["high"].to_list()
    low = j["low"].to_list()
    dirs, setups, trigs, atrs = (
        j["dir"].to_list(),
        j["setup"].to_list(),
        j["trig"].to_list(),
        j["atr"].to_list(),
    )
    i, n = 0, j.height
    while i < n:
        if not setups[i] or dirs[i] == 0 or close[i] is None or not atrs[i]:
            i += 1
            continue
        d0, c0, a0 = dirs[i], close[i], atrs[i]
        geo["episodes"] += 1
        # setup episode: consecutive setup bars, then up to 12 bars of grace for a trigger
        k, trig_at, mfe = i, None, 0.0
        while k < n and k <= i + 12 + 200 and dirs[k] == d0 and (setups[k] or k <= i + 12):
            if close[k] is not None:
                fav = (high[k] - c0) if d0 > 0 else (c0 - low[k])
                if trigs[k] and trig_at is None:
                    trig_at = k
                    break
                mfe = max(mfe, fav / a0)
            k += 1
        if i + H < n and close[i + H] is not None:
            geo["fwd_from_setup"].append(d0 * (close[i + H] - c0) / a0)
        if trig_at is not None and close[trig_at] is not None:
            geo["triggered"] += 1
            geo["delays"].append(trig_at - i)
            geo["drift_atr"].append(d0 * (close[trig_at] - c0) / a0)
            geo["mfe_before_trigger"].append(mfe)
            if trig_at + H < n and close[trig_at + H] is not None:
                geo["fwd_from_trigger"].append(d0 * (close[trig_at + H] - close[trig_at]) / a0)
        # skip the rest of this setup episode
        while k < n and setups[k] and dirs[k] == d0:
            k += 1
        i = max(k, i + 1)


def q(xs, p):
    xs = sorted(xs)
    return xs[int(p * (len(xs) - 1))] if xs else None


def mean(xs):
    return sum(xs) / len(xs) if xs else None


out["geometry"] = {
    "setup_episodes": geo["episodes"],
    "triggered_episodes": geo["triggered"],
    "trigger_rate": geo["triggered"] / geo["episodes"] if geo["episodes"] else None,
    "delay_bars_p50": q(geo["delays"], 0.5),
    "delay_bars_mean": mean(geo["delays"]),
    "drift_atr_mean": mean(geo["drift_atr"]),
    "drift_atr_p25_p50_p75": [q(geo["drift_atr"], p) for p in (0.25, 0.5, 0.75)],
    "mfe_before_trigger_mean": mean(geo["mfe_before_trigger"]),
    "fwd2h_from_setup_mean_atr": mean(geo["fwd_from_setup"]),
    "fwd2h_from_setup_n": len(geo["fwd_from_setup"]),
    "fwd2h_from_trigger_mean_atr": mean(geo["fwd_from_trigger"]),
    "fwd2h_from_trigger_n": len(geo["fwd_from_trigger"]),
}

# D. M1 depth by year -------------------------------------------------------------------------
m1_files = glob.glob(os.path.join(ROOT, "market", "XAUUSD", "M1", "*.parquet"))
m1 = pl.concat(
    [pl.read_parquet(f, columns=["timestamp", "spread"]) for f in m1_files], how="diagonal_relaxed"
).unique(subset=["timestamp"])
yr = (
    m1.group_by(pl.col("timestamp").dt.year().alias("y"))
    .agg(pl.len().alias("n"), pl.col("spread").median().alias("spread_med"))
    .sort("y")
)
out["m1_by_year"] = {
    int(r["y"]): [int(r["n"]), float(r["spread_med"])] for r in yr.iter_rows(named=True)
}

# E. statistical power ------------------------------------------------------------------------
N = NormalDist()


def n_needed(effect, sd, k, power=0.8, alpha=0.05):
    za = N.inv_cdf(1 - alpha / k)  # one-sided Bonferroni
    zb = N.inv_cdf(power)
    return math.ceil(((za + zb) * sd / effect) ** 2)


def mde(n, sd, k, power=0.8, alpha=0.05):
    return (N.inv_cdf(1 - alpha / k) + N.inv_cdf(power)) * sd / math.sqrt(n)


power = {}
for sd in (1.0, 1.3, 1.5):
    for k in (1, 20, 41):
        power[f"sd{sd}_K{k}"] = {f"+{e:.2f}R": n_needed(e, sd, k) for e in (0.05, 0.10, 0.15, 0.20)}
out["power_n_needed"] = power
out["power_mde"] = {
    f"n{n}_K{k}": round(mde(n, 1.3, k), 3)
    for n in (11, 50, 100, 120, 211, 752, 1598, 2727)
    for k in (1, 20, 41)
}
# frequency of the live baseline (SIGNAL_FUNNEL_ANALYSIS 10.4: 0.104..0.282 setups per full day)
freq = {}
for per_day in (0.104, 0.128, 0.205, 0.282):
    per_year = per_day * 250
    freq[str(per_day)] = {
        "per_month": round(per_day * 21, 2),
        "per_year": round(per_year, 1),
        "years_for_n_0.10R_K1_sd1.3": round(n_needed(0.10, 1.3, 1) / per_year, 1),
        "years_for_n_0.20R_K1_sd1.3": round(n_needed(0.20, 1.3, 1) / per_year, 1),
    }
out["frequency"] = freq
# forward: P(no setup in the observed live open time) at full and at actual coverage
live_open_minutes = 477
day_minutes = 23 * 60
for per_day in (0.104, 0.205, 0.282):
    lam_full = per_day * live_open_minutes / day_minutes
    lam_seen = lam_full * 0.4864
    out.setdefault("forward_null", {})[str(per_day)] = {
        "expected_setups_full_window": round(lam_full, 3),
        "P0_full": round(math.exp(-lam_full), 3),
        "expected_setups_recorded": round(lam_seen, 3),
        "P0_recorded": round(math.exp(-lam_seen), 3),
    }

print(json.dumps(out, indent=1, default=str))
