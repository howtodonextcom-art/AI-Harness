"""Assemble the decision inputs from market data at one moment and produce a signal.

Everything is computed from bars that had CLOSED by the decision time (the close of the last closed
M15 bar at or before ``at``), so the same call on data truncated there returns the identical signal
and a bar still forming at ``at`` is never used. Probabilities come from the historical analogues
(empirical frequencies of what followed, with the leakage rule of ADR-0013), labelled as such. The
evidence gate (ADR-0017) is bound to the Baseline C configuration this engine mirrors.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import polars as pl

from xau_edge.domain.timeframe import Timeframe
from xau_edge.experiments.registry import ExperimentRegistry, current_code_version
from xau_edge.news.calendar import (
    CalendarUnavailableError,
    EconomicCalendar,
    EventImpact,
    news_blocked,
)
from xau_edge.observability import log_event
from xau_edge.outcomes.engine import OutcomeConfig, compute_outcomes
from xau_edge.outcomes.summary import summarise
from xau_edge.patterns.representation import pattern_values, window_validity
from xau_edge.patterns.search import PatternIndex, SearchConfig
from xau_edge.signals.decision import DecisionPolicy, SignalInputs, decide
from xau_edge.signals.evidence import evidence_status
from xau_edge.signals.schema import EvidenceStatus, Signal
from xau_edge.strategies.context import build_context
from xau_edge.strategies.pattern import PatternConfig

_LOG = logging.getLogger(__name__)
EVIDENCE_FAMILY = "backtest"
WINDOW = 30


@dataclass(frozen=True)
class MarketFrames:
    """Validated bar frames of the four timeframes the dashboard shows."""

    m5: pl.DataFrame
    m15: pl.DataFrame
    h1: pl.DataFrame
    h4: pl.DataFrame


def evidence_params() -> dict[str, object]:
    """The configuration whose validation this engine relies on: Baseline C (analogues only)."""
    from xau_edge.evaluation.runner import strategy_params  # noqa: PLC0415 - avoids an import cycle

    return dict(strategy_params("baseline_c"))


def default_policy() -> DecisionPolicy:
    """Decision thresholds identical to the pre-registered Baseline C configuration."""
    c = PatternConfig()
    return DecisionPolicy(
        edge_threshold=c.edge_threshold,
        min_matches=c.min_matches,
        stop_atr=c.stop_atr,
        tp1_atr=c.target_atr,
        tp2_atr=c.target_atr * 1.5,
    )


def _closed(frame: pl.DataFrame, timeframe: Timeframe, moment: datetime) -> pl.DataFrame:
    """Bars whose close is at or before ``moment``."""
    return frame.filter(pl.col("timestamp") <= moment - timeframe.delta)


def _last_trend(ctx: pl.DataFrame) -> int:
    return int(ctx["trend"][-1]) if ctx.height else 0


def build_inputs(
    frames: MarketFrames,
    at: datetime,
    *,
    evidence: EvidenceStatus,
    calendar: EconomicCalendar | None = None,
    policy: DecisionPolicy | None = None,
    symbol: str = "XAUUSD",
) -> SignalInputs:
    """Inputs at the last M15 close at or before ``at`` using only bars closed by then."""
    pol = policy or default_policy()
    m15 = _closed(frames.m15, Timeframe.M15, at)
    if m15.height == 0:
        nan = float("nan")
        return SignalInputs(
            timestamp=at,
            price=nan,
            atr=nan,
            spread_points=nan,
            data_valid=False,
            evidence_status=evidence,
            symbol=symbol,
        )
    decision_time: datetime = m15["timestamp"][-1] + Timeframe.M15.delta
    ctx15 = build_context(m15, Timeframe.M15)
    last = ctx15.row(ctx15.height - 1, named=True)

    bias = {"M15": _last_trend(ctx15)}
    for label, frame, tf in (
        ("H4", frames.h4, Timeframe.H4),
        ("H1", frames.h1, Timeframe.H1),
        ("M5", frames.m5, Timeframe.M5),
    ):
        closed = _closed(frame, tf, decision_time)
        bias[label] = _last_trend(build_context(closed, tf)) if closed.height else 0

    m5_closed = _closed(frames.m5, Timeframe.M5, decision_time)
    spread = float(m5_closed["spread"][-1]) if m5_closed.height else float("nan")

    values = pattern_values(m15)
    q = m15.height - 1
    probs: tuple[float, float, float] | None = None
    n_matches, quality, exp_r_long, exp_r_short, mean_ret = 0, None, None, None, None
    if q >= WINDOW - 1 and window_validity(values, WINDOW)[q - WINDOW + 1]:
        found = PatternIndex(
            values, SearchConfig(window=WINDOW, horizon=60, k=20, method="euclidean")
        ).search(q)
        if found.matches and found.best_distance is not None and found.median_distance:
            high, low, close = (m15[k].to_numpy() for k in ("high", "low", "close"))
            atr_all = ctx15["atr_14"].fill_null(float("nan")).to_numpy()
            ends = np.array([m.end_index for m in found.matches], dtype=np.intp)
            outcome_cfg = OutcomeConfig(
                horizons=(PatternConfig().outcome_horizon,),
                stop_atr=pol.stop_atr,
                target_atr=pol.tp1_atr,
            )
            summary = summarise(compute_outcomes(high, low, close, atr_all, ends, outcome_cfg), 0)
            if summary is not None:
                probs = (summary.p_down, summary.p_neutral, summary.p_up)
                n_matches = summary.n
                quality = found.best_distance / found.median_distance
                exp_r_long, exp_r_short = summary.expected_r_long, summary.expected_r_short
                mean_ret = summary.mean_return

    news: bool | None = None
    if calendar is not None:
        try:
            news = news_blocked(
                calendar,
                decision_time,
                before_minutes=15,
                after_minutes=15,
                min_impact=EventImpact.HIGH,
            )
        except CalendarUnavailableError:
            news = None

    atr = last["atr_14"]
    return SignalInputs(
        symbol=symbol,
        timestamp=decision_time,
        timeframe="M15",
        price=float(last["close"]),
        atr=float("nan") if atr is None else float(atr),
        spread_points=spread,
        regime=last["regime"],
        htf_bias=bias,
        prob_down=None if probs is None else probs[0],
        prob_neutral=None if probs is None else probs[1],
        prob_up=None if probs is None else probs[2],
        probability_source="historical analogues (uncalibrated frequencies)",
        n_matches=n_matches,
        similarity_quality=quality,
        analogue_expected_r_long=exp_r_long,
        analogue_expected_r_short=exp_r_short,
        analogue_mean_return=mean_ret,
        nearest_resistance=last["resistance"],
        nearest_support=last["support"],
        news_blocked=news,
        data_valid=probs is not None,
        evidence_status=evidence,
    )


def generate_signal(
    frames: MarketFrames,
    at: datetime,
    registry: ExperimentRegistry,
    *,
    calendar: EconomicCalendar | None = None,
    policy: DecisionPolicy | None = None,
) -> Signal:
    """The signal at ``at``: evidence gate from the registry, inputs from closed bars, decision."""
    pol = policy or default_policy()
    evidence = evidence_status(registry, family=EVIDENCE_FAMILY, params=evidence_params())
    inputs = build_inputs(frames, at, evidence=evidence, calendar=calendar, policy=pol)
    commit, _ = current_code_version()
    signal = decide(inputs, pol, code_version=commit)
    log_event(
        _LOG,
        "signal.generated",
        direction=signal.direction.value,
        reasons=[r.value for r in signal.reasons],
        inputs_hash=signal.inputs_hash,
        decision_time=signal.timestamp,
    )
    return signal
