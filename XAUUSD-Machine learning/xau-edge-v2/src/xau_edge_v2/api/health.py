"""Health aggregation: data store, freshness, disk, live feed, decision engine and model status."""

from __future__ import annotations

from datetime import UTC, datetime

from xau_edge_v2 import __version__
from xau_edge_v2.api.context import AppContext
from xau_edge_v2.api.paper import engine_status, get_alerter
from xau_edge_v2.data.store_status import build_store_status
from xau_edge_v2.domain.contract import (
    HealthCheck,
    HealthResponse,
    StoreStatus,
    Timeframe,
)


def _freshness_check(store: StoreStatus) -> HealthCheck:
    m1 = next((t for t in store.timeframes if t.timeframe is Timeframe.M1), None)
    if m1 is None or m1.latest_bar_open is None:
        return HealthCheck(
            id="freshness", label="Độ mới dữ liệu", state="FAIL", detail="không có nến M1"
        )
    market = store.market_status.value
    if m1.state == "STALE":
        age = "?" if m1.open_age_seconds is None else f"{m1.open_age_seconds:.0f}"
        return HealthCheck(
            id="freshness", label="Độ mới dữ liệu", state="WARN",
            detail=f"nến M1 quá cũ: {age}s thị trường mở kể từ lần đóng cuối (thị trường {market})",
        )  # fmt: skip
    detail = (
        f"nến M1 đóng cách đây {m1.age_seconds:.0f}s"
        if m1.state == "FRESH"
        else f"thị trường {market}; nến M1 cuối cách {m1.age_seconds or 0:.0f}s (không tính là cũ)"
    )
    return HealthCheck(id="freshness", label="Độ mới dữ liệu", state="OK", detail=detail)


def _disk_check(store: StoreStatus, warn_gb: float, critical_gb: float) -> HealthCheck:
    free = store.disk_free_gb
    if free is None:
        return HealthCheck(
            id="disk", label="Ổ dữ liệu", state="WARN", detail="không đọc được dung lượng"
        )
    state = "FAIL" if free < critical_gb else ("WARN" if free < warn_gb else "OK")
    return HealthCheck(id="disk", label="Ổ dữ liệu", state=state, detail=f"còn {free:.1f} GB")


def _backup_checks(ctx: AppContext, now: datetime) -> list[HealthCheck]:
    """Mirrors of the daily backup, and the plain statement about the off-device copy."""
    mirrors = engine_status(ctx).mirrors
    near = [m for m in mirrors if not m.offdevice]
    off = [m for m in mirrors if m.offdevice]

    def check(cid: str, label: str, group: list) -> HealthCheck:  # type: ignore[type-arg]
        late = [
            m for m in group
            if m.last_ok is None or (now - m.last_ok).total_seconds() > 26 * 3600
        ]  # fmt: skip
        if late:
            why = "; ".join(f"{m.path}: {m.last_error or 'chưa có bản sao nào'}" for m in late)
            return HealthCheck(id=cid, label=label, state="WARN", detail=why)
        newest = max(m.last_ok for m in group if m.last_ok)
        return HealthCheck(
            id=cid,
            label=label,
            state="OK",
            detail=f"{len(group)} nơi, bản gần nhất {newest:%Y-%m-%d %H:%M}Z",
        )

    out = [
        check("backup_mirror", "Bản sao sao lưu (phân vùng khác)", near)
        if near
        else HealthCheck(
            id="backup_mirror",
            label="Bản sao sao lưu (phân vùng khác)",
            state="WARN",
            detail="chưa cấu hình nơi sao chép thứ hai",
        )
    ]
    out.append(
        check("backup_offdevice", "Bản sao NGOÀI thiết bị", off)
        if off
        else HealthCheck(
            id="backup_offdevice",
            label="Bản sao NGOÀI thiết bị",
            state="WARN",
            detail="CHƯA CÓ: mọi bản sao đang nằm trên cùng một ổ vật lý (đặt XAU_V2_BACKUP_OFFDEVICE_DIR tới ổ ngoài/NAS/thư mục đám mây đã đăng nhập)",
        )
    )
    alerter = get_alerter(ctx)
    if not alerter.configured:
        out.append(
            HealthCheck(
                id="alerts", label="Cảnh báo Telegram", state="WARN",
                detail="CHƯA cấu hình (đặt XAU_V2_TELEGRAM_BOT_TOKEN và XAU_V2_TELEGRAM_CHAT_ID trong .env)",
            )
        )  # fmt: skip
    elif alerter.last_error:
        out.append(
            HealthCheck(
                id="alerts",
                label="Cảnh báo Telegram",
                state="WARN",
                detail=f"gửi lỗi: {alerter.last_error} ({alerter.failed} lỗi, {alerter.sent} đã gửi)",
            )
        )
    else:
        last = (
            "chưa gửi"
            if alerter.last_sent_at is None
            else f"gửi lần cuối {alerter.last_sent_at:%Y-%m-%d %H:%M}Z"
        )
        out.append(
            HealthCheck(
                id="alerts",
                label="Cảnh báo Telegram",
                state="OK",
                detail=f"đã cấu hình, {alerter.sent} đã gửi, {last}; chỉ gửi cảnh báo vận hành",
            )
        )
    return out


