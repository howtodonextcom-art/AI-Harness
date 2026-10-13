"""Risk engine: decides whether a trade request may be taken, and how large.

It knows nothing about forecasts. Inputs are the request (direction, stop distance), the account,
and the market state; the output lists EVERY reason for a refusal. Limits come from configuration
(``RiskLimits`` and a prop-firm ``PropProfile``), never from constants in trading code.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from xau_edge.observability import log_event
from xau_edge.risk.kill_switch import KillSwitch
from xau_edge.risk.prop_rules import PropProfile
from xau_edge.risk.sizing import position_size

_LOG = logging.getLogger(__name__)


class RiskLimits(BaseModel):
    """Trade-level limits (fractions are percent of equity)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    risk_per_trade_pct: float = Field(default=0.5, gt=0, le=2.0)
    max_concurrent_trades: int = Field(default=1, ge=1)
    max_total_lots: float = Field(default=10.0, gt=0)
    daily_risk_budget_pct: float = Field(default=2.0, gt=0)
    consecutive_loss_limit: int = Field(default=3, ge=1)
    max_spread_points: float = Field(default=120.0, gt=0)
    blocked_regimes: tuple[str, ...] = ("SHOCK",)
    require_regime: bool = True
    """Refuse when the regime is unknown (fail safe); set False only for research runs."""
    contract_size: float = Field(default=100.0, gt=0)
    min_lot: float = Field(default=0.01, gt=0)
    lot_step: float = Field(default=0.01, gt=0)
    max_lot: float = Field(default=50.0, gt=0)


class AccountState(BaseModel):
    """Account snapshot supplied by the caller (backtest, paper broker or live broker)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: datetime
    initial_capital: float
    balance: float
    equity: float
    day_start_balance: float
    highest_eod_balance: float
    open_positions: int
    open_lots: float
    risk_taken_today: float
    consecutive_losses: int


class TradeRequest(BaseModel):
    """What the strategy wants: a direction and a stop distance in price units."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: datetime
    direction: Literal[-1, 1]
    stop_distance: float = Field(gt=0)


class MarketState(BaseModel):
    """Market conditions at the decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    spread_points: float
    regime: str | None = None
    news_blocked: bool = False


@dataclass(frozen=True)
class RiskDecision:
    """Outcome of a risk check."""

    allowed: bool
    lots: float
    risk_amount: float
    reasons: tuple[str, ...]


def _account_valid(a: AccountState) -> bool:
    values = (a.initial_capital, a.balance, a.equity, a.day_start_balance, a.highest_eod_balance)
    if not all(math.isfinite(v) and v > 0 for v in values):
        return False
    return (
        math.isfinite(a.open_lots)
        and a.open_lots >= 0
        and math.isfinite(a.risk_taken_today)
        and a.risk_taken_today >= 0
        and a.open_positions >= 0
        and a.consecutive_losses >= 0
    )


class RiskEngine:
    """Evaluate trade requests against limits, prop-firm floors and the kill switch."""

    def __init__(
        self, limits: RiskLimits, prop: PropProfile, kill_switch: KillSwitch | None = None
    ) -> None:
        self.limits = limits
        self.prop = prop
        self.kill_switch = kill_switch or KillSwitch()

    def _floors(self, a: AccountState) -> tuple[float, float]:
        daily = self.prop.daily_loss_floor(a.initial_capital, day_start_balance=a.day_start_balance)
        maximum = self.prop.max_loss_floor(
            a.initial_capital, highest_eod_balance=a.highest_eod_balance
        )
        return daily, maximum

    def check_account(self, account: AccountState) -> bool:
        """Trip the kill switch if equity is below a prop-firm floor. Returns True if breached."""
        if not _account_valid(account):
            self.kill_switch.trip("ACCOUNT_STATE_INVALID")
            return True
        daily, maximum = self._floors(account)
        if account.equity <= daily or account.equity <= maximum:
            self.kill_switch.trip(
                f"PROP_BREACH: equity {account.equity:.2f} below floor {max(daily, maximum):.2f}"
            )
            return True
        return False

    def evaluate(  # noqa: PLR0912 - one independent check per refusal reason
        self, request: TradeRequest, account: AccountState, market: MarketState
    ) -> RiskDecision:
        """Return the decision with ALL refusal reasons and the sized lots when allowed."""
        lim = self.limits
        reasons: list[str] = []
        if self.kill_switch.tripped:
            reasons.append("KILL_SWITCH")
        if not _account_valid(account):
            return self._finish([*reasons, "ACCOUNT_STATE_INVALID"], 0.0, 0.0)

        lots = position_size(
            account.equity,
            lim.risk_per_trade_pct / 100.0,
            request.stop_distance,
            contract_size=lim.contract_size,
            min_lot=lim.min_lot,
            lot_step=lim.lot_step,
            max_lot=lim.max_lot,
        )
        risk_amount = lots * request.stop_distance * lim.contract_size
        if lots == 0.0:
            reasons.append("SIZE_TOO_SMALL")

        daily_floor, max_floor = self._floors(account)
        buffer = self.prop.internal_buffer_pct_of_limit / 100.0
        worst_equity = account.equity - risk_amount
        if worst_equity <= daily_floor + buffer * self.prop.daily_loss_amount(
            account.initial_capital
        ):
            reasons.append("DAILY_LOSS_BUFFER")
        max_amount = account.initial_capital * self.prop.max_loss_limit_pct / 100.0
        if worst_equity <= max_floor + buffer * max_amount:
            reasons.append("MAX_LOSS_BUFFER")
        if account.open_positions >= lim.max_concurrent_trades:
            reasons.append("MAX_CONCURRENT")
        if account.open_lots + lots > lim.max_total_lots:
            reasons.append("MAX_EXPOSURE")
        budget = account.equity * lim.daily_risk_budget_pct / 100.0
        if account.risk_taken_today + risk_amount > budget + 1e-9:
            reasons.append("DAILY_RISK_BUDGET")
        if account.consecutive_losses >= lim.consecutive_loss_limit:
            reasons.append("CONSECUTIVE_LOSSES")
        if not (math.isfinite(market.spread_points) and market.spread_points >= 0):
            reasons.append("MARKET_STATE_INVALID")
        elif market.spread_points > lim.max_spread_points:
            reasons.append("SPREAD")
        if market.regime is None:
            if lim.require_regime:
                reasons.append("REGIME_UNKNOWN")
        elif market.regime in lim.blocked_regimes:
            reasons.append("VOLATILITY")
        if market.news_blocked:
            reasons.append("NEWS")
        return self._finish(reasons, lots, risk_amount)

    @staticmethod
    def _finish(reasons: list[str], lots: float, risk_amount: float) -> RiskDecision:
        allowed = not reasons
        if not allowed:
            log_event(_LOG, "risk.refused", logging.INFO, reasons=reasons)
            return RiskDecision(False, 0.0, 0.0, tuple(reasons))
        return RiskDecision(True, lots, risk_amount, ())
