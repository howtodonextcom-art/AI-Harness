"""The owner's override for an UNVALIDATED strategy (decision D2), enforced in the bridge.

Without validated evidence the signal layer answers WAIT with the single reason
``NO_VALIDATED_EDGE`` while still carrying the analysis lean and its levels. The override lets the
bridge act on exactly that case, and only when all of these hold: the override is enabled, the
signal came from the one named strategy, the lean and the levels are present, and NO other refusal
reason is present (news, regime, spread and the rest still block). The resulting intent is labelled
``UNVALIDATED`` everywhere. Nothing here relaxes the risk engine, the safety limits or the
kill switch.
"""

from __future__ import annotations

from dataclasses import dataclass

from xau_edge.signals.schema import Direction, EvidenceStatus, NoTradeReason, Signal

UNVALIDATED_LABEL = "UNVALIDATED"
VALIDATED_LABEL = "VALIDATED"


@dataclass(frozen=True)
class OverridePolicy:
    """Permission to trade one named strategy without validated evidence."""

    enabled: bool
    strategy_id: str

    def permits(self, signal: Signal, strategy_id: str | None) -> Direction | None:
        """The direction to trade when the override applies to ``signal``, else ``None``."""
        if not self.enabled or not self.strategy_id or strategy_id != self.strategy_id:
            return None
        if (
            signal.direction is not Direction.WAIT
            or signal.evidence_status is not EvidenceStatus.NONE
        ):
            return None
        if set(signal.reasons) != {NoTradeReason.NO_VALIDATED_EDGE}:
            return None
        lean = signal.candidate_direction
        levels = (signal.entry_zone, signal.stop_loss, signal.take_profit_1)
        if lean not in (Direction.BUY, Direction.SELL) or any(v is None for v in levels):
            return None
        return lean
