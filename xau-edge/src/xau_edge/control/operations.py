"""Smoke order and flatten on the DEMO account, through the existing executor only (F4, F5).

No new order path: ``build_smoke_intent``, ``Mt5DemoExecutor.submit_smoke``,
``Mt5DemoExecutor.close_position`` and ``Reconciler`` do all the work, exactly as
``scripts/smoke_demo_order.py`` does. The caller holds the bot lock (bot stopped) while these run.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from xau_edge.brokers.mt5_demo.executor import Mt5DemoExecutor, build_smoke_intent
from xau_edge.brokers.mt5_demo.reader import DemoReader
from xau_edge.execution.reconcile import Reconciler
from xau_edge.execution.state import ExecutionState

SMOKE_NOTE = "Smoke chỉ kiểm tra đường ống lệnh; KHÔNG phải bằng chứng edge."
FLATTEN_REASON = "WEB_FLATTEN"
MANUAL_CLOSE_HINT = (
    "Mở MT5 > tab Trade > nhấp phải vào ticket > Close Position; sau đó chạy lại preflight."
)


@dataclass(frozen=True)
class TradingKit:
    """The collaborators of one smoke or flatten run (real terminal or a fake)."""

    client: Any
    reader: DemoReader
    state: ExecutionState
    reconciler: Reconciler
    executor: Mt5DemoExecutor
    symbol: str
    magic: int


def bot_positions_on_broker(kit: TradingKit) -> list[str]:
    """Tickets on the broker that carry the bot's magic number."""
    return [p.ticket for p in kit.reader.positions() if p.magic == kit.magic]


def run_smoke(
    kit: TradingKit,
    *,
    now: Callable[[], datetime],
    hold_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """One 0.01-lot labelled BUY, held a few seconds, closed, reconciled."""
    info = kit.client.symbol_info(kit.symbol)
    tick = kit.client.symbol_info_tick(kit.symbol)
    if info is None or tick is None:
        return {"status": "REFUSED", "reasons": ["NO_PRICE"], "note": SMOKE_NOTE}
    ask = float(tick.ask)
    point = float(info.point)
    began = monotonic()
    moment = now()
    intent = build_smoke_intent(ask, moment, magic=kit.magic, symbol=kit.symbol)
    result = kit.executor.submit_smoke(intent, moment)
    out: dict[str, Any] = {
        "status": result.status,
        "reasons": list(result.reasons),
        "retcode": result.retcode,
        "requested_price": ask,
        "lots": intent.lots,
        "note": SMOKE_NOTE,
    }
    if result.status == "FILLED" and result.ticket is not None:
        position = next((p for p in kit.reader.positions() if p.ticket == result.ticket), None)
        if position is not None:
            out["fill_price"] = position.entry_price
            out["slippage_points"] = round((position.entry_price - ask) / point, 1)
        sleep(hold_seconds)
        closed = kit.executor.close_position(result.ticket, "SMOKE_DONE")
        out["close_status"] = closed.status
        out["close_reasons"] = list(closed.reasons)
        out["close_retcode"] = closed.retcode
        out["round_trip_seconds"] = round(monotonic() - began, 2)
        if closed.status != "FILLED":
            out["still_open_tickets"] = [result.ticket]
            out["manual_hint"] = MANUAL_CLOSE_HINT
    rec = kit.reconciler.check(kit.reader.snapshot(now()))
    out["reconcile_clean"] = rec.clean
    out["reconcile_codes"] = list(rec.codes)
    return out


def run_flatten(kit: TradingKit, *, now: Callable[[], datetime]) -> dict[str, Any]:
    """Close every position the bot owns (state + magic); manual positions are never touched.

    The caller trips the kill switch BEFORE calling this.
    """
    manual_before = [p.ticket for p in kit.reader.positions() if p.magic != kit.magic]
    results = []
    for record in kit.state.open_positions():
        closed = kit.executor.close_position(record.ticket, FLATTEN_REASON)
        results.append(
            {
                "ticket": record.ticket,
                "status": closed.status,
                "reasons": list(closed.reasons),
                "retcode": closed.retcode,
            }
        )
    still_open = bot_positions_on_broker(kit)
    rec = kit.reconciler.check(kit.reader.snapshot(now()))
    out: dict[str, Any] = {
        "positions": results,
        "still_open_tickets": still_open,
        "manual_positions_untouched": len(manual_before),
        "reconcile_clean": rec.clean,
        "reconcile_codes": list(rec.codes),
    }
    if still_open:
        out["manual_hint"] = MANUAL_CLOSE_HINT
    return out
