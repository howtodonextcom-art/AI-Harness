# Pattern Research V4: candidate shortlist (proposal only)

**NOT AUTHORIZED.** Edge Program V3 is closed (NO VIABLE EDGE FOUND). The current proposed V4 entry-geometry floor is **1.5 net R:R**, not 2.0; it is necessary and not sufficient. No edge, probability, or profitability is claimed.

## Verdict on the candidates

| Candidate | Class | Reason |
|---|---|---|
| Double Top / Bottom (incl. Adam and Eve), neckline close | FUTURE RESEARCH CANDIDATE, **low prior, conditional** | best new rubric score; enough events (287 in Development-2 H1); the textbook exit gives gross R:R about 0.72 and cannot meet the 1.5 net floor; do not stretch its target or tighten its invalidation stop to rescue it |
| Wolfe Wave (P5 or reclaim entry) | DETECTOR ONLY | disputed rules; the displayed R:R exists only with an extreme entry; the causal entries are at least 3 bars after P5 |
| Head and Shoulders | DETECTOR ONLY | 7 events in 8 years of H1: untestable |
| Falling / rising wedge, triangle, flag, cup and handle, diamond, harmonics | DOCUMENT ONLY | no detector; Bulkowski's statistics for wedges are weak or the worst; line fitting adds freedom |
| Break-and-retest | REJECT as new research | overlaps V2 H08 |
| Liquidity sweep / failed breakout | REJECT as new research | is V2 H07 |
| F1 opposite direction | POST-HOC, NOT VALIDATED, NOT AUTHORIZED | not a pattern programme, and not touched |

## Does any pattern provide earlier, causal information than the M5 trigger?

None demonstrated. Every causal trigger in this family carries a pivot confirmation lag (3 bars for the right-hand window on the pattern's own timeframe) and then waits for a boundary close (double top median +7 H1 bars, head and shoulders +1). Wolfe's reclaim variant adds a median of 0 extra bars after P5 is confirmed on a synthetic walk: the confirmation lag itself dominates. The reels' entries at Wolfe's P5 and at the butterfly's D are "earlier" only by acting before the point can be known (a hindsight drawing). A lower timeframe could produce a trigger sooner in wall-clock time, but with the same lag in its own bars and with a smaller structure, a worse cost-to-risk ratio.

## Candidate specification template (every field is mandatory before a charter)

Applied to the only conditional candidate. Items marked **TO FIX** must be preregistered before any outcome is read.

| Field | Double Top / Bottom (neckline close) |
|---|---|
| Mechanism | a second failed attempt at a level followed by a closed-bar break might mark exhaustion; supported only by folklore here (low prior) |
| Detector | `structure/reversal.py` (DOUBLE) with defaults; lifecycle in `formation.py` |
| Direction | each pattern keeps its textbook bias; no reverse-direction analysis |
| Actionable timestamp | the close of the neckline-break bar (`actionable_at`); first executable price is the next open |
| Entry | next-bar open after the neckline close, plus the measured spread and slippage |
| Stop | **TO FIX**: the invalidation reference (the peak) gives risk about one pattern height plus the break distance |
| Target | Textbook measured move only; if it cannot reach 1.5 net R with credible room, WAIT / REJECT |
| Minimum net R:R | 1.5 after spread, slippage, commission, swap; current proposed geometry floor, not a profitability claim |
| Time exit | **TO FIX**: a horizon, also the horizon of any probability |
| Cost model | the project's measured cost model (`foundation/cost_model_v2.json`) |
| Probability target | P(TP before SL within T), calibrated out of sample; none exists today |
| EV gate | EV in R above a preregistered positive threshold, and probability above break-even plus margins |
| Parameter budget | seven detector parameters at defaults, one variant per direction rule: K grows only by the registered variants |
| Frequency estimate | about 59 detections per 10,000 H1 bars (143 tops and 144 bottoms in 8 years), 12.5% overlap with the previous |
| Minimum sample | **TO FIX** after a power calculation; non-overlapping events only |
| Development split | Development-2 (burned) as a development set only |
| Validation split | Validation-2 (2019-2021), untouched, opened once |
| Test-H policy | locked; one run, after a frozen record and independent review; alpha 0.05 / (44 + new K) |
| Holdout policy | locked; last; same rule |
| K accounting | K_total is 44 today (21 + 20 + 3); every registered variant adds |

## What must hold before any of this is authorised

A mechanism with support beyond folklore; a causal entry, valid structural stop and realistic target that reach at least 1.5 net R with credible room; a sample large enough for preregistered power; a cost model that is verified and complete; untouched evaluation data (see `contamination-map.md`); and the decision of the owner. The floor alone is not edge or probability.
