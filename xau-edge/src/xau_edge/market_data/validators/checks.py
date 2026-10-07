"""Bar-data validation checks. Pure functions: inputs are never mutated or repaired."""

from __future__ import annotations

from datetime import datetime

import polars as pl

from xau_edge.domain.bars import REQUIRED_COLUMNS
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.validators.models import (
    IssueCode,
    Severity,
    ValidationConfig,
    ValidationIssue,
    ValidationReport,
)

_PRICE_COLS = ("open", "high", "low", "close")
_TS = "__ts"
_MINUTES_PER_HOUR = 60


def _sample(work: pl.DataFrame, mask: pl.Expr, limit: int) -> tuple[datetime, ...]:
    rows = work.filter(mask).select(_TS).head(limit)[_TS].to_list()
    return tuple(rows)


def _issue(
    code: IssueCode,
    severity: Severity,
    count: int,
    message: str,
    sample: tuple[datetime, ...] = (),
) -> ValidationIssue:
    return ValidationIssue(
        code=code, severity=severity, count=count, message=message, sample=sample
    )


def _count(work: pl.DataFrame, mask: pl.Expr) -> int:
    return int(work.select(mask.fill_null(False).sum()).item())


def _masked_issue(  # noqa: PLR0917
    work: pl.DataFrame,
    mask: pl.Expr,
    code: IssueCode,
    severity: Severity,
    message: str,
    limit: int,
) -> ValidationIssue | None:
    count = _count(work, mask)
    if count == 0:
        return None
    return _issue(code, severity, count, message, _sample(work, mask.fill_null(False), limit))


def _normalised_ts(df: pl.DataFrame) -> pl.Expr:
    """UTC view of the timestamp column for time-based checks (naive is read as UTC)."""
    dtype = df.schema["timestamp"]
    assert isinstance(dtype, pl.Datetime)  # noqa: S101 - checked by caller
    if dtype.time_zone is None:
        return pl.col("timestamp").dt.replace_time_zone("UTC")
    return pl.col("timestamp").dt.convert_time_zone("UTC")


