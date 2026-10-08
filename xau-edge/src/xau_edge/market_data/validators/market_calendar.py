"""Market-hours model used to tell real gaps from scheduled closures."""

from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import polars as pl
from pydantic import BaseModel, ConfigDict, Field, field_validator


class MarketCalendar(BaseModel):
    """Weekly closure window for an FX/CFD gold market, in a named local time zone.

    Minutes are minutes-of-day in ``timezone``. The default follows the common 24x5 convention:
    the market closes Friday 17:00 and reopens Sunday 17:00 New York time. Because that clock
    follows US daylight saving time, the UTC equivalent moves between 21:00 and 22:00.

    ASSUMPTION: real hours differ by broker (and some brokers add a daily break). Confirm
    against the broker before treating WEEKEND_BARS or MISSING_BARS as hard facts.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    timezone: str = "America/New_York"
    weekend_close_minute: int = Field(default=17 * 60, ge=0, lt=24 * 60)
    weekend_open_minute: int = Field(default=17 * 60, ge=0, lt=24 * 60)
    daily_break_start_minute: int | None = Field(default=None, ge=0, lt=24 * 60)
    daily_break_end_minute: int | None = Field(default=None, ge=0, lt=24 * 60)

    @field_validator("timezone")
    @classmethod
    def _known_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            msg = f"unknown IANA time zone {value!r}"
            raise ValueError(msg) from exc
        return value

    def closed_span_expr(self, ts: pl.Expr, span_minutes: int) -> pl.Expr:
        """True where a bar covering ``[ts, ts + span)`` lies entirely inside a closure.

        A bar that opens during a closure but trades later in its span (for example an H1 bar
        labelled 01:00 whose first tick is 01:05) is NOT closed. Judging by the open time alone
        wrongly flags such bars.
        """
        starts_closed = self.closed_expr(ts)
        if span_minutes <= 1:
            return starts_closed
        last_minute = ts + pl.duration(minutes=span_minutes - 1)
        return starts_closed & self.closed_expr(last_minute)

    def closed_expr(self, ts: pl.Expr) -> pl.Expr:
        """Expression that is true where a bar opening at ``ts`` falls in a closure.

        ``ts`` must be a tz-aware datetime expression; it is converted to ``timezone``.
        Polars weekday numbering: Monday=1 ... Sunday=7.
        """
        local = ts.dt.convert_time_zone(self.timezone)
        weekday = local.dt.weekday()
        minute = local.dt.hour().cast(pl.Int32) * 60 + local.dt.minute().cast(pl.Int32)
        closed = (
            (weekday == 6)
            | ((weekday == 5) & (minute >= self.weekend_close_minute))
            | ((weekday == 7) & (minute < self.weekend_open_minute))
        )
        start, end = self.daily_break_start_minute, self.daily_break_end_minute
        if start is not None and end is not None:
            in_break = (
                (minute >= start) & (minute < end)
                if start < end
                else (minute >= start) | (minute < end)
            )
            closed = closed | in_break
        return closed
