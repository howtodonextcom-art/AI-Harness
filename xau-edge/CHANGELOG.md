# Changelog

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
