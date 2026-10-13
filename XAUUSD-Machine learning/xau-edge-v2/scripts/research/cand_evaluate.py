"""Stage B + report: signals -> PAPER trades -> the eight sections of the candidate evaluation.

Reads the Stage A output (``cand_signals.py``), simulates every variant with the desk's rules
(``xau_edge_v2.research.backtest``), applies the statistics of the frozen spec, and writes
``<out>/summary.json`` plus ``<out>/report.md``.

FREEZE GATE: it refuses to run unless ``docs/research/cand_v2_spec.sha256`` exists and equals the
canonical hash of ``cand_v2_spec.json``. The spec hash and the git sha are written into the summary.
Only the DEV window is accepted unless ``--confirm`` is given (one look at VALIDATION / CONFIRM_C,
after ``docs/research/cand_v2_frozen.json`` exists).

    uv run python scripts/research/cand_evaluate.py --window DEV --signals data/research/cand --out data/research/cand_eval
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

for _v in ("POLARS_MAX_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "1"

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402
import polars as pl  # noqa: E402
from cand_signals import WINDOWS, months_of  # noqa: E402

from xau_edge_v2.config import Settings  # noqa: E402
from xau_edge_v2.core.candidate import CORE_TIER, VARIANTS  # noqa: E402
from xau_edge_v2.data.bar_store import BarStore  # noqa: E402
from xau_edge_v2.domain.contract import Timeframe  # noqa: E402
from xau_edge_v2.research.backtest import HORIZON, M1Series, Trade, run_variant  # noqa: E402
from xau_edge_v2.research.clean_view import require_clean  # noqa: E402
from xau_edge_v2.research.stats import (  # noqa: E402
    DEFF,
    N_MIN,
    SD_R,
    Bound,
    block_bootstrap,
    classify,
    n_required,
    safety_caps_hold,
)

SPEC = ROOT / "docs" / "research" / "cand_v2_spec.json"
GUARD = SPEC.with_suffix(".sha256")
PARENT = {
    "A_C1": "CTRL",
    "A_C2": "CTRL",
    "A_C3a": "CTRL",
    "A_C3b": "CTRL",
    "B_C1C2": "A_C2",
    "B_C2C3a": "A_C2",
    "LOO_noC1": "B_C2C3a",
    "X_C7": "CTRL",
    "X_CORE_C7": "CORE",
}
IN_CONTEXT = {  # change -> (variant containing it, variant without it)
    "C1": ("CORE", "LOO_noC1"),
    "C2": ("CORE", "LOO_noC2"),
    "C3a": ("CORE", "LOO_noC3a"),
    "C3b": ("CORE", "LOO_noC3b"),
}
SINGLETON = {"C1": "A_C1", "C2": "A_C2", "C3a": "A_C3a", "C3b": "A_C3b"}


def canonical_hash(path: Path = SPEC) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def load_m1(months: list[tuple[int, int]]) -> M1Series:
    """Closed M1 bars from the window start to ten days past its end (the simulation horizon)."""
    (y0, m0), (y1, m1) = months[0], months[-1]
    start = datetime(y0, m0, 1, tzinfo=UTC)
    end = datetime(y1 + (m1 == 12), m1 % 12 + 1, 1, tzinfo=UTC) + HORIZON  # noqa: PLR2004
    store = BarStore(Settings().data_root, cache_seconds=0.0)
    parts: list[pl.DataFrame] = []
    cursor = start
    while cursor < end:
        df = store.window(Timeframe.M1, cursor, end, 5000)
        if df.height == 0:
            break
        parts.append(df)
        if df.height < 5000:  # noqa: PLR2004
            break
        cursor = df["timestamp"][-1] + timedelta(seconds=1)
    full = pl.concat(parts, how="vertical_relaxed")
    if (
        os.environ.get("XAU_ALLOW_DEFECTIVE") != "1"
    ):  # outcomes on pseudo-bar months look 24 hours ahead
        require_clean(full, "M1 window")
    return M1Series(
        open_us=full["timestamp"].dt.epoch("us").to_numpy().astype(np.int64),
        open=full["open"].to_numpy(),
        high=full["high"].to_numpy(),
        low=full["low"].to_numpy(),
        close=full["close"].to_numpy(),
        spread=full["spread"].fill_null(0.0).to_numpy(),
    )


def read_all(folder: Path, prefix: str, months: list[tuple[int, int]]) -> pl.DataFrame:
    frames = [
        pl.read_parquet(folder / f"{prefix}_{y}-{m:02d}.parquet")
        for y, m in months
        if (folder / f"{prefix}_{y}-{m:02d}.parquet").exists()
    ]
    frames = [f for f in frames if f.height > 0]  # a month without signals is an empty file
    return pl.concat(frames, how="vertical_relaxed") if frames else pl.DataFrame()


def month_key(t: datetime) -> str:
    return f"{t.year}-{t.month:02d}"


def bound_of(trades: list[Trade]) -> Bound:
    return block_bootstrap([t.r_net for t in trades], [month_key(t.closed_at) for t in trades])


def verify_signals(sig: pl.DataFrame, bars: pl.DataFrame) -> dict[str, dict[str, int]]:
    """Safety violations among the EMITTED signals, per variant (spec: safety.violations)."""
    out: dict[str, dict[str, int]] = {}
    shock = bars.select("ts", "shock", "spread_pct")
    joined = sig.join(shock, on="ts", how="left")
    for name in VARIANTS:
        s = joined.filter(pl.col("variant") == name)
        flags = {c.lower() for c in VARIANTS[name]}
        out[name] = {
            "signals": s.height,
            "net_rr_below_1_5": s.filter(pl.col("net_rr") < 1.5 - 1e-9).height,
            "stop_above_3_atr": s.filter(pl.col("risk_dist") > 3.0 * pl.col("atr15") + 1e-9).height,
            "risk_not_0_25": s.filter((pl.col("risk_pct") - 0.25).abs() > 1e-9).height,
            "cost_r_above_cap": s.filter(pl.col("cost_r") > 0.15 + 1e-12).height
            if "c2" in flags
            else 0,
            "spread_spike": s.filter(pl.col("spread_pct") >= 0.99).height if "c2" in flags else 0,
            "on_shock_bar": s.filter(pl.col("shock")).height if "c3b" in flags else 0,
        }
    return out


def armed_episodes(bars: pl.DataFrame) -> int:
    """Contiguous runs (gap <= 60 min) of bars on which the control's setup condition held, per side."""
    armed = bars.filter(pl.col("armed_now")).sort("ts")
    n = 0
    last: dict[str, datetime] = {}
    for ts, side in zip(armed["ts"].to_list(), armed["side"].to_list(), strict=True):
        if side not in last or ts - last[side] > timedelta(minutes=60):
            n += 1
        last[side] = ts
    return n


