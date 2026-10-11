# Contamination map

Mandatory before any V4 proposal: which data and which people have influenced which choice, and what remains clean.

## Datasets: classification and what was done with each

| Dataset | Class | Access in this phase |
|---|---|---|
| Synthetic random walks and block-shuffled copies | OPEN_DESCRIPTIVE (synthetic) | used for controls, mutation checks and timing mechanics |
| Development-2 H1 (2011-01-01 to 2018-12-31, 48,470 bars) | **BURNED** (consumed by V2 Batch A and V3 F1/F3 Stage 1 outcome tests) | counts-only, geometry and timing statistics: detections per 10,000 bars, leg and span lengths, overlap, confirmation and trigger delays, double top/bottom lifecycle reach rates and invalidation reasons, textbook reference R:R and distance to invalidation at the moment of detection, a block-shuffled null. Run through `descriptive_data.require_descriptive` and a loader that filters inside the scan. Two runs of the same study (phase 2 and this phase), detector defaults unchanged between them; the second added statistics but no parameter was swept on market data |
| Validation-2 (2019-2021) | VALIDATION_PROTECTED (reserved, untouched) | **not opened**; the policy refuses it |
| Test-H (2022-01-01 to 2025-04-30) | TEST_H | **not opened**; refused |
| Holdout (2026-05-01 to 2026-10-07) | HOLDOUT | **not opened**; refused |
| `data/raw` FTMO 2025-05 to 2026-10 and the live ledger | contain the Holdout: FORBIDDEN | **not opened** |
| Any other file | UNKNOWN | not used |

## What influenced which choice

| Choice | Influenced by | Market data involved |
|---|---|---|
| Which patterns to look at | the owner's 29 Reels and the Wolfe reels, X snippets, YouTube, Bulkowski's pages (stock statistics) | none (Bulkowski's numbers are stock studies read from the web) |
| Rubric weights and scores | the author's judgement; rubric v1 and v2 written before scoring | none |
| Detector parameters | textbook conventions, synthetic tests; unchanged after the first Development-2 look | synthetic only |
| Which detectors were kept as DETECTOR ONLY | **partly Development-2 counts** (head and shoulders 7 events; Wolfe frequency) and geometry (textbook R:R of double top about 0.72) | Development-2 detection geometry, no price outcome |
| Direction of each pattern | the textbook bias; the reverse direction was never examined | none |
| The low prior given to double top/bottom | Development-2 reference R:R (a property of the shape at detection) and the null comparison | Development-2 |

So the idea-selection step has seen Development-2 descriptive geometry. That data is already burned for outcomes, which is why it was used; it is no longer a neutral development set for these specific ideas.

## What remains suitable for an honest evaluation

| Space | Suitable? | Condition |
|---|---|---|
| Validation-2 | yes, the cleanest historical data left | opened once, for a registered candidate only; looking at it for ideas would spend it |
| Test-H | yes, once | frozen record, independent review, alpha 0.05 / (44 + new K), one run per candidate |
| Holdout | yes, last | same rule |
| Forward data after 2026-10-07 | yes: it cannot have influenced any idea | needs continuous collection; decision coverage is 48.6% of the 95% gate today |
| Development-2 | development only | never as evidence |

The trial count today is K = 44 (21 + 20 + 3); this phase registered nothing and added no K because no outcome was evaluated.
