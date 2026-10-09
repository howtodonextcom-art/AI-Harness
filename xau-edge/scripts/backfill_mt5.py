"""Backfill ALL history the FTMO terminal can serve into the local bar ledger (v2, resumable).

    uv run --extra mt5 python scripts/backfill_mt5.py [--timeframes M1 H4 ...] [--since 2003-01-01]
                                                      [--write-report]

Per timeframe: newest bars first, then chunked BACKWARD retrieval until nothing older is returned
(bounded loops, repeated-boundary detection, validation and a SHA-256 per chunk in the event log).
Safe to interrupt and to rerun: stored bars are never overwritten and a rerun only adds what is
missing. Each timeframe ends in one explicit state (COMPLETE_AVAILABLE_HISTORY, TERMINAL_LIMITED,
BROKER_LIMITED, INCOMPLETE, UNKNOWN); TERMINAL_LIMITED prints the single owner action.
``--write-report`` writes docs/reports/mt5-backfill-final.json and .md.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.domain.timeframe import Timeframe  # noqa: E402
from xau_edge.market_data.history_backfill import (  # noqa: E402
    TERMINAL_LIMITED,
    backfill_timeframe,
    coverage_gaps,
)
from xau_edge.market_data.ledger import BarLedger  # noqa: E402
from xau_edge.market_data.mt5.runtime import DEFAULT_TERMINAL, open_feed  # noqa: E402

DEFAULT_ROOT = ROOT / "data" / "market"
REPORTS = ROOT / "docs" / "reports"
OWNER_ACTION = (
    "close FTMO MT5 completely, run `uv run python scripts/mt5_set_max_bars.py --value 10000000 "
    "--apply`, reopen FTMO MT5 and wait for login/synchronisation, then rerun "
    "`uv run --extra mt5 python scripts/backfill_mt5.py --write-report`"
)


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Báo cáo backfill lịch sử MT5 (cuối cùng)",
        "",
        f"Sinh bởi `scripts/backfill_mt5.py` lúc {report['finished_at']}. Máy chủ: {report['server']},"
        f" symbol broker: {report['broker_symbol']}, `Max bars in chart` của terminal:"
        f" {report['terminal_max_bars']}.",
        "",
        "| Khung | Yêu cầu từ | Broker trả về sớm nhất | Local sớm nhất | Local mới nhất | Số nến | Trạng thái | Đủ? |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, row in report["timeframes"].items():
        lines.append(
            f"| {name} | {row['requested_oldest'][:10]} | {row['broker_returned_oldest']} |"
            f" {row['local_oldest']} | {row['local_latest']} | {row['rows']} | {row['state']} |"
            f" {'có' if row['complete'] else 'chưa'} |"
        )
    lines += ["", "## Lý do và khoảng trống lớn nhất", ""]
    for name, row in report["timeframes"].items():
        lines.append(f"* **{name}** — {row['reason']}")
        for gap in report["gaps"].get(name, []):
            lines.append(f"  * khoảng trống {gap['hours']} giờ: {gap['after']} → {gap['before']}")
    lines += [
        "",
        "Trạng thái: `COMPLETE_AVAILABLE_HISTORY` (đủ), `BROKER_LIMITED` (broker không có sớm hơn;"
        " đủ theo định nghĩa), `TERMINAL_LIMITED` (terminal chặn: cần hành động của chủ dự án),"
        " `INCOMPLETE` (chạy lại), `UNKNOWN`.",
        "Khoảng trống lớn là nến broker không có trong khung đó (cuối tuần/ngày lễ/giờ nghỉ là bình"
        " thường; xem `docs/MT5_DATA_PLATFORM.md`). Không có nến nào bị bịa từ khung khác.",
    ]
    if report["owner_action_required"]:
        lines += ["", f"**OWNER_ACTION_REQUIRED:** {report['owner_action_required']}"]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal-path", default=DEFAULT_TERMINAL)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--timeframes", nargs="+", default=[t.value for t in Timeframe])
    parser.add_argument("--since", default="2003-01-01", help="oldest date wanted (YYYY-MM-DD)")
    parser.add_argument("--max-chunks", type=int, default=400)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    wanted = datetime.fromisoformat(args.since).replace(tzinfo=UTC)
    ledger = BarLedger(args.root)
    outcomes: dict[str, Any] = {}
    gaps: dict[str, Any] = {}
    with open_feed(args.terminal_path) as feed:
        facts = feed.facts()
        mapping = feed.discover_symbol(args.symbol)
        feed.select(mapping.broker_symbol)
        for name in args.timeframes:
            tf = Timeframe(name)
            outcome = backfill_timeframe(
                feed,
                ledger,
                symbol=mapping.canonical_symbol,
                broker_symbol=mapping.broker_symbol,
                timeframe=tf,
                requested_oldest=wanted,
                max_bars=facts.max_bars,
                max_chunks=args.max_chunks,
            )
            outcomes[name] = outcome.as_dict()
            gaps[name] = coverage_gaps(ledger.load(mapping.canonical_symbol, tf), tf)
            print(name, outcome.state, outcome.local_oldest, outcome.rows, "-", outcome.reason)
    limited = any(o["state"] == TERMINAL_LIMITED for o in outcomes.values())
    report = {
        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "server": facts.server,
        "broker_symbol": mapping.broker_symbol,
        "terminal_max_bars": facts.max_bars,
        "since_wanted": wanted.isoformat(),
        "timeframes": outcomes,
        "gaps": gaps,
        "owner_action_required": OWNER_ACTION if limited else None,
    }
    ledger.log_event(
        mapping.canonical_symbol,
        "BACKFILL",
        {"summary": {k: v["state"] for k, v in outcomes.items()}},
    )
    if args.write_report:
        (REPORTS / "mt5-backfill-final.json").write_text(
            json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8"
        )
        (REPORTS / "mt5-backfill-final.md").write_text(markdown(report), encoding="utf-8")
    if limited:
        print("OWNER_ACTION_REQUIRED:", OWNER_ACTION)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
