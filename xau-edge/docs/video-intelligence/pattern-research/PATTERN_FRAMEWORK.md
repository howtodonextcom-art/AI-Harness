# Pattern framework: design decision

Question: how should chart-pattern detectors share a contract so that more patterns can be added
safely, without any of them being able to look at the future or to pass for a signal?

## Criteria (fixed before comparing the options)

| Criterion | Weight | Meaning |
|---|---|---|
| Causality | 3 | Can a detector be proven unable to use data after the detection bar? |
| Testability | 3 | Can the same proof and the same contract tests be reused for every detector? |
| Traceability | 2 | Does a detection say which points, when each became knowable, and under which definition? |
| Reusability | 2 | Can a new pattern be added without touching the others? |
| Visualisation compatibility | 1 | Can a chart draw it without implying more than is known? |
| Performance | 1 | Linear in the number of bars on research-sized series |

## Options

| Option | Causality | Testability | Traceability | Reusability | Visualisation | Performance | Score (0-5, weighted /12) |
|---|---|---|---|---|---|---|---|
| A. One function per pattern returning its own tuple type (what `wolfe.py` started as) | 3: depends on each author | 2: every pattern needs its own proof | 2: fields differ | 2 | 2: needs an adapter per pattern | 5 | 2.6 |
| **B. A shared `PatternDetection` contract plus an empirical causality harness; detectors stay vectorised functions** | 4: enforced by one test that runs on every detector | 5: one harness, same invariants | 5: three time stamps, point confirmation times, definition id | 4 | 4: points carry `confirmed_at` | 4 | 4.4 |
| C. Streaming detectors with an explicit `update(bar)` state machine | 5: causal by construction | 4 | 4 | 3: each pattern is a class with state | 4 | 4 | 4.1 |

Selected: **B**. C is the strongest on causality but costs a rewrite of the existing vectorised
research code and is not needed to *prove* causality: the harness proves it on data. The two reversal
detectors were written in the streaming style inside a vectorised function (one pass over the bars, a
pattern is "armed" until a later close triggers it), which gets most of C's guarantee without the
class machinery. If a future detector cannot be expressed that way, C is the escape hatch.

## The contract (`structure/detection.py`)

`PatternDetection` carries: `pattern_id` (deterministic), `pattern_type`, `bias` (the textbook
implication, not advice), `points` (label, bar, price, **confirmed_at**), and three bar indexes kept
apart on purpose:

* `geometry_known_at`: the last point of the geometry became confirmed;
* `detected_at`: the whole pattern including its trigger event is known;
* `actionable_at`: the close of this bar is the earliest moment to act.

It also carries `trigger_bar` and `trigger_delay_bars` (how late the detection is versus the textbook
trigger), `geometry_fit` (fit to the definition's tolerances, explicitly not a probability),
`source_definition`, `reference_levels` (labelled geometry such as "invalidation_reference", never
orders), and two constants a detector cannot change: `evidence = "GEOMETRY_ONLY"` and
`outcome_evidence = "NONE"`. A validator rejects disordered times and a point confirmed after the
geometry was "known". The model is frozen.

Detector quality and strategy quality are separate by construction: a detection says the geometry was
found and when it was knowable; it says nothing about what happens next, and a UI must not collapse
the two (a research overlay must not look like a trade recommendation).

## The causality harness

`causality_violations(detect, high, low, close, cuts)` runs the detector on the data up to each cut
and requires the output to equal the full run's detections whose `actionable_at <= cut`. It is applied
to every detector on seeded random walks, and it is checked to be non-vacuous: mutants that peek
(a pivot treated as known when it forms; a trigger scan that runs past the available data; a
detection reported when its last point forms) make it fail, and a mutant that ignores supersession
fails a separate no-duplicate property.

Results: Wolfe 2,520 cuts over 40 series, 0 violations; the look-ahead mutant gave 49.

## Shared plumbing

`structure/pivots.py` is the single place that turns swings into pivots and applies the confirmation
lag (`confirmed_at = bar + right`), plus `alternate()`, which reports a superseded pivot so a detector
can retire anything built on it. `structure/pattern_stats.py` computes frequency, geometry, timing and
overlap from detections only; it is given no prices, so it cannot compute outcomes.

## Not built

Streaming class detectors (option C), a registry that auto-discovers detectors, drawing code for a
chart overlay, and any link to the trading engine (none is allowed in this phase).