def summarize(name: str, trades: list[Trade], counters: Any, years: float) -> dict[str, Any]:
    b = bound_of(trades)
    status, why = classify(b)
    order = sorted(trades, key=lambda t: t.closed_at)
    ok, mdd, worst = safety_caps_hold(
        [t.r_net for t in order], [month_key(t.closed_at) for t in order]
    )
    n = len(trades)
    by_year: dict[int, list[float]] = {}
    for t in trades:
        by_year.setdefault(t.opened_at.year, []).append(t.r_net)
    return {
        "variant": name,
        "changes": list(VARIANTS[name]),
        "signal_rows": counters.signal_rows,
        "episodes": counters.episodes,
        "episodes_per_year": round(counters.episodes / years, 2),
        "attempted": counters.attempted,
        "refused": counters.refused,
        "unresolved": counters.unresolved,
        "executed": n,
        "executed_per_year": round(n / years, 2),
        "buy": sum(t.side == "BUY" for t in trades),
        "sell": sum(t.side == "SELL" for t in trades),
        "E": None if n == 0 else round(b.mean, 4),
        "E_lower": None if n == 0 else round(b.lower, 4),
        "E_upper": None if n == 0 else round(b.upper, 4),
        "months_with_trades": b.months,
        "status": status,
        "status_reason": why,
        "win_rate": None
        if n == 0
        else round(sum(t.reason == "TAKE_PROFIT" for t in trades) / n, 3),
        "false_positive_rate": None
        if n == 0
        else round(sum(t.false_positive for t in trades) / n, 3),
        "mdd_R": round(mdd, 2),
        "worst_month_R": round(worst, 2),
        "caps_hold": ok,
        "gap_through_stop": sum(t.gap for t in trades),
        "ambiguous_bars": sum(t.ambiguous for t in trades),
        "horizon_exits": sum(t.reason == "HORIZON" for t in trades),
        "mean_r_price": None if n == 0 else round(float(np.mean([t.r_price for t in trades])), 4),
        "mean_r_swap": None if n == 0 else round(float(np.mean([t.r_swap for t in trades])), 4),
        "mean_r_slip_plan": None
        if n == 0
        else round(float(np.mean([t.r_slip for t in trades])), 4),
        "mean_r_spread_plan": None
        if n == 0
        else round(float(np.mean([t.r_spread for t in trades])), 4),
        "sessions": {
            s: sum(t.session == s for t in trades) for s in sorted({t.session for t in trades})
        },
        "by_year": {
            str(y): {"n": len(v), "E": round(float(np.mean(v)), 3)}
            for y, v in sorted(by_year.items())
        },
    }


