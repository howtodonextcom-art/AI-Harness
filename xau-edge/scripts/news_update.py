"""Daily news-calendar update job (run from Task Scheduler / cron once a day).

    uv run python scripts/news_update.py --source D:/feeds/calendar.csv
    uv run python scripts/news_update.py --source https://your-trusted-host/calendar.csv --notify

``--source`` may also come from XAU_EDGE_NEWS_SOURCE. The output defaults to
XAU_EDGE_NEWS_CALENDAR_PATH (or data/news/calendar.csv). The file is replaced atomically and only
after the source parsed cleanly; on any problem the old file stays and the exit code is non-zero.
The default source is the Forex Factory weekly feed (``--source forexfactory``); see
docs/reports/NEWS_SOURCE_DECISION.md and docs/operations/news-calendar.md.

Exit codes: 0 ok and coverage sufficient; 1 update refused/failed; 2 updated but coverage is short.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from xau_edge.config import Settings
from xau_edge.execution.status import Alert
from xau_edge.news.providers import CalendarProviderError, provider_from_source
from xau_edge.news.status import read_update_status
from xau_edge.news.update import (
    MIN_COVERAGE_DAYS,
    CalendarUpdateError,
    calendar_file_alert,
    record_update,
    update_calendar,
)
from xau_edge.ops.notifier import AlertEvent, build_dispatcher


def _notify(alert: Alert, now: datetime) -> None:
    dispatcher = build_dispatcher()
    result = dispatcher.dispatch(AlertEvent.from_alert(alert, at=now))
    print(f"notify: {result.reason}")


def _attempted_recently(out: Path, now: datetime, args: argparse.Namespace) -> bool:
    status = read_update_status(out)
    try:
        last = datetime.fromisoformat(str(status["last_attempt_at"])) if status else None
    except (KeyError, ValueError):
        return False
    return last is not None and now - last < timedelta(minutes=args.min_interval_minutes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default=os.environ.get("XAU_EDGE_NEWS_SOURCE") or "forexfactory",
        help="forexfactory | a local CSV path | an https CSV URL",
    )
    parser.add_argument("--out", default=None)
    parser.add_argument("--min-days", type=float, default=MIN_COVERAGE_DAYS)
    parser.add_argument(
        "--notify", action="store_true", help="push the alert via Telegram/fallback"
    )
    parser.add_argument(
        "--min-interval-minutes",
        type=float,
        default=30.0,
        help="skip the fetch when the last attempt (ok or failed) is newer; the feed rate-limits",
    )
    parser.add_argument("--force", action="store_true", help="ignore --min-interval-minutes")
    parser.add_argument("--check-only", action="store_true", help="only check the coverage left")
    args = parser.parse_args()

    settings = Settings()
    out = (
        Path(args.out)
        if args.out
        else settings.news_calendar_path or Path("data/news/calendar.csv")
    )
    now = datetime.now(UTC)

    if not args.check_only and not args.force and _attempted_recently(out, now, args):
        print(f"skip: the last attempt is newer than {args.min_interval_minutes:g} minutes")
        args.check_only = True
    if not args.check_only:
        if not args.source:
            print("ERROR: no --source and XAU_EDGE_NEWS_SOURCE is not set", file=sys.stderr)
            return 1
        try:
            result = update_calendar(provider_from_source(args.source), out, now=now)
        except (CalendarUpdateError, CalendarProviderError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            record_update(out, now=now, ok=False, source=args.source, error=str(exc))
            if args.notify:
                _notify(
                    Alert("NEWS_UPDATE_FAILED", "warning", f"calendar update failed: {exc}"), now
                )
            return 1
        record_update(out, now=now, ok=True, source=args.source, result=result)
        print(
            f"OK {result.path}: {result.events} events (+{result.added}), coverage "
            f"{result.coverage[0]:%Y-%m-%d}..{result.coverage[1]:%Y-%m-%d}, "
            f"{'written' if result.changed else 'unchanged'}"
        )

    alert = calendar_file_alert(out, now, min_days=args.min_days)
    if alert is None:
        print("coverage: sufficient")
        return 0
    print(f"{alert.severity.upper()} {alert.code}: {alert.message}")
    if args.notify:
        _notify(alert, now)
    return 2


if __name__ == "__main__":
    sys.exit(main())
