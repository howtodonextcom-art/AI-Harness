"""Canonical ExecutionIntent: copy geometry from TradingSignal. Adapters must not reprice.

The paper desk already consumes ``TradingSignal`` directly. Demo and Funded adapters may only
translate this intent. They may not recompute direction, entry, SL, TP or invent a risk model.
Spread is applied once, by the engine (ASK for BUY, BID for SELL). A second spread adjustment
downstream is a bug.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from xau_edge.trading.schema import SCHEMA_VERSION, TradeDecision, TradingSignal

INTENT_SCHEMA_VERSION = 1


class ExecutionIntent(BaseModel):
    """One execution request derived only from a TradingSignal (no second pricing)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = INTENT_SCHEMA_VERSION
    signal_id: str
    setup_id: str
    symbol: str
    decision: TradeDecision
    side: Literal["BUY", "SELL"] | None
    entry: float | None
    entry_basis: Literal["ASK", "BID", "UNKNOWN"]
    sl: float | None
    tp: float | None
    rr: float | None
    risk_pct: float | None
    risk_amount: float | None
    lots: float | None
    expiry: datetime | None
    invalidation: str | None
    strategy_id: str
    strategy_version: str
    evidence_label: str
    source_mode: str
    code_version: str
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    refusal_reasons: tuple[str, ...] = ()
    dry_run: bool = True
    provenance: dict[str, str | float | int | None] = Field(default_factory=dict)

    @property
    def actionable(self) -> bool:
        return self.side is not None and self.entry is not None and self.sl is not None


def intent_from_signal(signal: TradingSignal, *, dry_run: bool = True) -> ExecutionIntent:
    """Copy levels from the signal. Never add spread. Never flip the side."""
    side: Literal["BUY", "SELL"] | None
    if signal.decision is TradeDecision.BUY:
        side = "BUY"
    elif signal.decision is TradeDecision.SELL:
        side = "SELL"
    else:
        side = None
    basis = signal.entry_basis
    if side == "BUY" and basis == "UNKNOWN" and signal.ask is not None:
        basis = "ASK"
    if side == "SELL" and basis == "UNKNOWN" and signal.bid is not None:
        basis = "BID"
    return ExecutionIntent(
        signal_id=signal.signal_id,
        setup_id=signal.setup_id,
        symbol=signal.symbol,
        decision=signal.decision,
        side=side,
        entry=signal.entry_price,
        entry_basis=basis,
        sl=signal.stop_loss,
        tp=signal.take_profit,
        rr=signal.risk_reward,
        risk_pct=signal.risk_pct,
        risk_amount=signal.risk_amount,
        lots=signal.position_size,
        expiry=signal.signal_expiry,
        invalidation=signal.invalidation,
        strategy_id=signal.strategy_id,
        strategy_version=signal.strategy_version,
        evidence_label=signal.evidence_status.value,
        source_mode=signal.source_mode,
        code_version=signal.code_version,
        reasons=signal.reasons,
        warnings=signal.warnings,
        refusal_reasons=tuple(r.value for r in signal.refusal_reasons),
        dry_run=dry_run,
        provenance={
            "schema_version": signal.schema_version,
            "intent_schema": INTENT_SCHEMA_VERSION,
            "contract_schema": SCHEMA_VERSION,
            "generated_at": (
                None if signal.generated_at is None else signal.generated_at.isoformat()
            ),
        },
    )


class PaperAdapter:
    """Operational adapter: hands the intent to the paper desk without repricing."""

    name = "paper"

    def translate(self, intent: ExecutionIntent) -> dict[str, Any]:
        return {
            "adapter": self.name,
            "dry_run": True,
            "symbol": intent.symbol,
            "side": intent.side,
            "setup_id": intent.setup_id,
            "signal_id": intent.signal_id,
            "entry": intent.entry,
            "entry_basis": intent.entry_basis,
            "sl": intent.sl,
            "tp": intent.tp,
            "risk_pct": intent.risk_pct,
            "lots": intent.lots,
            "expiry": None if intent.expiry is None else intent.expiry.isoformat(),
        }


class DemoDryRunAdapter:
    """DRY-RUN only. Translates format. Never sends an order. Never recalculates geometry."""

    name = "demo_dry_run"
    enabled = False

    def translate(self, intent: ExecutionIntent) -> dict[str, Any]:
        return {
            "adapter": self.name,
            "dry_run": True,
            "would_send": False,
            "symbol": intent.symbol,
            "side": intent.side,
            "setup_id": intent.setup_id,
            "signal_id": intent.signal_id,
            "entry": intent.entry,
            "entry_basis": intent.entry_basis,
            "sl": intent.sl,
            "tp": intent.tp,
            "rr": intent.rr,
            "risk_pct": intent.risk_pct,
            "expiry": None if intent.expiry is None else intent.expiry.isoformat(),
            "evidence": intent.evidence_label,
            "source_mode": intent.source_mode,
            "refusal_reasons": list(intent.refusal_reasons),
        }


class FundedAdapter:
    """Contract only. Always disabled. Never sends an order."""

    name = "funded"
    enabled = False

    def translate(self, intent: ExecutionIntent) -> dict[str, Any]:
        return {
            "adapter": self.name,
            "dry_run": True,
            "would_send": False,
            "enabled": False,
            "blocked": "FUNDED_DISABLED",
            "symbol": intent.symbol,
            "side": intent.side,
            "setup_id": intent.setup_id,
            "signal_id": intent.signal_id,
        }