def incremental(name: str, parent: str, trades: dict[str, list[Trade]]) -> dict[str, Any]:
    have = {(t.opened_at, t.side) for t in trades[parent]}
    extra = [t for t in trades[name] if (t.opened_at, t.side) not in have]
    b = bound_of(extra)
    status, why = classify(b)
    return {
        "variant": name,
        "parent": parent,
        "n": len(extra),
        "E": None if not extra else round(b.mean, 4),
        "lower": None if not extra else round(b.lower, 4),
        "upper": None if not extra else round(b.upper, 4),
        "status": status,
        "reason": why,
    }


def selection(
    summ: dict[str, dict[str, Any]], inc: dict[str, dict[str, Any]], viol: dict[str, dict[str, int]]
) -> dict[str, Any]:
    """Apply the preregistered rule (spec: selection_rule) to the four CORE changes."""
    verdict: dict[str, Any] = {}
    included: set[str] = set()
    for change, (with_v, without_v) in IN_CONTEXT.items():
        single = SINGLETON[change]
        s_ok = (
            summ[single]["episodes"] >= summ["CTRL"]["episodes"]
            and summ[with_v]["episodes"] >= summ[without_v]["episodes"]
        )
        v_ok = all(
            sum(v for k, v in viol[x].items() if k != "signals") == 0 for x in (single, with_v)
        )
        statuses = [
            inc[f"{single}|CTRL"]["status"],
            inc[f"{with_v}|{without_v}"]["status"],
            summ[with_v]["status"],
        ]
        o_ok = "REFUTED_HARM" not in statuses
        caps_ok = summ[single]["caps_hold"] and summ[with_v]["caps_hold"]
        inconclusive = "INCONCLUSIVE" in statuses
        priority = change in ("C1", "C2")
        passed = s_ok and v_ok and o_ok and caps_ok
        verdict[change] = {
            "S_structural": s_ok,
            "V_safety": v_ok,
            "O_not_refuted": o_ok,
            "caps": caps_ok,
            "statuses": statuses,
            "enters": passed,
            "flag": (
                "research, flagged"
                if (inconclusive and not priority)
                else "owner priority"
                if inconclusive
                else ""
            ),
        }
        if passed:
            included.add(change)
    sets = {k: {c for c in v} for k, v in VARIANTS.items() if k in CORE_TIER}
    names = [k for k, v in sets.items() if v == {c for c in included}]
    if names:
        chosen = names[0]
    else:
        fits = [(len(v), -summ[k]["episodes"], k) for k, v in sets.items() if v <= included]
        chosen = max(fits)[2] if fits else "CTRL"
    return {
        "changes": verdict,
        "included": sorted(included),
        "frozen_candidate": chosen,
        "no_candidate": chosen == "CTRL",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", choices=sorted(WINDOWS), default="DEV")
    ap.add_argument("--signals", default="data/research/cand")
    ap.add_argument("--out", default="data/research/cand_eval")
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument(
        "--only-existing",
        action="store_true",
        help="debug: use only months that have Stage A files",
    )
    ap.add_argument(
        "--variants",
        default="",
        help="comma list (confirmation runs the frozen candidate and the control)",
    )
    a = ap.parse_args()
    if not GUARD.exists() or GUARD.read_text(encoding="utf-8").strip() != canonical_hash():
        sys.exit("FREEZE GATE: cand_v2_spec.sha256 is missing or does not match cand_v2_spec.json")
    if a.window != "DEV":
        frozen = ROOT / "docs" / "research" / "cand_v2_frozen.json"
        if not a.confirm or not frozen.exists():
            sys.exit(
                "Validation / Confirm-C need --confirm AND docs/research/cand_v2_frozen.json (freeze gate)"
            )
    folder = Path(a.signals)
    months = months_of(a.window)
    if a.only_existing:
        months = [
            (y, m)
            for y, m in months
            if (folder / f"sig_{y}-{m:02d}.parquet").exists()
            and (folder / f"bars_{y}-{m:02d}.parquet").exists()
        ]
    sig, bars = read_all(folder, "sig", months), read_all(folder, "bars", months)
    if sig.height == 0 or bars.height == 0:
        sys.exit("no Stage A output for this window")
    years = len(months) / 12.0
    names = [v for v in a.variants.split(",") if v] or list(VARIANTS)
    m1 = load_m1(months)
    trades: dict[str, list[Trade]] = {}
    counters: dict[str, Any] = {}
    for name in names:
        rows = sig.filter(pl.col("variant") == name).to_dicts()
        trades[name], counters[name] = run_variant(name, rows, m1)
        print(
            f"{name}: {counters[name].executed} trades from {counters[name].episodes} episodes",
            flush=True,
        )
    summ = {n: summarize(n, trades[n], counters[n], years) for n in names}
    viol = verify_signals(sig, bars)
    armed = armed_episodes(bars)
    out: dict[str, Any] = {
        "window": a.window,
        "spec_sha256": canonical_hash(),
        "git_sha": git_sha(),
        "generated_at": datetime.now(UTC).isoformat(),
        "years": years,
        "armed_episodes": armed,
        "bars": bars.height,
        "power": {
            "sd": SD_R,
            "deff": DEFF,
            "n_min": N_MIN,
            "n_required": {d: n_required(d) for d in (0.3, 0.2, 0.15, 0.1)},
        },
        "variants": summ,
        "violations": viol,
    }
    if a.window == "DEV" and len(names) == len(VARIANTS):
        inc = {f"{n}|{p}": incremental(n, p, trades) for n, p in PARENT.items()}
        for change, (w, wo) in IN_CONTEXT.items():
            inc[f"{w}|{wo}"] = incremental(w, wo, trades)
            inc[f"{SINGLETON[change]}|CTRL"] = incremental(SINGLETON[change], "CTRL", trades)
        out["incremental"] = inc
        out["selection"] = selection(summ, inc, viol)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "summary.json").write_text(
        json.dumps(out, indent=1, default=str), encoding="utf-8"
    )
    all_trades = [vars(t) for n in names for t in trades[n]]
    if all_trades:
        pl.DataFrame(all_trades, infer_schema_length=None).write_parquet(
            Path(a.out) / "trades.parquet"
        )
    print(json.dumps({k: out[k] for k in ("window", "spec_sha256", "git_sha")}, indent=1))


if __name__ == "__main__":
    main()
