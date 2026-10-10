"""The economic calendar reaches the trade engine: ``/trade`` is no longer UNKNOWN once set."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tests.unit.market_data.test_collector_ledger import NOW, FakeClient, make_collector
from xau_edge.api.trade import build_trade_engine
from xau_edge.market_data.validators.market_calendar import MarketCalendar
from xau_edge.ops.notifier import NullNotifier
from xau_edge.trading.engine import TradeEngine
from xau_edge.trading.live_source import LiveTradingMarketSource

SERVE_API = Path(__file__).resolve().parents[3] / "scripts" / "serve_api.py"


def _z(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _calendar(path: Path, start: datetime, end: datetime, rows: list[str]) -> Path:
    body = [f"# coverage: {_z(start)}..{_z(end)}", "time_utc,category,impact,available_at", *rows]
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    return path


def _engine(tmp_path: Path, calendar: Path | None) -> TradeEngine:
    client = FakeClient()
    make_collector(tmp_path / "market", client).run_once()
    engine = build_trade_engine(
        tmp_path / "market",
        tmp_path / "trade",
        code_version="t",
        source=LiveTradingMarketSource(tmp_path / "market", MarketCalendar()),
        clock=lambda: client.now,
        notifier=NullNotifier(),
        news_calendar_path=calendar,
    )
    engine.step()
    return engine


def _codes(view: dict[str, object]) -> set[str]:
    return {c["code"] for c in view["conditions"]}  # type: ignore[attr-defined]


def test_a_high_impact_event_inside_the_window_blocks_the_decision(tmp_path: Path) -> None:
    event = NOW + timedelta(minutes=10)
    known = NOW - timedelta(days=3)
    cal = _calendar(
        tmp_path / "cal.csv",
        NOW - timedelta(days=7),
        NOW + timedelta(days=7),
        [f"{_z(event)},NFP,high,{_z(known)}"],
    )
    view = _engine(tmp_path, cal).view()
    assert view["news"]["state"] == "BLOCKED"
    assert view["news"]["warning"] is False
    assert "NEWS_UNKNOWN" not in _codes(view)
    assert view["decision"]["decision"] == "WAIT"
    assert "NEWS_WINDOW" in view["decision"]["refusal_reasons"]


def test_a_covering_calendar_without_events_is_clear(tmp_path: Path) -> None:
    cal = _calendar(tmp_path / "cal.csv", NOW - timedelta(days=7), NOW + timedelta(days=7), [])
    view = _engine(tmp_path, cal).view()
    assert view["news"]["state"] == "CLEAR"
    assert "NEWS_UNKNOWN" not in _codes(view)


def test_a_calendar_that_no_longer_covers_now_stays_unknown_and_says_why(tmp_path: Path) -> None:
    cal = _calendar(tmp_path / "cal.csv", NOW - timedelta(days=14), NOW - timedelta(days=1), [])
    view = _engine(tmp_path, cal).view()
    assert view["news"]["state"] == "UNKNOWN"
    unknown = next(c for c in view["conditions"] if c["code"] == "NEWS_UNKNOWN")
    assert "coverage" in unknown["message"]
    assert "coverage" in view["news"]["text"]


def test_a_row_published_after_now_is_look_ahead_and_never_trusted(tmp_path: Path) -> None:
    event = NOW + timedelta(minutes=10)
    cal = _calendar(
        tmp_path / "cal.csv",
        NOW - timedelta(days=7),
        NOW + timedelta(days=7),
        [f"{_z(event)},CPI,high,{_z(NOW + timedelta(hours=1))}"],
    )
    assert _engine(tmp_path, cal).view()["news"]["state"] == "UNKNOWN"


def test_without_a_calendar_the_engine_behaves_as_before(tmp_path: Path) -> None:
    engine = _engine(tmp_path, None)
    view = engine.view()
    assert engine.config.news_calendar_path is None
    assert view["news"]["state"] == "UNKNOWN"
    assert view["news"]["text"] == "NEWS NOT VERIFIED: no economic calendar"


def test_serve_api_passes_the_configured_calendar_to_the_trade_engine() -> None:
    tree = ast.parse(SERVE_API.read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "build_trade_engine"
    ]
    assert len(calls) == 1
    keyword = next((k for k in calls[0].keywords if k.arg == "news_calendar_path"), None)
    assert keyword is not None
    assert ast.unparse(keyword.value) == "settings.news_calendar_path"
