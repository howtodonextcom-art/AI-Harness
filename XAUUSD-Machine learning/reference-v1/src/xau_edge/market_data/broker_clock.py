"""Broker server clocks.

MetaTrader reports bar times as the *broker server wall clock*. Many brokers (including the
FTMO demo server verified in Sprint 2) run a clock pinned to New York time plus a fixed number
of hours, so that the 17:00 New York market rollover always lands on server midnight. That
clock follows US daylight saving and cannot be expressed as a single IANA zone: an IANA zone
such as ``Europe/Athens`` follows EU rules and is wrong for a few weeks every spring and autumn.

``BrokerClock`` therefore supports two kinds of clock:

* ``NY+7``: server wall clock = New York wall clock + 7 hours (any integer offset is accepted);
* an IANA zone name, e.g. ``Europe/Athens``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, TypeVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import polars as pl
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

NEW_YORK = "America/New_York"
_NY_TOKEN = re.compile(r"^NY([+-]\d{1,2})$", re.IGNORECASE)
_MAX_NY_OFFSET_HOURS = 14
_NY_ROLLOVER_MINUTE = 17 * 60
_WEEKEND_GAP = timedelta(hours=24)

SeriesOrExpr = TypeVar("SeriesOrExpr", pl.Series, pl.Expr)


class BrokerClockError(ValueError):
    """Raised for an unparseable or invalid broker clock token."""


class BrokerClock(BaseModel):
    """Maps naive broker wall-clock times to and from true UTC."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    iana: str | None = None
    ny_offset_hours: int | None = None

    @model_validator(mode="after")
    def _exactly_one_kind(self) -> BrokerClock:
        if (self.iana is None) == (self.ny_offset_hours is None):
            msg = "invalid broker clock: set exactly one of iana / ny_offset_hours"
            raise ValueError(msg)
        if self.ny_offset_hours is not None and abs(self.ny_offset_hours) > _MAX_NY_OFFSET_HOURS:
            msg = f"invalid broker clock: NY offset {self.ny_offset_hours}h out of range"
            raise ValueError(msg)
        if self.iana is not None:
            try:
                ZoneInfo(self.iana)
            except (
                ZoneInfoNotFoundError,
                ValueError,
                OSError,
            ) as exc:  # OSError: directory names on 3.12
                msg = f"invalid broker clock: unknown IANA zone {self.iana!r}"
                raise ValueError(msg) from exc
        return self

    @classmethod
    def parse(cls, token: str) -> BrokerClock:
        """Parse ``"NY+7"`` / ``"NY-2"`` or an IANA zone name such as ``"Europe/Athens"``."""
        text = token.strip()
        match = _NY_TOKEN.match(text)
        if not text or (text.upper().startswith("NY") and not match):
            msg = f"invalid broker clock {token!r}: expected 'NY+<hours>' or an IANA zone"
            raise BrokerClockError(msg)
        try:
            return cls(ny_offset_hours=int(match.group(1))) if match else cls(iana=text)
        except ValidationError as exc:
            detail = (
                exc.errors()[0]["msg"]
                .removeprefix("Value error, ")
                .removeprefix("invalid broker clock: ")
            )
            msg = f"invalid broker clock {token!r}: {detail}"
            raise BrokerClockError(msg) from exc

    @property
    def token(self) -> str:
        """Canonical text form, accepted by :meth:`parse`."""
        if self.iana is not None:
            return self.iana
        return f"NY{self.ny_offset_hours:+d}"

    def server_to_utc(self, naive: SeriesOrExpr, *, strict: bool = True) -> SeriesOrExpr:
        """Naive server wall-clock values -> tz-aware UTC.

        With ``strict`` (default) ambiguous and non-existent local times raise; otherwise they
        become null (use only for slots known to fall in closed hours).
        """
        policy: Literal["raise", "null"] = "raise" if strict else "null"
        if self.iana is not None:
            local = naive.dt.replace_time_zone(self.iana, ambiguous=policy, non_existent=policy)
        else:
            shifted = naive - timedelta(hours=self.ny_offset_hours or 0)
            local = shifted.dt.replace_time_zone(NEW_YORK, ambiguous=policy, non_existent=policy)
        return local.dt.convert_time_zone("UTC")

    def utc_to_server(self, utc: SeriesOrExpr) -> SeriesOrExpr:
        """tz-aware UTC values -> naive server wall-clock values."""
        if self.iana is not None:
            return utc.dt.convert_time_zone(self.iana).dt.replace_time_zone(None)
        ny_wall = utc.dt.convert_time_zone(NEW_YORK).dt.replace_time_zone(None)
        return ny_wall + timedelta(hours=self.ny_offset_hours or 0)

    def to_server_wall(self, utc_dt: datetime) -> datetime:
        """A single UTC instant -> naive server wall clock."""
        if self.iana is not None:
            return utc_dt.astimezone(ZoneInfo(self.iana)).replace(tzinfo=None)
        ny_wall = utc_dt.astimezone(ZoneInfo(NEW_YORK)).replace(tzinfo=None)
        return ny_wall + timedelta(hours=self.ny_offset_hours or 0)

    def label_as_utc(self, utc_dt: datetime) -> datetime:
        """Server wall clock for ``utc_dt``, labelled as UTC (what MT5 request bounds expect)."""
        return self.to_server_wall(utc_dt).replace(tzinfo=UTC)


