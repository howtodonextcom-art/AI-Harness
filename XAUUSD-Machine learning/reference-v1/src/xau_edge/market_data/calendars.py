"""The FTMO session calendar: weekly template from the broker profile + inferred closures."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.profiles import BrokerProfile
from xau_edge.market_data.session_exceptions import load_closures
from xau_edge.market_data.validators.market_calendar import MarketCalendar

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROFILE = ROOT / "configs" / "brokers" / "ftmo_demo.yaml"
DEFAULT_EXCEPTIONS = ROOT / "configs" / "brokers" / "ftmo_session_exceptions.yaml"


def ftmo_profile(path: Path = DEFAULT_PROFILE) -> BrokerProfile:
    return BrokerProfile.from_yaml(path)


def ftmo_calendar(
    profile_path: Path = DEFAULT_PROFILE, exceptions_path: Path = DEFAULT_EXCEPTIONS
) -> MarketCalendar:
    """Weekly template (measured: closes 16:50 NY, reopens 18:05 NY) plus closures."""
    base = ftmo_profile(profile_path).validation.calendar
    return base.model_copy(update={"closures": load_closures(exceptions_path)})


CALENDAR_VERIFIED_FROM = datetime(2025, 1, 1, tzinfo=UTC)
"""The weekly template was measured on recent data; earlier broker eras may differ (UNKNOWN)."""


def classify_incomplete(
    incomplete: tuple[datetime, ...],
    target: Timeframe,
    source_bars: pl.DataFrame,
    calendar: MarketCalendar,
    *,
    verified_from: datetime = CALENDAR_VERIFIED_FROM,
) -> dict[str, list[datetime]]:
    """Why each resampling bucket was dropped: BOUNDARY, HOLIDAY, EARLY_CLOSE, DATA_GAP, UNKNOWN."""
    out: dict[str, list[datetime]] = {
        "BOUNDARY": [], "HOLIDAY": [], "EARLY_CLOSE": [], "DATA_GAP": [], "UNKNOWN": []
    }  # fmt: skip
    if source_bars.height == 0:
        return out
    first = source_bars["timestamp"].min()
    last = source_bars["timestamp"].max()
    for start in incomplete:
        end = start + target.delta
        at_edge = [x for x in (first, last) if isinstance(x, datetime) and start <= x < end]
        if at_edge:
            out["BOUNDARY"].append(start)
        elif hit := next((w for w in calendar.closures if w.start < end and w.end > start), None):
            out[hit.reason].append(start)
        elif start >= verified_from:
            out["DATA_GAP"].append(start)
        else:
            out["UNKNOWN"].append(start)
    return out
