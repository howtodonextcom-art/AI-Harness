# Sprint 1 - Implementation report

Date: 2026-10-08. Scope: the brief's section 55 (bootstrap, domain models, MT5 interface, offline
adapter, validation tests). Trading execution was not implemented and cannot be enabled.

## Quality gate result

`.\scripts\dev.ps1 check` passes: ruff (lint and format), `mypy --strict` (all source and test files),
pytest.

| Metric | Value |
|---|---|
| Tests | 106 passed (unit 105, integration 1) when the `mt5` extra is installed; a clean-room rebuild from `uv.lock` without it gave 95 passed, 2 skipped (before 9 DST/timezone tests were added; that clean-room run was not repeated afterwards) |
| Coverage | 98% (551 statements, 7 missed; branch coverage on) |
| Source / tests | 17 files, 983 lines / 15 files, 944 lines |
| Mutation spot-check | 10 hand-made mutants (boundary flips, removed safety steps, wrong timezone default); 4 survived the first test set, tests were strengthened, all 10 are now killed |
| Secrets scan | clean (only dummy `s3cret` fixtures in tests) |
| Order/position API names in `src/` | none; a test enforces this for `market_data/mt5` |

Gate: **passed**. Nothing was hidden or waived.

## Files created

* Project: `pyproject.toml`, `uv.lock`, `Makefile`, `scripts/dev.ps1`, `.gitignore`, `.env.example`,
  `README.md`, `CHANGELOG.md`, `AGENTS.md`, `data/*/.gitkeep`
* Source (`src/xau_edge/`): `config.py`; `domain/{timeframe,instrument,bars}.py`;
  `market_data/{source,store}.py`; `market_data/importers/file_source.py`;
  `market_data/mt5/source.py`; `market_data/validators/{models,checks,market_calendar}.py`
* Tests: unit tests for domain, validators (including DST cases), file source, MT5 source (fake client),
  raw store, config, edge cases; one integration test (file -> store -> validation)
* Docs: `docs/PROJECT_PLAN.md`, `docs/architecture/system.md`, `docs/research/dependency-review.md`,
  `docs/decisions/0001-0007`, this report
* ECC: `.claude/` (489 files, profile `minimal`, `--no-hooks`) installed project-local with the
  ECC installer; install state is healthy (`ecc doctor`: OK)

Files modified: none outside `xau-edge/`. (Pre-existing change in the parent repo:
`ECC-Sandbox-evidence/npm-test-gitbash.log`, written by an earlier background test run.)

## Architecture decisions

ADR-0001 single `src/` package; 0002 Polars + Parquet (DuckDB next); 0003 Python >= 3.12 + uv;
0004 UTC bar-open timestamps with explicit broker zone; 0005 validators report, sources never
repair, raw data immutable; 0006 no copyleft/ambiguous-licence dependencies; 0007 DST-aware
market calendar.

## Dependencies

Runtime: numpy 2.5.3, polars 2.0.0, pydantic 2.13.5, pydantic-settings 2.15.0, pyyaml 6.0.3,
tzdata 2026.5. Optional: MetaTrader5 5.0.6231 (installed and importable on 3.14, verified).
Dev: pytest, pytest-cov, hypothesis, ruff, mypy, types-PyYAML. Full evaluation of 25+ packages,
including rejected ones (backtesting.py AGPL, vectorbt licence unclear, freqtrade/backtrader GPL):
`docs/research/dependency-review.md`.

## How ECC was used

ECC's `minimal` profile was installed into the project (`xau-edge/.claude`, no hooks). The
`planner` format shaped `docs/PROJECT_PLAN.md`; `tdd-workflow` was followed (tests written first,
RED confirmed by import failure, then GREEN); `verification-loop` phases drove the gate and the
security grep. ECC agents were **not** run as separate sub-agents: the installed components are
only discovered by a Claude Code session started inside `xau-edge/`, so they were applied as written
procedures. No ECC hook is active.

## Red-team: how could Sprint 1 be wrong?

| Question | Finding | Status |
|---|---|---|
| Data errors | All validator tests use **synthetic** data. No real XAUUSD export has been validated; thresholds (1% missing, 2000-point spread) are guesses | Open: Sprint 2 |
| Timestamps | MT5 returns broker wall-clock labelled UTC. Conversion logic is unit-tested against a fake client whose constants match the real module, but **never run against a live terminal**; broker timezone is unknown | Open: Sprint 2, highest risk |
| Market hours | First design used a fixed 22:00 UTC weekend; wrong for US summer time | **Found and fixed** (ADR-0007) |
| Holidays / early closes | Not modelled; they will surface as MISSING_BARS | Open |
| H4 alignment | Hour offsets are allowed because broker H4 bars start at server midnight; a broker with half-hour offsets would be flagged | Accepted |
| Future leakage / look-ahead | Not applicable yet (no features or patterns); leakage tests are required in Epic 07 | Deferred |
| Repainting | Not applicable yet | Deferred |
| Cost assumptions | `Instrument` defaults for XAUUSD (2 digits, contract 100) are assumptions | Open: confirm with broker spec |
| Library risk | Polars 2.0.0 is two days old; pinned `>=2,<3` with a lock file | Monitor |
| Python range | Only 3.14.4 tested; 3.12 and 3.13 are untested | Open: CI matrix |
| Raw-store hash | Content hash uses CSV serialisation of floats; stable on this version, not guaranteed across Polars versions | Low; re-hash on upgrade |
| Immutability | Read-only attribute deters edits but does not prevent deliberate changes by a privileged user; `verify()` detects them | Accepted |

## Known limitations

* No resampling, dataset catalog, DuckDB queries, features, structure, patterns, backtesting,
  signals, API or dashboard (by design, later sprints).
* `ValidationConfig` thresholds are not yet read from a YAML config file (defaults in code).
* No CI pipeline yet; the gate runs locally.
* Line endings: Git on this machine converts LF to CRLF in the working copy; harmless but noisy.

## Recommended Sprint 2

1. Run the MT5 adapter on a **demo** terminal, derive and record the broker timezone, validate a
   week of M5 XAUUSD, and compare derived H1/H4 bars to the broker's own.
2. Resampling M5 -> M15/H1/H4 with broker-consistent alignment, and cross-timeframe checks.
3. DuckDB dataset catalog over Parquet with content-hash versioning.
4. Validate a real XAUUSD export; tune thresholds from evidence, document the result.
5. Broker market-hours profile, YAML configs, CI with Python 3.12/3.13/3.14.
