# Why the desk said WAIT during the 4186 to 4199 rally (2026-10-11 23:10-23:30 UTC)

Read-only diagnosis. No strategy, gate, parameter or runtime change. No outcome metric used.

## Verdict

**By design, not a bug (confidence about 85%).** Every decision from the open until 23:49 UTC was stopped by the safety gates (execution quality and volatility), which run before the setup chain; the setup/trigger logic was never evaluated. The recomputed state matches the logged state (6 of 7 sampled minutes identical in every field; see 5.).

## 1. Premise correction

4168 was the session-low reference, not the starting price. The move that the screenshot shows is about 4186.6 to 4199.3 in 20 minutes (about 13 points), with M15 ranges of 6.5 and 6.6 in the two largest bars.

## 2. Decisions since open (105 rows, `data/trade/decisions-20261011.jsonl`)

| Item | Count |
|---|---|
| Decisions since the open | 105 (continuous, one per M1) |
| First refusal SPREAD_TOO_WIDE | 100 |
| VOLATILITY_TOO_LOW present | 105 / 105 |
| STALE_DATA | 4 |
| Context during the rally | H1 BULLISH, H4 RANGE, M15 REVERSAL_DOWN or RANGE, M5 FLAT/DOWN |

## 3. Why the gates fired

- Execution quality POOR: M1 spread 38 to 46 points against a 300-bar M5 spread median of 36 and p90 of 44; rule is percentile at or above `wide_spread_percentile` 0.9 (or spread/ATR above 0.15). With `spread_veto` on, this is SPREAD_TOO_WIDE (`baseline.py::_gates`).
- Volatility LOW: M15 ATR14 = 3.77 points, percentile rank 0.045 in the last 200 bars (threshold 0.2, p20 = 4.77, median 6.46). The rally was too short to lift a 14-bar ATR out of the bottom 20%.
- Both gates return before direction, pullback and trigger. So "WAIT" here means "market conditions refused", not "no setup found".

## 4. Classification

| Class | Finding |
|---|---|
| (1) By design | Yes: the gates did what the baseline specifies (thin, wide-spread session after the rollover) |
| (2) Bug | None found: recomputed state equals logged state; decision stream continuous |
| (3) Ops/data | Not a cause. 4 STALE_DATA rows are isolated; coverage 57.83% is a whole-history figure |

## 5. Verification detail

Recomputation with `build_market_state` from the ledger at 22:10, 22:40, 23:05, 23:15, 23:30, 23:45, 23:49: volatility, spread state, H4, H1, M15, M5 equal the log in all but one case. At 23:45 the recompute gave GOOD/GOOD where the log says WIDE; the difference is the spread input (ledger bar spread 38 versus the live tick spread used by the engine). It does not change the verdict because VOLATILITY_TOO_LOW alone still blocks.

## 6. What this does not say

It does not say the gates are well tuned, and a move of this kind says nothing about edge. Whether a rally that raises realized range while the 14-bar ATR is still low should release the volatility gate is a design question. It is recorded only as a V4 research question (does a gate based on ATR percentile lag short bursts?), to be answered on historical data with the pre-registered protocol, not by changing parameters from one session.

## 7. Owner decision (optional)

None required. If you want the screen to say it more plainly, the "CHỜ" reason line could name the gate (spread / low volatility) first; that is a wording change only.
