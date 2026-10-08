"""Resample bars to a coarser timeframe on broker-clock boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

import polars as pl

from xau_edge.domain.bars import coerce_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.broker_clock import BrokerClock
from xau_edge.market_data.validators.market_calendar import MarketCalendar

SpreadPolicy = Literal["first", "last", "max", "mean"]


@dataclass(frozen=True)
class ResampleResult:
    """Resampled bars plus the buckets that were dropped for lacking source bars."""

    frame: pl.DataFrame
    incomplete: tuple[datetime, ...]
    """UTC open times of buckets missing source bars during open market hours (not in ``frame``)."""


def _spread_expr(policy: SpreadPolicy) -> pl.Expr:
    col = pl.col("spread")
    match policy:
        case "first":
            return col.first()
        case "last":
            return col.last()
        case "max":
            return col.max()
        case "mean":
            return col.mean().round(0).cast(pl.Int64)
        case _:
            msg = f"unknown spread_policy {policy!r}; use one of first, last, max, mean"
            raise ValueError(msg)


def resample_bars(
    df: pl.DataFrame,
    source: Timeframe,
    target: Timeframe,
    *,
    clock: BrokerClock,
    calendar: MarketCalendar,
    spread_policy: SpreadPolicy = "last",
) -> ResampleResult:
    """Aggregate ``source`` bars into ``target`` bars.

    Buckets are aligned to the broker's server clock (so H4 bars start at server 00:00, 04:00,
    ...), exactly as the broker builds its own bars. A bucket is complete when it holds a bar
    for every source slot that the market calendar says is open; incomplete buckets are
    excluded from the frame and reported, never silently filled.

    The input must have strictly increasing timestamps (run ``validate_bars`` first).
    """
    if target.minutes <= source.minutes or target.minutes % source.minutes != 0:
        msg = "target timeframe must be a coarser multiple of the source timeframe"
        raise ValueError(msg)
    steps = df["timestamp"].diff().drop_nulls()
    if steps.len() > 0 and not bool((steps > timedelta(0)).all()):
        msg = "timestamps must be strictly increasing (sorted, no duplicates); run validate_bars"
        raise ValueError(msg)

    ratio = target.minutes // source.minutes
    tgt_step = f"{target.minutes}m"
    spread = _spread_expr(spread_policy)  # validates the policy before any work is done

    work = df.with_columns(
        clock.utc_to_server(pl.col("timestamp")).dt.truncate(tgt_step).alias("_bucket"),
        calendar.closed_span_expr(pl.col("timestamp"), source.minutes)
        .fill_null(False)
        .alias("_in_closed_slot"),
    )
    has_real = pl.col("real_volume").count() > 0
    buckets = work.group_by("_bucket", maintain_order=True).agg(
        pl.col("open").first(),
        pl.col("high").max(),
        pl.col("low").min(),
        pl.col("close").last(),
        pl.col("tick_volume").sum(),
        spread.alias("spread"),
        pl.when(has_real).then(pl.col("real_volume").sum()).otherwise(None).alias("real_volume"),
        (~pl.col("_in_closed_slot")).sum().alias("_n"),  # only bars in OPEN slots count
    )

    slots = (
        buckets.select("_bucket")
        .with_columns(pl.int_ranges(0, ratio).alias("_i"))
        .explode("_i")
        .with_columns(
            (pl.col("_bucket") + pl.duration(minutes=pl.col("_i") * source.minutes)).alias("_slot")
        )
        .with_columns(clock.server_to_utc(pl.col("_slot"), strict=False).alias("_slot_utc"))
        .with_columns(
            calendar.closed_span_expr(pl.col("_slot_utc"), source.minutes)
            .fill_null(True)
            .alias("_closed")
        )
    )
    expected = slots.group_by("_bucket").agg((~pl.col("_closed")).sum().alias("_expected"))

    joined = buckets.join(expected, on="_bucket", how="left")
    complete_mask = pl.col("_n") >= pl.col("_expected")
    incomplete_buckets = joined.filter(~complete_mask).sort("_bucket")["_bucket"]
    kept = joined.filter(complete_mask)

    frame = kept.with_columns(clock.server_to_utc(pl.col("_bucket")).alias("timestamp")).select(
        "timestamp", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"
    )
    incomplete = tuple(clock.server_to_utc(incomplete_buckets).to_list())
    return ResampleResult(frame=coerce_bars(frame), incomplete=incomplete)
