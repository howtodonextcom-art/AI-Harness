"""Signal-only report of CAND_V2_CORE_1.1.0 Stage A (``cand_replay.py`` output). No outcome, no PnL.

Reads ``data/research/stage_a_core/{signals,stats}_<month>.*`` (written by the continuous replay) and,
when present, the multifamily signals, and reports per variant: raw eligibility (the chain would be
satisfied with the gates off), signals after the cost and structural gates, episodes (gap <= 60
minutes, same side), direction balance, regime/session distribution, overlap with the multifamily
branch, geometry feasibility and a research power estimate.

    uv run python scripts/research/stage_a_core_report.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

from xau_edge_v2.research.stats import n_required  # noqa: E402

SEGMENTS = (
    ("stage_a_core", "2005-11", "2009-02"),
    ("stage_a_core_seg2", "2009-03", "2012-06"),
    ("stage_a_core_seg3", "2012-07", "2015-10"),
    ("stage_a_core_seg4", "2015-11", "2018-12"),
)
"""Four contiguous segments run by four low-priority workers. The lifecycle memory is continuous
inside a segment; at the three boundaries it starts empty (C1 keeps 6 M5 bars, so at most the first
bars of a segment can differ from one continuous run)."""
EPISODE_GAP = 3600  # seconds
DELTAS = (0.20, 0.30)


def q(values: list[float], p: float) -> float | None:
    return None if not values else round(float(np.percentile(values, p)), 3)


def dist(values: list[float]) -> dict[str, object]:
    return {"p10": q(values, 10), "p50": q(values, 50), "p90": q(values, 90), "n": len(values)}


def episodes(df: pl.DataFrame) -> pl.DataFrame:
    """First signal of every maximal run of one side whose consecutive gaps are <= 60 minutes."""
    rows = df.sort("ts").to_dicts()
    heads: list[dict[str, object]] = []
    last: dict[str, datetime] = {}
    for r in rows:
        prev = last.get(r["side"])
        if prev is None or (r["ts"] - prev).total_seconds() > EPISODE_GAP:
            heads.append(r)
        last[r["side"]] = r["ts"]
    return pl.DataFrame(heads, infer_schema_length=None) if heads else df.head(0)


def main() -> None:
    stats, months, files = [], [], []
    for folder, lo, hi in SEGMENTS:
        base = ROOT / "data" / "research" / folder
        for p in sorted(base.glob("stats_*.json")):
            month = p.stem.removeprefix("stats_")
            if lo <= month <= hi:
                stats.append(json.loads(p.read_text()))
                months.append(month)
                sp = base / f"signals_{month}.parquet"
                if sp.exists():
                    files.append(sp)
    order = sorted(range(len(months)), key=lambda i: months[i])
    stats = [stats[i] for i in order]
    months = [months[i] for i in order]
    sig = pl.concat([pl.read_parquet(f) for f in files], how="diagonal_relaxed") if files else None
    bars = sum(s["bars"] for s in stats)
    skipped = sum(s["skipped"] for s in stats)
    chain_ok = sum(s["chain_ok_bars"] for s in stats)
    years = bars * 300 / (365.25 * 86400) / (5 / 7)
    out: dict[str, object] = {
        "purpose": "Stage A signal-only report for CAND_V2_CORE_1.1.0 (no outcome, no PnL)",
        "months_processed": len(months),
        "first_month": months[0] if months else None,
        "last_month": months[-1] if months else None,
        "complete": len(months) == len(set(months))
        and bool(months)
        and months[-1] == "2018-12"
        and len(months) == 158,
        "segments": [list(x) for x in SEGMENTS],
        "segment_boundary_note": "lifecycle memory starts empty at 2009-03, 2012-07 and 2015-11 (6 M5 bars of C1 memory)",
        "m5_bars_evaluated": bars,
        "m5_bars_skipped_no_state": skipped,
        "raw_eligibility_chain_ok_bars_gates_off": chain_ok,
        "outcomes_read": False,
        "protected_windows_read": [],
    }
    variants: dict[str, object] = {}
    if sig is not None:
        for name in sorted(sig["variant"].unique().to_list()):
            v = sig.filter(pl.col("variant") == name)
            ep = episodes(v)
            risk = [
                abs(r["entry"] - r["sl"]) / r["atr_m15"]
                for r in ep.to_dicts()
                if r.get("atr_m15") and r.get("sl") is not None
            ]
            per_year = Counter(r["ts"].year for r in ep.to_dicts())
            rate = ep.height / years if years else 0.0
            variants[name] = {
                "signals_after_gates": v.height,
                "episodes": ep.height,
                "direction": dict(Counter(r["side"] for r in ep.to_dicts())),
                "regime_h4": dict(Counter(r.get("h4_regime") for r in ep.to_dicts())),
                "regime_m15": dict(Counter(r.get("m15_regime") for r in ep.to_dicts())),
                "session": dict(Counter(r.get("session") for r in ep.to_dicts())),
                "lifecycle": dict(Counter(r.get("lifecycle") for r in ep.to_dicts())),
                "per_year_episodes": {str(k): c for k, c in sorted(per_year.items())},
                "geometry": {
                    "risk_atr": dist(risk),
                    "net_rr": dist([r["net_rr"] for r in ep.to_dicts() if r.get("net_rr")]),
                },
                "research_power": {f"n_required_for_{d:.2f}R": n_required(d) for d in DELTAS}
                | {
                    f"years_to_reach_n_for_{d:.2f}R": None
                    if rate <= 0
                    else round(n_required(d) / rate, 1)
                    for d in DELTAS
                }
                | {"episodes_per_year": round(rate, 2)},
            }
    out["variants"] = variants
    # overlap of the CORE branch with the multifamily branch (accepted heads, same side within 1 hour)
    mfp = ROOT / "data" / "research" / "multifamily_signals_dev.parquet"
    if sig is not None and mfp.exists() and "CORE" in variants:
        core = episodes(sig.filter(pl.col("variant") == "CORE"))
        mf = pl.read_parquet(mfp).filter(pl.col("episode_head") & pl.col("first_refusal").is_null())
        mf_rows = [(r["family"], r["side"], r["known_at_us"] / 1e6) for r in mf.to_dicts()]
        res: dict[str, dict[str, int]] = {}
        for fam in ("B", "C", "D"):
            same = opp = 0
            for r in core.to_dicts():
                t = r["ts"].replace(tzinfo=UTC).timestamp()
                side = 1 if r["side"] == "BUY" else -1
                hits = [s for f, s, k in mf_rows if f == fam and abs(k - t) <= EPISODE_GAP]
                same += int(any(s == side for s in hits))
                opp += int(any(s == -side for s in hits))
            res[fam] = {
                "core_episodes": core.height,
                "same_side_within_1h": same,
                "opposite_side_within_1h": opp,
            }
        out["overlap_core_vs_multifamily"] = res
    path = ROOT / "docs" / "research" / "core_stage_a_dev.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False)[:6000])


if __name__ == "__main__":
    main()
