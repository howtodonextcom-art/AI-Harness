"""Verify the MT5 adapter against a live DEMO terminal (read-only market data).

What it does, in order:
  1. connects to the local terminal and REFUSES to continue unless the account is a DEMO account;
  2. measures the server-clock offset from a live tick;
  3. downloads XAUUSD M5/M15/H1/H4 history month by month through ``Mt5BarSource``,
     stores it in the immutable raw store, and validates it with the broker profile;
  4. infers the broker clock from the weekly session boundaries;
  5. resamples M5 to M15/H1/H4 and cross-checks the result against the broker's own bars.

It never calls any trading function and never prints account identifiers or balances.
Usage (Windows, MT5 extra installed):
    uv run --extra mt5 python scripts/verify_mt5.py --since 2025-05-01
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from xau_edge.domain.bars import BarRequest
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.broker_clock import BrokerClock, infer_broker_clock
from xau_edge.market_data.catalog import DatasetCatalog
from xau_edge.market_data.mt5.source import Mt5BarSource, Mt5Settings, load_mt5_module
from xau_edge.market_data.profiles import BrokerProfile
from xau_edge.market_data.resampling import SpreadPolicy, resample_bars
from xau_edge.market_data.store import RawStore
from xau_edge.market_data.validators import validate_bars
from xau_edge.market_data.validators.coverage import check_coverage
from xau_edge.market_data.validators.cross_check import cross_check

DEFAULT_TERMINAL = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
SPREAD_POLICIES: tuple[SpreadPolicy, ...] = ("first", "last", "max", "mean")


def month_ranges(since: datetime, until: datetime) -> list[tuple[datetime, datetime]]:
    """Calendar-month UTC windows covering ``[since, until)``."""
    out = []
    cursor = since
    while cursor < until:
        nxt = datetime(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1, tzinfo=UTC)
        out.append((cursor, min(nxt, until)))
        cursor = nxt
    return out


def fetch_all(
    source: Mt5BarSource, symbol: str, tf: Timeframe, since: datetime, now: datetime
) -> pl.DataFrame:
    """Download ``tf`` bars month by month, dropping the still-forming last bar."""
    parts = []
    for start, end in month_ranges(since, now):
        frame = source.fetch_bars(BarRequest(symbol=symbol, timeframe=tf, start=start, end=end))
        if frame.height:
            parts.append(frame)
    bars = pl.concat(parts) if parts else pl.DataFrame()
    if bars.height == 0:
        return bars
    return bars.filter(pl.col("timestamp") + tf.delta <= now)  # exclude the open (forming) bar


def issue_summary(issues: Any) -> list[dict[str, Any]]:
    return [
        {
            "code": i.code.value,
            "severity": i.severity.value,
            "count": i.count,
            "first_samples": [t.isoformat() for t in i.sample[:3]],
        }
        for i in issues
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--since", default="2025-05-01")
    parser.add_argument("--profile", default="configs/brokers/ftmo_demo.yaml")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--report", default="data/processed/mt5_verification.json")
    args = parser.parse_args()

    profile = BrokerProfile.from_yaml(args.profile)
    mt5 = load_mt5_module()
    if not mt5.initialize(path=args.terminal_path, timeout=90000):
        print(f"initialize failed: {mt5.last_error()}")
        return 2
    try:
        account = mt5.account_info()
        if account is None or account.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
            print("REFUSING: the connected account is not a DEMO account (or none is logged in).")
            return 3
        terminal = mt5.terminal_info()
        mt5.symbol_select(args.symbol, True)

        now = datetime.now(UTC)
        tick = mt5.symbol_info_tick(args.symbol)
        measured_offset_h = None
        if tick is not None:
            measured = datetime.fromtimestamp(tick.time, UTC) - now
            measured_offset_h = round(measured.total_seconds() / 3600, 1)
        expected_offset_h = (
            profile.clock.to_server_wall(now) - now.replace(tzinfo=None)
        ).total_seconds() / 3600

        source = Mt5BarSource(mt5, Mt5Settings(broker_timezone=profile.clock.token))
        since = datetime.fromisoformat(args.since).replace(tzinfo=UTC)
        store = RawStore(Path(args.data_dir) / "raw")
        result: dict[str, Any] = {
            "generated_at": now.isoformat(),
            "server": account.server,
            "terminal_trade_allowed": bool(terminal.trade_allowed),
            "profile": profile.name,
            "clock": profile.clock.token,
            "live_server_offset_hours": measured_offset_h,
            "profile_predicted_offset_hours": expected_offset_h,
            "timeframes": {},
        }
        frames: dict[Timeframe, pl.DataFrame] = {}
        for tf in Timeframe:
            bars = fetch_all(source, args.symbol, tf, since, now)
            frames[tf] = bars
            dataset = store.write(
                bars, symbol=args.symbol, timeframe=tf, source=f"mt5-{profile.name}", fetched_at=now
            )
            report = validate_bars(bars, tf, symbol=args.symbol, config=profile.validation)
            coverage = check_coverage(bars, since, now)
            issues = (*report.issues, *([coverage] if coverage else []))
            passed = report.passed and coverage is None
            result["timeframes"][tf.value] = {
                "rows": bars.height,
                "first": bars["timestamp"].min().isoformat(),
                "last": bars["timestamp"].max().isoformat(),
                "sha256": dataset.sha256[:16],
                "passed": passed,
                "issues": issue_summary(issues),
            }
            print(f"fetched {tf.value}: {bars.height} rows, {'PASSED' if passed else 'FAILED'}")
            for i in issues:
                print(f"    [{i.severity.value}] {i.code.value} count={i.count}")
    finally:
        mt5.shutdown()

    # Dataset of record: merge every raw fetch (newest wins) and validate THAT, because a single
    # fetch can be truncated by the terminal's bar limit while earlier fetches kept the history.
    catalog = DatasetCatalog(Path(args.data_dir) / "raw")
    record: dict[str, Any] = {}
    for tf in Timeframe:
        loaded = catalog.load(args.symbol, tf)
        frames[tf] = loaded.frame
        rep = validate_bars(loaded.frame, tf, symbol=args.symbol, config=profile.validation)
        cov = check_coverage(loaded.frame, since, now)
        merged_issues = (*rep.issues, *([cov] if cov else []))
        record[tf.value] = {
            "rows": loaded.frame.height,
            "dataset_id": loaded.dataset_id,
            "raw_files": len(loaded.datasets),
            "duplicates_resolved": loaded.duplicates_resolved,
            "passed": rep.passed and cov is None,
            "issues": issue_summary(merged_issues),
        }
        print(
            f"merged  {tf.value}: {loaded.frame.height} rows from {len(loaded.datasets)} fetches, "
            f"{'PASSED' if rep.passed and cov is None else 'FAILED'}"
        )
        for i in merged_issues:
            print(f"    [{i.severity.value}] {i.code.value} count={i.count}")
    result["dataset_of_record"] = record

    # Clock inference from weekly session boundaries (naive server labels).
    m5 = frames[Timeframe.M5]
    labelled = m5.with_columns(profile.clock.utc_to_server(pl.col("timestamp")).alias("timestamp"))
    candidates = [
        BrokerClock.parse(t)
        for t in (
            *(f"NY{h:+d}" for h in range(4, 10)),
            "Europe/Athens",
            "Europe/Helsinki",
            "Europe/Istanbul",
            "UTC",
        )
    ]
    scores = infer_broker_clock(labelled, candidates)  # judged on the raw server labels
    result["clock_inference"] = [
        {
            "clock": s.clock.token,
            "consistency": round(s.consistency, 4),
            "anchor_error_min": s.anchor_error_minutes,
            "weeks": s.weeks,
        }
        for s in scores[:8]
    ]

    # Resample M5 and compare against the broker's own higher-timeframe bars.
    comparisons: dict[str, Any] = {}
    for tf in (Timeframe.M15, Timeframe.H1, Timeframe.H4):
        derived = resample_bars(
            m5, Timeframe.M5, tf, clock=profile.clock, calendar=profile.validation.calendar
        )
        reference = frames[tf]
        lo, hi = derived.frame["timestamp"].min(), derived.frame["timestamp"].max()
        ref_window = reference.filter((pl.col("timestamp") >= lo) & (pl.col("timestamp") <= hi))
        report = cross_check(
            derived.frame,
            ref_window,
            price_tolerance=1e-9,
            columns=("open", "high", "low", "close", "tick_volume"),
        )
        spread_mismatch = {
            p: cross_check(
                resample_bars(
                    m5,
                    Timeframe.M5,
                    tf,
                    clock=profile.clock,
                    calendar=profile.validation.calendar,
                    spread_policy=p,
                ).frame,
                ref_window,
                columns=("spread",),
            ).mismatches.get("spread", 0)
            for p in SPREAD_POLICIES
        }
        comparisons[tf.value] = {
            "derived_rows": derived.frame.height,
            "reference_rows_in_window": ref_window.height,
            "matched": report.matched,
            "only_in_derived": report.only_in_derived,
            "only_in_reference": report.only_in_reference,
            "incomplete_buckets": len(derived.incomplete),
            "column_mismatches": report.mismatches,
            "spread_mismatches_by_policy": spread_mismatch,
        }
        print(
            f"{tf.value}: matched {report.matched}/{ref_window.height}, "
            f"mismatches {report.mismatches or 'none'}, only_ref {report.only_in_reference}, "
            f"incomplete {len(derived.incomplete)}, spread by policy {spread_mismatch}"
        )
    result["resample_vs_broker"] = comparisons

    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(
        f"live offset {result['live_server_offset_hours']}h vs profile {result['profile_predicted_offset_hours']}h"
    )
    print(
        "top clock candidates:",
        [
            (c["clock"], c["consistency"], c["anchor_error_min"])
            for c in result["clock_inference"][:4]
        ],
    )
    print(f"report written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
