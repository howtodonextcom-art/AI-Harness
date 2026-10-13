"""Market-data routes: history by range, live quote, broker symbol spec. All read-only."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from xau_edge_v2.api.context import AppContext
from xau_edge_v2.data.bar_store import MAX_LIMIT
from xau_edge_v2.domain.contract import (
    Bar,
    BarsResponse,
    ErrorBody,
    FormingResponse,
    QuoteResponse,
    SymbolInfo,
    Tick,
    TicksResponse,
    Timeframe,
)

router = APIRouter(prefix="/api/v2/market", tags=["market"])

ERRORS: dict[int | str, dict[str, Any]] = {422: {"model": ErrorBody}, 404: {"model": ErrorBody}}


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        ErrorBody(error_code=code, message=message).model_dump(), status_code=status
    )


def _ctx(request: Request) -> AppContext:
    ctx: AppContext = request.app.state.ctx
    return ctx


def _aware(value: datetime | None) -> bool:
    return value is None or value.tzinfo is not None


@router.get("/bars", response_model=BarsResponse, responses=ERRORS)
def bars(  # noqa: PLR0913, PLR0917 - the query parameters ARE the contract
    request: Request,
    timeframe: Timeframe = Timeframe.M15,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 500,
    before: datetime | None = None,
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
) -> BarsResponse | JSONResponse:
    """History window (closed bars, ascending).

    * none of ``before/from/to``: the newest ``limit`` bars;
    * ``before=T`` (or ``to=T`` alone): the newest ``limit`` bars strictly before ``T``;
    * ``from=A`` [``to=B``]: the first ``limit`` bars in ``[A, B)``.

    ``before`` cannot be combined with ``from``; every bound must carry a timezone.
    """
    store = _ctx(request).store
    if not all(_aware(v) for v in (before, start, end)):
        return _error(
            422, "BARS_TZ_REQUIRED", "from/to/before need a timezone, e.g. 2026-10-12T00:00:00Z"
        )
    if before is not None and (start is not None or end is not None):
        return _error(422, "BARS_PARAMS_CONFLICT", "before cannot be combined with from/to")
    if start is not None and end is not None and end <= start:
        return _error(422, "BARS_RANGE_INVALID", "to must be after from")
    if not store.reachable():
        return _error(404, "STORE_UNAVAILABLE", "the market store is not reachable")

    if start is not None:
        frame = store.window(timeframe, start, end, limit)
    else:
        frame = store.tail(timeframe, limit, before if before is not None else end)

    rows = [
        Bar(
            time=r["timestamp"],
            open=r["open"], high=r["high"], low=r["low"], close=r["close"],
            tick_volume=r["tick_volume"] or 0.0,
            spread=r["spread"],
            is_closed=True,
        )
        for r in frame.iter_rows(named=True)
    ]  # fmt: skip
    cov = store.coverage(timeframe)
    first = rows[0].time if rows else None
    last = rows[-1].time if rows else None
    return BarsResponse(
        timeframe=timeframe,
        bars=tuple(rows),
        oldest_available=cov.oldest,
        newest_available=cov.newest,
        has_more_before=bool(first and cov.oldest and cov.oldest < first),
        has_more_after=bool(last and cov.newest and cov.newest > last),
        data_version=_ctx(request).data_version(cov),
    )


MAX_TICKS_PER_REQUEST = 20_000


@router.get("/ticks", response_model=TicksResponse, responses=ERRORS)
def ticks(
    request: Request,
    start: Annotated[datetime, Query(alias="from")],
    end: Annotated[datetime, Query(alias="to")],
    limit: Annotated[int, Query(ge=1, le=MAX_TICKS_PER_REQUEST)] = 5000,
) -> TicksResponse | JSONResponse:
    """Ticks in ``[from, to)``, oldest first, at most ``limit`` (``has_more`` when truncated)."""
    store = _ctx(request).ticks
    if start.tzinfo is None or end.tzinfo is None:
        return _error(
            422, "TICKS_TZ_REQUIRED", "from/to need a timezone, e.g. 2026-10-12T00:00:00Z"
        )
    if end <= start:
        return _error(422, "TICKS_RANGE_INVALID", "to must be after from")
    if not store.days():
        return _error(404, "TICKS_UNAVAILABLE", "the tick store is empty or not reachable")
    frame = store.load(start, end, limit=limit + 1)
    more = frame.height > limit
    rows = tuple(
        Tick(time_msc=r["timestamp_msc"], time=r["timestamp"], bid=r["bid"], ask=r["ask"])
        for r in frame.head(limit).iter_rows(named=True)
    )
    return TicksResponse(
        ticks=rows,
        count=len(rows),
        limit=limit,
        has_more=more,
        first_day=store.first_day(),
        last_day=store.last_day(),
    )


@router.get("/forming", response_model=FormingResponse)
def forming(request: Request) -> FormingResponse:
    """The still-open bar of each timeframe (from the collector's live file)."""
    live = _ctx(request).live
    return FormingResponse(bars=live.forming(), updated_at=live.updated_at())


@router.get("/quote", response_model=QuoteResponse)
def quote(request: Request) -> QuoteResponse:
    ctx = _ctx(request)
    return ctx.live.quote(ctx.calendar)


@router.get("/symbol", response_model=SymbolInfo, responses={404: {"model": ErrorBody}})
def symbol(request: Request) -> SymbolInfo | JSONResponse:
    info = _ctx(request).live.symbol_info()
    if info is None:
        return _error(
            404, "SYMBOL_SPEC_UNAVAILABLE", "the collector has not published the symbol spec"
        )
    return info