@dataclass(frozen=True)
class ClockScore:
    """How well one candidate clock explains the weekly session boundaries in a dataset."""

    clock: BrokerClock
    consistency: float
    """Share of weeks whose close/open fall on the modal New York minute (1.0 = stable)."""
    anchor_error_minutes: int
    """Distance of the modal weekly close from the 17:00 New York rollover (tie-breaker)."""
    weeks: int


def _modal_fraction(values: list[int]) -> tuple[float, int]:
    counts: dict[int, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    modal_value, modal_count = max(counts.items(), key=lambda kv: (kv[1], -kv[0]))
    return modal_count / len(values), modal_value


def infer_broker_clock(bars: pl.DataFrame, candidates: list[BrokerClock]) -> list[ClockScore]:
    """Rank candidate clocks by how stable the weekly close/open is in New York time.

    ``bars`` carries naive broker wall-clock ``timestamp`` labels. The real session boundary is
    anchored to New York time, so the correct clock yields a constant New York minute-of-day for
    the last bar before each weekend gap, across US and EU daylight-saving changes. Clocks that
    differ only by a constant hour tie on consistency; ``anchor_error_minutes`` breaks the tie
    toward the conventional 17:00 New York rollover and should be confirmed with a live
    server-time offset measurement.
    """
    scores: list[ClockScore] = []
    for clock in candidates:
        utc = clock.server_to_utc(bars["timestamp"], strict=False).drop_nulls()
        if utc.len() < 2:
            continue
        gaps = (utc.diff() > _WEEKEND_GAP).fill_null(False)
        gap_idx = [i for i, flag in enumerate(gaps.to_list()) if flag]
        if not gap_idx:
            continue
        ny = utc.dt.convert_time_zone(NEW_YORK)
        minutes = (ny.dt.hour().cast(pl.Int32) * 60 + ny.dt.minute().cast(pl.Int32)).to_list()
        closes = [minutes[i - 1] for i in gap_idx]
        opens = [minutes[i] for i in gap_idx]
        close_frac, close_mode = _modal_fraction(closes)
        open_frac, _ = _modal_fraction(opens)
        scores.append(
            ClockScore(
                clock=clock,
                consistency=(close_frac + open_frac) / 2,
                anchor_error_minutes=abs(close_mode - _NY_ROLLOVER_MINUTE),
                weeks=len(gap_idx),
            )
        )
    return sorted(scores, key=lambda s: (-round(s.consistency, 9), s.anchor_error_minutes))
