"""Forward evidence summaries: descriptive only, with the protocol's minimums enforced."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from xau_edge_v2.paper import forward as fw

US = 1_000_000
BAR = 300 * US
T0 = int(datetime(2026, 10, 13, 8, 0, tzinfo=UTC).timestamp()) * US


def row(
    i: int,
    action: str = "WAIT",
    level: int = 1,
    refusals: tuple[str, ...] = ("NO_SETUP",),
    **kw: Any,
) -> dict[str, Any]:
    return {
        "bar_open_us": T0 + i * BAR, "logged_at": "x", "action": action, "readiness_level": level,
        "bias": "NEUTRAL", "refusals": json.dumps(list(refusals)), "price": 2000.0 + i,
        "spread_points": 30.0, "atr_m15": 2.0, "market_status": "OPEN", "data_quality": "OK",
        "decision_id": f"d{i}", "strategy_version": "1.1.0", "setup_id": None, **kw,
    }  # fmt: skip


def position(
    i: int, net: float, risk: float = 25.0, version_decision: str | None = None
) -> dict[str, Any]:
    return {
        "status": "CLOSED", "decision_id": version_decision or f"d{i}", "pnl_usd": net, "swap_usd": 0.0,
        "risk_amount": risk,
    }  # fmt: skip


def bars(n: int) -> list[int]:
    return [T0 + i * BAR for i in range(n)]


def test_wilson_interval() -> None:
    assert fw.wilson(0, 0) is None
    lo, hi = fw.wilson(8, 10) or (0, 0)
    assert 0.49 < lo < 0.50 and 0.93 < hi < 0.95
    lo, hi = fw.wilson(50, 100) or (0, 0)
    assert 0.40 < lo < 0.41 and 0.59 < hi < 0.60
    lo0, hi0 = fw.wilson(0, 5) or (1, 0)
    assert lo0 == 0.0 and hi0 > 0.4  # five losses do not prove a zero win rate


def test_gaps_merge_consecutive_missing_bars_into_runs() -> None:
    expected = bars(10)
    logged = {expected[i] for i in (0, 1, 4, 5, 9)}
    found = fw.gaps(expected, logged, BAR)
    assert [(g.bars, g.start.timestamp() * US, g.end.timestamp() * US) for g in found] == [
        (2, expected[2], expected[3] + BAR),
        (3, expected[6], expected[8] + BAR),
    ]
    assert fw.gaps(expected, set(expected), BAR) == []


def test_funnel_counts_actions_levels_refusals_and_distinct_setups() -> None:
    rows = [
        row(0, level=0, refusals=("NO_DIRECTION",)),
        row(1, level=1, refusals=("TIMEFRAME_CONFLICT", "SPREAD_TOO_WIDE")),
        row(2, level=4, refusals=("SPREAD_TOO_WIDE",)),
        row(3, "BUY", 6, (), setup_id="s1"),
        row(4, "BUY", 6, (), setup_id="s1"),  # the same setup seen on a second bar
        row(5, "SELL", 6, (), setup_id="s2"),
    ]
    f = fw.funnel(rows)
    assert f.by_action == {"WAIT": 3, "BUY": 2, "SELL": 1}
    assert (
        f.by_readiness["NEUTRAL"] == 1
        and f.by_readiness["TRIGGER"] == 1
        and f.by_readiness["READY"] == 3
    )
    assert f.first_refusal == {"SPREAD_TOO_WIDE": 1, "NO_DIRECTION": 1, "TIMEFRAME_CONFLICT": 1}
    assert f.signals == 3 and f.distinct_setups == 2


def test_no_observations_is_said_plainly() -> None:
    s = fw.summarize([], [], [], paper_return_pct=None, hold_prices=None)
    assert (
        s.evidence == "NO_OBSERVATIONS" and s.funnel is None and s.progress.claim_allowed is False
    )
    assert s.progress.coverage is None and "chưa có quan sát" in s.progress.reason


def test_a_summary_describes_and_never_claims_before_every_minimum_is_met() -> None:
    rows = [row(i) for i in range(50)]
    s = fw.summarize(rows, [], bars(50), paper_return_pct=0.0, hold_prices=(2000.0, 2049.0))
    assert s.evidence == "FORWARD_ACCUMULATING" and s.logged_bars == 50 and s.expected_bars == 50
    assert s.progress.coverage == 1.0 and s.progress.claim_allowed is False
    assert "0/100 lệnh đã đóng" in s.progress.reason and "ngày quan sát" in s.progress.reason
    assert "giả thuyết forward" in s.progress.reason  # no owner-approved hypothesis
    assert s.buy_and_hold_pct == pytest.approx(2.45) and s.paper_return_pct == 0.0
    assert "MÔ TẢ" in s.notes[0] and "UNVALIDATED" in s.notes[0]


def test_coverage_exposes_downtime_instead_of_hiding_it() -> None:
    rows = [row(i) for i in (0, 1, 2, 7, 8, 9)]  # the engine was down for bars 3..6
    s = fw.summarize(rows, [], bars(10), paper_return_pct=0.0, hold_prices=None)
    assert s.logged_bars == 6 and s.expected_bars == 10
    assert (
        s.progress.coverage == pytest.approx(0.6) and "độ phủ quan sát 60.0%" in s.progress.reason
    )
    assert [g.bars for g in s.gaps] == [4]
    assert s.buy_and_hold_pct is None


def test_trades_are_grouped_by_strategy_version_and_small_samples_are_flagged() -> None:
    rows = [
        row(0, strategy_version="1.1.0"),
        row(1, strategy_version="1.1.0"),
        row(2, strategy_version="1.2.0"),
    ]
    positions = [position(0, 50.0), position(1, -25.0), position(2, -10.0)]
    s = fw.summarize(rows, positions, bars(3), paper_return_pct=0.1, hold_prices=None)
    by = {t.strategy_version: t for t in s.trades}
    assert by["1.1.0"].closed == 2 and by["1.1.0"].wins == 1 and by["1.1.0"].losses == 1
    assert by["1.1.0"].total_r == pytest.approx(2.0 - 1.0) and by["1.1.0"].mean_r == pytest.approx(
        0.5
    )
    lo, hi = by["1.1.0"].win_rate_ci95 or (0, 1)
    assert lo < 0.2 and hi > 0.8  # n = 2: the interval is huge, and the summary says so
    assert by["1.2.0"].closed == 1
    assert "chiến lược đổi giữa chừng" in s.progress.reason
    assert any("Mẫu lệnh quá nhỏ" in n for n in s.notes)


def test_a_claim_needs_every_minimum_and_an_owner_approved_hypothesis() -> None:
    days = 61
    n = int(days * 24 * 12)  # one closed M5 bar every 5 minutes, all logged
    rows = [row(i) for i in range(n)]
    trades = [position(i % n, 10.0) for i in range(100)]
    ok = fw.summarize(
        rows, trades, bars(n), paper_return_pct=1.0, hold_prices=(1.0, 2.0), owner_hypothesis=True
    )
    assert ok.progress.closed_trades == 100 and ok.progress.observed_days >= 60
    assert ok.progress.claim_allowed is True and "đủ mọi mức tối thiểu" in ok.progress.reason
    no_hyp = fw.summarize(rows, trades, bars(n), paper_return_pct=1.0, hold_prices=(1.0, 2.0))
    assert no_hyp.progress.claim_allowed is False and "giả thuyết forward" in no_hyp.progress.reason
    few = fw.summarize(
        rows,
        trades[:99],
        bars(n),
        paper_return_pct=1.0,
        hold_prices=(1.0, 2.0),
        owner_hypothesis=True,
    )
    assert few.progress.claim_allowed is False and "99/100" in few.progress.reason
    assert few.progress.eta_days_to_min_trades == pytest.approx(
        1 / (99 / few.progress.observed_days), rel=1e-4
    )
    gappy = [r for i, r in enumerate(rows) if i % 10 != 5]
    cov = fw.summarize(
        gappy, trades, bars(n), paper_return_pct=1.0, hold_prices=(1.0, 2.0), owner_hypothesis=True
    )
    assert cov.progress.claim_allowed is False and "độ phủ" in cov.progress.reason
