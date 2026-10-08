# Changelog

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
