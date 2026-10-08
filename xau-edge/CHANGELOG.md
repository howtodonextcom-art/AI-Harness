# Changelog

## 0.3.0 - 2026-10-08 (roadmap debt and indicators)

### Added
* `features/indicators.py`: SMA, EMA, RSI, ATR, true range, ADX/+DI/-DI, MACD, slow stochastic,
  Bollinger bands, simple/log/rolling returns and rolling volatility as pure NumPy functions
  (causal, `NaN` warm-up, inputs untouched). Golden tests against recorded TA-Lib output
  (`tests/fixtures/talib_golden.json`), repainting tests, property tests (ADR-0010).
* `observability.py`: JSON-lines logging with credential redaction, bounded output and a formatter
  that never raises. Events `raw.write`, `validation.result`, `catalog.load`.
* `docs/BRIEF.md`, `docs/ROADMAP_TRACEABILITY.md`, `docs/architecture/data-flow.md`,
  `docs/testing/testing-strategy.md`; `tests/regression` (pinned hashes), `tests/statistical`.
* `.pre-commit-config.yaml` (configuration only) and `scripts/block_env_files.py`.

### Changed
* `PROJECT_PLAN.md`: epic 19 (news risk), richer acceptance for epics 10, 11, 14, 15, run-ladder,
  sprint numbering aligned with the roadmap table, sprint closing criteria (red-team, overfitting).

## 0.2.1 - 2026-10-08 (ECC review remediation)

### Security
* `Settings` is immutable and re-validates on copy: live trading cannot be enabled by assignment
  or `model_copy` (F-02).
* `Mt5BarSource` refuses non-DEMO accounts on connect and on every fetch (F-03) and only holds an
  allowlist proxy of the MT5 module, so order/position functions are unreachable (F-04).
* `.gitignore` now covers CSV/Parquet/DuckDB/log/key/credential files anywhere (F-07); the sdist
  ships only source, tests, docs, configs, scripts and the lock file (V-02).
* CI installs with `uv sync --locked` and a pinned uv version (F-21).

### Fixed
* A gap longer than `max_closure_minutes` that ends at a reopening is now data loss, not a holiday
  warning (F-01). The FTMO profile sets 28 h from measured Christmas/New Year closures.
* `Mt5BarSource` drops the bar still forming (F-05); request bounds are tested (F-13).
* `DatasetCatalog.load` re-hashes every file and raises `RawDataIntegrityError` on tampering (F-06);
  SQL has memory/thread limits and a timeout (F-14).
* `cross_check` flags duplicate timestamps and compares null/NaN consistently (F-08, F-09).
* `coerce_bars` refuses to truncate fractional numbers into integers (F-10).
* `FileBarSource` infers epoch units safely, rejects date-shaped integers, names the offending
  timestamp, and exposes a valid raw-store source name (F-11, F-12, F-20).
* Raw store validates names on read, rejects Windows reserved names, and reports unreadable files
  accurately (F-15). Half-configured daily breaks are rejected (F-16). Resampling counts only bars
  in open slots (F-17) and rejects unknown spread policies (F-18).
* Package version now matches the changelog (V-01); a test keeps them in sync.

### Second review round (three independent reviewers, no CRITICAL/HIGH)
* `DatasetCatalog.available()` ignores stray directories instead of failing all queries.
* Raw-store reads check the sidecar against the file (name hash, rows, time range, symbol,
  timeframe); names use `fullmatch` so a trailing newline is refused.
* SQL results are capped (`max_rows`), the timer is a daemon and only genuine timeouts are
  reported as such.
* `Mt5BarSource.connect` shuts the terminal down on any failure while checking the account; the
  read-only proxy docstring no longer claims to stop deliberate in-process misuse.
* `Settings.model_copy` rejects unknown keys; `coerce_bars` also refuses Decimal rounding;
  `FileBarSource` names are always valid store sources; clock error messages are not repeated.
* `.gitignore` covers secret-looking names and more data formats; sdist has explicit excludes;
  CI checkout does not persist credentials and jobs have a timeout.
* Found by testing on Python 3.12: `ZoneInfo("Europe")` raises `PermissionError`; invalid zone
  names are now reported cleanly on every supported version.

## 0.2.0 - 2026-10-08 (Sprint 2)

### Added
* `BrokerClock` (`NY+N` or IANA) and `infer_broker_clock`; broker profiles
  (`configs/brokers/ftmo_demo.yaml`, `BrokerProfile`).
* `resample_bars` (M5 -> M15/H1/H4 on server-clock boundaries, calendar-aware completeness).
* `cross_check`, `check_coverage`; `DatasetCatalog` (merge of raw fetches, dataset id, read-only SQL).
* `RawStore` records fetch time in a `.meta.json` sidecar and lists datasets.
* `scripts/verify_mt5.py`; `docs/reports/mt5-verification.md`; ADR-0008, ADR-0009.
* CI workflow (ubuntu/windows x Python 3.12-3.14), actions pinned by commit SHA.

### Changed
* Validator: bars are "closed" only if their whole span is inside a closure; gaps ending at a
  scheduled reopening are reported as `UNSCHEDULED_CLOSURES`; new `INCOMPLETE_COVERAGE`.
* `MarketCalendar` fields are minutes in its own time zone (`weekend_close_minute`, ...).
* Dependencies: + duckdb, pyarrow.

### Fixed
* False `WEEKEND_BARS` warnings on higher timeframes and holiday early closes counted as data loss.

## 0.1.0 - 2026-10-08 (Sprint 1)

### Added
* Project bootstrap: uv, ruff, mypy (strict), pytest, coverage, Makefile and `scripts/dev.ps1`.
* Domain: `Timeframe`, `Instrument` (XAUUSD defaults flagged as assumptions), bar schema,
  `Bar`, `BarRequest`, `coerce_bars`.
* `BarSource` protocol; `FileBarSource` (CSV/TSV/Parquet, MetaTrader export format, timezone
  conversion with DST-ambiguity errors); `Mt5BarSource` (read-only, injectable client).
* `RawStore`: write-once, content-addressed, read-only Parquet.
* `validate_bars`: 14 issue codes with ERROR/WARNING severities and a configurable,
  DST-aware market calendar (default: Friday/Sunday 17:00 New York; ADR-0007).
* `Settings` with live trading hard-disabled.
* Documentation: AGENTS.md, project plan, architecture, dependency review, ADR-0001..0006.

### Known limitations
See `docs/reports/sprint-1-report.md`.
