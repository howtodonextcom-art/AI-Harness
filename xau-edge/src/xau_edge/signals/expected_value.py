"""Expected value after costs (brief 23): EV = P(win) x AvgWin - P(loss) x AvgLoss - Costs."""

from __future__ import annotations

import math

from xau_edge.outcomes.summary import OutcomeSummary


def cost_in_r(
    spread_points: float, slippage_points: float, stop_distance: float, *, point: float = 0.01
) -> float:
    """Round-trip friction in units of the stop distance (one spread plus slippage on two fills).

    Commission and swap are added by the caller when the account type requires them.
    """
    if not (math.isfinite(spread_points) and spread_points >= 0):
        msg = f"spread_points must be a non-negative number, got {spread_points}"
        raise ValueError(msg)
    if not (math.isfinite(stop_distance) and stop_distance > 0):
        msg = f"stop_distance must be positive, got {stop_distance}"
        raise ValueError(msg)
    return (spread_points + 2.0 * slippage_points) * point / stop_distance


def expected_r(
    p_win: float, avg_win_r: float, p_loss: float, avg_loss_r: float, cost_r: float
) -> float:
    """``p_win x avg_win - p_loss x avg_loss - cost`` with ``avg_loss_r`` as a positive number."""
    if not (0.0 <= p_win <= 1.0 and 0.0 <= p_loss <= 1.0 and p_win + p_loss <= 1.0 + 1e-9):
        msg = "p_win and p_loss must be probabilities that sum to at most 1"
        raise ValueError(msg)
    return p_win * avg_win_r - p_loss * avg_loss_r - cost_r


def analogue_expected_r(summary: OutcomeSummary, direction: int, cost_r: float) -> float:
    """Mean barrier-trade R of the analogues for ``direction`` (+1/-1) minus friction."""
    gross = summary.expected_r_long if direction > 0 else summary.expected_r_short
    return gross - cost_r
