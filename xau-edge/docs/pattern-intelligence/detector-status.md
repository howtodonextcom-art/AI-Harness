# Detector status

## Repository detectors

| Detector | Module | Causality | Repaint class | Controls | Parity |
|---|---|---|---|---|---|
| Wolfe Wave (P5 confirmed; LINE13_RECLAIM; ETA options) | `structure/wolfe.py` | prefix invariance: an ad hoc run on 40 random series / 2,520 cuts gave 0 violations (not a committed test); committed tests: 6 series x 47 cuts, and reclaim mode 14 series x 60 cuts, 0 violations; a look-ahead mutant produced 49 in the ad hoc run | NON_REPAINT PROVEN (confirmed pivots only) | random walk 46.5 per 10,000 bars; block-shuffled Development-2 15.8; real 14.6 | contract adapter matches `detect_wolfe` |
| Double top / double bottom | `structure/reversal.py` | prefix invariance on random walks; mutants (look-ahead scan, trigger on low, supersession ignored) fail | NON_REPAINT PROVEN | random walk 58.5; shuffled null 55.8; real 59.2 | lifecycle CONFIRMED = detections, 192 of 192 on random walks |
| Head and shoulders / inverse | `structure/reversal.py` | same harness | NON_REPAINT PROVEN | random walk 4.3; shuffled null 2.7; real 1.4 | n/a |
| Formation lifecycle (double top/bottom) | `structure/formation.py` | lifecycle prefix invariance: 0 violations on 6 series x 51 cuts (committed test); mutants fail | NON_REPAINT PROVEN | description in `dev2_h1_descriptive.json` | exact parity with the detector |
| Pivots | `structure/pivots.py` | a pivot is used only at `confirmed_at = bar + right` | n/a | n/a | n/a |

Detector quality and strategy quality stay separate: every detection is `evidence = GEOMETRY_ONLY`, `outcome_evidence = NONE`.

## Defects found and fixed in this phase

1. Formation tracking: a weak early second peak invalidated a structure that a later higher peak would have armed (45 differences from the detector on random walks): fixed by deferring the failure until the peak can no longer be replaced.
2. The equal-peak band of the lifecycle was tighter than the detector's when the second peak is higher (it uses the larger peak in the height): fixed with the exact band `tol / (1 - tol)`.
3. A structure too small at its valley but qualifying at the second peak could not start (17 differences): it now starts at NEAR_CONFIRMATION, no earlier state is invented.
4. Formation ids changed as points were added, which the prefix test caught: the id is now stable (from A and V), the detector's id is stored separately.

## Third-party libraries: the same harness applied to code we do not own

`smart-money-concepts` (joshyattridge, MIT, 2.1k stars; installed in an isolated temporary environment, never in the project environment). One seeded random walk of 400 bars, swing_length 5, prefix cuts every 3 bars (127 cuts):

| Function | Result |
|---|---|
| `swing_highs_lows` | **REPAINTING near the live edge**: in 124 cases a swing-low label was shown within the last 0-10 bars of a truncated series and was absent from the full-series output; confirmed labels appear with a median lag of 5 bars (equal to `swing_length`, correct) but are placed at the pivot's own row, so a backtest that reads that row uses information from 5 future bars |
| `fvg` | no label changed (0 changes); every label is retroactive: it sits on the middle candle but is known one bar later (minimum lag 1, median 2) |
| import | crashes on a Windows cp1252 console (it prints an emoji in `__init__`); works with UTF-8 |

Scope: one series, two functions, one parameter set; reproduces the concern raised in a public pull request, it is not a full audit. The scripts are in `scripts/third_party_audit/` and need a separate environment with the package.

## External repositories (README level; code not vendored)

| Repository | Licence | What | Decision |
|---|---|---|---|
| joshyattridge/smart-money-concepts | MIT | SMC functions (swings, BOS/CHoCH, order blocks, FVG, liquidity) | **REJECT for use** (swings repaint at the live edge; retroactive labels); BORROW the idea of testing third-party code with prefix cuts |
| gilson0516/pt-lib (fork of tan-yang/pt-lib; built on BennyThadikaran/stock-pattern) | GPL-3.0 | 28 patterns on a left/right pivot framework | **BORROW IDEA** only (GPL cannot be vendored; the README does not address look-ahead) |
| BennyThadikaran/stock-pattern | GPL-3.0 | CLI scanner, harmonics; README says it gives no buy or sell signals | NOT NEEDED (not read beyond a search snippet) |
| zeta-zetra/chart_patterns | none stated | doubles, flag, head and shoulders, triangles | **REJECT** (no licence stated, method undocumented, look-ahead unaddressed) |
| keithorange/PatternPy | not read | rolling-window detection | **REJECT** (rolling windows are not pivot-confirmed; not read) |
| Shashank200345/Sweep | MIT | SMC detectors with a 135-test suite and a look-ahead test directory ("truncation and future-perturbation invariants"), 0 stars, 18 commits | **BORROW IDEA**: the invariants are the prefix test used here; its claim was not independently verified |
| earlier: khou/watch-video, stevederico/video-understanding, microsoft/playwright-mcp | MIT, MIT, Apache-2.0 | video skills; MCP browser | see the phase 2 report |

## Not implemented

Falling/rising wedge, triangle, flag, cup and handle, diamond, harmonics, Quasimodo, supply and demand: no detector. The author's drawings of these are recorded as observations; whether a detector could find the same shapes causally is unknown.
