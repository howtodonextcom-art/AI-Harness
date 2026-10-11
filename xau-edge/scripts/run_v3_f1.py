"""F1-USDRES-z2.0 runner: oracle parity (no outcome statistics printed) and the single Stage 1 run.

    .venv\\Scripts\\python.exe scripts\\run_v3_f1.py --parity
    .venv\\Scripts\\python.exe scripts\\run_v3_f1.py --stage1

Stage 1 = Development-2 (decision time 2011-01-01 .. 2018-12-31), alpha 0.0333, minimum n 1,000.
It refuses to run twice: an existing result file is never overwritten.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np

from xau_edge.research_v3 import f1
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
PREREG_COMMIT = "4a03273e9bcc0c982aefc640ace8e357221c2de1"
ALPHA_STAGE1 = 0.0333
MIN_EVENTS_PER_YEAR = 150
N_MIN_DEV = 1000
DEV_START, DEV_END = datetime(2011, 1, 1, tzinfo=UTC), datetime(2019, 1, 1, tzinfo=UTC)
PARITY_START, PARITY_END = datetime(2012, 1, 1, tzinfo=UTC), datetime(2012, 7, 1, tzinfo=UTC)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    cmd = ["git", *args]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()  # noqa: S603


def _inputs(h1_from: date, h1_to: date, m1_from: date) -> f1.Inputs:
    return f1.Inputs(
        xau_h1=load_bars("XAUUSD", "H1", h1_from, h1_to),
        eur_h1=load_bars("EURUSD", "H1", h1_from, h1_to),
        jpy_h1=load_bars("USDJPY", "H1", h1_from, h1_to),
        xau_m1=load_bars("XAUUSD", "M1", m1_from, h1_to),
    )


def parity() -> int:
    inp = _inputs(date(2011, 1, 1), date(2012, 7, 31), date(2012, 1, 1))
    res = f1.run(inp, PARITY_START, PARITY_END)
    j = f1.joined_returns(inp.xau_h1, inp.eur_h1, inp.jpy_h1)
    y, u = j["r_xau"].to_numpy(), j["u"].to_numpy()
    z = f1.rolling_z(y, u)
    jt = j["timestamp"].dt.epoch("us").to_numpy()
    rows = np.flatnonzero(
        (jt >= PARITY_START.timestamp() * 1e6) & (jt < PARITY_END.timestamp() * 1e6)
    )
    vec_events = {int(jt[i]) for i in rows if abs(z[i]) >= f1.Z_STAR}
    ref_events = {int(jt[i]) for i in rows if abs(f1.reference_z(y, u, int(i))) >= f1.Z_STAR}
    m1 = inp.xau_m1
    bars = list(
        zip(
            m1["timestamp"].dt.epoch("us").to_list(),
            m1["open"].to_list(),
            m1["high"].to_list(),
            m1["low"].to_list(),
            m1["spread"].cast(float).to_list(),
            strict=True,
        )
    )
    diffs = {
        "event_set": len(vec_events ^ ref_events),
        "direction": 0,
        "exit_time": 0,
        "reason": 0,
        "gross_r": 0,
        "base_net_before_swap_r": 0,
    }
    for t in res["trades"]:
        k = int(np.searchsorted(jt, t["decision_us"]))
        if int(-np.sign(f1.reference_z(y, u, k))) != t["direction"]:
            diffs["direction"] += 1
        h1 = inp.xau_h1["timestamp"].dt.epoch("us").to_numpy()
        hk = int(np.searchsorted(h1, t["decision_us"]))
        timeout_hour = int(h1[hk + 1 + f1.TIMEOUT_BARS])
        window = [b for b in bars if t["entry_us"] <= b[0] < timeout_hour + f1.HOUR_US]
        g_ref = f1.reference_trade(
            window, t["entry_us"], timeout_hour, t["direction"], t["atr"], 0.0, 0.0
        )
        b_ref = f1.reference_trade(
            window, t["entry_us"], timeout_hour, t["direction"], t["atr"], 1.6, 3.0
        )
        if g_ref is None or b_ref is None:
            diffs["exit_time"] += 1
            continue
        _, _, gr = g_ref
        bx, br_reason, br = b_ref
        diffs["exit_time"] += int(bx != t["exit_us"])
        diffs["reason"] += int(br_reason != t["reason"])
        diffs["gross_r"] += int(abs(gr - t["gross_r"]) > 1e-9)
        diffs["base_net_before_swap_r"] += int(abs(br - (t["base_r"] - t["swap_r"])) > 1e-9)
    report = {
        "family": "F1-USDRES-z2.0",
        "kind": "oracle parity (vectorized vs reference); outcome statistics deliberately not computed",
        "window": [PARITY_START.isoformat(), PARITY_END.isoformat()],
        "events_compared": len(vec_events),
        "trades_compared": len(res["trades"]),
        "differences": diffs,
        "verdict": "PASS" if not any(diffs.values()) else "FAIL",
        "code_head": _git("rev-parse", "HEAD"),
        "generated_at": datetime.now(UTC).isoformat(),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "F1_parity.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))
    return 0 if report["verdict"] == "PASS" else 1


def stage1() -> int:
    out_json = OUT / "F1_stage1.json"
    if out_json.exists():
        print("F1 Stage 1 already ran; refusing to run again:", out_json)
        return 2
    if _git(
        "status",
        "--porcelain",
        "--",
        "src/xau_edge/research_v3",
        "src/xau_edge/features/indicators.py",
        "scripts/run_v3_f1.py",
    ):
        print("runner code is not committed; commit the implementation before the outcome run")
        return 3
    frozen = [
        "docs/research/edge-program-v3/F1_gold_usd_residual.md",
        "docs/research/edge-program-v3/COMMON_PROTOCOL.md",
    ]
    if _git("diff", PREREG_COMMIT, "--name-only", "--", *frozen):
        print("the preregistration or protocol changed after", PREREG_COMMIT)
        return 4
    inp = _inputs(date(2010, 1, 1), date(2019, 1, 31), date(2011, 1, 1))
    res = f1.run(inp, DEV_START, DEV_END)
    tr = res["trades"]
    base = np.array([t["base_r"] for t in tr])
    pess = np.array([t["pess_r"] for t in tr])
    gross = np.array([t["gross_r"] for t in tr])
    days = np.array([t["day"] for t in tr], dtype=np.int64)
    years = np.array([t["year"] for t in tr])
    first_day = f1.trading_day(int(DEV_START.timestamp() * 1e6))
    last_day = f1.trading_day(int(DEV_END.timestamp() * 1e6) - 1)
    boot = block_bootstrap_means(
        base,
        days,
        calendar=weekday_calendar(min(first_day, int(days.min())), max(last_day, int(days.max()))),
    )
    p = float((boot <= 0).mean())
    pl_ = placebo_percentile(
        np.array([t["long_base_r"] for t in tr]),
        np.array([t["short_base_r"] for t in tr]),
        float(base.mean()),
    )
    by_year = {
        int(yv): {"n": int((years == yv).sum()), "mean_base_r": float(base[years == yv].mean())}
        for yv in np.unique(years)
    }
    years_pos = sum(1 for v in by_year.values() if v["mean_base_r"] > 0)
    no_top = mean_without_top(base)
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
    hours = np.array([datetime.fromtimestamp(t["decision_us"] / 1e6, tz=UTC).hour for t in tr])
    sessions = {
        "ASIA_00_07": (0, 7),
        "LONDON_07_12": (7, 12),
        "OVERLAP_12_16": (12, 16),
        "NY_LATE_16_21": (16, 21),
        "ROLLOVER_21_24": (21, 24),
    }
    reasons = [t["reason"] for t in tr]
    n_years = (DEV_END - DEV_START).days / 365.25
    result = {
        "family": "F1-USDRES-z2.0",
        "stage": "Stage 1 (Development-2)",
        "window": [DEV_START.isoformat(), DEV_END.isoformat()],
        "counts": res["counts"],
        "n": len(tr),
        "events_per_year": len(tr) / n_years,
        "gross": describe(gross),
        "net_base": describe(base),
        "net_pessimistic": describe(pess),
        "net_base_triple_wednesday_sensitivity": float(
            np.mean([t["base_triple_wed_r"] for t in tr])
        ),
        "net_base_zero_swap_sensitivity": float(np.mean([t["base_zero_swap_r"] for t in tr])),
        "frequency_label": "ECONOMICALLY IMPRACTICAL"
        if len(tr) / ((DEV_END - DEV_START).days / 365.25) < MIN_EVENTS_PER_YEAR
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
        "pre_post_2015": {
            k: float(base[m].mean()) if m.any() else None
            for k, m in (("2011_2014", years < 2015), ("2015_2018", years >= 2015))
        },
        "by_session_utc": {
            k: {
                "n": int(((hours >= a) & (hours < b)).sum()),
                "mean_base_r": float(base[(hours >= a) & (hours < b)].mean())
                if ((hours >= a) & (hours < b)).any()
                else None,
            }
            for k, (a, b) in sessions.items()
        },
        "exit_reasons": {r: reasons.count(r) for r in sorted(set(reasons))},
        "cost_attribution_mean_r": {
            "gross": float(gross.mean()),
            "slippage": float(-np.mean([t["slip_r"] for t in tr])),
            "swap": float(np.mean([t["swap_r"] for t in tr])),
            "spread_and_path": float(
                base.mean()
                - gross.mean()
                + np.mean([t["slip_r"] for t in tr])
                - np.mean([t["swap_r"] for t in tr])
            ),
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
            "prereg_sha256": _sha(V3 / "F1_gold_usd_residual.md"),
            "protocol_sha256": _sha(V3 / "COMMON_PROTOCOL.md"),
            "cross_asset_manifest_sha256": _sha(V3 / "foundation" / "cross_asset_manifest.json"),
            "swap_points": {"long": -69.25, "short": -4.2, "read_at": "2026-10-11T06:16Z"},
            "generated_at": datetime.now(UTC).isoformat(),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, indent=1), encoding="utf-8")
    with (OUT / "F1_stage1_trades.csv").open("w", newline="", encoding="utf-8") as fh:
        cols = [
            "decision_us",
            "z",
            "direction",
            "atr",
            "entry_us",
            "exit_us",
            "entry_px",
            "exit_px",
            "reason",
            "gross_r",
            "base_r",
            "pess_r",
            "swap_r",
            "nights",
            "day",
            "year",
        ]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(tr)
    print(
        json.dumps(
            {k: result[k] for k in ("n", "events_per_year", "verdict")}
            | {
                "gate": gate,
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
