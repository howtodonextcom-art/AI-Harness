"""Trade governor: exposure, frequency, cooldown and daily-loss guards (trading core 22 and 23).

Independent of the strategy: it only looks at what was opened and what was lost. It refuses NEW
trades (with a reason); closing existing positions on an emergency is the position manager's job.
The thresholds are configuration; nothing here knows any prop-firm rule (those stay in the
verified funded rules, never hard-coded).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field

from xau_edge.trading.schema import Refusal


class GovernorConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_open_positions: int = Field(default=1, ge=1)
    max_total_risk_pct: float = Field(default=1.0, gt=0)
    max_trades_per_hour: int = Field(default=2, ge=1)
    max_trades_per_session: int = Field(default=3, ge=1)
    max_trades_per_day: int = Field(default=6, ge=1)
    cooldown_after_loss_minutes: int = Field(default=30, ge=0)
    cooldown_after_streak_minutes: int = Field(default=240, ge=0)
    loss_streak_limit: int = Field(default=3, ge=1)
    daily_loss_stop_pct: float = Field(default=2.0, gt=0)
    """No NEW trades once realised plus floating loss reaches this share of day-start equity."""
    daily_loss_flatten_pct: float = Field(default=3.5, gt=0)
    """Emergency floor: the manager is told to flatten (always larger than the stop)."""


@dataclass
class _Trade:
    opened: datetime
    session: str
    risk_pct: float


@dataclass
class TradeGovernor:
    """Stateful guard fed with opens and closes; ``check`` answers for a NEW trade."""

    config: GovernorConfig = field(default_factory=GovernorConfig)
    _opens: list[_Trade] = field(default_factory=list)
    _closes: list[tuple[datetime, float]] = field(default_factory=list)
    _open_risk: dict[str, float] = field(default_factory=dict)

    def record_open(self, ticket: str, now: datetime, session: str, risk_pct: float) -> None:
        self._opens.append(_Trade(now, session, risk_pct))
        self._open_risk[ticket] = risk_pct

    def record_close(self, ticket: str, now: datetime, pnl: float) -> None:
        self._open_risk.pop(ticket, None)
        self._closes.append((now, pnl))

    def open_positions(self) -> int:
        return len(self._open_risk)

    def loss_streak(self) -> int:
        streak = 0
        for _, pnl in reversed(self._closes):
            if pnl < 0:
                streak += 1
            else:
                break
        return streak

    def daily_loss_pct(self, day_start_equity: float, equity: float) -> float:
        """Loss (positive number) of today's equity against the day start, floating included."""
        if day_start_equity <= 0:
            return 0.0
        return max(0.0, (day_start_equity - equity) / day_start_equity * 100.0)

    def flatten_required(self, day_start_equity: float, equity: float) -> bool:
        return self.daily_loss_pct(day_start_equity, equity) >= self.config.daily_loss_flatten_pct

    def check(
        self,
        now: datetime,
        session: str,
        new_risk_pct: float,
        *,
        day_start_equity: float,
        equity: float,
    ) -> list[Refusal]:
        """Reasons a new trade must be refused now (empty list: allowed)."""
        cfg = self.config
        out: list[Refusal] = []
        if self.daily_loss_pct(day_start_equity, equity) >= cfg.daily_loss_stop_pct:
            out.append(Refusal.DAILY_LIMIT)
        today = now.date()
        todays = [t for t in self._opens if t.opened.date() == today]
        if len(todays) >= cfg.max_trades_per_day:
            out.append(Refusal.DAILY_LIMIT)
        if sum(1 for t in todays if t.session == session) >= cfg.max_trades_per_session:
            out.append(Refusal.DAILY_LIMIT)
        if (
            sum(1 for t in self._opens if now - t.opened < timedelta(hours=1))
            >= cfg.max_trades_per_hour
        ):
            out.append(Refusal.DAILY_LIMIT)
        if self.open_positions() >= cfg.max_open_positions:
            out.append(Refusal.RISK_LIMIT)
        if sum(self._open_risk.values()) + new_risk_pct > cfg.max_total_risk_pct + 1e-9:
            out.append(Refusal.RISK_LIMIT)
        if self._closes:
            last_time, last_pnl = self._closes[-1]
            streak = self.loss_streak()
            if (
                streak >= cfg.loss_streak_limit
                and now - last_time < timedelta(minutes=cfg.cooldown_after_streak_minutes)
            ) or (
                last_pnl < 0
                and now - last_time < timedelta(minutes=cfg.cooldown_after_loss_minutes)
            ):
                out.append(Refusal.COOLDOWN)
        return list(dict.fromkeys(out))
