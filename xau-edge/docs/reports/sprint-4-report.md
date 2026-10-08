# Sprint 4 - Report

Date: 2026-10-08. Scope (Epic 04 part 2): candle geometry, volume features, temporal and session
features, versioned feature set keyed by dataset id, feature store. Pre-commit hooks installed.

## Delivered

| Item | Module | Notes |
|---|---|---|
| Candle geometry | `features/candles.py` | body, wicks, body/range, body/ATR, wick/ATR, range/ATR; `NaN` for zero range or unavailable ATR |
| Volume | `features/volume.py` | tick volume z-score (sample std, window incl. current bar), volume change |
| Sessions | `features/sessions.py` | hour (UTC), day of week, ASIA / LONDON / NEW_YORK / LONDON_NY_OVERLAP / OFF_HOURS from local exchange hours (ADR-0011) |
| Feature set | `features/feature_set.py` | 40 columns (incl. `gap_before`), `available_at`, warm-up as null, `feature_id` = hash(version, dataset id, timeframe, config) |
| Feature store | `FeatureStore` | write-once Parquet + sidecar, hash-verified read, safe names |
| Hooks | `.pre-commit-config.yaml` | installed into the local git hooks; ruff, format, mypy, .env guard run on commits touching `xau-edge/` |

## Evidence

* **RED:** new test modules failed at import (`xau_edge.features.candles`, `.volume`, `.sessions`,
  `.feature_set` absent) before implementation; feature-set tests failed with a Polars
  expression error and were then fixed.
* **Real data smoke test** (FTMO demo M5 101,135 bars, H1): build in 0.4 s for M5; no infinities;
  RSI 5-93, ADX 6-84, stochastic %K 0.6-99.9, body/ATR up to 7; session counts plausible. This is a
  sanity check of ranges, not research evidence.
* **Mutation spot-check:** 15 mutants (candle wicks, ratio guard, z-score ddof and alignment,
  session boundary and zone, label mapping, `available_at`, ATR period, ordering check, return
  type, version in id, tamper check). 12 killed at first; 3 survived and were killed after adding an
  adjacent-duplicate-timestamp case, a simple-vs-log return check and a version-in-id test.
* **Causality:** the whole feature frame is compared after truncating the bars (cuts at 120 and 250
  of 300 rows): identical rows.
* **Regression pin:** hash of the default feature set on a fixed synthetic input.

## Independent review (fresh context, 1 reviewer)

No look-ahead found; DST checked on five transition dates; parquet round trip exact. Fixed with
tests: null timestamps were labelled `OFF_HOURS` (now rejected); returns across weekend gaps looked
like one-bar returns (new `gap_before` column); store `read` accepted refs outside its root;
Windows-reserved dataset ids (e.g. `NUL`); private helpers imported across modules (now public
`as_series`, `as_hlc`, `check_period`). Accepted: non-atomic write race (single-writer research
tool), pinned hash depends on library float formatting (a tripwire, re-pin on upgrade).

## Red-team: how could this sprint be wrong?

| Question | Finding | Status |
|---|---|---|
| Session definitions arbitrary | Hours are a convention (ADR-0011); no evidence yet they matter | Open; Sprint 7-9 must report by session before using it |
| Gap handling | Windows span weekends and holidays (consecutive-bar convention) | Documented; gap-aware variant would need a new version |
| `available_at` ignored downstream | A later join on `timestamp` would leak the current bar's close | Mitigated by ADR-0011 and by tests added in Sprint 6-7 |
| Tick volume | Broker tick counts, not traded volume; may differ across brokers and hours | Accepted; z-score is relative |
| Spread not a feature | Spread enters through costs in Sprint 8, from M5 data | Deferred |
| Data quality | Features assume validated, sorted, unique bars; checked structurally only | Accepted |
| Real-data coverage | One broker, one symbol, 17 months | Open (as in Sprint 2) |
| Holiday calendar | Moved to Sprint 8 (affects validator warnings and cost realism, not features) | Deferred with reason |
