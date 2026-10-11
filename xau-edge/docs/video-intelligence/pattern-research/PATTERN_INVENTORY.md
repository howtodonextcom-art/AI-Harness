# Pattern inventory and prioritisation

Method: `rubric.json` (criteria, weights and the selection rule) was written before `scores.json`; the
script `scripts/pattern_rubric.py` does the arithmetic and the robustness checks, so the table below is
reproducible (`uv run python scripts/pattern_rubric.py`). One rater scored (the research agent); each
score has a one-line rationale in `scores.json`. Scores are judgement, not measurement.

Selection rule, fixed in advance: implement a candidate only if it is not disqualified, scores at least
70 of 100 and is in the top two; at most two; if fewer qualify, implement fewer.

## Result

| Rank | Candidate | Score | Status |
|---|---|---|---|
| 1 | Double Top / Double Bottom | 78.8 | **implemented** |
| 2 | Head and Shoulders / Inverse | 73.8 | **implemented** |
| 3 | Break-and-Retest | 62.5 | not implemented: below 70, and overlaps V2 H08 |
| (4) | Liquidity Sweep + Reclaim | 58.8 | **disqualified**: it is V2 H07 (12 variants, Stage 1 failed) |
| 5 | Wolfe Wave | 57.5 | already implemented in phase 1 (before this rubric) |
| 6 | Triangle | 55.0 | not implemented |
| 6 | Flag / Pennant | 55.0 | not implemented |
| 8 | Cup and Handle | 47.5 | not implemented |
| 9 | Supply / Demand zone interaction | 36.2 | **disqualified**: no formal definition without discretion |
| 10 | Diamond | 33.8 | **disqualified**: no formal definition without discretion |

The Wolfe Wave was built before the rubric existed and scores 57.5; it would not have been selected by
the rule. It stays as a detector because it is already built, tested and documented, and because it is
the subject of the reel, not because it ranks well.

## Robustness

* Weights: each weight multiplied by a random factor in 0.5..1.5, 2,000 draws, seed 11. Double Top is in
  the top two in 100% of draws (rank 1 in 100%), Head and Shoulders in 100%; no other candidate ever
  reaches the top two.
* Scoring error: every score moved by -1/0/+1 with probabilities 0.15/0.70/0.15, 2,000 draws. Double Top
  99.9% in the top two, Head and Shoulders 97.7%, Break-and-Retest 2.4%, Wolfe 0.1%.

So the choice is stable against the weights and mostly stable against single-point scoring mistakes. It
is not independent of the rater's overall view (for example, that a neckline break on a closed bar is an
easy event to detect causally).

## Parameter count, as built (the rubric scored it as "about 6")

Double top/bottom and head and shoulders share seven parameters: `pivot_left`, `pivot_right`,
`equal_tolerance`, `min_height_atr`, `min_bars_between`, `max_pattern_bars`, `max_break_bars`
(plus two fixed constants, ATR period 14 and zero buffers). That is slightly above the "about 6" used in
the score; the effect on the ranking was not re-run (it would not change the order given the margins
above, but it is recorded rather than assumed).

## Notes on the candidates not built

* **Break-and-Retest:** the closest existing mechanism is H08 breakout acceptance and continuation
  (V2). Its appeal here was that it is an entry-timing mechanism; that is a reason to study it inside the
  existing baseline's timing diagnostics, not a reason to add a second detector.
* **Liquidity sweep:** H07 used previous-day and Asia levels in reject and accept modes. A new
  definition of the level would still be the same mechanism.
* **Triangle and flag:** need line fitting or a pole definition; sources disagree on both.
* **Diamond, supply/demand, cup and handle:** no shared geometry or too rare on intraday gold.

## Not a recommendation

None of these patterns has outcome evidence in this repository, and the rubric does not measure
profitability. A high score means "clear to define and safe to detect", nothing more.
