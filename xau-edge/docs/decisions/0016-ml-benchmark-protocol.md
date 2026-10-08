# ADR-0016: Machine-learning benchmark protocol

Status: accepted (2026-10-08)

**Why run ML at all after Checkpoint 1.** The checkpoint rule says to continue only with evidence;
the owner asked to proceed to completion, so the benchmark is run as a test of whether anything
beats the null, under the same pre-registered criteria, and is allowed to fail.

**Task and label.** Three-class direction of the next 20 M15 bars in ATR units (neutral band 0.5
ATR), the brief's P(up)/P(down)/P(neutral). Known gap: the label is a close-to-close move while the
trade uses a 1.5 ATR stop, 3.0 ATR target and 20-bar hold, so a high probability edge does not imply the
barrier trade wins. A barrier-outcome label is a candidate follow-up (a new variant).

**Models and hyperparameters.** Logistic regression, random forest, XGBoost, LightGBM, fixed settings
(`models/zoo.py`), not searched. Missing values: median imputation in the pipeline (fitted on fit rows
only) for linear and forest models; boosters handle them natively. One thread, fixed seed.

**Walk-forward.** Monthly folds, expanding window, embargo of `horizon` rows between fit, calibration
and test, calibration on the most recent 25% of the training rows, minimum 3,000 fit rows
(see docs/research/model-evaluation.md). Sigmoid (Platt) calibration is the primary variant; isotonic
and none were each run once for comparison and counted in K.

**Decision rule.** Beat the per-fold base rate on both Brier and log loss, and pass all seven edge
criteria on Development and Validation. The unlock for the test period additionally requires the
same dataset ids as the earlier passes.

**Artifacts.** A trained model with its calibrator is stored with the required metadata
(`models/` folder, git-ignored); `approved: False` unless a registry pass exists. joblib files are
pickle-based, so only files written by this project are loaded, after a hash check.

**Known limits.** `beats_base_rate` is a point comparison without an interval; with the edge criteria
in force this is acceptable, but a per-fold test would be stronger. Validation labels near 2026-04-30
look up to 20 bars into the test period (scoring only, not fitting).
