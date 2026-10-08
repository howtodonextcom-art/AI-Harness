"""Read-only bot endpoints: status, account, positions, cycles, journal, reconciliation, alerts.

Everything is served from files and the persistent state the bot writes; the API never talks to the
terminal and has no route that changes anything (ADR-0019: the kill switch is a local command).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query

from xau_edge.execution.journal import ExecutionJournal
from xau_edge.execution.runner import JournalError
from xau_edge.execution.state import ExecutionState, StateError
from xau_edge.execution.status import BotStatus, evaluate_health, read_status

Limit = Annotated[int, Query(ge=1, le=500)]


@dataclass(frozen=True)
class BotContext:
    """Where the bot keeps its files."""

    state_path: Path
    status_path: Path
    cycles_path: Path
    journal_path: Path


def _tail_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
        return [json.loads(line) for line in lines]
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="a bot log file is unreadable") from exc


def add_bot_routes(app: FastAPI, bot: BotContext | None, clock: Callable[[], datetime]) -> None:
    """Register the GET-only ``/bot/*`` routes."""

    def need() -> BotContext:
        if bot is None:
            raise HTTPException(status_code=503, detail="the bot is not configured")
        return bot

    def status_or_none(ctx: BotContext) -> BotStatus | None:
        try:
            return read_status(ctx.status_path)
        except ValueError as exc:
            raise HTTPException(status_code=503, detail="the bot status is unreadable") from exc

    def state_or_none(ctx: BotContext) -> ExecutionState | None:
        if not ctx.state_path.exists():
            return None
        try:
            return ExecutionState(ctx.state_path)
        except StateError as exc:
            raise HTTPException(
                status_code=503, detail="the execution state is unreadable"
            ) from exc

    def kill_switch(state: ExecutionState | None) -> dict[str, Any]:
        if state is None:
            return {"tripped": False, "reason": "", "known": False}
        try:
            tripped, reason = state.kill_switch_state()
        except StateError as exc:
            raise HTTPException(status_code=503, detail="the kill switch is unreadable") from exc
        return {"tripped": tripped, "reason": reason, "known": True}

    @app.get("/bot/status")
    def bot_status() -> dict[str, Any]:
        ctx = need()
        status = status_or_none(ctx)
        state = state_or_none(ctx)
        alerts = evaluate_health(status, state, clock())
        return {
            "configured": True,
            "live_trading": False,
            "status": status.model_dump(mode="json") if status else None,
            "kill_switch": kill_switch(state),
            "alerts": [a.__dict__ for a in alerts],
            "healthy": not any(a.severity == "critical" for a in alerts),
        }

    @app.get("/bot/alerts")
    def bot_alerts() -> dict[str, Any]:
        ctx = need()
        alerts = evaluate_health(status_or_none(ctx), state_or_none(ctx), clock())
        return {"alerts": [a.__dict__ for a in alerts]}

    @app.get("/bot/account")
    def bot_account() -> dict[str, Any]:
        status = status_or_none(need())
        if status is None:
            return {"available": False}
        return {
            "available": True,
            "updated_at": status.updated_at.isoformat(),
            "connected": status.connected,
            "demo": status.account_demo,
            "balance": status.balance,
            "equity": status.equity,
        }

    @app.get("/bot/positions")
    def bot_positions() -> dict[str, Any]:
        status = status_or_none(need())
        return {
            "positions": [p.model_dump(mode="json") for p in status.positions] if status else []
        }

    @app.get("/bot/reconciliation")
    def bot_reconciliation() -> dict[str, Any]:
        status = status_or_none(need())
        if status is None:
            return {"available": False}
        return {
            "available": True,
            "clean": status.reconcile_clean,
            "codes": status.reconcile_codes,
            "updated_at": status.updated_at.isoformat(),
        }

    @app.get("/bot/cycles")
    def bot_cycles(limit: Limit = 50) -> dict[str, Any]:
        return {"cycles": _tail_jsonl(need().cycles_path, limit)}

    @app.get("/bot/journal")
    def bot_journal(limit: Limit = 100) -> dict[str, Any]:
        try:
            return {"events": ExecutionJournal(need().journal_path).read(limit)}
        except JournalError as exc:
            raise HTTPException(
                status_code=503, detail="the execution journal is unreadable"
            ) from exc