def _paper_checks(ctx: AppContext, store: StoreStatus, now: datetime) -> list[HealthCheck]:
    """The paper book and its engine: watchdog, database integrity, backup, unmanaged positions."""
    cfg = ctx.settings
    status = engine_status(ctx)
    open_count = len(ctx.desk.store.positions("OPEN", 50))
    out: list[HealthCheck] = []
    if not cfg.engine_enabled:
        loop = HealthCheck(
            id="engine_loop", label="Vòng nền PAPER", state="WARN",
            detail="engine TẮT: lệnh mở không được quản lý, không ghi quan sát forward",
        )  # fmt: skip
    else:
        limit = 3 * cfg.paper_poll_seconds + 10
        age = None if status.last_ok is None else (now - status.last_ok).total_seconds()
        up = (now - status.started).total_seconds()
        if age is None and up > limit + 20:
            state, detail = "FAIL", f"engine chưa chạy xong lượt nào sau {up:.0f}s"
        elif age is not None and age > limit:
            state, detail = (
                "WARN",
                f"engine không có lượt thành công nào trong {age:.0f}s (ngưỡng {limit:.0f}s)",
            )
        elif (
            status.last_error_at is not None
            and (now - status.last_error_at).total_seconds() < limit
        ):
            state, detail = "WARN", f"lượt gần nhất lỗi: {status.last_error}"
        else:
            state, detail = (
                "OK",
                f"{status.ticks} lượt, {status.errors} lỗi, lượt cuối {status.last_ms:.0f} ms",
            )
        loop = HealthCheck(id="engine_loop", label="Vòng nền PAPER", state=state, detail=detail)
    out.append(loop)
    backup = (
        "chưa sao lưu"
        if status.last_backup is None
        else f"sao lưu {status.last_backup:%Y-%m-%d %H:%M}Z"
    )
    if status.integrity:
        out.append(
            HealthCheck(
                id="paper_db",
                label="CSDL sổ PAPER",
                state="FAIL",
                detail="; ".join(status.integrity[:3]),
            )
        )
    else:
        out.append(
            HealthCheck(
                id="paper_db",
                label="CSDL sổ PAPER",
                state="OK",
                detail=f"toàn vẹn, {backup}, {status.logged_bars} nến M5 đã ghi",
            )
        )
    out += _backup_checks(ctx, now)
    m1 = next((t for t in store.timeframes if t.timeframe == "M1"), None)
    stale = m1 is not None and m1.state == "STALE"
    if open_count and stale:
        out.append(
            HealthCheck(
                id="paper",
                label="Sổ PAPER",
                state="WARN",
                detail=f"{open_count} lệnh đang mở nhưng dữ liệu M1 cũ: không có nến mới để quản lý SL/TP",
            )
        )
    else:
        out.append(
            HealthCheck(
                id="paper",
                label="Sổ PAPER",
                state="OK",
                detail=f"tự động {'BẬT' if ctx.desk.auto else 'TẮT'}, {open_count} lệnh đang mở",
            )
        )
    return out


def build_health(ctx: AppContext) -> HealthResponse:
    now = datetime.now(UTC)
    cfg = ctx.settings
    store = build_store_status(ctx.store, ctx.calendar, now)
    checks: list[HealthCheck] = [
        HealthCheck(
            id="store",
            label="Kho dữ liệu (chỉ đọc)",
            state="OK" if store.reachable else "FAIL",
            detail=store.root if store.reachable else f"không tìm thấy {store.root}",
        )
    ]
    if store.reachable:
        checks.append(_freshness_check(store))
        quote = ctx.live.quote(ctx.calendar, now)
        if quote.state in {"UNAVAILABLE", "STALE"}:
            checks.append(
                HealthCheck(id="live", label="Quote live", state="WARN", detail=quote.reason)
            )
        else:
            checks.append(
                HealthCheck(id="live", label="Quote live", state="OK", detail=quote.reason)
            )
    checks.append(_disk_check(store, cfg.disk_warn_gb, cfg.disk_critical_gb))
    checks.append(
        HealthCheck(
            id="engine", label="Bộ máy quyết định", state="OK",
            detail="baseline v1.1.0 (UNVALIDATED, PAPER), khớp V1 theo golden test",
        )
    )  # fmt: skip
    checks += _paper_checks(ctx, store, now)
    checks.append(
        HealthCheck(
            id="model",
            label="Mô hình ML",
            state="NOT_DEPLOYED",
            detail="V0 bị loại tại Kiểm định (RETIRED): không hiển thị dự báo, không thẩm quyền",
        )
    )
    states = {c.state for c in checks}
    status = "DOWN" if "FAIL" in states else ("DEGRADED" if states - {"OK"} else "OK")
    return HealthResponse(
        status=status,
        version=__version__,
        generated_at=now,
        uptime_s=round((now - ctx.started).total_seconds(), 1),
        checks=tuple(checks),
        store=store,
    )
