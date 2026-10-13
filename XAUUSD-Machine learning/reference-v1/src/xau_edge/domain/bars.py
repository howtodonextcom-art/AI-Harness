"""Bar data contract: Polars schema, single-bar model, and request model."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final

import polars as pl
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from xau_edge.domain.timeframe import Timeframe

BAR_COLUMNS: Final = (
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
)
"""Canonical column order of every bar frame in the platform."""

REQUIRED_COLUMNS: Final = BAR_COLUMNS[:-1]
"""All columns except ``real_volume``, which many CFD brokers do not provide."""

BAR_SCHEMA: Final[dict[str, pl.DataType | type[pl.DataType]]] = {
    "timestamp": pl.Datetime("us", "UTC"),
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "tick_volume": pl.Int64,
    "spread": pl.Int64,
    "real_volume": pl.Int64,
}
"""Contract: ``timestamp`` is the bar OPEN time in UTC; ``spread`` is in points."""


class MissingColumnsError(ValueError):
    """Raised when a frame lacks required bar columns."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"Missing required bar columns: {', '.join(missing)}")


class TimestampTypeError(TypeError):
    """Raised when the timestamp column is not a datetime type."""


def empty_bars() -> pl.DataFrame:
    """Return an empty frame with the canonical bar schema."""
    return pl.DataFrame(schema=BAR_SCHEMA)


def coerce_bars(df: pl.DataFrame) -> pl.DataFrame:
    """Return ``df`` restricted and cast to the canonical bar contract.

    The input is not modified. Time zones are deliberately NOT altered here: a naive or
    non-UTC timestamp column is preserved so that the validators can report it.
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise MissingColumnsError(missing)

    ts_dtype = df.schema["timestamp"]
    if not isinstance(ts_dtype, pl.Datetime):
        msg = f"timestamp must be a Datetime column, got {ts_dtype}"
        raise TimestampTypeError(msg)

    work = df
    if "real_volume" not in work.columns:
        work = work.with_columns(pl.lit(None, dtype=pl.Int64).alias("real_volume"))

    for name, dtype in BAR_SCHEMA.items():
        source = work.schema[name]
        if dtype.is_integer() and not source.is_integer():
            as_float = pl.col(name).cast(pl.Float64)
            fractional = work.select(
                ((as_float - as_float.round(0)).abs() > 0).fill_null(False).sum()
            ).item()
            if fractional:
                msg = (
                    f"{name} has {fractional} non-integer value(s); refusing to truncate "
                    "them into integers"
                )
                raise ValueError(msg)

    casts: list[pl.Expr] = [pl.col("timestamp").cast(pl.Datetime("us", ts_dtype.time_zone))]
    casts.extend(
        pl.col(name).cast(dtype) for name, dtype in BAR_SCHEMA.items() if name != "timestamp"
    )
    return work.select(casts).select(BAR_COLUMNS)


class Bar(BaseModel):
    """A single OHLC bar with enforced invariants (for live/paper paths, not bulk data)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = Field(min_length=1)
    timeframe: Timeframe
    timestamp: AwareDatetime
    open: float = Field(gt=0, allow_inf_nan=False)
    high: float = Field(gt=0, allow_inf_nan=False)
    low: float = Field(gt=0, allow_inf_nan=False)
    close: float = Field(gt=0, allow_inf_nan=False)
    tick_volume: int = Field(ge=0)
    spread: int = Field(ge=0)
    real_volume: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _ohlc_consistent(self) -> Bar:
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            msg = "OHLC violates low <= open/close <= high"
            raise ValueError(msg)
        return self


class BarRequest(BaseModel):
    """Request for bars in ``[start, end)`` (UTC)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = Field(min_length=1)
    timeframe: Timeframe
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def _ordered(self) -> BarRequest:
        if self.start.astimezone(UTC) >= self.end.astimezone(UTC):
            msg = "start must be strictly before end"
            raise ValueError(msg)
        return self

    @property
    def start_utc(self) -> datetime:
        """Start bound normalised to UTC."""
        return self.start.astimezone(UTC)

    @property
    def end_utc(self) -> datetime:
        """End bound normalised to UTC."""
        return self.end.astimezone(UTC)
