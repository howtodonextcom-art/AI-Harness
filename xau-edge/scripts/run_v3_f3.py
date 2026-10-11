"""F3-USMOM-0930-1400-1500-1645 runner: oracle parity (no outcome statistics) and the single Stage 1 run.

    .venv\\Scripts\\python.exe scripts\\run_v3_f3.py --parity
    .venv\\Scripts\\python.exe scripts\\run_v3_f3.py --stage1

Stage 1 = Development-2 (New York dates 2011-01-01 .. 2018-12-31), alpha 0.0333, minimum n 1,500.
Preregistration: F3_us_session_momentum.md (4a03273) + F3_amendment_1.md (6ca3342).
It refuses to run twice: an existing result file is never overwritten.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from xau_edge.features import indicators as ind
from xau_edge.market_data.calendars import ftmo_calendar
from xau_edge.research_v2.frame import _mismatch_days, uncertified_years
from xau_edge.research_v3 import f3
from xau_edge.research_v3.data import ROOT, load_bars
from xau_edge.research_v3.stats import (
    block_bootstrap_means,
    describe,
    mean_without_top,
    placebo_percentile,
    stage1_gate,
    weekday_calendar,
)

V3 = ROOT / "docs" / "research" / "edge-program-v3"
OUT = V3 / "results"
CERTIFICATE = ROOT / "docs" / "research" / "edge-program-v2" / "clock-certificate.json"
PREREG_COMMIT = "4a03273e9bcc0c982aefc640ace8e357221c2de1"
AMENDMENT_COMMIT = "6ca3342"
ALPHA_STAGE1 = 0.0333
MIN_EVENTS_PER_YEAR = 150
N_MIN_DEV = 1500
DEV_START, DEV_END = date(2011, 1, 1), date(2019, 1, 1)
PARITY_WINDOWS = [(date(2012, 1, 1), date(2012, 7, 1)), (date(2012, 10, 1), date(2012, 12, 1))]
DATA_FILES = [
    p
    for tf in ("H1", "M1")
    for p in sorted((ROOT / "data" / "market" / "XAUUSD" / tf).glob("*.parquet"))
    if "2010-11" <= p.stem <= "2019-01"
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    cmd = ["git", *args]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()  # noqa: S603


def _closures() -> f3.Closures:
    return f3.Closures.from_windows([(w.start, w.end) for w in ftmo_calendar().closures])


def _load(start: date, end: date) -> tuple[pl.DataFrame, pl.DataFrame]:
    h1 = load_bars("XAUUSD", "H1", start - timedelta(days=40), end + timedelta(days=1))
    m1 = load_bars("XAUUSD", "M1", start - timedelta(days=1), end + timedelta(days=1))
    return h1, m1


def _ny(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        pl.col("timestamp").dt.convert_time_zone("America/New_York").alias("ny")
    ).with_columns(
        pl.col("ny").dt.date().alias("d"),
        pl.col("ny").dt.strftime("%H:%M").alias("hm"),
    )


def _parity_window(start: date, end: date) -> dict[str, Any]:
    h1, m1 = _load(start, end)
    closures, bad_years = _closures(), uncertified_years(CERTIFICATE)
    res = f3.run(h1, m1, start, end, closures, bad_years)
    by_date = {t["ny_date"]: t for t in res["trades"]}

    h1_ny = _ny(h1).with_columns(
        pl.Series(
            "atr",
            ind.atr(h1["high"].to_numpy(), h1["low"].to_numpy(), h1["close"].to_numpy(), 14),
        )
    )
    ref_atr = {
        r["d"]: r["atr"] for r in h1_ny.filter(pl.col("hm") == "14:00").iter_rows(named=True)
    }
    ny = _ny(m1)
    groups = {
        k[0]: g
        for k, g in ny.filter(pl.col("hm").is_between(pl.lit("09:00"), pl.lit("17:00"))).group_by(
            "d"
        )
    }
    weekdays = [
        start + timedelta(days=i)
        for i in range((end - start).days)
        if (start + timedelta(days=i)).weekday() < 5
    ]
    v2_mask = {d for d in _mismatch_days(weekdays) if d.year in bad_years}
    diffs = {"clock_mask_vs_v2": 0, "event_set": 0, "direction": 0, "exit_time": 0, "reason": 0}
    diffs |= {"atr": 0, "gross_r": 0, "base_r": 0, "pess_r": 0}
    masked = 0
    for d in weekdays:
        diffs["clock_mask_vs_v2"] += int(f3.clock_unsafe(d, bad_years) != (d in v2_mask))
        if d in v2_mask or closures.overlaps(
            f3.ny_us(d, f3.OPEN_NY), f3.ny_us(d, f3.SESSION_END_NY)
        ):
            masked += 1
            continue
        g = groups.get(d)
        bars = (
            {}
            if g is None
            else {
                r["hm"]: (r["open"], r["high"], r["low"], float(r["spread"]))
                for r in g.iter_rows(named=True)
            }
        )
        mine = by_date.get(d.isoformat())
        a = float(ref_atr.get(d, float("nan")))
        ok_atr = bool(np.isfinite(a) and a > 0)
        g_ref = f3.reference_day(bars, a, 0.0, 0.0) if ok_atr else None
        b_ref = f3.reference_day(bars, a, 1.6, 3.0) if ok_atr else None
        p_ref = f3.reference_day(bars, a, 2.4, 6.0) if ok_atr else None
        if (b_ref is None) != (mine is None):
            diffs["event_set"] += 1
            continue
        if mine is None or b_ref is None or g_ref is None or p_ref is None:
            continue
        diffs["atr"] += int(abs(a - mine["atr"]) > 1e-12)
        diffs["pess_r"] += int(abs(p_ref[3] - mine["pess_r"]) > 1e-9)
        s, hm, reason, r = b_ref
        exit_hm = (
            datetime.fromtimestamp(mine["exit_us"] / 1e6, tz=UTC)
            .astimezone(f3.NEW_YORK)
            .strftime("%H:%M")
        )
        diffs["direction"] += int(s != mine["direction"])
        diffs["exit_time"] += int(hm != exit_hm)
        diffs["reason"] += int(reason != mine["reason"])
        diffs["gross_r"] += int(abs(g_ref[3] - mine["gross_r"]) > 1e-9)
        diffs["base_r"] += int(abs(r - mine["base_r"]) > 1e-9)
    return {
        "window": [start.isoformat(), end.isoformat()],
        "weekdays": len(weekdays),
        "masked_or_closed_days": masked,
        "trades_compared": len(res["trades"]),
        "runner_counts": res["counts"],
        "differences": diffs,
    }


def parity() -> int:
    windows = [_parity_window(a, b) for a, b in PARITY_WINDOWS]
    report = {
        "family": "F3-USMOM-0930-1400-1500-1645",
        "kind": "oracle parity (array runner vs New-York-clock reference); outcome statistics not computed",
        "windows": windows,
        "verdict": "PASS" if not any(any(w["differences"].values()) for w in windows) else "FAIL",
        "code_head": _git("rev-parse", "HEAD"),
        "generated_at": datetime.now(UTC).isoformat(),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "F3_parity.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))
    return 0 if report["verdict"] == "PASS" else 1


def _grouped(base: np.ndarray, keys: np.ndarray) -> dict[str, dict[str, float | int]]:
    return {
        str(k): {"n": int((keys == k).sum()), "mean_base_r": float(base[keys == k].mean())}
        for k in np.unique(keys)
    }


def stage1() -> int:
    out_json = OUT / "F3_stage1.json"
    rel = "docs/research/edge-program-v3/results/F3_stage1.json"
    if out_json.exists() or _git("log", "--oneline", "--all", "--", rel):
        print("F3 Stage 1 already ran; refusing to run again:", out_json)
        return 2
    if _git(
        "status",
        "--porcelain",
        "--",
        "src/xau_edge/research_v3",
        "src/xau_edge/research_v2/frame.py",
        "src/xau_edge/features/indicators.py",
        "src/xau_edge/market_data/calendars.py",
        "src/xau_edge/market_data/session_exceptions.py",
        "src/xau_edge/market_data/validators/market_calendar.py",
        "docs/research/edge-program-v2/clock-certificate.json",
        "configs/brokers",
        "tests/research_v3",
        "scripts/run_v3_f3.py",
    ):
        print("runner code is not committed; commit the implementation before the outcome run")
        return 3
    if _git(
        "diff",
        PREREG_COMMIT,
        "--name-only",
        "--",
        "docs/research/edge-program-v3/F3_us_session_momentum.md",
        "docs/research/edge-program-v3/COMMON_PROTOCOL.md",
    ) or _git(
        "diff",
        AMENDMENT_COMMIT,
        "--name-only",
        "--",
        "docs/research/edge-program-v3/F3_amendment_1.md",
    ):
        print("the preregistration, amendment or protocol changed after registration")
        return 4
    h1, m1 = _load(DEV_START, DEV_END)
    res = f3.run(h1, m1, DEV_START, DEV_END, _closures(), uncertified_years(CERTIFICATE))
    tr = res["trades"]
    base = np.array([t["base_r"] for t in tr])
    pess = np.array([t["pess_r"] for t in tr])
    gross = np.array([t["gross_r"] for t in tr])
    days = np.array([t["day"] for t in tr], dtype=np.int64)
    years = np.array([t["year"] for t in tr])
    boot = block_bootstrap_means(
        base, days, calendar=weekday_calendar(int(days.min()), int(days.max()))
    )
    p = float((boot <= 0).mean())
    pl_ = placebo_percentile(
        np.array([t["long_base_r"] for t in tr]),
        np.array([t["short_base_r"] for t in tr]),
        float(base.mean()),
    )
    by_year = _grouped(base, years)
    years_pos = sum(1 for v in by_year.values() if v["mean_base_r"] > 0)
    no_top = mean_without_top(base)
    n_years = (DEV_END - DEV_START).days / 365.25
    gate = stage1_gate(
        n=len(tr),
        n_min=N_MIN_DEV,
        p=p,
        alpha=ALPHA_STAGE1,
        mean_base=float(base.mean()),
        mean_pess=float(pess.mean()),
        years_positive=years_pos,
        mean_without_top1pct=no_top,
        placebo_pct=pl_["percentile_of_real"],
    )
    atr = np.array([t["atr"] for t in tr])
    move = np.abs(np.array([t["move_0930_1400"] / t["open_0930"] for t in tr]))
    quint = np.searchsorted(np.quantile(move, [0.2, 0.4, 0.6, 0.8]), move, side="right") + 1
    reasons = [t["reason"] for t in tr]
    slip = float(np.mean([t["slip_r"] for t in tr]))
    result = {
        "family": "F3-USMOM-0930-1400-1500-1645",
        "stage": "Stage 1 (Development-2)",
        "window_ny_dates": [DEV_START.isoformat(), DEV_END.isoformat()],
        "counts": res["counts"],
        "n": len(tr),
        "events_per_year": len(tr) / n_years,
        "gross": describe(gross),
        "net_base": describe(base),
        "net_pessimistic": describe(pess),
        "frequency_label": "ECONOMICALLY IMPRACTICAL"
        if len(tr) / n_years < MIN_EVENTS_PER_YEAR
        else "FREQUENCY OK",
        "bootstrap": {
            "p_one_sided": p,
            "ci95_mean_base": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
            "resamples": int(boot.size),
            "block_days": 5,
            "seed": 20261011,
        },
        "placebo": pl_,
        "by_year": by_year,
        "by_weekday_descriptive": _grouped(base, np.array([t["weekday"] for t in tr])),
        "by_abs_move_quintile_descriptive": _grouped(base, quint),
        "exit_reasons": {r: reasons.count(r) for r in sorted(set(reasons))},
        "cost_attribution_mean_r": {
            "gross": float(gross.mean()),
            "slippage": -slip,
            "spread_and_path": float(base.mean() - gross.mean() + slip),
            "net_base": float(base.mean()),
        },
        "break_even_commission_usd_per_lot_per_side": float(base.mean() / np.mean(2 / (100 * atr))),
        "expected_contribution_per_year_pct_at_0_25_risk": 0.25
        * (len(tr) / n_years)
        * float(base.mean()),
        "mean_without_top_1pct": no_top,
        "years_positive": years_pos,
        "gate": gate | {"alpha": ALPHA_STAGE1, "n_min": N_MIN_DEV},
        "verdict": gate["verdict"],
        "provenance": {
            "code_head": _git("rev-parse", "HEAD"),
            "preregistration_commit": PREREG_COMMIT,
            "amendment_commit": AMENDMENT_COMMIT,
            "prereg_sha256": _sha(V3 / "F3_us_session_momentum.md"),
            "amendment_sha256": _sha(V3 / "F3_amendment_1.md"),
            "protocol_sha256": _sha(V3 / "COMMON_PROTOCOL.md"),
            "clock_certificate_sha256": _sha(CERTIFICATE),
            "data_files": len(DATA_FILES),
            "data_sha256_of_file_hashes": hashlib.sha256(
                "".join(f"{p.parent.name}/{p.name}:{_sha(p)}\n" for p in DATA_FILES).encode()
            ).hexdigest(),
            "closures_sha256": _sha(ROOT / "configs" / "brokers" / "ftmo_session_exceptions.yaml"),
            "generated_at": datetime.now(UTC).isoformat(),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, indent=1), encoding="utf-8")
    with (OUT / "F3_stage1_trades.csv").open("w", newline="", encoding="utf-8") as fh:
        cols = ["ny_date", "direction", "move_0930_1400", "atr", "entry_us", "exit_us"]
        cols += ["entry_px", "exit_px", "reason", "gross_r", "base_r", "pess_r", "day", "year"]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(tr)
    print(
        json.dumps(
            {k: result[k] for k in ("n", "events_per_year", "verdict", "counts")}
            | {
                "gate": gate,
                "mean_gross": result["gross"]["mean_r"],
                "mean_base": result["net_base"]["mean_r"],
                "mean_pess": result["net_pessimistic"]["mean_r"],
                "p": p,
            },
            indent=1,
        )
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--parity", action="store_true")
    g.add_argument("--stage1", action="store_true")
    a = ap.parse_args()
    return parity() if a.parity else stage1()


if __name__ == "__main__":
    sys.exit(main())
