# Pattern similarity (Epic 07)

Brief sections 14, 15 and 26. Code: `xau_edge.patterns`. Decisions: ADR-0013.

## What is compared

A pattern is the last `W` bars (20, 30, 50 or 100) expressed as six scale-free channels per bar:
close-to-close change, signed body, upper wick, lower wick and range, each divided by the ATR of the
same bar, plus the tick-volume z-score. Nothing uses absolute prices or any statistic computed over
the whole history, so a window looks the same at 1,800 or 4,000 and in quiet or busy markets, and no
future information can enter through normalisation.

## Methods (one interface: `f(query, candidates) -> distances`)

| Method | Definition | Notes |
|---|---|---|
| `euclidean` | L2 on the flattened window | default; sensitive to amplitude and timing |
| `cosine` | 1 - cos angle | ignores amplitude |
| `pearson` | 1 - correlation | ignores offset and positive scale |
| `dtw` | multivariate dynamic time warping, optional Sakoe-Chiba band | absorbs small timing shifts; about 20x slower |
| `znorm_path` | per-channel z-normalised L2 | the distance the Matrix Profile family uses |
| `mass_distance_profile`, `matrix_profile` | FFT distance profile and a reference self-join | verified equal to the direct computation, including series at a 1e9 price level (inputs are centred first); the self-join is O(n^2 log n), for small series and motif exploration only |

Matrix Profile in the strict sense (STUMPY) is not a dependency: STUMPY pulls in numba, which does
not support every Python version in the CI matrix. The nearest-neighbour search the project needs is
query against history, for which the distance profile above is the building block.

## Leakage rules (the point of this module)

For a query ending at bar `q`, a candidate ending at `e` is admissible only if
`e + H < q - W + 1` with `H` the longest outcome horizon (default 60). That excludes the query, all
windows overlapping it, and every candidate whose outcome would overlap the query window or lie in
its future. The search slices the data to `q + 1` rows before computing anything. Selected
neighbours must be at least `W` bars apart (configurable) so one market episode is not counted many
times. Tests: `tests/unit/patterns/test_search.py` and `tests/statistical/test_pattern_leakage.py`
(future replacement with garbage and NaN for every method on many random queries; no match with an
overlapping outcome; planted future twins and twins inside the forbidden zone are never returned;
planted past twins are found first).

## Benchmark (FTMO demo M15, 34,075 bars, W = 30, H = 60; one query, about 25,000 candidates)

| Method | ms / query |
|---|---|
| cosine | 51 |
| euclidean | 58 |
| pearson | 62 |
| znorm_path | 129 |
| dtw (band 5) | 1,199 |
| plain per-window NumPy loop (euclidean) | 79 |

The vectorised search returns the same nearest neighbour as the loop but is only about 1.3x faster:
the cost is dominated by building the candidate matrix, not by Python overhead. DTW is practical for
sampled queries, not for scanning every bar of a backtest.

## How similar is "similar"? (sanity, not evidence of edge)

On 30 random queries per window size, the best match has a distance about 0.5-0.65 of the median
candidate distance (0.51 for W = 20 up to 0.64 for W = 100). In 6 x W dimensions distances
concentrate, so analogues are only moderately closer than a typical window, and longer windows are
less distinctive. Whether the outcomes after such analogues carry information is tested in Sprint 7,
against the base rate, with these windows and horizons fixed in advance.

## Red-team notes

* Overlapping analogues from the same episode inflate sample size: handled by the separation rule.
* Analogues come from one broker and 17 months, with at most about 25,000 admissible windows per
  query; rare patterns may have no good match (the result reports `best_distance` and `median_distance`).
* Volume z-score is a broker tick count; consider dropping that channel if it adds noise.
* Window size, method and `k` are tuning knobs: using the same data to choose them and to judge
  them would overfit. Choose on one period, judge on a later one, and count the variants tried.
