# ADR-0017: Signal engine and the evidence gate

Status: accepted (2026-10-08)

**Principle (brief sections 2 and 56).** Forecasting and the trading decision are separate layers.
The forecast is a set of probabilities with their provenance; the decision layer applies explicit
checks and may answer WAIT for any of twelve reasons. A refusal is a complete, valid output.

**Evidence gate.** After Checkpoint 1 no strategy or model passed the pre-registered criteria. The
decision layer therefore requires `EvidenceStatus.VALIDATED`, computed from the experiment registry:
some configuration's LATEST record must have passed in development, validation AND test. Without it the
final direction is WAIT with reason `NO_VALIDATED_EDGE`, while the analysis (`candidate_direction`,
probabilities, expected value, levels, explanation) is still shown so the user can see what the
evidence says. The schema enforces the invariant: a BUY/SELL object cannot be constructed with refusal
reasons or without validated evidence.

**Probabilities.** From the historical analogues (empirical frequencies of what followed the 20 most
similar earlier windows, leakage rule of ADR-0013), labelled "uncalibrated frequencies". No
percentage is presented as confidence; a calibrated model would replace this source only after it
passes ADR-0016's rule.

**Expected value.** Mean barrier-trade R of the analogues for the chosen side (gross) minus friction
in R (one spread plus two slippage fills over the stop distance); must exceed `min_ev_r` (0).

**Fail safe.** Unknown regime, unknown news state (no calendar) and non-finite or inconsistent
inputs are refusals, never silent passes.

**Reproducibility.** Inputs are digested (`inputs_hash`) and the git commit is stored; the same
data at the same decision time yields the same signal, and bars after the decision time cannot change
it (tests truncate the data).

**Not in scope.** The risk engine (sizing, prop limits, kill switch) is applied separately, after
the signal, by the paper broker and any future executor.
