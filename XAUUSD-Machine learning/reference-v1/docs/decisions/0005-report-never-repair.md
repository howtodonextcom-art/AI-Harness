# ADR-0005: Validators report, sources do not repair, raw data is immutable

Status: accepted (2026-10-08)

**Decision.** Sources return data as read (no sorting, de-duplication or gap filling).
`validate_bars` returns a report and never mutates its input. Raw data is stored write-once,
content-addressed and read-only; re-writing identical data is a no-op, different data at an
existing path raises.

**Why.** Silent repair hides data problems that later look like model edge. Repairs belong in an
explicit, versioned CLEAN stage (RAW -> CLEAN -> RESAMPLED -> FEATURES) with its own tests.

**Severity.** ERROR = unfit for research (schema, nulls, non-finite, duplicates, order,
alignment, OHLC, non-positive price, negative volume/spread, non-UTC, missing bars above a
threshold). WARNING = review (weekend bars, small gaps, wide spreads).
