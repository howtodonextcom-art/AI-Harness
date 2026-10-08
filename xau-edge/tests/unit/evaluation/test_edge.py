"""The seven edge criteria of docs/evals/edge-criteria.md as executable checks."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from xau_edge.evaluation.edge import evaluate_edge, fold_bounds

START = datetime(2026, 1, 1, tzinfo=UTC)
END = datetime(2026, 5, 1, tzinfo=UTC)
INITIAL = 100_000.0


def _trades(
    rs: list[float], sessions: list[str] | None = None, regimes: list[str] | None = None
) -> pl.DataFrame:
    n = len(rs)
    span = (END - START) / n
    entry = [START + span * i + timedelta(hours=1) for i in range(n)]
    risk = 500.0
    return pl.DataFrame(
        {
            "entry_time": pl.Series(entry, dtype=pl.Datetime("us", "UTC")),
            "exit_time": pl.Series(
                [e + timedelta(hours=1) for e in entry], dtype=pl.Datetime("us", "UTC")
            ),
            "net_r": rs,
            "net_pnl": [r * risk for r in rs],
            "gross_pnl": [r * risk for r in rs],
            "session": (sessions or ["LONDON", "NEW_YORK", "ASIA", "OVERLAP"] * (n // 4 + 1))[:n],
            "regime": (regimes or ["RANGE", "TREND_UP", "TREND_DOWN"] * (n // 3 + 1))[:n],
        }
    )


def _equity(trades: pl.DataFrame) -> pl.DataFrame:
    days = (END - START).days
    ts = [START + timedelta(days=d) for d in range(days)]
    bal = INITIAL
    values = []
    pnl = trades.sort("entry_time")
    idx = 0
    rows = pnl.iter_rows(named=True)
    nxt = next(rows, None)
    for t in ts:
        while nxt is not None and nxt["exit_time"] <= t:
            bal += nxt["net_pnl"]
            nxt = next(rows, None)
        values.append(bal)
    del idx
    return pl.DataFrame(
        {"timestamp": pl.Series(ts, dtype=pl.Datetime("us", "UTC")), "equity": values}
    )


def _verdict(rs: list[float], variants: int = 1, **kw: list[str]):  # type: ignore[no-untyped-def]
    t = _trades(rs, **kw)
    return evaluate_edge(
        t,
        _equity(t),
        period=(START, END),
        variants=variants,
        initial_capital=INITIAL,
        n_resamples=300,
    )


def _good() -> list[float]:
    rng = np.random.default_rng(3)
    return [float(x) for x in np.where(rng.random(240) < 0.45, 2.0, -1.0)]  # E[R] = 0.35


def test_a_healthy_strategy_passes_every_criterion() -> None:
    v = _verdict(_good())
    failed = {k: c for k, c in v.criteria.items() if not c.passed}
    assert not failed, failed
    assert v.passed


def test_too_few_trades_fails_the_count_criterion() -> None:
    v = _verdict(_good()[:60])
    assert not v.criteria["min_trades"].passed
    assert not v.passed


def test_mean_r_not_clearly_positive_fails_the_confidence_criterion() -> None:
    rng = np.random.default_rng(1)
    noise = [float(x) for x in rng.normal(0.02, 1.0, 240)]
    v = _verdict(noise)
    assert not v.criteria["ci_lower_above_zero"].passed


def test_more_variants_tried_make_the_confidence_criterion_stricter() -> None:
    rs = _good()
    easy = _verdict(rs, variants=1).criteria["ci_lower_above_zero"]
    hard = _verdict(rs, variants=1000).criteria["ci_lower_above_zero"]
    assert hard.value < easy.value  # lower bound sinks as alpha shrinks


def test_profit_factor_below_the_threshold_fails() -> None:
    rs = [1.15] * 40 + [-1.0] * 35  # PF = 46 / 35 = 1.31 per block, scale to make it ~1.1
    weak = [
        0.5 if r > 0 else -0.45 for r in _good()
    ]  # wins 0.5, losses 0.45 at 45% -> PF 0.41... negative
    assert _verdict(weak).criteria["profit_factor"].passed is False
    assert _verdict(rs * 3).criteria["profit_factor"].passed


def test_deep_drawdown_in_r_fails() -> None:
    rs = _good()
    rs[100:120] = [-1.0] * 20  # a 20 R losing run
    v = _verdict(rs)
    assert not v.criteria["max_drawdown_r"].passed
    assert v.criteria["max_drawdown_r"].value >= 20.0


def test_walk_forward_folds_must_be_mostly_positive() -> None:
    rs = [1.0] * 60 + [-1.5] * 60 + [-1.5] * 60 + [1.0] * 60  # only 2 of 4 folds positive
    v = _verdict(rs)
    assert v.criteria["positive_folds"].value == 2
    assert not v.criteria["positive_folds"].passed


def test_one_lucky_trade_cannot_carry_the_result() -> None:
    rs = [-0.05] * 239 + [200.0]
    v = _verdict(rs)
    assert not v.criteria["robust_to_best_trades"].passed


def test_profit_concentrated_in_one_session_fails() -> None:
    rs = _good()
    sessions = ["LONDON" if r > 0 else "ASIA" for r in rs]
    v = _verdict(rs, sessions=sessions)
    assert not v.criteria["no_concentration"].passed


def test_concentration_fails_when_there_is_no_profit_at_all() -> None:
    v = _verdict([-0.1] * 200)
    assert not v.criteria["no_concentration"].passed


def test_fold_bounds_split_the_period_into_four_equal_contiguous_parts() -> None:
    folds = fold_bounds((START, END), 4)
    assert len(folds) == 4
    assert folds[0][0] == START
    assert folds[-1][1] == END
    assert all(folds[i][1] == folds[i + 1][0] for i in range(3))
    widths = {(b - a) for a, b in folds}
    assert max(widths) - min(widths) <= timedelta(microseconds=1)


def test_missing_columns_are_rejected() -> None:
    t = _trades(_good())
    with pytest.raises(ValueError, match="column"):
        evaluate_edge(
            t.drop("session"), _equity(t), period=(START, END), variants=1, initial_capital=INITIAL
        )
    with pytest.raises(ValueError, match="variants"):
        evaluate_edge(t, _equity(t), period=(START, END), variants=0, initial_capital=INITIAL)


def test_verdict_is_serialisable_for_the_registry() -> None:
    v = _verdict(_good())
    json.dumps(v.as_dict(), allow_nan=False)


def test_a_strategy_without_any_loss_does_not_fail_the_profit_factor_criterion() -> None:
    v = _verdict([1.0] * 150)
    assert v.criteria["profit_factor"].passed
    assert v.criteria["profit_factor"].value is None


def test_no_trades_fails_the_profit_factor_criterion() -> None:
    t = _trades([-1.0]).head(0)
    v = evaluate_edge(
        t, _equity(_trades([-1.0])), period=(START, END), variants=1, initial_capital=INITIAL
    )
    assert not v.criteria["profit_factor"].passed
    assert not v.passed
