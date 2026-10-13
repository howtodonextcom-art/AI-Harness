"""Forward evidence summary (read-only): what the engine observed and did, with no claim attached."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request

from xau_edge_v2.api.context import AppContext
from xau_edge_v2.data.bar_store import MAX_LIMIT
from xau_edge_v2.domain.contract import ForwardSummary, Timeframe
from xau_edge_v2.paper import forward

router = APIRouter(prefix="/api/v2/forward", tags=["forward"])
_US = 1_000_000
BAR_US = 300 * _US


def m5_opens(ctx: AppContext, first_us: int, last_us: int) -> list[int]:
    """Open times (µs) of the closed M5 bars the store holds in ``[first, last]``."""
    out: list[int] = []
    cursor = datetime.fromtimestamp(first_us / _US, UTC)
    end = datetime.fromtimestamp(last_us / _US + 1, UTC)
    while cursor < end:
        frame = ctx.store.window(Timeframe.M5, cursor, end, MAX_LIMIT)
        if frame.height == 0:
            break
        stamps = [int(v) for v in frame["timestamp"].dt.epoch("us").to_list()]
        out += stamps
        if frame.height < MAX_LIMIT:
            break
        cursor = datetime.fromtimestamp(stamps[-1] / _US + 1, UTC)
    return out


def build_summary(ctx: AppContext, now: datetime | None = None) -> ForwardSummary:
    moment = now or datetime.now(UTC)
    desk = ctx.desk
    rows = desk.store.decision_rows()
    quote = ctx.live.quote(ctx.calendar, moment)
    bid, ask = (quote.bid, quote.ask) if quote.available else (None, None)
    books = desk.books(moment, bid, ask)
    paper_return = (books["equity"] / desk.start_equity - 1) * 100
    expected = (
        m5_opens(ctx, int(rows[0]["bar_open_us"]), int(rows[-1]["bar_open_us"])) if rows else []
    )
    prices = [r["price"] for r in rows if r["price"] is not None]
    hold = (float(prices[0]), float(prices[-1])) if len(prices) >= 2 else None
    return forward.summarize(
        rows,
        desk.store.all_positions_oldest_first(),
        expected,
        paper_return_pct=paper_return,
        hold_prices=hold,
        bar_us=BAR_US,
    )


@router.get("/summary", response_model=ForwardSummary)
def summary(request: Request) -> ForwardSummary:
    ctx: AppContext = request.app.state.ctx
    return build_summary(ctx)
