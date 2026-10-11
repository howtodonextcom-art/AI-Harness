# ADR-0026: One canonical brain — TradingSignal → ExecutionIntent

Status: **ACCEPTED** (2026-10-11). Full rationale: `docs/decisions/drafts/0026-canonical-brain-direct-intent.md`.

Implemented:

- `TradeEngine` / `decide()` remains the only live PAPER decision path.
- `intent_from_signal` copies geometry; adapters (`PaperAdapter`, `DemoDryRunAdapter`,
  `FundedAdapter`) must not reprice. Demo is dry-run only; Funded is disabled.
- `trading/adapter.py` and `signals.engine.generate_signal` are **DEPRECATED — READ ONLY /
  MIGRATION PENDING**. Legacy `/paper/*` and `demo_trader.py` stay until parity is proven
  on a live window (synthetic harness already exists: `scripts/decision_parity.py`).
- BUY spread is applied once (engine ASK). Feeding `to_legacy_signal` into `SignalBridge`
  remains a known double-spread bug; that path is not used for execution.
