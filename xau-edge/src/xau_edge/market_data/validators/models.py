"""Validation result and configuration models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.validators.market_calendar import MarketCalendar


class Severity(StrEnum):
    """Issue severity. ERROR makes a dataset unfit for research use."""

    ERROR = "ERROR"
    WARNING = "WARNING"


class IssueCode(StrEnum):
    """Machine-readable validation issue identifiers."""

    MISSING_COLUMNS = "MISSING_COLUMNS"
    EMPTY = "EMPTY"
    NON_UTC_TIMESTAMPS = "NON_UTC_TIMESTAMPS"
    NULL_VALUES = "NULL_VALUES"
    NON_FINITE_VALUES = "NON_FINITE_VALUES"
    DUPLICATE_TIMESTAMPS = "DUPLICATE_TIMESTAMPS"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    MISALIGNED_TIMESTAMPS = "MISALIGNED_TIMESTAMPS"
    MISSING_BARS = "MISSING_BARS"
    UNSCHEDULED_CLOSURES = "UNSCHEDULED_CLOSURES"
    INCOMPLETE_COVERAGE = "INCOMPLETE_COVERAGE"
    WEEKEND_BARS = "WEEKEND_BARS"
    INVALID_OHLC = "INVALID_OHLC"
    NON_POSITIVE_PRICE = "NON_POSITIVE_PRICE"
    NEGATIVE_VOLUME = "NEGATIVE_VOLUME"
    INVALID_SPREAD = "INVALID_SPREAD"


class ValidationConfig(BaseModel):
    """Thresholds for validation. Defaults are conservative and should be reviewed per broker."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    calendar: MarketCalendar = Field(default_factory=MarketCalendar)
    max_spread_points: int = Field(default=2000, ge=0)
    max_missing_fraction: float = Field(default=0.01, ge=0, le=1)
    min_closure_minutes: int = Field(default=30, ge=0)
    """A gap at least this long that ends at a scheduled reopening is reported as an
    UNSCHEDULED_CLOSURES warning (holiday / early close) instead of as missing data."""
    max_closure_minutes: int = Field(default=24 * 60, ge=1)
    """Upper bound on the open-hours minutes a single gap may span and still be treated as a
    closure. Longer gaps are data loss even if they end at a reopening: an outage must not be able
    to hide as a holiday. The default is one trading day; broker profiles raise it using measured
    holiday closures."""

    @model_validator(mode="after")
    def _closure_bounds_are_ordered(self) -> ValidationConfig:
        if self.max_closure_minutes < self.min_closure_minutes:
            msg = "max_closure_minutes must be >= min_closure_minutes"
            raise ValueError(msg)
        return self

    max_samples: int = Field(default=5, ge=0)


class ValidationIssue(BaseModel):
    """One class of problem found in a dataset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: IssueCode
    severity: Severity
    count: int = Field(ge=0)
    message: str
    sample: tuple[datetime, ...] = ()


class ValidationReport(BaseModel):
    """Outcome of validating one bar dataset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    timeframe: Timeframe
    rows: int
    issues: tuple[ValidationIssue, ...] = ()

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        """Issues with ERROR severity."""
        return tuple(i for i in self.issues if i.severity is Severity.ERROR)

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        """Issues with WARNING severity."""
        return tuple(i for i in self.issues if i.severity is Severity.WARNING)

    @property
    def passed(self) -> bool:
        """True when no ERROR-severity issue exists (warnings are allowed)."""
        return not self.errors

    def summary(self) -> str:
        """Human-readable multi-line summary."""
        verdict = (
            "PASSED"
            if self.passed
            else f"FAILED ({len(self.errors)} errors, {len(self.warnings)} warnings)"
        )
        lines = [f"{self.symbol} {self.timeframe.value}: {self.rows} rows - {verdict}"]
        lines.extend(
            f"- [{i.severity.value}] {i.code.value} count={i.count}: {i.message}"
            for i in self.issues
        )
        return "\n".join(lines)
