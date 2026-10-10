"""Server-authoritative data ages and the system health rows the trading screen shows.

The page never decides what is "stale": it shows what the server says. Four different ages are kept
apart, because they mean different things (a closed market ages the first two, nothing is wrong):

* ``quote``               seconds since the last tick the executable quote comes from
* ``last_bar``            seconds since the newest closed M1 bar
* ``collector_heartbeat`` seconds since the collector last wrote its status file (it beats on a
                          closed market too)
* ``last_decision``       seconds since the engine last computed a decision

States: FRESH, STALE, MARKET_CLOSED (old, but the market is closed: expected), UNAVAILABLE and
REPLAY (not live data).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

QUOTE_STALE_SECONDS = 30.0
COLLECTOR_STALE_SECONDS = 60.0
DECISION_STALE_SECONDS = (
    150.0  # one new closed M1 bar is expected every 60 s while the market is open
)
TICK_LAG_WARN_SECONDS = 120.0


def _age_row(age: float | None, state: str) -> dict[str, Any]:
    return {"age_seconds": None if age is None else round(age, 1), "state": state}


def _live_state(
    age: float | None, limit: float, *, market_open: bool, heartbeat: bool = False
) -> str:
    if age is None:
        return "UNAVAILABLE"
    if not market_open and not heartbeat:
        return "MARKET_CLOSED"
    return "STALE" if age > limit else "FRESH"


def data_ages(
    *,
    live: bool,
    market_open: bool,
    quote_age: float | None,
    bar_age: float | None,
    bars_stale: bool,
    collector_age: float | None,
    decision_age: float | None,
) -> dict[str, Any]:
    """The four ages with a state each. A closed market never makes the quote or the bars STALE."""
    if not live:
        replay = {"age_seconds": None, "state": "REPLAY"}
        return {
            "live": False,
            "market_open": market_open,
            "quote": replay,
            "last_bar": replay,
            "collector_heartbeat": replay,
            "last_decision": replay,
        }
    bar_state = (
        "UNAVAILABLE"
        if bar_age is None
        else "MARKET_CLOSED"
        if not market_open
        else "STALE"
        if bars_stale
        else "FRESH"
    )
    return {
        "live": True,
        "market_open": market_open,
        "quote": _age_row(
            quote_age, _live_state(quote_age, QUOTE_STALE_SECONDS, market_open=market_open)
        ),
        "last_bar": _age_row(bar_age, bar_state),
        # a stopped collector is a fault even on a closed market: it wakes up with the market
        "collector_heartbeat": _age_row(
            collector_age,
            _live_state(
                collector_age, COLLECTOR_STALE_SECONDS, market_open=market_open, heartbeat=True
            ),
        ),
        "last_decision": _age_row(
            decision_age, _live_state(decision_age, DECISION_STALE_SECONDS, market_open=market_open)
        ),
    }


def _row(row_id: str, label: str, state: str, detail: str) -> dict[str, str]:
    return {"id": row_id, "label": label, "state": state, "detail": detail}


def system_health(
    *,
    collector: dict[str, Any] | None,
    collector_age: float | None,
    live: bool,
    writer_error: str | None,
    coverage: dict[str, Any] | None,
    news: dict[str, Any] | None,
    strategy_version: str,
    source_mode: str,
) -> list[dict[str, str]]:
    """One row per component the trader depends on: OK, WARN, ERROR or UNKNOWN, and why."""
    rows: list[dict[str, str]] = []
    if not live or collector is None:
        why = "replay: no live collector" if not live else "collector status file missing"
        for row_id, label in (
            ("mt5", "MT5 terminal"),
            ("collector", "Collector"),
            ("bar_parity", "Nến khớp terminal"),
            ("tick_storage", "Lưu tick"),
            ("disk", "Ổ đĩa"),
        ):
            rows.append(_row(row_id, label, "UNKNOWN", why))
    else:
        rows.append(_mt5(collector))
        rows.append(_collector(collector, collector_age))
        rows.append(_parity(collector))
        rows.append(_ticks(collector))
        rows.append(_disk(collector))
    rows.append(_row("api", "API", "OK", "đang trả lời (bạn đang đọc dữ liệu từ nó)"))
    rows.append(_coverage(coverage))
    rows.append(_news(news))
    rows.append(
        _row("writer_lock", "Quyền ghi bàn PAPER", "ERROR", writer_error)
        if writer_error
        else _row(
            "writer_lock", "Quyền ghi bàn PAPER", "OK", "tiến trình này giữ quyền ghi duy nhất"
        )
    )
    rows.append(_row("strategy", "Phiên bản chiến lược", "OK", f"v{strategy_version}"))
    rows.append(
        _row("source_mode", "Nguồn dữ liệu", "OK", "LIVE")
        if source_mode == "LIVE"
        else _row("source_mode", "Nguồn dữ liệu", "WARN", f"{source_mode}: KHÔNG PHẢI LIVE")
    )
    return rows


def _mt5(collector: dict[str, Any]) -> dict[str, str]:
    connected = collector.get("connected")
    server = collector.get("server") or "?"
    if connected is True:
        return _row("mt5", "MT5 terminal", "OK", f"đã kết nối ({server}, chỉ đọc)")
    if connected is False:
        return _row("mt5", "MT5 terminal", "ERROR", "terminal không kết nối")
    return _row("mt5", "MT5 terminal", "UNKNOWN", "collector chưa báo trạng thái kết nối")


def _collector(collector: dict[str, Any], age: float | None) -> dict[str, str]:
    if age is None or age > COLLECTOR_STALE_SECONDS:
        ago = "không rõ" if age is None else f"{age:.0f} s trước"
        return _row("collector", "Collector", "ERROR", f"không còn ghi nhịp tim (lần cuối {ago})")
    health = str(collector.get("health", "UNKNOWN"))
    reasons = "; ".join(str(r) for r in collector.get("reasons", [])[:2])
    state = {"GOOD": "OK", "DEGRADED": "WARN", "STALE": "ERROR"}.get(health, "UNKNOWN")
    return _row("collector", "Collector", state, f"{health}: {reasons}" if reasons else health)


def _parity(collector: dict[str, Any]) -> dict[str, str]:
    reasons = [str(r) for r in collector.get("reasons", [])]
    differing = [r for r in reasons if "differ from the terminal" in r]
    if differing:
        return _row(
            "bar_parity",
            "Nến khớp terminal",
            "WARN",
            differing[0] + " (chưa được sửa có kiểm toán)",
        )
    return _row(
        "bar_parity", "Nến khớp terminal", "OK", "không có nến lệch chưa xử lý trong giờ qua"
    )


def _ticks(collector: dict[str, Any]) -> dict[str, str]:
    store = collector.get("tick_store") or {}
    if not store.get("enabled"):
        return _row("tick_storage", "Lưu tick", "UNKNOWN", "lưu tick đang tắt")
    lag = store.get("lag_seconds")
    if lag is None:
        return _row("tick_storage", "Lưu tick", "UNKNOWN", "chưa có độ trễ")
    state = "OK" if float(lag) <= TICK_LAG_WARN_SECONDS else "WARN"
    return _row(
        "tick_storage",
        "Lưu tick",
        state,
        f"chậm {float(lag):.0f} s, phủ đến {store.get('covered_until')}",
    )


def _disk(collector: dict[str, Any]) -> dict[str, str]:
    disk = collector.get("disk") or {}
    level = str(disk.get("level", "UNKNOWN"))
    drives = [d for d in disk.get("drives", []) if d.get("level") not in (None, "GOOD")]
    worst = "; ".join(f"{d['drive']} còn {d['free_gb']} GB" for d in drives[:3])
    state = {"GOOD": "OK", "WARN": "WARN", "CRITICAL": "ERROR"}.get(level, "UNKNOWN")
    if state == "OK" and drives:
        state = "WARN"
    detail = f"ổ dữ liệu còn {disk.get('free_gb', '?')} GB" + (f"; {worst}" if worst else "")
    return _row("disk", "Ổ đĩa", state, detail)


def _coverage(coverage: dict[str, Any] | None) -> dict[str, str]:
    if coverage is None:
        return _row(
            "decision_coverage", "Độ phủ quyết định", "UNKNOWN", "chưa có dữ liệu (hoặc replay)"
        )
    detail = (
        f"{coverage['coverage_pct']:.1f}% ({coverage['recorded_m1_decisions']}/"
        f"{coverage['expected_m1_decisions']})"
    )
    return _row(
        "decision_coverage", "Độ phủ quyết định", "OK" if coverage["complete"] else "WARN", detail
    )


def _news(news: dict[str, Any] | None) -> dict[str, str]:
    if news is None:
        return _row("news", "Lịch tin tức", "UNKNOWN", "chưa có thông tin")
    state = str(news.get("state", "UNKNOWN"))
    mapped = {"CLEAR": "OK", "BLOCKED": "OK", "ERROR": "ERROR"}.get(state, "WARN")
    return _row("news", "Lịch tin tức", mapped, f"{state}: {news.get('detail') or ''}".strip())


def decision_age(now: datetime, generated_at: datetime | None) -> float | None:
    """Seconds since the engine last computed a decision."""
    return None if generated_at is None else max(0.0, (now - generated_at).total_seconds())
