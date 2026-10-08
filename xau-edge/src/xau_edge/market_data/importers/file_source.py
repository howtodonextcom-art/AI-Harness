"""Offline bar source reading CSV (including MetaTrader exports) and Parquet files."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Final

import polars as pl

from xau_edge.domain.bars import BarRequest, coerce_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.broker_clock import BrokerClock

_CSV_SUFFIXES: Final = {".csv", ".tsv", ".txt"}
_PARQUET_SUFFIXES: Final = {".parquet", ".pq"}

_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "timestamp": ("timestamp", "time", "datetime", "date_time"),
    "open": ("open",),
    "high": ("high",),
    "low": ("low",),
    "close": ("close",),
    "tick_volume": ("tick_volume", "tickvol", "tick_vol"),
    "spread": ("spread",),
    "real_volume": ("real_volume", "vol", "real_vol"),
}

_DATETIME_FORMATS: Final = (
    "%Y-%m-%d %H:%M:%S%.f",
    "%Y.%m.%d %H:%M:%S%.f",
    "%Y-%m-%dT%H:%M:%S%.f",
    "%Y-%m-%d %H:%M",
    "%Y.%m.%d %H:%M",
)
_OFFSET_FORMATS: Final = (
    "%Y-%m-%dT%H:%M:%S%.f%z",
    "%Y-%m-%d %H:%M:%S%.f%z",
    "%Y-%m-%dT%H:%M:%S%.f%:z",
    "%Y-%m-%d %H:%M:%S%.f%:z",
)


class UnsupportedFileError(ValueError):
    """Raised for files whose extension is not a supported bar format."""


def _normalise(name: str) -> str:
    return name.strip().strip("<>").strip().lower()


def _sniff_separator(path: Path) -> str:
    with path.open(encoding="utf-8-sig") as handle:
        header = handle.readline()
    for sep in ("\t", ";", ","):
        if sep in header:
            return sep
    return ","


def _parse_text_timestamp(series: pl.Series, clock: BrokerClock) -> pl.Series:
    series = series.str.replace(r"Z$", "+0000")
    for fmt in _OFFSET_FORMATS:
        try:
            return series.str.to_datetime(fmt, time_unit="us", strict=True).dt.convert_time_zone(
                "UTC"
            )
        except pl.exceptions.PolarsError:
            continue
    for fmt in _DATETIME_FORMATS:
        try:
            naive = series.str.to_datetime(fmt, time_unit="us", strict=True)
        except pl.exceptions.PolarsError:
            continue
        return clock.server_to_utc(naive)
    msg = f"Cannot parse timestamps; sample value: {series[0]!r}"
    raise ValueError(msg)


class FileBarSource:
    """Read bars from a CSV/TSV or Parquet file.

    ``source_timezone`` names the zone of timestamps that carry no offset (for example a
    broker server zone). It is converted to UTC; DST ambiguities raise rather than guess.
    ``columns`` optionally maps canonical names (``open``, ``tick_volume`` ...) to file headers.
    """

    def __init__(
        self,
        path: Path | str,
        *,
        symbol: str,
        timeframe: Timeframe,
        source_timezone: str = "UTC",
        columns: Mapping[str, str] | None = None,
    ) -> None:
        self.path = Path(path)
        self.symbol = symbol
        self.timeframe = timeframe
        self.source_timezone = source_timezone
        self._clock = BrokerClock.parse(source_timezone)
        self.columns = dict(columns or {})
        self.name = f"file:{self.path.name}"

    def fetch_bars(self, request: BarRequest) -> pl.DataFrame:
        """Return file contents restricted to ``[request.start, request.end)``."""
        if request.symbol != self.symbol:
            msg = f"request symbol {request.symbol!r} != source symbol {self.symbol!r}"
            raise ValueError(msg)
        if request.timeframe is not self.timeframe:
            msg = (
                f"request timeframe {request.timeframe.value} != "
                f"source timeframe {self.timeframe.value}"
            )
            raise ValueError(msg)

        suffix = self.path.suffix.lower()
        if suffix not in _CSV_SUFFIXES | _PARQUET_SUFFIXES:
            msg = f"Unsupported bar file type {suffix!r}; use CSV/TSV or Parquet"
            raise UnsupportedFileError(msg)
        if not self.path.exists():
            raise FileNotFoundError(self.path)

        raw = pl.read_parquet(self.path) if suffix in _PARQUET_SUFFIXES else self._read_csv()
        frame = coerce_bars(self._canonicalise(raw))
        return frame.filter(
            (pl.col("timestamp") >= request.start_utc) & (pl.col("timestamp") < request.end_utc)
        )

    def _read_csv(self) -> pl.DataFrame:
        return pl.read_csv(self.path, separator=_sniff_separator(self.path), encoding="utf8")

    def _canonicalise(self, raw: pl.DataFrame) -> pl.DataFrame:
        by_norm = {_normalise(c): c for c in raw.columns}
        combine_date_time = (
            "timestamp" not in self.columns
            and "date" in by_norm
            and "time" in by_norm
            and not {"timestamp", "datetime", "date_time"} & by_norm.keys()
        )
        work = raw
        if combine_date_time:
            # MetaTrader exports split the stamp into <DATE> and <TIME>.
            work = work.with_columns(
                (
                    pl.col(by_norm["date"]).cast(pl.String)
                    + " "
                    + pl.col(by_norm["time"]).cast(pl.String)
                ).alias("__combined_ts")
            )
            by_norm = {k: v for k, v in by_norm.items() if k not in {"date", "time"}}
            by_norm["__combined_ts"] = "__combined_ts"

        rename: dict[str, str] = {}
        for canonical, aliases in _ALIASES.items():
            explicit = self.columns.get(canonical)
            if canonical == "timestamp" and combine_date_time:
                candidates: tuple[str, ...] = ("__combined_ts",)
            else:
                candidates = (_normalise(explicit),) if explicit else aliases
            for cand in candidates:
                if cand in by_norm:
                    rename[by_norm[cand]] = canonical
                    break

        work = work.rename(rename)
        if "timestamp" not in work.columns:
            date_only = by_norm.get("date")
            if date_only:
                work = work.with_columns(pl.col(date_only).cast(pl.String).alias("timestamp"))
        if "timestamp" not in work.columns:
            return work  # coerce_bars will report the missing column

        return work.with_columns(self._timestamp_series(work["timestamp"]).alias("timestamp"))

    def _timestamp_series(self, series: pl.Series) -> pl.Series:
        dtype = series.dtype
        if isinstance(dtype, pl.Datetime):
            if dtype.time_zone is None:
                return self._clock.server_to_utc(series.cast(pl.Datetime("us")))
            return series.dt.convert_time_zone("UTC")
        if dtype.is_integer():
            return self._clock.server_to_utc(
                pl.from_epoch(series, time_unit="s").cast(pl.Datetime("us"))
            )
        return _parse_text_timestamp(series.cast(pl.String), self._clock)
