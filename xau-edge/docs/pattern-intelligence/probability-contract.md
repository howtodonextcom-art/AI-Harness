# Probability contract

Implemented in `src/xau_edge/decision_research/probability.py`, tested, **not wired to anything**.

## Principle

A probability is either evidence-backed or it is `null`. No function in the package turns a pattern, a shape, an R:R, a "confidence", a social frequency or a model intuition into a number (a test scans the package for such functions). `BUY 72%`, `SELL 30%` or `Confidence 87%` must never be produced from geometry.

## Three different probabilities, never interchanged

| Probability | Meaning | Status |
|---|---|---|
| Pattern completion | P(a developing structure reaches confirmation) | only a descriptive frequency exists (below); not a forecast and not published |
| Direction | P(price is higher / lower after a horizon) | none |
| Trade success | P(take profit before stop loss within horizon T given the proposed BUY or SELL) | none; this is the only one a decision may use, and it needs an authorised study |

Descriptive completion frequency, as a structure statistic only: on Development-2 H1, of 3,456 double top/bottom structures that reached POSSIBLE, 8.3% reached CONFIRMED, 24.2% reached NEAR_CONFIRMATION and 31.7% DEVELOPING (a Gaussian random walk gives 6.5% confirmed; the block-shuffled null was not run for the lifecycle). That shows how rarely a "possible" pattern completes (so POSSIBLE is mostly noise); it must **not** be shown as "probability of completion" to a user and says nothing about price after confirmation.

## Required fields

`TradeSuccessProbability`: `side`, `estimate`, `ci_low`, `ci_high`, `sample_n`, `horizon_minutes` (no horizon, no probability), `calibration_status` (UNVALIDATED, DEVELOPMENT, OOS_CALIBRATED, FORWARD_CALIBRATED), `evidence_ref` (the study). The estimate must lie inside its interval. `DecisionProbability` holds `buy_success`, `sell_success`, a status and a note; **unvalidated means every number is null**.

## Publication rule

A probability may be shown only if (all enforced by `publication_problems`): calibration status is OOS_CALIBRATED or FORWARD_CALIBRATED (DEVELOPMENT is never published); the sample is at least a preregistered minimum; the confidence interval is no wider than a preregistered maximum. Otherwise: probability hidden, reason shown ("INSUFFICIENT_SAMPLE", "CALIBRATION_DEVELOPMENT", "PROBABILITY_UNAVAILABLE", "CONFIDENCE_INTERVAL_TOO_WIDE"), action WAIT.

Required margin: `required_probability = break_even + calibration_margin + uncertainty_margin`, both margins preregistered, so a trade is never taken at mere break-even.

## Calibration requirements for a future programme

Frozen before any out-of-sample result is read: the calibration method (Platt/logistic or isotonic or another justified one), the metrics (Brier score, log loss, reliability curve, ECE where useful), the horizon, the cost model, the minimum sample, the era and regime stability criteria, and the interval method. Trade-specific targets (P(TP before SL within T | proposed BUY)) are preferred over generic "market up" probabilities.

## What the UI may say before validation

Educational wording only, for example: "Mẫu hình Double Bottom đang hình thành. Tiến độ hình thành: 75%. Chưa xác nhận. Cần neckline break để hoàn chỉnh. Hành động: CHỜ." The progress figure is a **structural milestone count** (25, 50, 75, 100) labelled FORMATION_PROGRESS; it is not a win probability and not a completion probability. It must never say "BUY 72%". Research overlays must not look like trade recommendations.

## What a validated UI could show (not available, not authorised)

Action; pattern and formation status; entry, stop, target; net R:R (for example 2.25R); the break-even rate (for example 34%); estimated success with its interval and N; expected value in R; the evidence level; or WAIT with "no side exceeds the authorisation threshold". Today the correct output for every one of these fields except the formation status is "unavailable".
