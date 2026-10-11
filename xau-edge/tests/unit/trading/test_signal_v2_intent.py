"""TradingSignal v2 (additive) and ExecutionIntent: no second pricing, no silent coercion."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.unit.trading.helpers import SPEC, aligned_state
from xau_edge.trading.baseline import DecisionContext, decide
from xau_edge.trading.execution_intent import (
    DemoDryRunAdapter,
    FundedAdapter,
    PaperAdapter,
    intent_from_signal,
)
from xau_edge.trading.schema import (
    SCHEMA_VERSION,
    EvidenceLabel,
    TradeDecision,
    TradingSignal,
    read_signal_record,
)

CTX = DecisionContext(spec=SPEC, equity=100_000.0, source_mode="LIVE", bid=2000.0, ask=2000.25)


def test_old_journal_records_read_as_schema_version_1() -> None:
    rec = read_signal_record({"signal_id": "abc", "decision": "WAIT", "symbol": "XAUUSD"})
    assert rec.schema_version == 1
    assert rec.source_mode == "UNKNOWN"


def test_v2_signal_carries_source_and_aliases() -> None:
    s = decide(aligned_state(), CTX)
    assert s.schema_version == SCHEMA_VERSION
    assert s.source_mode == "LIVE"
    assert s.entry == s.entry_price
    assert s.sl == s.stop_loss
    assert s.tp == s.take_profit
    assert s.rr == s.risk_reward
    assert s.evidence_label is EvidenceLabel.UNVALIDATED_BASELINE
    if s.decision is TradeDecision.BUY:
        assert s.entry_basis == "ASK"


def test_unknown_schema_version_is_refused() -> None:
    s = decide(aligned_state(), CTX)
    with pytest.raises(ValidationError):
        TradingSignal(**{**s.model_dump(), "schema_version": 99})


def test_intent_copies_geometry_and_does_not_add_spread() -> None:
    s = decide(aligned_state(), CTX)
    assert s.decision is TradeDecision.BUY
    assert s.entry_price is not None
    intent = intent_from_signal(s)
    assert intent.side == "BUY"
    assert intent.entry == s.entry_price
    assert intent.sl == s.stop_loss
    assert intent.tp == s.take_profit
    assert intent.entry_basis == "ASK"
    assert intent.dry_run is True
    # same snapshot, same signal, same intent — no second ask/spread bump
    again = intent_from_signal(s)
    assert again.entry == intent.entry
    assert again.model_dump() == intent.model_dump()


def test_demo_dry_run_consumes_canonical_intent_without_repricing() -> None:
    s = decide(aligned_state(), CTX)
    intent = intent_from_signal(s)
    translated = DemoDryRunAdapter().translate(intent)
    assert translated["dry_run"] is True
    assert translated["would_send"] is False
    assert translated["entry"] == intent.entry
    assert translated["sl"] == intent.sl
    assert translated["tp"] == intent.tp
    paper = PaperAdapter().translate(intent)
    assert paper["entry"] == intent.entry
    funded = FundedAdapter().translate(intent)
    assert funded["blocked"] == "FUNDED_DISABLED"
    assert funded["would_send"] is False
