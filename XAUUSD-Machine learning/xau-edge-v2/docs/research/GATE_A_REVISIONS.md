# Gate A revisions: what changed, what contradicted, how it was resolved

Date: 2026-10-13. Decision: CONDITIONAL APPROVAL. Spec: `cand_v2_spec.json` (frozen when hashed).

| # | Change | Reason |
|---|---|---|
| 1 | The seven changes are no longer merged. CORE = C1, C2, C3a, C3b (+ guards). C4/C5/C6/C7 exploratory; C7 (geometry) gets research priority, Dev-only | owner condition 1 |
| 2 | Cost accounting split into planning gate / screen / realised charges; cost_R defined exactly | double-counting |
| 3 | Control-relative comparison replaced by incremental-trade analysis plus absolute safety caps; difference test only when both arms have N >= 30 | the control has too few trades |
| 4 | Three-state outcome status (SUPPORTED / REFUTED_HARM / INCONCLUSIVE) with N_min and N_req | no statistical power |
| 5 | SHOCK, lifecycle invalidation, execution timing, episode-to-trade defined; variant list closed; K accounting, primary endpoint and selection rule locked | owner condition 2 |
| 6 | Power formula corrected and verified by simulation | the old figure had no power term |
| 7 | Validation and Confirm-C usable once each after the freeze; contamination ledger added; Test-H and Holdout locked | owner condition 3 |
| 8 | K_V2_CAND_ML opened as a shadow family | owner condition 4 |

## Contradictions found and how they were resolved
1. **"No new ML family" (earlier instruction) vs ML shadow (now).** Resolved by ADR-V2-017: a new family, shadow only, K=2; ML V0 stays retired.
2. **The Gate A report said the cost cap 0.15 was "derived from the algebra of MIN_NET_RR".** That algebra (spread at most 0.2R) comes from the control's net_rr, which itself deducts the spread although a BUY already enters at the ask. 0.15 is therefore a stated a-priori safety margin, not a derivation. Resolved by defining cost_R from realised friction and by stating the BUY conservatism.
3. **The Gate A report said Validation outcomes were unseen and also that Validation counts were looked at.** Both true: counts seen, outcomes not. The ledger records it; Validation is a blind window for outcomes only.
4. **The Gate A report required both "add-one-in" and "leave-one-out" to support a change.** With so few trades neither can ever be SUPPORTED, so the rule would reject everything or nothing at random. Replaced by the selection rule (structural + safety + not REFUTED_HARM); INCONCLUSIVE is allowed for C1/C2 and flagged for C3.
5. **"At least 150 episodes" and "at least 50 per year" acceptance vs the measured 17 per year.** These are feasibility thresholds, not safety; they stay as REPORTED feasibility lines, not as gates on a change. A candidate that cannot reach 100 forward trades in 24 months is reported as "not verifiable in a reasonable time".
6. **C3a "subsumed by C2" was asserted.** It is a hypothesis; C3a has its own variant (A_C3a, B_C2C3a, LOO_noC3a).
7. **The Gate A report called the candidate a new brain candidate.** CAND-CORE changes gating and lifecycle only; the labels are the control's. Stated in ADR-V2-016.
8. **The 0.15 cap was computed after being written.** The ledger records that the cap was not changed after seeing that it passes 72% of Dev chain signals.
