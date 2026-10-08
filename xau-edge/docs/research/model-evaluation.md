# Model evaluation (Epics 11 and 12)

Brief sections 18-20 and 26. Code: `xau_edge.models`, `xau_edge.evaluation.model_runner`. Criteria:
`docs/evals/edge-criteria.md`. Decisions: ADR-0016.

## Protocol

* **Task:** from the state at the close of an M15 bar, predict whether the next 20 bars (5 hours)
  move up, down or neutral (neutral band 0.5 ATR): P(down), P(neutral), P(up).
* **Features:** 54 scale-free columns (returns, distance to EMAs, ADX/DI, RSI, MACD in ATR units,
  stochastic, Bollinger position and width, volatility, candle and volume features, cyclical time,
  session and regime one-hots, market-structure state). No absolute price levels.
* **Models, in the brief's order:** logistic regression, random forest, XGBoost, LightGBM. Fixed,
  modest hyperparameters chosen a priori (ADR-0016); no tuning. No deep models.
* **Walk-forward:** calendar-month folds. For a fold starting at row `f`, fit rows are labelled rows with
  index <= `f - 21` (a 20-bar label is fully known before the fold's first decision); the most recent
  25% of those rows, with another 20-row embargo, calibrate the probabilities (sigmoid/Platt by default;
  isotonic and none were also run once). A fold needs 3,000 fit rows, so the first Development months
  (May-June 2025) are not scored.
* **Scoring:** Brier score and log loss against the no-skill forecast (class frequencies of the fold's own
  fit labels), per-class expected calibration error, raw versus calibrated.
* **Trading evaluation:** signals when the calibrated edge `P(up) - P(down)` is at least 0.15 and the
  chosen side has probability >= 0.40; same backtest, costs and seven edge criteria as the baselines.
* A model counts as better only if it beats the base rate on BOTH Brier and log loss AND passes every
  edge criterion on Development and Validation.

## Results (K = 7 variants counted, then 10 with the extra calibrations)

| Model (sigmoid) | Period | Log loss (base) | Beats base | Trades | Net | PF | Edge criteria passed |
|---|---|---|---|---|---|---|---|
| logistic | Development | 1.0132 (1.0159) | yes, by 0.003 | 418 | +18.96% | 1.14 | 2 / 7 |
| | Validation | 1.0235 (1.0170) | **no** | 264 | -13.71% | 0.81 | 1 / 7 |
| random forest | Development | 1.0172 (1.0159) | no | 563 | -2.24% | 0.99 | 1 / 7 |
| | Validation | 1.0231 (1.0170) | no | 281 | -8.51% | 0.89 | 1 / 7 |
| XGBoost | Development | 1.0199 (1.0159) | no | 539 | -6.63% | 0.95 | 1 / 7 |
| | Validation | 1.0218 (1.0170) | no | 317 | -14.47% | 0.84 | 1 / 7 |
| LightGBM | Development | 1.0211 (1.0159) | no | 561 | +3.06% | 1.02 | 1 / 7 |
| | Validation | 1.0220 (1.0170) | no | 295 | -11.78% | 0.86 | 1 / 7 |

Calibration comparison (logistic): sigmoid log loss 1.013 / 1.024; isotonic 1.153 / 1.055 (it
overfits its small calibration set); no calibration 1.0362 on Validation (overconfident). Sigmoid
calibration is therefore the only variant worth keeping, and even calibrated models do not beat a
forecast that always says "the usual class frequencies".

## Conclusion

No model beats the base rate out of sample, and none passes the edge criteria. The one Development
success (logistic regression: slightly better log loss, +19% in the backtest) did not replicate on the
next four months. **No model is promoted; the test period remains locked.** This is the expected
outcome for noisy 5-hour direction forecasts of a liquid instrument, and it is the result.

## Red-team notes

* Hyperparameters were not searched; a tuned model might look better on Development and would then
  need to prove itself on unseen data with a larger K.
* Features are technical only; no news, order-flow, cross-asset or macro data.
* Calibration on 25% of a monthly-expanding training set is small early in the sample.
* Gold's 2025-26 drift is large; classes are imbalanced by regime, so the base rate itself moves.
