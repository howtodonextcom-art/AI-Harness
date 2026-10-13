"""Server-authoritative data ages and the system health rows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from xau_edge.trading.data_health import data_ages, decision_age, system_health

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)


def ages(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "live": True,
        "market_open": True,
        "quote_age": 2.0,
        "bar_age": 30.0,
        "bars_stale": False,
        "collector_age": 5.0,
        "decision_age": 20.0,
    }
    return data_ages(**{**base, **over})


def test_an_open_market_with_everything_current_is_fresh() -> None:
    out = ages()
    assert {
        k: out[k]["state"] for k in ("quote", "last_bar", "collector_heartbeat", "last_decision")
    } == {
        "quote": "FRESH",
        "last_bar": "FRESH",
        "collector_heartbeat": "FRESH",
        "last_decision": "FRESH",
    }


def test_a_closed_market_is_not_stale_but_a_dead_collector_still_is() -> None:
    out = ages(market_open=False, quote_age=73_000.0, bar_age=73_000.0, decision_age=73_000.0)
    assert out["quote"]["state"] == "MARKET_CLOSED"
    assert out["last_bar"]["state"] == "MARKET_CLOSED"
    assert out["last_decision"]["state"] == "MARKET_CLOSED"
    assert (
        out["quote"]["age_seconds"] == 73_000.0
    )  # the age is still shown, only its meaning differs
    assert out["collector_heartbeat"]["state"] == "FRESH"
    dead = ages(market_open=False, collector_age=900.0)
    assert dead["collector_heartbeat"]["state"] == "STALE"  # it is what wakes up with the market


def test_an_open_market_marks_each_age_stale_on_its_own() -> None:
    assert ages(quote_age=45.0)["quote"]["state"] == "STALE"
    assert ages(bars_stale=True)["last_bar"]["state"] == "STALE"
    assert ages(collector_age=61.0)["collector_heartbeat"]["state"] == "STALE"
    assert ages(decision_age=200.0)["last_decision"]["state"] == "STALE"
    one_bad = ages(quote_age=45.0)
    assert (
        one_bad["last_bar"]["state"] == "FRESH"
    )  # four separate concepts, never one blurred "stale"


def test_a_missing_age_is_unavailable_and_a_replay_is_never_live_data() -> None:
    out = ages(quote_age=None, bar_age=None, collector_age=None, decision_age=None)
    assert {
        out[k]["state"] for k in ("quote", "last_bar", "collector_heartbeat", "last_decision")
    } == {"UNAVAILABLE"}
    replay = ages(live=False)
    assert replay["live"] is False
    assert {
        replay[k]["state"] for k in ("quote", "last_bar", "collector_heartbeat", "last_decision")
    } == {"REPLAY"}


def test_decision_age_is_seconds_since_the_last_decision() -> None:
    assert decision_age(NOW, NOW - timedelta(seconds=42)) == 42.0
    assert decision_age(NOW, None) is None
    assert decision_age(NOW, NOW + timedelta(seconds=5)) == 0.0


COLLECTOR: dict[str, Any] = {
    "connected": True,
    "server": "FTMO-Demo",
    "health": "GOOD",
    "reasons": ["all checks passed"],
    "tick_store": {
        "enabled": True,
        "lag_seconds": 3.0,
        "covered_until": "2026-10-12T11:59:57+00:00",
    },
    "disk": {
        "level": "GOOD",
        "free_gb": 82.4,
        "drives": [
            {"drive": "C:", "free_gb": 14.8, "level": "WARN"},
            {"drive": "D:", "free_gb": 100, "level": "GOOD"},
        ],
    },
}


def health(**over: Any) -> dict[str, dict[str, str]]:
    base: dict[str, Any] = {
        "collector": COLLECTOR,
        "collector_age": 4.0,
        "live": True,
        "writer_error": None,
        "coverage": {
            "complete": True,
            "coverage_pct": 99.0,
            "recorded_m1_decisions": 99,
            "expected_m1_decisions": 100,
        },
        "news": {"state": "CLEAR", "detail": "ok"},
        "strategy_version": "1.1.0",
        "source_mode": "LIVE",
    }
    return {r["id"]: r for r in system_health(**{**base, **over})}


def test_every_component_has_a_row_and_a_drive_warning_is_visible() -> None:
    rows = health()
    assert set(rows) == {
        "mt5",
        "collector",
        "bar_parity",
        "tick_storage",
        "disk",
        "api",
        "decision_coverage",
        "news",
        "writer_lock",
        "strategy",
        "source_mode",
    }
    assert rows["mt5"]["state"] == "OK"
    assert rows["collector"]["state"] == "OK"
    assert (
        rows["disk"]["state"] == "WARN" and "C: còn 14.8 GB" in rows["disk"]["detail"]
    )  # a drive that does not hold the data
    assert rows["strategy"]["detail"] == "v1.1.0"
    assert rows["source_mode"]["state"] == "OK"


def test_each_problem_shows_on_its_own_row() -> None:
    rows = health(
        collector={
            **COLLECTOR,
            "connected": False,
            "reasons": ["3 stored bar(s) differ from the terminal"],
            "health": "DEGRADED",
        },
        collector_age=300.0,
        writer_error="another process owns the desk",
        coverage={
            "complete": False,
            "coverage_pct": 48.6,
            "recorded_m1_decisions": 232,
            "expected_m1_decisions": 477,
        },
        news={"state": "STALE", "detail": "the calendar coverage has ended"},
        source_mode="ACCEPTANCE_REPLAY",
    )
    assert rows["mt5"]["state"] == "ERROR"
    assert rows["collector"]["state"] == "ERROR" and "300 s" in rows["collector"]["detail"]
    assert rows["bar_parity"]["state"] == "WARN"
    assert rows["writer_lock"]["state"] == "ERROR"
    assert (
        rows["decision_coverage"]["state"] == "WARN"
        and "48.6%" in rows["decision_coverage"]["detail"]
    )
    assert rows["news"]["state"] == "WARN"
    assert (
        rows["source_mode"]["state"] == "WARN"
        and "KHÔNG PHẢI LIVE" in rows["source_mode"]["detail"]
    )


def test_a_blocked_news_window_is_not_a_fault_but_an_error_calendar_is() -> None:
    assert health(news={"state": "BLOCKED", "detail": "x"})["news"]["state"] == "OK"
    assert health(news={"state": "ERROR", "detail": "x"})["news"]["state"] == "ERROR"
    assert health(news={"state": "NOT_CONFIGURED", "detail": "x"})["news"]["state"] == "WARN"


def test_without_a_live_collector_the_collector_rows_are_unknown_not_ok() -> None:
    for rows in (health(collector=None, collector_age=None), health(live=False, collector=None)):
        assert {
            rows[i]["state"] for i in ("mt5", "collector", "bar_parity", "tick_storage", "disk")
        } == {"UNKNOWN"}
