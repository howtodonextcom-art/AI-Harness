# ADR-V2-016: CONTROL_V1_COMPAT and Candidate V2

Status: accepted (Gate A, 2026-10-13, conditional). Spec: `docs/research/cand_v2_spec.json`.

## Decision
- `CONTROL_V1_COMPAT` is `core/decision.py:decide` with default config (baseline v1.1.0). It is immutable and pinned by `tests/unit/test_strategy_lock.py`.
- The candidate (`xau_mtf_cv2`, `2.0.0-cand.1`) is a separate package that CALLS the control's `decide()`; it never edits it. Chain labels, stop, targets, net R:R and sizing are the control's code. With every flag off it equals the control (parity test).
- CORE changes: C1 lifecycle memory, C2 cost-per-risk gate, C3a drop LOW volatility percentile gate, C3b replace the HIGH gate by a SHOCK guard. Exploratory (Dev only, cannot enter the frozen candidate): C7; C4, C5, C6 not implemented.
- Not automatic: the seven changes are never merged. The frozen candidate is chosen by the preregistered rule.

## Invariants (unchanged)
`MIN_NET_RR 1.5`, `R_MULTIPLE 2.0`, risk 0.25%, broker stop constraints, daily loss governor, PAPER only, Human final authority.

## Consequences
- CAND-CORE changes gating and lifecycle, not the labels that decide direction/setup/trigger. It is not claimed to be a new brain; that is a finding for the report.
- Frequency is never an objective. Reachability is measured separately from executed trades and from expectancy.
- Confirmation: Validation 2019-2021 and Confirm-C 2025-05..2026-04, ONE look each, after the freeze, success on both. Test-H and Holdout stay locked; no authority to open them.
- Costs: planning gate (net_rr), screen (cost_R) and accounting (realised PAPER fills) are three separate things; only the realised PnL enters the endpoint.
