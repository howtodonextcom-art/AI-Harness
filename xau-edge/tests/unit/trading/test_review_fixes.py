"""Fixes from the independent review: previous-day range at the day boundary, the isolation guard,
display bias from raw labels, signal expiry and the chart marker bar."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from tests.unit.trading.helpers import m1_series, resample
from xau_edge.strategies.edge_program import SERVER_CLOCK
from xau_edge.trading.engine import _bias_of
from xau_edge.trading.market_state import previous_day_range

ROOT = Path(__file__).resolve().parents[3] / "src" / "xau_edge"


def _h1() -> pl.DataFrame:
    return resample(m1_series(60 * 24 * 6, seed=5, vol=0.6), 60)


def _server_day(ts: datetime) -> object:
    return SERVER_CLOCK.utc_to_server(
        pl.Series("t", [ts], dtype=pl.Datetime("us", "UTC"))
    ).dt.date()[0]


def test_previous_day_range_is_right_in_the_first_server_hour_of_a_day() -> None:
    h1 = _h1()
    stamps = h1["timestamp"].to_list()
    # a decision at server 00:30 (no H1 bar of the new day has closed yet)
    at = next(
        t + timedelta(minutes=30)
        for t in stamps[60:]
        if SERVER_CLOCK.utc_to_server(
            pl.Series("t", [t], dtype=pl.Datetime("us", "UTC"))
        ).dt.hour()[0]
        == 0
    )
    closed = h1.filter(pl.col("timestamp") + pl.duration(hours=1) <= at)
    pdh, pdl = previous_day_range(closed, SERVER_CLOCK, at)
    days = SERVER_CLOCK.utc_to_server(closed["timestamp"]).dt.date()
    today = _server_day(at)
    yesterday = max(d for d in set(days.to_list()) if d < today)
    expected = closed.filter(days == yesterday)
    assert pdh == expected["high"].max() and pdl == expected["low"].min()
    # one hour later the answer is the same day's range, not a different one
    later = at + timedelta(hours=1)
    closed_later = h1.filter(pl.col("timestamp") + pl.duration(hours=1) <= later)
    assert previous_day_range(closed_later, SERVER_CLOCK, later) == (pdh, pdl)


def test_the_isolation_guard_names_the_real_order_modules() -> None:
    guard = (
        ROOT.parent.parent / "tests" / "unit" / "trading" / "test_live_path_isolation.py"
    ).read_text(encoding="utf-8")
    for real in ("executor", "orders", "trade"):
        assert real in guard
    # nothing in the desk's code path imports the executor, and the real module exists
    assert (ROOT / "brokers" / "mt5_demo" / "executor.py").exists()
    for path in [*sorted((ROOT / "trading").glob("*.py")), ROOT / "api" / "trade.py"]:
        text = path.read_text(encoding="utf-8")
        assert not re.search(
            r"^\s*(from|import)\s+xau_edge\.brokers\.mt5_demo\.executor", text, re.M
        )
        assert "order_send" not in text.replace("order_send/", "").replace('"order_send"', "")


def test_the_bias_arrow_comes_from_raw_labels_not_display_strings() -> None:
    assert [_bias_of(x) for x in ("BULLISH", "UP", "REVERSAL_UP", "TREND_UP", "ACTIVE_UP")] == [
        1
    ] * 5
    assert [_bias_of(x) for x in ("BEARISH", "DOWN", "REVERSAL_DOWN", "TREND_DOWN")] == [-1] * 4
    assert [_bias_of(x) for x in ("RANGE", "NEUTRAL", "FLAT", "UNKNOWN", "QUIET")] == [0] * 5
    assert _bias_of("ARMED (UP / PULLBACK)") == 0  # a display string is never a bias source


def test_a_utc_datetime_has_a_stable_server_day() -> None:
    assert _server_day(datetime(2026, 3, 3, 12, tzinfo=UTC)) is not None


# -- signal validity, golden streams ---------------------------------------------------------------


def test_a_signal_is_never_shown_valid_longer_than_the_next_m5_close() -> None:
    from tests.unit.trading.helpers import SPEC, aligned_state  # noqa: PLC0415
    from xau_edge.trading.baseline import BaselineConfig, DecisionContext, decide  # noqa: PLC0415
    from xau_edge.trading.engine import cap_validity  # noqa: PLC0415
    from xau_edge.trading.setup_machine import SetupLifecycle, SetupPhase  # noqa: PLC0415

    state = aligned_state()
    lc = SetupLifecycle(SetupPhase.TRIGGERED, 1, state.timestamp, state.timestamp, 1, True, "t")
    buy = decide(
        state,
        DecisionContext(spec=SPEC, equity=100_000.0, lifecycle=lc),
        BaselineConfig(version="1.2.1"),
    )
    assert buy.signal_expiry is not None
    assert buy.signal_expiry == buy.timestamp + timedelta(minutes=15)  # the baseline's own expiry
    last_close = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)
    capped = cap_validity(buy, last_close)
    assert capped.signal_expiry == last_close + timedelta(minutes=5)
    wait = decide(aligned_state(h1_trend="NEUTRAL"), DecisionContext(spec=SPEC), BaselineConfig())
    assert cap_validity(wait, last_close) == wait  # a WAIT has nothing to cap


def test_the_telemetry_marker_bar_is_the_trigger_bar_not_the_decision_time(tmp_path: Path) -> None:
    from tests.unit.trading.helpers import SPEC, aligned_state  # noqa: PLC0415
    from xau_edge.trading.baseline import BaselineConfig, DecisionContext, decide  # noqa: PLC0415
    from xau_edge.trading.telemetry import DecisionTelemetry  # noqa: PLC0415

    buy = decide(aligned_state(), DecisionContext(spec=SPEC, equity=100_000.0), BaselineConfig())
    trigger_bar = datetime(2026, 3, 2, 9, 55, tzinfo=UTC)
    now = datetime(2026, 3, 2, 10, 3, tzinfo=UTC)
    DecisionTelemetry(tmp_path).append_signal(buy, at=now, bar_time=trigger_bar)
    assert DecisionTelemetry(tmp_path).read_signals(now)[0]["bar_time"] == trigger_bar.isoformat()
    # the same setup is not logged again the next UTC day (a setup can span midnight)
    DecisionTelemetry(tmp_path).append_signal(buy, at=now + timedelta(days=1), bar_time=trigger_bar)
    assert DecisionTelemetry(tmp_path).read_signals(now + timedelta(days=1)) == []
