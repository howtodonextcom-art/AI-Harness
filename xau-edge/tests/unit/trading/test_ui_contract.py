"""The dashboard reads these fields of a paper trade (apps/dashboard/lib/trade.ts: PaperTrade).

A field the UI reads but the desk never writes shows "—" on a real trade while every mocked e2e
test stays green (this happened once with ``initial_tp``). This test ties the two together: it opens
and closes a REAL desk trade and checks every field the UI, the journal and the chart markers use.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from tests.unit.trading.test_paper_desk import NOW, Q, make_desk, opened

UI_OPEN_KEYS = {
    "trade_id", "side", "status", "fill_price", "sl", "initial_sl", "tp", "lots", "risk_pct",
    "risk_amount", "opened_at", "created_at", "setup_id", "market", "decision",
    "current_price", "unrealized_pnl", "unrealized_r", "duration_minutes",
}  # fmt: skip
UI_CLOSED_KEYS = UI_OPEN_KEYS - {"current_price", "unrealized_pnl", "unrealized_r"} | {
    "closed_at", "exit_price", "exit_reason", "net_pnl", "r_multiple", "mfe_r", "mae_r",
}  # fmt: skip


def test_an_open_paper_position_has_every_field_the_ui_and_the_chart_read(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    opened(desk)
    view = desk.position_view(Q(), NOW + timedelta(minutes=3))
    assert view is not None
    assert set(view) >= UI_OPEN_KEYS, UI_OPEN_KEYS - set(view)
    assert view["tp"] > view["fill_price"] > view["sl"]  # BUY levels on the right side
    assert "initial_tp" not in view  # the old, wrong name must not come back


def test_a_closed_trade_has_every_field_the_journal_and_exit_markers_read(tmp_path: Path) -> None:
    desk = make_desk(tmp_path)
    rec = opened(desk)
    done = desk.manual_close(
        rec["trade_id"], Q(bid=2000.6, ask=2000.85), NOW + timedelta(minutes=2)
    )
    assert set(done) >= UI_CLOSED_KEYS, UI_CLOSED_KEYS - set(done)
    assert done["exit_reason"] == "MANUAL_CLOSE" and done["closed_at"] is not None
