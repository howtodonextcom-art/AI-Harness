# Sprint 2 - Implementation report

Date: 2026-10-08. Goal: make the data layer trustworthy against a real broker feed. Scope:
live MT5 verification (FTMO **demo**), resampling, dataset catalog, broker profiles, validator
corrections. Still no features, strategies, or execution; live trading remains impossible.

## Quality gate result

`.\scripts\dev.ps1 check` passes (ruff lint and format, `mypy --strict`, pytest).

| Metric | Value |
|---|---|
| Tests | 173 passed (Sprint 1: 106) |
| Coverage | 98% (889 statements, 11 missed; branch coverage on) |
| Python versions | 3.12.13, 3.13.13 and 3.14.4: all 173 tests and `mypy --strict` pass on each |
| Mutation spot-check | 12 hand-made mutants (clock sign flips, completeness rule, bucket width, closure thresholds, coverage boundaries, calendar span, catalog precedence, tolerance boundary); all killed on the first full pass, after two boundary tests were added beforehand |
| Secrets scan | one finding, see "Open issue: account number" |
| CI | workflow added; its first GitHub run (commit `5f49e71`) passed all 6 jobs (Ubuntu and Windows x Python 3.12-3.14); this was only learned afterwards, see the note below the table |

## What the live verification established

Full detail: `docs/reports/mt5-verification.md`.

* Account was DEMO (guarded in code); terminal had algorithmic trading disabled.
* XAUUSD spec matches the Sprint 1 defaults (2 digits, contract 100).
* The server clock is **New York + 7 h**, not an IANA zone (ADR-0008). Live offset +3 h agrees.
* Session: Sunday 18:05 to Friday 16:50 New York with a daily break 16:50-18:05.
* Resampling M5 to M15/H1/H4 reproduces the broker's own bars exactly: 0 differences in open,
  high, low, close or tick volume across 44,797 compared bars.
* Spread cannot be reproduced from M5 spreads (best rule still differs on 26-48% of bars).
* The terminal silently truncates history at about 100,000 M5 bars.

## Defects the real data exposed (all fixed with tests)

| Defect | Effect | Fix |
|---|---|---|
| Fixed 22:00 UTC weekend (Sprint 1 first draft, already corrected in ADR-0007) | phantom missing bars in US summer | New York local-time calendar |
| Calendar judged bars by open time only | 372 false `WEEKEND_BARS` warnings on M15/H1/H4 | span-aware `closed_span_expr` |
| Holiday early closes counted as data loss | M5 reported FAILED (1,245 "missing" bars) | `UNSCHEDULED_CLOSURES` warning; 2 genuine single-bar gaps remain as `MISSING_BARS` |
| Silent history truncation undetectable by row checks | a fetch could lose its first week unnoticed | `check_coverage`; validate the merged dataset of record |
| `Europe/Athens` accepted as the broker clock | 1 h error for 3-4 weeks a year | `BrokerClock` with `NY+N` |

Note: the CI claim above was corrected afterwards. The public GitHub Actions API showed the run for
`5f49e71` completed with `success` on Ubuntu and Windows for Python 3.12, 3.13 and 3.14.

## Files

Created (source): `market_data/{broker_clock,resampling,catalog,profiles}.py`,
`market_data/validators/{market_calendar,cross_check,coverage}.py`.
Changed: `store.py` (fetch-time sidecar, `datasets()`), `validators/{checks,models}.py`,
`mt5/source.py` and `importers/file_source.py` (use `BrokerClock`), `pyproject.toml`
(+ duckdb, pyarrow).
Also: `configs/brokers/ftmo_demo.yaml`, `scripts/verify_mt5.py`,
`.github/workflows/xau-edge-ci.yml`, ADR-0008/0009, `docs/reports/mt5-verification.md`, updates to
README, plan, architecture, dependency review, changelog and AGENTS.md.
Size: src 1,554 lines in 23 files; tests 1,516 lines in 23 files; scripts 245 lines.

## Red-team: how could Sprint 2 be wrong?

| Question | Finding | Status |
|---|---|---|
| Single source | One broker, demo account, one symbol, 17 months. Live feeds/sessions/spreads may differ | Open |
| DST coverage | Only one autumn and one spring US/EU mismatch window in the history | Open; more history would strengthen the clock evidence |
| Clock ties | `NY+6/7/8` tie on stability; selection rests on the live +3 h offset and the 17:00 anchor | Mitigated; re-measure when the DST regime changes |
| Holidays | Not modelled. A genuine outage that ends at a reopening looks like an early close (warning only) | Open |
| Irregular holiday sessions | 12 H4 bars flagged `MISSING_BARS` (warning) around Christmas/New Year-style schedules | Accepted |
| Derived bars exclude incomplete buckets | 2-14 buckets per timeframe are excluded and reported; they are holiday partials, not hidden | Accepted |
| Spread | Derived HTF spread is not the broker's; costs must use M5/tick spread | Documented |
| Terminal truncation | Merge preserves history only if an earlier fetch had it; a fresh install would have only ~100k M5 bars | Open: raise "Max bars in chart" or accumulate regularly |
| Look-ahead / leakage | Not applicable yet (no features) | Deferred to Epic 07 |
| Merge rule | "Newest fetch wins" assumes later broker data is a correction, not a regression | Accepted; duplicates are counted and the dataset id changes |
| DuckDB SQL surface | Read-only check is a prefix test; external access is disabled at the engine level | Accepted |
| CI | Believed unrun at report time; it had in fact run and passed on all 6 matrix jobs | Closed (verified via the public Actions API) |

## Open issue: account number in `.env.example`

During the sprint the committed template `xau-edge/.env.example` was edited to contain a real
MT5 login number (`MT5_LOGIN=...`). It was never committed. It was **excluded from the Sprint 2
commit** and left untouched in the working tree. Move the value into `.env`
(git-ignored) and restore the template line to `MT5_LOGIN=`. If the number was ever pushed
elsewhere, treat it as exposed.

## Known limitations

* No holiday calendar; no tick data; no feature, structure, pattern, backtest, signal, API or
  dashboard code.
* `DatasetCatalog.sql` loads every dataset into memory per call; fine at this size, not for tick data.
* The verification script targets the Windows terminal path used on this machine (overridable
  with `--terminal-path`).
* ECC was used as a method (plan format, test-first, verification loop, red-team) rather than as
  running sub-agents.

## Recommended Sprint 3

See `docs/PROJECT_PLAN.md`: indicators with golden tests, candle/volume/session features,
M5-based cost inputs, a holiday calendar, and (CI already passes) a `pip-audit` step.
