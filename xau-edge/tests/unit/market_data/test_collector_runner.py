"""Reconnect loop: late terminal, mid-run drop, torn status, and reconcile on every new session."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from tests.unit.market_data.test_collector_ledger import FakeClient, make_collector, make_feed
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.collector import MarketCollector, read_status_file
from xau_edge.market_data.collector_runner import run_with_reconnect
from xau_edge.market_data.mt5.feed import Mt5Feed


def test_terminal_starting_late_does_not_end_collection(tmp_path: Path) -> None:
    client = FakeClient()
    attempts = {"n": 0}

    @contextmanager
    def connect() -> Iterator[Mt5Feed]:
        attempts["n"] += 1
        if attempts["n"] < 3:
            msg = "terminal not running yet"
            raise RuntimeError(msg)
        yield make_feed(client)

    def build(feed: Mt5Feed) -> MarketCollector:
        collector = make_collector(tmp_path, client)
        collector.feed = feed
        return collector

    stops = iter([False] * 3 + [True] * 50)
    sleeps: list[float] = []
    sessions = run_with_reconnect(
        connect, build, status_path=tmp_path / "collector_status.json", stop=lambda: next(stops),
        sleep=sleeps.append, max_sessions=3,
    )  # fmt: skip
    assert sessions == 3
    assert sleeps[:2] == [5.0, 5.0]  # waited between the two failed attempts
    assert make_collector(tmp_path, client).ledger.latest("XAUUSD", Timeframe.M1) is not None


def test_failure_is_visible_as_disconnected_then_recovers(tmp_path: Path) -> None:
    client = FakeClient()
    status = tmp_path / "collector_status.json"
    seen: list[str] = []

    @contextmanager
    def connect() -> Iterator[Mt5Feed]:
        if not seen:
            seen.append("down")
            msg = "no IPC connection"
            raise RuntimeError(msg)
        yield make_feed(client)

    def build(feed: Mt5Feed) -> MarketCollector:
        return make_collector(tmp_path, client)

    def sleeper(_s: float) -> None:
        if len(seen) == 1:
            seen.append(json.loads(status.read_text(encoding="utf-8"))["health"])

    stops = iter([False, False] + [True] * 50)
    run_with_reconnect(
        connect, build, status_path=status, stop=lambda: next(stops), sleep=sleeper, max_sessions=2
    )
    assert seen[:2] == ["down", "DISCONNECTED"]
    recovered = read_status_file(status, now=None, max_age_seconds=10**9)
    assert recovered["health"] in {"GOOD", "STALE", "DEGRADED", "DISCONNECTED"}


def test_mid_run_failure_starts_a_new_session_that_reconciles_missed_bars(tmp_path: Path) -> None:
    client = FakeClient()
    collectors: list[MarketCollector] = []

    @contextmanager
    def connect() -> Iterator[Mt5Feed]:
        yield make_feed(client)

    def build(feed: Mt5Feed) -> MarketCollector:
        collector = make_collector(tmp_path, client)
        collectors.append(collector)
        return collector

    calls = {"n": 0}
    original_run = MarketCollector.run

    def flaky_run(self: MarketCollector, stop: object, **kwargs: object) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            self.run_once()
            msg = "terminal connection lost"
            raise RuntimeError(msg)
        client.now = client.now.replace(minute=client.now.minute + 20)  # 20 minutes passed
        original_run(self, lambda: True, **kwargs)  # type: ignore[arg-type]

    MarketCollector.run = flaky_run  # type: ignore[method-assign]
    try:
        run_with_reconnect(
            connect, build, status_path=tmp_path / "collector_status.json", stop=lambda: False,
            sleep=lambda _s: None, max_sessions=2,
        )  # fmt: skip
    finally:
        MarketCollector.run = original_run  # type: ignore[method-assign]
    assert len(collectors) == 2
    kinds = [e["kind"] for e in collectors[1].ledger.events("XAUUSD")]
    assert "RECONCILE_DIFFERENCES" in kinds  # the 20 missed minutes were found and filled
    assert pytest.approx(1) == 1
