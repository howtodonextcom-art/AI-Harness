"""Bot status snapshot and health alerts (ADR-0019).

The bot writes ``status.json`` after every cycle; the read-only API and the dashboard only read it,
so the web application never needs a terminal connection. ``evaluate_health`` turns the snapshot,
the heartbeat and the persistent kill switch into a list of alerts that an operator or an external
watcher can act on. A missing or unreadable status is itself an alert, never "all clear".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from xau_edge.execution.reconcile import BrokerSnapshot, ReconcileResult
from xau_edge.execution.runner import CycleReport
from xau_edge.execution.state import ExecutionState, StateError

Severity = Literal["info", "warning", "critical"]


class StatusPosition(BaseModel):
    """An open position, without account identifiers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ticket: str
    symbol: str
    direction: Literal[-1, 1]
    lots: float
    entry_price: float
    stop_loss: float
    take_profit: float
    opened_at: datetime
    bot_owned: bool


class StatusCycle(BaseModel):
    """The last decision cycle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_time: str | None
    direction: str
    accepted: bool
    reasons: list[str]
    data_age_minutes: float | None


class BotStatus(BaseModel):
    """What the dashboard shows about the running bot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    updated_at: datetime
    mode: Literal["disabled", "dry-run", "demo"]
    live_trading: Literal[False] = False
    symbol: str
    connected: bool
    account_demo: bool | None
    balance: float | None
    equity: float | None
    positions: list[StatusPosition]
    reconcile_clean: bool | None
    reconcile_codes: list[str]
    last_cycle: StatusCycle | None
    news_status: Literal["unknown", "risk", "clear"]
    loop_interval_minutes: int = 15


def write_status(path: Path, status: BotStatus) -> None:
    """Atomically replace the status file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(status.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(path)


def read_status(path: Path) -> BotStatus | None:
    """The stored status, ``None`` if there is none; a corrupt file raises ``ValueError``."""
    if not path.exists():
        return None
    try:
        return BotStatus.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, json.JSONDecodeError) as exc:
        msg = f"the bot status file is unreadable: {exc}"
        raise ValueError(msg) from exc


@dataclass(frozen=True)
class Alert:
    """One thing an operator should look at."""

    code: str
    severity: Severity
    message: str


def evaluate_health(
    status: BotStatus | None,
    state: ExecutionState | None,
    now: datetime,
    *,
    stale_after: timedelta = timedelta(minutes=40),
) -> list[Alert]:
    """Alerts from the status snapshot and the persistent state (empty means healthy)."""
    alerts: list[Alert] = []
    if state is not None:
        try:
            tripped, reason = state.kill_switch_state()
            if tripped:
                alerts.append(Alert("KILL_SWITCH_TRIPPED", "critical", f"kill switch: {reason}"))
        except StateError as exc:
            alerts.append(Alert("STATE_UNAVAILABLE", "critical", str(exc)))
    if status is None:
        alerts.append(Alert("NO_STATUS", "warning", "the bot has not written a status yet"))
        return alerts
    age = now.astimezone(UTC) - status.updated_at.astimezone(UTC)
    if age > stale_after:
        minutes = int(age.total_seconds() // 60)
        alerts.append(Alert("HEARTBEAT_STALE", "critical", f"no cycle for {minutes} minutes"))
    if not status.connected:
        alerts.append(Alert("TERMINAL_DISCONNECTED", "critical", "the MT5 terminal is unreachable"))
    if status.account_demo is False:
        alerts.append(Alert("ACCOUNT_NOT_DEMO", "critical", "the connected account is not DEMO"))
    if status.reconcile_clean is False:
        codes = ", ".join(status.reconcile_codes)
        alerts.append(Alert("RECONCILE_DIRTY", "critical", f"broker and bot disagree: {codes}"))
    cycle = status.last_cycle
    if cycle is not None and "DATA_STALE" in cycle.reasons:
        alerts.append(Alert("DATA_STALE", "warning", "market data is older than the limit"))
    if status.news_status == "unknown":
        alerts.append(Alert("NEWS_UNKNOWN", "info", "no economic calendar: signals stay WAIT"))
    return alerts


def build_status(
    now: datetime,
    *,
    mode: Literal["disabled", "dry-run", "demo"],
    symbol: str,
    snapshot: BrokerSnapshot | None,
    reconcile: ReconcileResult | None,
    report: CycleReport | None,
    bot_tickets: frozenset[str] = frozenset(),
) -> BotStatus:
    """Assemble the status from one cycle; a missing snapshot means the terminal was unreachable."""
    cycle = (
        StatusCycle(
            decision_time=report.decision_time,
            direction=report.direction,
            accepted=report.accepted,
            reasons=list(report.reasons),
            data_age_minutes=report.data_age_minutes,
        )
        if report
        else None
    )
    news = "unknown" if report is None or "NEWS_UNKNOWN" in report.reasons else "clear"
    if report is not None and "NEWS_RISK" in report.reasons:
        news = "risk"
    return BotStatus(
        updated_at=now,
        mode=mode,
        symbol=symbol,
        connected=snapshot is not None,
        account_demo=snapshot.account.is_demo if snapshot else None,
        balance=snapshot.account.balance if snapshot else None,
        equity=snapshot.account.equity if snapshot else None,
        positions=[
            StatusPosition(
                ticket=p.ticket,
                symbol=p.symbol,
                direction=p.direction,
                lots=p.lots,
                entry_price=p.entry_price,
                stop_loss=p.stop_loss,
                take_profit=p.take_profit,
                opened_at=p.opened_at,
                bot_owned=p.ticket in bot_tickets,
            )
            for p in (snapshot.positions if snapshot else ())
        ],
        reconcile_clean=reconcile.clean if reconcile else None,
        reconcile_codes=list(reconcile.codes) if reconcile else [],
        last_cycle=cycle,
        news_status=news,
    )