def _missing_bars(
    work: pl.DataFrame, timeframe: Timeframe, config: ValidationConfig
) -> ValidationIssue | None:
    unique_ts = work.select(pl.col(_TS).unique().sort())
    if unique_ts.height < 2:
        return None
    tf_minutes = timeframe.minutes
    gaps = (
        unique_ts.with_columns(pl.col(_TS).shift(1).alias("prev"))
        .with_columns(((pl.col(_TS) - pl.col("prev")).dt.total_minutes() // tf_minutes).alias("n"))
        .filter(pl.col("n") > 1)
    )
    if gaps.is_empty():
        return None
    slots = (
        gaps.with_columns(pl.int_ranges(1, pl.col("n")).alias("idx"))
        .explode("idx")
        .with_columns(
            (pl.col("prev") + pl.duration(minutes=pl.col("idx") * tf_minutes)).alias("slot")
        )
        .filter(~config.calendar.closed_expr(pl.col("slot")))
        .sort("slot")
    )
    missing = slots.height
    if missing == 0:
        return None
    fraction = missing / (unique_ts.height + missing)
    severity = Severity.ERROR if fraction > config.max_missing_fraction else Severity.WARNING
    sample = tuple(slots["slot"].head(config.max_samples).to_list())
    return _issue(
        IssueCode.MISSING_BARS,
        severity,
        missing,
        f"{missing} expected bars absent during open market hours "
        f"({fraction:.2%} of expected; threshold {config.max_missing_fraction:.2%})",
        sample,
    )


def validate_bars(
    df: pl.DataFrame,
    timeframe: Timeframe,
    *,
    symbol: str = "XAUUSD",
    config: ValidationConfig | None = None,
) -> ValidationReport:
    """Validate a bar frame against the platform data contract.

    The frame is never sorted, de-duplicated or repaired; problems are only reported.
    """
    cfg = config or ValidationConfig()

    def report(issues: list[ValidationIssue]) -> ValidationReport:
        return ValidationReport(
            symbol=symbol, timeframe=timeframe, rows=df.height, issues=tuple(issues)
        )

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        return report(
            [
                _issue(
                    IssueCode.MISSING_COLUMNS,
                    Severity.ERROR,
                    len(missing_cols),
                    f"missing columns: {', '.join(missing_cols)}",
                )
            ]
        )
    if df.height == 0:
        return report([_issue(IssueCode.EMPTY, Severity.ERROR, 0, "dataset has no rows")])
    if not isinstance(df.schema["timestamp"], pl.Datetime):
        return report(
            [
                _issue(
                    IssueCode.NON_UTC_TIMESTAMPS,
                    Severity.ERROR,
                    df.height,
                    f"timestamp is {df.schema['timestamp']}, expected Datetime(UTC)",
                )
            ]
        )

    issues: list[ValidationIssue] = []
    ts_dtype = df.schema["timestamp"]
    assert isinstance(ts_dtype, pl.Datetime)  # noqa: S101 - narrowed above
    if ts_dtype.time_zone != "UTC":
        zone = ts_dtype.time_zone or "naive"
        issues.append(
            _issue(
                IssueCode.NON_UTC_TIMESTAMPS,
                Severity.ERROR,
                df.height,
                f"timestamps are {zone}; the contract requires tz-aware UTC",
            )
        )

    work = df.with_columns(_normalised_ts(df).alias(_TS))
    ts = pl.col(_TS)
    limit = cfg.max_samples

    required_non_volume = [*_PRICE_COLS, "timestamp", "tick_volume", "spread"]
    any_null = pl.any_horizontal(*(pl.col(c).is_null() for c in required_non_volume))
    float_cols = [pl.col(c) for c in _PRICE_COLS]
    non_finite = pl.any_horizontal(
        *(c.is_nan().fill_null(False) | c.is_infinite().fill_null(False) for c in float_cols)
    )
    usable = ~any_null & ~non_finite

    checks: list[ValidationIssue | None] = [
        _masked_issue(
            work,
            any_null,
            IssueCode.NULL_VALUES,
            Severity.ERROR,
            "null values in required columns",
            limit,
        ),
        _masked_issue(
            work,
            non_finite,
            IssueCode.NON_FINITE_VALUES,
            Severity.ERROR,
            "NaN or infinite price values",
            limit,
        ),
    ]

    duplicated = ts.is_duplicated()
    dup_count = df.height - work.select(ts.n_unique()).item()
    if dup_count > 0:
        dup_sample = tuple(
            work.filter(duplicated)
            .select(ts.unique(maintain_order=True))
            .head(limit)[_TS]
            .to_list()
        )
        checks.append(
            _issue(
                IssueCode.DUPLICATE_TIMESTAMPS,
                Severity.ERROR,
                dup_count,
                f"{dup_count} rows repeat an earlier timestamp",
                dup_sample,
            )
        )

    checks.append(
        _masked_issue(
            work,
            ts.diff().dt.total_microseconds() < 0,
            IssueCode.OUT_OF_ORDER,
            Severity.ERROR,
            "timestamps are not monotonically increasing",
            limit,
        )
    )

    step = min(timeframe.minutes, _MINUTES_PER_HOUR)
    misaligned = (ts != ts.dt.truncate("1m")) | ((ts.dt.minute() % step) != 0)
    checks.append(
        _masked_issue(
            work,
            misaligned,
            IssueCode.MISALIGNED_TIMESTAMPS,
            Severity.ERROR,
            f"timestamps not aligned to {timeframe.value} boundaries",
            limit,
        )
    )

    checks.append(_missing_bars(work, timeframe, cfg))
    checks.append(
        _masked_issue(
            work,
            cfg.calendar.closed_expr(ts),
            IssueCode.WEEKEND_BARS,
            Severity.WARNING,
            "bars open while the market calendar says the market is closed",
            limit,
        )
    )

    o, h, low, c = (pl.col(n) for n in _PRICE_COLS)
    bad_ohlc = usable & ((low > h) | (o < low) | (o > h) | (c < low) | (c > h))
    checks.append(
        _masked_issue(
            work,
            bad_ohlc,
            IssueCode.INVALID_OHLC,
            Severity.ERROR,
            "violates low <= open/close <= high",
            limit,
        )
    )
    non_positive = usable & ((o <= 0) | (h <= 0) | (low <= 0) | (c <= 0))
    checks.append(
        _masked_issue(
            work,
            non_positive,
            IssueCode.NON_POSITIVE_PRICE,
            Severity.ERROR,
            "price is zero or negative",
            limit,
        )
    )
    negative_volume = (pl.col("tick_volume") < 0) | (pl.col("real_volume") < 0)
    checks.append(
        _masked_issue(
            work,
            negative_volume,
            IssueCode.NEGATIVE_VOLUME,
            Severity.ERROR,
            "negative volume",
            limit,
        )
    )
    checks.append(
        _masked_issue(
            work,
            pl.col("spread") < 0,
            IssueCode.INVALID_SPREAD,
            Severity.ERROR,
            "negative spread",
            limit,
        )
    )
    checks.append(
        _masked_issue(
            work,
            pl.col("spread") > cfg.max_spread_points,
            IssueCode.INVALID_SPREAD,
            Severity.WARNING,
            f"spread above {cfg.max_spread_points} points",
            limit,
        )
    )

    issues.extend(i for i in checks if i is not None)
    return report(issues)
