"""Pre-registered evaluation of baseline variants on BURNED windows (decisions only, no outcomes).

ONE process per window evaluates ALL variants: the market state and the setup lifecycle are
computed once per decision and shared (``evaluate_many``), the process runs at below-normal
priority, prints progress, checkpoints after every trading day and can resume (``--resume``).
Variants: v1.1, none, A, B, C, AB, ABC (attribution only; the pre-registration forbids choosing by
outcome). ``--workers`` runs several windows in parallel (default: a quarter of the cores).

Usage: ``uv run python scripts/trade_v12_eval.py --start 2025-08-04 --end 2025-09-01``
       ``uv run python scripts/trade_v12_eval.py --windows 2025-08-04:2025-09-01 2025-12-01:2025-12-29``
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl
from signal_funnel_dump import BURNED_FROM, BURNED_TO, EQUITY, WARMUP, tail_view

from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.ledger import BarLedger
from xau_edge.ops.priority import default_workers, lower_priority
from xau_edge.strategies.edge_program import SERVER_CLOCK
from xau_edge.trading.baseline import BaselineConfig
from xau_edge.trading.decision_core import SnapshotInputs, comparable, evaluate_many
from xau_edge.trading.frames import from_frames
from xau_edge.trading.live_source import spec_from_broker
from xau_edge.trading.market_state import SnapshotMemo
from xau_edge.trading.schema import TradeDecision
from xau_edge.trading.sizing import SymbolSpec

VARIANTS: dict[str, dict[str, Any]] = {
    "v1.1": {"version": "1.1.0"},
    "none": {"version": "1.2.0", "v12_lifecycle": False, "v12_m5_geometry": False, "v12_vol_warning": False},
    "A": {"version": "1.2.0", "v12_m5_geometry": False, "v12_vol_warning": False},
    "B": {"version": "1.2.0", "v12_lifecycle": False, "v12_vol_warning": False},
    "C": {"version": "1.2.0", "v12_lifecycle": False, "v12_m5_geometry": False},
    "AB": {"version": "1.2.0", "v12_vol_warning": False},
    "ABC": {"version": "1.2.0"},
    "D": {"version": "1.1.0", "spread_veto": False},
    "ABCD": {"version": "1.2.0", "spread_veto": False},
}  # fmt: skip
PROGRESS_EVERY = 500


def plan_problems(signal: Any, spec: SymbolSpec, equity: float) -> list[str]:
    out: list[str] = []
    side = 1 if signal.decision is TradeDecision.BUY else -1
    e, sl, tp = signal.entry_price, signal.stop_loss, signal.take_profit
    if None in (e, sl, tp, signal.position_size, signal.risk_reward, signal.signal_expiry):
        return ["INCOMPLETE_PLAN"]
    if not (side * (e - sl) > 0 and side * (tp - e) > 0):
        out.append("LEVELS_ON_WRONG_SIDE")
    if abs(e - sl) < spec.min_stop_distance():
        out.append("STOP_INSIDE_BROKER_MINIMUM")
    if signal.position_size < spec.volume_min - 1e-12:
        out.append("LOT_BELOW_MINIMUM")
    steps = signal.position_size / spec.volume_step
    if abs(steps - round(steps)) > 1e-6:
        out.append("LOT_NOT_ON_STEP")
    if signal.risk_amount is not None and signal.risk_amount > equity * 0.005 + 1e-6:
        out.append("RISK_ABOVE_CAP")
    if signal.risk_reward < 1.5 - 1e-9:
        out.append("RR_BELOW_MINIMUM")
    return out


def _new_acc() -> dict[str, Any]:
    return {
        "counts": {}, "first_refusals": {}, "phases": {}, "problems": {}, "sessions": {},
        "hours": {}, "signals": [], "day_hashes": [], "parity_mismatches": 0,
    }  # fmt: skip


def _bump(table: dict[str, int], key: str) -> None:
    table[key] = table.get(key, 0) + 1


def run_window(job: dict[str, Any]) -> str:
    lower_priority()
    start = datetime.fromisoformat(job["start"]).replace(tzinfo=UTC)
    end = datetime.fromisoformat(job["end"]).replace(tzinfo=UTC)
    if start < BURNED_FROM or end > BURNED_TO:
        msg = "refused: window must lie inside the burned period 2025-05-01..2026-04-30"
        raise SystemExit(msg)
    names: list[str] = job["variants"]
    out_dir = Path(job["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{job['start']}_{job['end']}"
    ckpt_path = out_dir / f"ckpt_{tag}.json"
    ledger = BarLedger(Path(job["root"]))
    bars = from_frames(
        {
            tf: ledger.load("XAUUSD", tf, start - w, end + timedelta(days=1))
            for tf, w in WARMUP.items()
        }
    )
    live = json.loads((Path(job["root"]) / "live.json").read_text(encoding="utf-8"))
    spec = spec_from_broker(live.get("symbol_spec")) or SymbolSpec()
    configs = {n: BaselineConfig(allow_unknown_news=True, **VARIANTS[n]) for n in names}
    memo = SnapshotMemo(limit=200_000)
    rows = bars.frames[Timeframe.M5].filter(
        (pl.col("available_at") >= start) & (pl.col("available_at") < end)
    )
    acc = {n: _new_acc() for n in names}
    done_days: list[str] = []
    resumed = False
    if job["resume"] and ckpt_path.exists():
        saved = json.loads(ckpt_path.read_text(encoding="utf-8"))
        if saved.get("variants") == names:
            acc, done_days, resumed = saved["acc"], saved["done_days"], True
    stream = {n: hashlib.sha256() for n in names}
    day_digest = {n: hashlib.sha256() for n in names}
    total = rows.height
    started = time.perf_counter()
    current_day: str | None = None
    processed = 0
    for row in rows.iter_rows(named=True):
        at = row["available_at"]
        day = at.strftime("%Y-%m-%d")
        if day != current_day:
            if current_day is not None and current_day not in done_days:
                for n in names:
                    acc[n]["day_hashes"].append(day_digest[n].hexdigest()[:16])
                    day_digest[n] = hashlib.sha256()
                done_days.append(current_day)
                ckpt_path.write_text(
                    json.dumps({"variants": names, "acc": acc, "done_days": done_days}),
                    encoding="utf-8",
                )
            current_day = day
        if day in done_days:
            continue
        spread, close = float(row["spread"]), float(row["close"])
        inputs = SnapshotInputs(
            tail_view(bars, at), at, close, close + spread * spec.point, spread, spec, EQUITY,
            "UNKNOWN", True, True,
        )  # fmt: skip
        state, signals = evaluate_many(inputs, configs, SERVER_CLOCK, memo)
        full_signal = None
        if job["parity"] and "ABC" in signals:
            full_in = SnapshotInputs(
                bars.truncated(at), at, close, close + spread * spec.point, spread, spec,
                EQUITY, "UNKNOWN", True, True,
            )  # fmt: skip
            _, many = evaluate_many(full_in, {"ABC": configs["ABC"]}, SERVER_CLOCK, memo)
            full_signal = many["ABC"]
        for n, signal in signals.items():
            a = acc[n]
            blob = json.dumps(comparable(signal), sort_keys=True, default=str).encode()
            stream[n].update(blob)
            day_digest[n].update(blob)
            _bump(a["counts"], signal.decision.value)
            _bump(a["phases"], str(signal.metadata.get("setup_phase", "-")))
            if signal.decision is TradeDecision.WAIT:
                _bump(a["first_refusals"], signal.refusal_reasons[0].value)
            else:
                for p in plan_problems(signal, spec, EQUITY):
                    _bump(a["problems"], p)
                _bump(a["sessions"], state.session)
                _bump(a["hours"], str(at.hour))
                a["signals"].append(
                    {
                        "at": at.isoformat(), "side": signal.decision.value,
                        "setup_id": signal.setup_id,
                        "armed": signal.metadata.get("setup_bars_since_armed"),
                        "m15_bar": at.replace(minute=at.minute - at.minute % 15).isoformat(),
                        "rr": signal.risk_reward, "quality": signal.entry_quality,
                    }
                )  # fmt: skip
            if (
                n == "ABC"
                and full_signal is not None
                and comparable(full_signal) != comparable(signal)
            ):
                a["parity_mismatches"] += 1
        processed += 1
        if processed % PROGRESS_EVERY == 0:
            elapsed = time.perf_counter() - started
            eta = elapsed / processed * (total - processed)
            print(
                f"[{tag}] {processed}/{total} decisions, {elapsed:.0f}s, ETA {eta:.0f}s",
                file=sys.stderr,
                flush=True,
            )
    if current_day is not None and current_day not in done_days:
        for n in names:
            acc[n]["day_hashes"].append(day_digest[n].hexdigest()[:16])
        done_days.append(current_day)
    reports: dict[str, Any] = {}
    for n in names:
        a = acc[n]
        ids = Counter(s["setup_id"] for s in a["signals"])
        same_m15 = Counter((s["side"], s["m15_bar"]) for s in a["signals"])
        n_sig = a["counts"].get("BUY", 0) + a["counts"].get("SELL", 0)
        report = {
            "variant": n,
            "window": [job["start"], job["end"]],
            "decisions": sum(a["counts"].values()),
            "counts": a["counts"],
            "trading_days": len(done_days),
            "signal_decisions": n_sig,
            "distinct_setups": len(ids),
            "distinct_setups_per_day": round(len(ids) / max(1, len(done_days)), 3),
            "setup_ids_with_more_than_one_decision": sum(1 for v in ids.values() if v > 1),
            "same_side_same_m15_bar_decisions": sum(1 for v in same_m15.values() if v > 1),
            "setup_phase_counts": a["phases"],
            "first_refusals": sorted(a["first_refusals"].items(), key=lambda kv: -kv[1])[:12],
            "plan_violations": a["problems"],
            "sessions": a["sessions"],
            "hours_utc": dict(sorted(a["hours"].items(), key=lambda kv: int(kv[0]))),
            "parity_mismatches": a["parity_mismatches"]
            if (job["parity"] and n == "ABC")
            else "not run",
            "day_hashes_sha": hashlib.sha256("".join(a["day_hashes"]).encode()).hexdigest()[:16],
            "stream_hash": "n/a (resumed)" if resumed else stream[n].hexdigest()[:16],
            "signals": a["signals"][:200],
        }
        (out_dir / f"eval_{n}_{tag}.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        reports[n] = {k: v for k, v in report.items() if k != "signals"}
    print(json.dumps(reports, indent=1))
    ckpt_path.unlink(missing_ok=True)
    return tag


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--windows", nargs="*", default=[], help="START:END pairs")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--variants", nargs="*", default=list(VARIANTS))
    parser.add_argument("--root", default="data/market")
    parser.add_argument("--parity", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--workers", type=int, default=default_workers())
    parser.add_argument("--out-dir", default="data/trade/reports/v12")
    args = parser.parse_args()
    pairs = [w.split(":") for w in args.windows]
    if args.start and args.end:
        pairs.append([args.start, args.end])
    if not pairs:
        parser.error("give --start/--end or --windows")
    jobs = [
        {"start": s, "end": e, "variants": args.variants, "root": args.root, "parity": args.parity,
         "resume": args.resume, "out_dir": args.out_dir}
        for s, e in pairs
    ]  # fmt: skip
    workers = min(args.workers, len(jobs))
    if workers <= 1:
        for job in jobs:
            run_window(job)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            list(pool.map(run_window, jobs))


if __name__ == "__main__":
    main()
