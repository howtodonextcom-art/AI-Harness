# ADR-0028: TradingSignal contract v2 (additive)

Status: **ACCEPTED** (2026-10-11). Full rationale: `docs/decisions/drafts/0028-trading-signal-contract-v2-additive.md`.

- Write path sets `schema_version=2` plus `source_mode`, `setup_phase`, `entry_basis`,
  `equity_basis`. Existing field names stay (`entry_price` / `stop_loss` / `take_profit` /
  `risk_reward` / `evidence_status`) with aliases `entry` / `sl` / `tp` / `rr` / `evidence_label`.
- Journals: `read_signal_record` (`extra=ignore`) reads v1 and v2. Unknown versions fail
  validation (`schema_version` not in {1, 2}). No silent coercion.
- Evidence can never be `VALIDATED` on this operational baseline.
