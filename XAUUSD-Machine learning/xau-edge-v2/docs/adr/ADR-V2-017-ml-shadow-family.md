# ADR-V2-017: ML shadow family K_V2_CAND_ML

Status: accepted (Gate A, 2026-10-13). Supersedes the earlier "no new ML family" instruction ONLY for a shadow with no trading authority.

## Decision
- A new research family `K_V2_CAND_ML`, K = 2 (logistic regression, LightGBM classifier), one-sided 97.5% per comparison, authority NONE (ADR-V2-005 stands).
- The model runs live and forward on the candidate's ARMED states and writes `p_win`, an uncertainty interval, and its disagreement with the rule engine to an append-only log. It cannot create, cancel or modify BUY/SELL/WAIT.
- Label: triple-barrier outcome of the candidate's hypothetical entry, after the PAPER fill rules (stop wins when ambiguous). Features: causal, from the existing state only; no new indicator.
- ML V0 (volatility) stays RETIRED at Validation; its K family stays closed.

## Statistical power (corrected)
`n = DEFF * ((z_alpha + z_beta) * sd / delta)^2` with sd 1.5, DEFF 1.5, alpha 0.025 one-sided, power 0.8: 295 trades for delta 0.30R, 663 for 0.20R, 1178 for 0.15R, 2649 for 0.10R. Monte Carlo (`scripts/research/power.py`) reproduces 0.80. The Gate A figure omitted the power term. At the measured frequency (about 17 episodes a year in the modern window) none of these is reachable on forward data in years, and the confirmation windows are too small. So the expected state of the ML shadow is INCONCLUSIVE for a long time, and it stays SHADOW until a protected window with enough trades is authorised by the owner.

## Acceptance for any authority review (not automatic)
Brier/log-loss better than the base rate with a lower bound above 0; 80% interval coverage inside 75-85%; lift in E of the ML-allowed set of at least +0.15R with lower bound above 0 AND N at least N_req(0.15R); positive in at least 75% of years; replay/live feature parity. Otherwise SHADOW forever.
