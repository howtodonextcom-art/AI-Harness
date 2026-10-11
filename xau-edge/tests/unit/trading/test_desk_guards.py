"""flatten_required and daily_loss_guard are wired into the paper desk (no broker send)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.trading.test_paper_desk import bars, make_desk, opened
from xau_edge.trading.governor import GovernorConfig
from xau_edge.trading.paper_desk import DeskRefusal
from xau_edge.trading.schema import Refusal


def test_daily_loss_stop_blocks_a_new_open(tmp_path: Path) -> None:
    desk = make_desk(tmp_path, governor=GovernorConfig(daily_loss_stop_pct=0.01))
    desk.day_start_equity = lambda now: 1_000_000.0  # type: ignore[method-assign]
    with pytest.raises(DeskRefusal) as exc:
        opened(desk)
    assert exc.value.code == Refusal.DAILY_LIMIT.value


def test_flatten_required_closes_an_open_paper_position(tmp_path: Path) -> None:
    desk = make_desk(
        tmp_path,
        governor=GovernorConfig(daily_loss_stop_pct=50.0, daily_loss_flatten_pct=0.01),
    )
    rec = opened(desk)
    assert rec["status"] == "OPEN"
    desk.day_start_equity = lambda now: 1_000_000.0  # type: ignore[method-assign]
    closed = desk.process_bars(bars([(1, 2000.2, 2000.5, 1999.9, 2000.2)]))
    assert len(closed) == 1
    assert closed[0]["exit_reason"] == "DAILY_LOSS_GUARD"
    journal = (tmp_path / "paper_journal.jsonl").read_text(encoding="utf-8")
    assert "DAILY_LOSS_GUARD" in journal
