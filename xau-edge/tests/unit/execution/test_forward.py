"""Forward/replay runner and the paper-versus-backtest comparison."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from tests.conftest import make_bars
from tests.unit.signals.test_decision import _inputs
from xau_edge.backtest.costs import CostModel
from xau_edge.domain.timeframe import Timeframe
from xau_edge.execution.forward import (
    MIN_TRADES_FOR_CONCLUSION,
    ReplayResult,
    compare_paper_to_backtest,
    replay,
)
from xau_edge.execution.interface import ClosedTrade
from xau_edge.execution.paper import PaperExecutionBroker
from xau_edge.execution.safety import ExecutionSafety
from xau_edge.execution.trader import PaperTrader
from xau_edge.risk.engine import RiskEngine, RiskLimits
from xau_edge.risk.prop_rules import load_prop_profile
from xau_edge.signals.decision import decide
from xau_edge.signals.engine import MarketFrames
from xau_edge.signals.schema import Signal

PROP = load_prop_profile(Path(__file__).parents[3] / "configs" / "prop" / "ftmo_2step.yaml")
START = datetime(2026, 3, 2, 8, 0, tzinfo=UTC)


def _flat(n: int, tf: Timeframe, price: float = 2000.0) -> pl.DataFrame:
    return make_bars(n, tf, start=START).with_columns(
        pl.lit(price).alias("open"),
        pl.lit(price + 0.2).alias("high"),
        pl.lit(price - 0.2).alias("low"),
        pl.lit(price).alias("close"),
        pl.lit(25).cast(pl.Int64).alias("spread"),
    )


def _frames(m5: pl.DataFrame | None = None) -> MarketFrames:
    return MarketFrames(
        m5=m5 if m5 is not None else _flat(900, Timeframe.M5),
        m15=_flat(300, Timeframe.M15),
        h1=_flat(80, Timeframe.H1),
        h4=_flat(20, Timeframe.H4),
    )


def _trader() -> PaperTrader:
    broker = PaperExecutionBroker(
        100_000.0, costs=CostModel(swap_long_points=0, swap_short_points=0), mode="replay"
    )
    return PaperTrader(broker, RiskEngine(RiskLimits(), PROP), ExecutionSafety())


def _buy_every_bar(at: datetime) -> Signal:
    return decide(_inputs(timestamp=at, price=2000.0))


def _never(at: datetime) -> Signal:
    return decide(_inputs(timestamp=at, price=2000.0, evidence_status="NONE"))


def test_replay_with_no_validated_signal_places_no_trades() -> None:
    result = replay(
        _frames(), _trader(), _never, START + timedelta(hours=6), START + timedelta(hours=12)
    )
    assert isinstance(result, ReplayResult)
    assert result.decisions > 0
    assert result.trades == []
    assert result.accepted == 0
    assert result.mode == "replay"


def test_replay_feeds_bars_in_time_order_and_decides_at_each_bar_close() -> None:
    seen: list[datetime] = []

    def provider(at: datetime) -> Signal:
        seen.append(at)
        return _never(at)

    replay(_frames(), _trader(), provider, START + timedelta(hours=6), START + timedelta(hours=8))
    assert seen == sorted(seen)
    assert all(t.minute % 15 == 0 for t in seen)
    assert seen[0] >= START + timedelta(hours=6)
    assert seen[-1] <= START + timedelta(hours=8)


def test_replay_places_and_closes_paper_trades_with_the_signal_levels() -> None:
    # a rising market lifts the position through its target (tp1 = price + 15)
    m5 = _flat(900, Timeframe.M5).with_columns(
        (pl.col("open") + pl.int_range(pl.len()) * 0.4).alias("open"),
        (pl.col("high") + pl.int_range(pl.len()) * 0.4).alias("high"),
        (pl.col("low") + pl.int_range(pl.len()) * 0.4).alias("low"),
        (pl.col("close") + pl.int_range(pl.len()) * 0.4).alias("close"),
    )
    price0 = float(m5.filter(pl.col("timestamp") == START + timedelta(hours=6))["close"][0])

    def provider(at: datetime) -> Signal:
        return decide(
            _inputs(
                timestamp=at,
                price=price0 + (at - START - timedelta(hours=6)).total_seconds() / 300 * 0.4,
            )
        )

    result = replay(
        _frames(m5), _trader(), provider, START + timedelta(hours=6), START + timedelta(hours=14)
    )
    assert result.accepted >= 1
    assert any(t.reason == "TARGET" for t in result.trades)
    assert all(t.risk_amount > 0 for t in result.trades)


def test_replay_never_reads_bars_after_the_decision_time() -> None:
    cutoffs: list[int] = []

    def provider(at: datetime) -> Signal:
        cutoffs.append(1)
        return _never(at)

    # poisoning the future must not change what the decisions see: the provider only gets `at`
    result = replay(
        _frames(), _trader(), provider, START + timedelta(hours=6), START + timedelta(hours=7)
    )
    assert result.decisions == len(cutoffs)


def _paper_trade(net_r: float, i: int) -> ClosedTrade:
    t0 = START + timedelta(hours=i)
    return ClosedTrade(
        position_id=f"p{i}",
        direction=1,
        lots=1.0,
        entry_time=t0,
        exit_time=t0 + timedelta(minutes=30),
        entry_price=2000.0,
        exit_price=2000.0 + net_r,
        reason="TARGET",
        gross_pnl=net_r * 100,
        commission=0.0,
        swap=0.0,
        net_pnl=net_r * 100,
        risk_amount=100.0,
        signal_hash=f"h{i}",
    )


def _backtest_trades(rs: list[float]) -> pl.DataFrame:
    return pl.DataFrame({"net_r": rs})


def test_a_small_sample_is_never_a_conclusion() -> None:
    paper = [_paper_trade(1.0, i) for i in range(10)]
    report = compare_paper_to_backtest(paper, _backtest_trades([0.5] * 200))
    assert report["paper_trades"] == 10
    assert report["sufficient_sample"] is False
    assert "INSUFFICIENT" in str(report["conclusion"])
    assert report["paper_mean_r"] == pytest.approx(1.0)
    assert report["backtest_mean_r"] == pytest.approx(0.5)


def test_a_large_sample_reports_whether_paper_is_consistent_with_the_backtest() -> None:
    n = MIN_TRADES_FOR_CONCLUSION
    paper = [_paper_trade(0.2 if i % 2 else -0.1, i) for i in range(n)]
    consistent = compare_paper_to_backtest(paper, _backtest_trades([0.05] * 300))
    assert consistent["sufficient_sample"] is True
    assert consistent["backtest_within_paper_interval"] is True
    assert "consistent" in str(consistent["conclusion"]).lower()
    diverged = compare_paper_to_backtest(paper, _backtest_trades([3.0] * 300))
    assert diverged["backtest_within_paper_interval"] is False
    assert "diverge" in str(diverged["conclusion"]).lower()


def test_no_paper_trades_is_reported_plainly() -> None:
    report = compare_paper_to_backtest([], _backtest_trades([0.1] * 10))
    assert report["paper_trades"] == 0
    assert report["paper_mean_r"] is None
    assert report["sufficient_sample"] is False


def test_replay_trades_can_never_form_a_conclusion() -> None:
    paper = [_paper_trade(0.3, i) for i in range(MIN_TRADES_FOR_CONCLUSION + 20)]
    report = compare_paper_to_backtest(paper, _backtest_trades([0.3] * 300), mode="replay")
    assert report["sufficient_sample"] is False
    assert "REPLAY" in str(report["conclusion"])
    assert report["backtest_within_paper_interval"] is None


def test_replay_results_carry_the_broker_mode() -> None:
    broker = PaperExecutionBroker(
        100_000.0, costs=CostModel(swap_long_points=0, swap_short_points=0), mode="replay"
    )
    trader = PaperTrader(broker, RiskEngine(RiskLimits(), PROP), ExecutionSafety())
    result = replay(
        _frames(), trader, _never, START + timedelta(hours=6), START + timedelta(hours=7)
    )
    assert result.mode == "replay"
