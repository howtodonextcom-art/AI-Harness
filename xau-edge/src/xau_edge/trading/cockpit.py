"""The trader-facing truth, computed on the SERVER: hero state, conditions, plan, funnel, evidence.

The browser renders these objects and never infers strategy state itself. Everything here is a pure
function of server objects (the decision, the snapshot, the desk, the telemetry), so each rule can
be tested without a browser.

Two ideas are kept strictly apart:

* ``WAIT`` means "the engine evaluated successfully and chose no trade";
* ``UNAVAILABLE`` / ``STALE`` / ``MARKET_CLOSED`` mean "this decision cannot be trusted or does
  not exist" and must never be shown as a plain WAIT.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from xau_edge.trading.baseline import STRATEGY_ID
from xau_edge.trading.schema import TradeDecision, TradingSignal

INSTALLED_VERSIONS = ("1.1.0", "1.2.0", "1.2.1")
VERSION_NOTES = {
    "1.1.0": "operational baseline (default)",
    "1.2.0": "pre-registered candidate: rejected by its own frequency band",
    "1.2.1": "v1.2.0 plus the independent-review fixes (opt-in)",
}
EXIT_BANNER_MINUTES = 30

# conditions that make the decision itself untrustworthy (-> UNAVAILABLE / STALE hero)
UNTRUSTED_STALE = ("COLLECTOR_STALE", "DATA_STALE", "QUOTE_STALE")
UNTRUSTED_FAULT = (
    "MT5_DISCONNECTED",
    "SPEC_MISSING",
    "ENGINE_ERROR",
    "WRITER_LOCK",
    "PAPER_STATE_ERROR",
    "NO_DECISION",
)

REFUSAL_GROUPS = {
    "NO_DIRECTION": "NO_DIRECTION",
    "TIMEFRAME_CONFLICT": "TIMEFRAME_CONFLICT",
    "NO_SETUP": "NO_SETUP",
    "NO_TRIGGER": "NO_TRIGGER",
    "VOLATILITY_TOO_HIGH": "VOLATILITY",
    "VOLATILITY_TOO_LOW": "VOLATILITY",
    "VOLUME_TOO_LOW": "VOLUME",
    "SPREAD_TOO_WIDE": "SPREAD",
    "RR_TOO_LOW": "RR",
    "TOO_CLOSE_TO_RESISTANCE": "RR",
    "TOO_CLOSE_TO_SUPPORT": "RR",
    "INVALID_STOP_DISTANCE": "RISK",
    "RISK_LIMIT": "RISK",
    "DAILY_LIMIT": "RISK",
    "COOLDOWN": "RISK",
    "STALE_DATA": "STALE",
    "UNKNOWN_STATE": "STALE",
    "BROKER_DISCONNECTED": "STALE",
    "MARKET_CLOSED": "MARKET_CLOSED",
    "NEWS_UNKNOWN": "NEWS",
    "NEWS_WINDOW": "NEWS",
}
REFUSAL_GROUP_ORDER = (
    "NO_DIRECTION",
    "TIMEFRAME_CONFLICT",
    "NO_SETUP",
    "NO_TRIGGER",
    "VOLATILITY",
    "VOLUME",
    "SPREAD",
    "RR",
    "RISK",
    "STALE",
    "MARKET_CLOSED",
    "NEWS",
)

BLOCKER_TEXT = {
    "PAPER_STATE_ERROR": "PAPER STATE ERROR: the paper state cannot be trusted",
    "WRITER_LOCK": "SINGLE WRITER CONFLICT: another process owns the paper desk",
    "CLOSURE_NEAR": "PAPER ENTRY BLOCKED: a market closure is approaching",
    "RISK_LIMIT": "a position is already open or the total risk limit is reached",
    "COOLDOWN": "cooling down after the previous trade",
    "DAILY_LIMIT": "the daily or session limit is reached",
    "STALE_DATA": "market data is not fresh enough",
    "QUOTE_STALE": "the quote is too old",
    "EXPIRED": "the setup has expired",
    "NOT_ACTIONABLE": "the plan is incomplete",
    "RISK_INVALID": "the risk plan is invalid (lot, stop or R/R)",
    "NO_SYMBOL_SPEC": "the broker symbol specification is unavailable",
    "DUPLICATE_SETUP": "this setup was already taken",
}


def blocker(code: str, message: str | None = None) -> dict[str, str]:
    return {"code": code, "message": message or BLOCKER_TEXT.get(code, code)}


def condition(code: str, severity: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


# ---- strategy -----------------------------------------------------------------------------------


def strategy_info(active_version: str) -> dict[str, Any]:
    """Which baseline is RUNNING and which are merely installed (never implied to be running)."""
    return {
        "id": STRATEGY_ID,
        "active_version": active_version,
        "label": f"{STRATEGY_ID} v{active_version}",
        "evidence": "UNVALIDATED OPERATIONAL BASELINE",
        "installed": [
            {
                "version": v,
                "status": "ACTIVE" if v == active_version else "AVAILABLE_INACTIVE",
                "note": VERSION_NOTES[v],
            }
            for v in INSTALLED_VERSIONS
        ],
    }


# ---- plan ---------------------------------------------------------------------------------------

PLAN_FIELDS = ("entry_price", "stop_loss", "take_profit", "risk_reward", "signal_expiry")


def trade_plan(
    signal: TradingSignal,
    *,
    plans: list[dict[str, Any]] | None,
    default_risk_pct: float,
    expired: bool,
    seconds_to_expiry: float | None,
) -> dict[str, Any] | None:
    """The plan card for a BUY/SELL (None for WAIT); ``complete`` False means NOT actionable."""
    if signal.decision is TradeDecision.WAIT:
        return None
    missing = [f for f in PLAN_FIELDS if getattr(signal, f) is None]
    chosen = next(
        (p for p in plans or [] if abs(float(p["risk_pct"]) - default_risk_pct) < 1e-9), None
    )
    if chosen is None or not chosen.get("ok"):
        missing.append("risk_plan")
    entry = signal.entry_price
    return {
        "side": signal.decision.value,
        "entry_basis": "ask" if signal.decision is TradeDecision.BUY else "bid",
        "planned_entry": entry,
        "sl": signal.stop_loss,
        "tp1": signal.take_profit,
        "tp2": signal.take_profit_2,
        "rr_net": signal.risk_reward,
        "required_win_rate": signal.required_win_rate,
        "default_risk_pct": default_risk_pct,
        "lots": None if chosen is None else chosen.get("lots"),
        "risk_amount": None if chosen is None else chosen.get("risk_amount"),
        "potential_tp_value": None if chosen is None else chosen.get("gain_at_tp"),
        "expires_at": None if signal.signal_expiry is None else signal.signal_expiry.isoformat(),
        "seconds_to_expiry": seconds_to_expiry,
        "expired": expired,
        "invalidation": signal.invalidation,
        "strategy_version": signal.strategy_version,
        "setup_id": signal.setup_id,
        "complete": not missing,
        "missing": missing,
    }


# ---- hero ---------------------------------------------------------------------------------------


def hero_state(  # noqa: PLR0911 - one return per product state, in priority order
    *,
    signal: TradingSignal | None,
    conditions: list[dict[str, str]],
    expired: bool,
    plan: dict[str, Any] | None,
    position: dict[str, Any] | None,
    last_exit: dict[str, Any] | None,
    market_open: bool,
    now: datetime,
) -> dict[str, Any]:
    """BUY READY / SELL READY / SETUP ARMED / POSITION OPEN / EXITED / WAIT / and the non-WAIT
    states (UNAVAILABLE, STALE, MARKET CLOSED, NOT ACTIONABLE, EXPIRED SETUP)."""
    codes = {c["code"] for c in conditions if c["severity"] == "ERROR"}

    def hero(
        state: str, label: str, tone: str, detail: str, side: str | None = None
    ) -> dict[str, Any]:
        return {"state": state, "label": label, "tone": tone, "detail": detail, "side": side}

    faults = sorted(codes & set(UNTRUSTED_FAULT))
    if signal is None or faults:
        why = ", ".join(faults) if faults else "the engine has not produced a decision yet"
        return hero("UNAVAILABLE", "DECISION UNAVAILABLE", "error", f"Not WAIT: {why}")
    stale = sorted(codes & set(UNTRUSTED_STALE))
    if stale and market_open:
        return hero(
            "STALE",
            "STALE — NOT ACTIONABLE",
            "error",
            f"Data cannot be trusted: {', '.join(stale)}",
        )
    if not market_open:
        return hero(
            "MARKET_CLOSED", "MARKET CLOSED", "neutral", "The market is closed; no decision is made"
        )
    if position is not None and position.get("status") == "OPEN":
        side = str(position.get("side"))
        return hero(
            "POSITION_OPEN", f"POSITION OPEN — {side}", "info", "A paper position is open", side
        )
    if signal.decision is not TradeDecision.WAIT:
        side = signal.decision.value
        if expired:
            return hero(
                "EXPIRED_SETUP",
                "EXPIRED SETUP",
                "warn",
                f"The {side} plan is no longer valid",
                side,
            )
        if plan is None or not plan["complete"]:
            missing = ", ".join(plan["missing"]) if plan else "plan"
            return hero(
                "NOT_ACTIONABLE",
                "SETUP DETECTED — NOT ACTIONABLE",
                "warn",
                f"{side} setup, but the plan is incomplete: {missing}",
                side,
            )
        return hero(
            f"{side}_READY",
            f"{side} READY",
            "buy" if side == "BUY" else "sell",
            "M5 trigger confirmed; plan complete",
            side,
        )
    if signal.metadata.get("setup_phase") == "ARMED":
        return hero(
            "SETUP_ARMED",
            "SETUP ARMED",
            "info",
            "An M15 setup is armed; waiting for the M5 trigger",
        )
    if last_exit is not None:
        closed_at = datetime.fromisoformat(str(last_exit["closed_at"]))
        if now - closed_at <= timedelta(minutes=EXIT_BANNER_MINUTES):
            return hero(
                "EXITED",
                f"EXITED — {last_exit['exit_reason']}",
                "info",
                f"Last paper trade {last_exit['trade_id']} closed",
            )
    return hero("WAIT", "WAIT", "neutral", "The engine evaluated and chose no trade")


# ---- funnel -------------------------------------------------------------------------------------


def funnel(
    records: Iterable[dict[str, Any]],
    signals: Iterable[dict[str, Any]],
    trades: Iterable[dict[str, Any]],
    day: datetime,
) -> dict[str, Any]:
    """Where the trading funnel stops today, from server telemetry (never built in the browser)."""
    rows = list(records)
    armed: set[str] = set()
    outcome: dict[str, set[str]] = {"TRIGGERED": set(), "EXPIRED": set(), "INVALIDATED": set()}
    first = Counter[str]()
    for r in rows:
        phase, armed_at = r.get("setup_phase"), r.get("armed_at")
        if armed_at and phase in ("ARMED", "TRIGGERED", "EXPIRED", "INVALIDATED"):
            armed.add(str(armed_at))
            if phase in outcome:
                outcome[phase].add(str(armed_at))
        if r.get("decision") == "WAIT" and r.get("refusals"):
            first[REFUSAL_GROUPS.get(r["refusals"][0], "OTHER")] += 1
    sigs = list(signals)
    today = f"{day.astimezone(UTC):%Y-%m-%d}"
    mine = [
        t
        for t in trades
        if str(t.get("created_at", ""))[:10] == today and t["status"] != "CANCELLED"
    ]
    exits = Counter(str(t.get("exit_reason")) for t in mine if t["status"] == "CLOSED")
    return {
        "day": today,
        "decisions": len(rows),
        "armed_setups": len(armed),
        "triggered_setups": len(outcome["TRIGGERED"]),
        "expired_setups": len(outcome["EXPIRED"]),
        "invalidated_setups": len(outcome["INVALIDATED"]),
        "actionable_buy": sum(1 for s in sigs if s.get("side") == "BUY"),
        "actionable_sell": sum(1 for s in sigs if s.get("side") == "SELL"),
        "paper_opens": len(mine),
        "paper_exits": sum(exits.values()),
        "exit_reasons": dict(exits),
        "refusals": {g: first.get(g, 0) for g in REFUSAL_GROUP_ORDER},
        "top_refusals": [[g, n] for g, n in first.most_common(5)],
    }


# ---- forward acceptance -------------------------------------------------------------------------

FORWARD_TEXT = {
    "F0": "no live actionable setup observed yet",
    "F1": "a live setup was seen; no paper trade opened from it",
    "F2": "a live paper trade is open or was opened; none completed",
    "F3": "one live paper trade completed",
    "F4": "several live paper trades completed with no correctness failure",
}
F4_MIN_TRADES = 3
REQUIRED_CLOSE_FIELDS = ("exit_reason", "exit_price", "net_pnl", "r_multiple", "mfe_r", "mae_r")


def read_all_signals(root: Path) -> list[dict[str, Any]]:
    """Every logged actionable decision (all days) of this root."""
    out: list[dict[str, Any]] = []
    for path in sorted(root.glob("signals-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict):
                out.append(value)
    return out


def forward_acceptance(
    signals: Iterable[dict[str, Any]], trades: Iterable[dict[str, Any]], *, source_mode: str
) -> dict[str, Any]:
    """F0..F4 from LIVE evidence only. Replay and fixtures can never raise this level."""
    if source_mode != "LIVE":
        return {
            "level": "F0",
            "text": "not a live run (acceptance replay): no live evidence",
            "live": False,
            "counts": {},
        }
    live_signals = [s for s in signals if s.get("source_mode", "LIVE") == "LIVE"]
    live_trades = [
        t
        for t in trades
        if t.get("source_mode", "LIVE") == "LIVE" and t["status"] in ("OPEN", "CLOSED")
    ]
    closed = [t for t in live_trades if t["status"] == "CLOSED"]
    failures = [
        t["trade_id"] for t in closed if any(t.get(f) is None for f in REQUIRED_CLOSE_FIELDS)
    ]
    level = "F0"
    if live_signals:
        level = "F1"
    if live_trades:
        level = "F2"
    if closed:
        level = "F3"
    if len(closed) >= F4_MIN_TRADES and not failures:
        level = "F4"
    return {
        "level": level,
        "text": FORWARD_TEXT[level],
        "live": True,
        "counts": {
            "live_setups": len({s.get("setup_id") for s in live_signals}),
            "paper_opened": len(live_trades),
            "paper_completed": len(closed),
            "correctness_failures": len(failures),
        },
    }
