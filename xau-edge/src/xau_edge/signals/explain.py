"""Plain-language explanations (brief section 22). Every line is derived from the inputs."""

from __future__ import annotations

from xau_edge.signals.schema import Direction, NoTradeReason

_BIAS = {1: "bullish", 0: "neutral", -1: "bearish"}
REASON_TEXT: dict[NoTradeReason, str] = {
    NoTradeReason.NO_VALIDATED_EDGE: (
        "no strategy or model has passed the pre-registered validation on every period"
    ),
    NoTradeReason.EDGE_INSUFFICIENT: "the probability edge between up and down is too small",
    NoTradeReason.EV_NOT_POSITIVE: "expected value after costs is not positive",
    NoTradeReason.RISK_REWARD_POOR: "the reward-to-risk ratio is below the minimum",
    NoTradeReason.REGIME_UNSUPPORTED: "the market regime is unknown or not supported",
    NoTradeReason.NEWS_RISK: "inside the window of a high-impact news event",
    NoTradeReason.NEWS_UNKNOWN: "news risk cannot be assessed (no calendar coverage)",
    NoTradeReason.SPREAD_EXCESSIVE: "the spread is wider than the limit",
    NoTradeReason.DATA_INVALID: "the input data or probabilities are invalid",
    NoTradeReason.MODEL_UNCERTAIN: "too few or too dissimilar historical analogues",
    NoTradeReason.HTF_BIAS_CONFLICT: "the trade is against the higher-timeframe bias",
    NoTradeReason.ENTRY_QUALITY_POOR: "price is too close to an opposing support or resistance",
}


def bias_text(value: int | None) -> str:
    """Words for a -1/0/+1 bias."""
    return "unknown" if value is None else _BIAS.get(value, "unknown")


def explain(
    *,
    candidate: Direction | None,
    final: Direction,
    reasons: tuple[NoTradeReason, ...],
    htf_bias: dict[str, int],
    regime: str | None,
    probs: tuple[float, float, float] | None,
    n_matches: int,
    expected_r: float | None,
    atr: float | None,
    source: str,
) -> tuple[str, ...]:
    """Ordered explanation lines for a decision."""
    lines: list[str] = []
    lines.append(
        "Context: "
        + ", ".join(f"{tf} {bias_text(htf_bias.get(tf))}" for tf in ("H4", "H1", "M15", "M5"))
    )
    lines.append(f"Regime: {regime or 'unknown'}")
    if atr is not None:
        lines.append(f"Volatility: ATR {atr:.2f}")
    if probs is not None:
        down, neutral, up = probs
        lines.append(
            f"Probabilities ({source}): up {up:.0%}, down {down:.0%}, neutral {neutral:.0%} "
            f"from {n_matches} historical analogues"
        )
    if expected_r is not None:
        lines.append(f"Expected value after costs: {expected_r:+.2f} R")
    if candidate is not None:
        lines.append(f"Analysis leans {candidate.value}")
    if final is Direction.WAIT:
        lines.append("Decision WAIT because: " + "; ".join(REASON_TEXT[r] for r in reasons))
    else:
        lines.append(f"Decision {final.value}: every check passed and the evidence gate is open")
    return tuple(lines)
