"""The decision surface: closed bars + live quote + broker spec -> core decision -> StateSnapshot.

PAPER only, label UNVALIDATED. Nothing is fabricated: when the bars or the data are missing the
answer is UNAVAILABLE with a reason, and every WAIT names its blocker.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime

from xau_edge_v2.api.context import AppContext
from xau_edge_v2.api.model import model_info
from xau_edge_v2.core.advice import advise
from xau_edge_v2.core.decision import Decision, DecisionConfig, DecisionContext, decide
from xau_edge_v2.core.execution import ExecutionAssessment, assess_execution
from xau_edge_v2.core.frames import ORDER, Frame, MultiFrames
from xau_edge_v2.core.market_state import build_market_state
from xau_edge_v2.core.risk import SymbolSpec
from xau_edge_v2.data.frames import frame_from_polars
from xau_edge_v2.domain.contract import (
    ActionCode,
    DataInfo,
    EvidenceLabel,
    HumanRecord,
    M1Execution,
    ModelInfo,
    ModelStatus,
    MtfRow,
    Readiness,
    RiskInfo,
    StateSnapshot,
    SystemAdvice,
    Timeframe,
    TradePlan,
    readiness_level,
)
from xau_edge_v2.domain.market import MarketStatus

HISTORY_BARS = 450
"""Bars read per timeframe: the state engine uses the last 400."""

BLOCKERS: dict[str, tuple[str, str]] = {
    "NO_DIRECTION": ("H1 chưa có xu hướng rõ", "H1 chuyển sang tăng hoặc giảm rõ ràng"),
    "TIMEFRAME_CONFLICT": ("Khung lớn ngược hướng H1", "H4 và M15 thôi ngược hướng H1"),
    "NO_SETUP": ("Chưa có nhịp hồi (pullback) trên M15", "M15 hồi về vùng EMA nhanh theo xu hướng"),
    "NO_TRIGGER": ("M5 chưa xác nhận", "M5 có động lượng cùng chiều xu hướng"),
    "SPREAD_TOO_WIDE": ("Spread đang rộng", "Spread trở lại bình thường"),
    "VOLUME_TOO_LOW": ("M1 quá vắng (tick volume thấp)", "Hoạt động M1 trở lại bình thường"),
    "VOLATILITY_TOO_HIGH": ("Biến động quá cao", "Biến động hạ nhiệt"),
    "VOLATILITY_TOO_LOW": ("Biến động quá thấp", "Biến động tăng lại"),
    "TOO_CLOSE_TO_RESISTANCE": ("Quá sát kháng cự", "Giá có thêm khoảng trống tới kháng cự"),
    "TOO_CLOSE_TO_SUPPORT": ("Quá sát hỗ trợ", "Giá có thêm khoảng trống tới hỗ trợ"),
    "RR_TOO_LOW": ("R/R sau chi phí quá thấp", "Có điểm vào cho R/R ròng đủ lớn"),
    "INVALID_STOP_DISTANCE": ("Không có SL hợp lệ", "Cấu trúc cho SL trong giới hạn ATR"),
    "RISK_LIMIT": ("Không cỡ lệnh được trong giới hạn rủi ro", "Rủi ro đủ cho lô tối thiểu"),
    "DAILY_LIMIT": ("Chạm giới hạn ngày", "Sang ngày mới"),
    "COOLDOWN": ("Đang nghỉ sau lệnh", "Hết thời gian nghỉ"),
    "NEWS_UNKNOWN": ("Chưa xác minh tin tức", "Xác minh lịch tin"),
    "NEWS_WINDOW": ("Đang trong cửa sổ tin", "Hết cửa sổ tin"),
    "STALE_DATA": ("Dữ liệu cũ hoặc thiếu", "Dữ liệu mới về"),
    "MARKET_CLOSED": ("Thị trường đang đóng cửa", "Thị trường mở lại"),
    "BROKER_DISCONNECTED": ("Mất kết nối nguồn giá", "Nguồn giá hoạt động lại"),
    "UNKNOWN_STATE": ("Thiếu dữ liệu để đánh giá", "Đủ dữ liệu các khung lớn"),
}

_READINESS = tuple(Readiness)


def load_frames(ctx: AppContext) -> MultiFrames:
    frames: dict[Timeframe, Frame] = {}
    for tf in ORDER:
        frame = frame_from_polars(tf, ctx.store.tail(tf, HISTORY_BARS))
        if frame is not None:
            frames[tf] = frame
    return MultiFrames(frames)


def unavailable_state(now: datetime, version: str, code: str, why: str) -> StateSnapshot:
    return StateSnapshot(
        generated_at=now,
        action=ActionCode.UNAVAILABLE,
        readiness=Readiness.NEUTRAL,
        readiness_level=readiness_level(Readiness.NEUTRAL),
        bias="NEUTRAL",
        headline="Không có quyết định: thiếu dữ liệu đầu vào",
        reason_codes=(code,),
        blocker=why,
        next_condition="Kho dữ liệu có đủ nến các khung",
        evidence=EvidenceLabel.UNVALIDATED,
        model=ModelInfo(status=ModelStatus.NOT_DEPLOYED, note="chưa triển khai (G6)"),
        data=DataInfo(data_version=version, data_timestamp=None, stale=True),
    )


def _spec(ctx: AppContext) -> tuple[SymbolSpec, bool]:
    info = ctx.live.symbol_info()
    if info is None:
        return SymbolSpec(), False
    return (
        SymbolSpec(
            point=info.point,
            tick_size=info.tick_size,
            tick_value=info.tick_value,
            contract_size=info.contract_size,
            volume_min=info.volume_min,
            volume_max=info.volume_max,
            volume_step=info.volume_step,
            stops_level_points=info.stops_level_points,
            freeze_level_points=info.freeze_level_points,
            digits=info.digits,
        ),
        True,
    )


@dataclass(frozen=True)
class Analysis:
    """The strategy's decision plus the M1 execution assessment computed from the same bars."""

    decision: Decision
    execution: ExecutionAssessment


def compute_decision(ctx: AppContext, at: datetime) -> Decision | None:
    """The core decision at ``at`` (None when there are no bars at all)."""
    analysis = compute_analysis(ctx, at)
    return None if analysis is None else analysis.decision


def compute_analysis(ctx: AppContext, at: datetime) -> Analysis | None:
    """Decision + M1 execution at ``at`` (None when there are no bars at all)."""
    frames = load_frames(ctx)
    if not frames.frames:
        return None
    quote = ctx.live.quote(ctx.calendar, at)
    status = ctx.calendar.status(at)
    spec, spec_known = _spec(ctx)
    state = build_market_state(
        frames,
        at,
        spread_points=quote.spread_points if quote.state == "FRESH" else None,
        broker_clock=ctx.broker_clock,
        market_open=status is MarketStatus.OPEN,
        memo=ctx.memo,
    )
    fresh = quote.state == "FRESH"
    cfg = DecisionConfig()
    bid, ask = quote.bid if quote.available else None, quote.ask if quote.available else None
    refusals = ctx.desk.governor_refusals(at, cfg.risk_pct, bid, ask)
    decision = decide(
        state,
        DecisionContext(
            spec=spec,
            equity=ctx.desk.equity(at, bid, ask),
            feed_connected=quote.available,
            cooldown_active="COOLDOWN" in refusals,
            daily_limit_hit="DAILY_LIMIT" in refusals,
            risk_limit_hit="RISK_LIMIT" in refusals,
            market_open=status is MarketStatus.OPEN,
            market_status=status.value,
            data_ok=fresh or status is not MarketStatus.OPEN,
            spec_known=spec_known,
            bid=quote.bid if fresh else None,
            ask=quote.ask if fresh else None,
        ),
        cfg,
    )
    execution = assess_execution(
        decision,
        state,
        frames.as_of(Timeframe.M1, at),
        spec,
        bid=quote.bid if fresh else None,
        ask=quote.ask if fresh else None,
    )
    return Analysis(decision, execution)


def _headline(d: Decision) -> str:
    if d.action == "BUY":
        return "MUA (PAPER): kế hoạch hợp lệ"
    if d.action == "SELL":
        return "BÁN (PAPER): kế hoạch hợp lệ"
    first = d.refusals[0] if d.refusals else "NO_SETUP"
    return f"CHỜ: {BLOCKERS.get(first, ('', ''))[0] or first}"


M1_TEXT: dict[str, str] = {
    "M1_UNKNOWN": "M1 chưa đánh giá được (thiếu nến hoặc kế hoạch)",
    "M1_TOO_EARLY": "M1: quá sớm (M5 chưa xác nhận trigger)",
    "M1_WATCH": "M1: theo dõi (chưa đi theo hướng giao dịch)",
    "M1_FORMING": "M1: đang hình thành (chưa đủ xác nhận)",
    "M1_CONFIRMED": "M1: đã xác nhận nhưng chất lượng thực thi kém",
    "M1_TOO_LATE": "M1: quá muộn (R:R ròng đã giảm dưới mức chấp nhận)",
    "M1_INVALIDATED": "M1: kế hoạch đã vô hiệu (giá chạm/vượt SL)",
}


def blocker_text(code: str) -> str:
    """Human wording for a strategy refusal code or an ``M1_*`` timing hold."""
    return M1_TEXT.get(code) or BLOCKERS.get(code, (code, ""))[0]


def _mtf(d: Decision) -> tuple[MtfRow, ...]:
    """What each timeframe says, in the roles the chain gives them."""
    s = d.state
    if s is None:
        return ()
    rows = (
        (Timeframe.H4, "Chế độ (chỉ chặn)", s.h4_regime),
        (Timeframe.H1, "Hướng (duy nhất)", s.h1_trend),
        (Timeframe.M30, "Bối cảnh (chỉ hiển thị)", s.m30_structure),
        (Timeframe.M15, "Setup", f"{s.m15_structure} / {s.m15_pullback}"),
        (Timeframe.M5, "Trigger", s.m5_momentum),
        (Timeframe.M1, "Thực thi (chỉ chặn)", d.m1_execution_state),
    )
    out: list[MtfRow] = []
    for tf, role, verdict in rows:
        if tf.value not in s.available_timeframes:
            out.append(MtfRow(timeframe=tf, role=role, verdict="UNKNOWN", detail="thiếu dữ liệu"))
            continue
        detail = "nến cũ" if tf.value in s.stale_timeframes else ""
        out.append(MtfRow(timeframe=tf, role=role, verdict=verdict, detail=detail))
    return tuple(out)


def to_snapshot(d: Decision, now: datetime, version: str) -> StateSnapshot:
    level = d.readiness_level
    plan = risk = None
    if d.action in ("BUY", "SELL"):
        assert d.entry_price is not None
        assert d.stop_loss is not None
        assert d.take_profit is not None
        assert d.net_rr is not None
        plan = TradePlan(
            side="BUY" if d.action == "BUY" else "SELL",
            entry=d.entry_price,
            stop_loss=d.stop_loss,
            take_profit_1=d.take_profit,
            take_profit_2=d.take_profit_2,
            net_rr=d.net_rr,
        )
        risk = RiskInfo(
            risk_pct=d.risk_pct or 0.0,
            lots=d.lots,
            risk_amount=d.risk_amount,
            cost_usd=None if d.cost is None else d.cost.total_usd,
            cost_status="UNKNOWN" if d.cost is None else d.cost.status,
            swap_note=None if d.cost is None else d.cost.swap_note,
        )
    blocker, nxt = (None, None)
    if d.refusals:
        blocker, nxt = BLOCKERS.get(d.refusals[0], (d.refusals[0], None))
    state = d.state
    newest = None if state is None else state.snapshots.get("M5") or state.snapshots.get("M15")
    return StateSnapshot(
        generated_at=now,
        action=ActionCode(d.action),
        readiness=_READINESS[level],
        readiness_level=level,
        bias="BUY" if d.bias == "BUY" else "SELL" if d.bias == "SELL" else "NEUTRAL",
        headline=_headline(d),
        reason_codes=d.refusals or ("PLAN_READY",),
        blocker=blocker,
        next_condition=nxt,
        evidence=EvidenceLabel.UNVALIDATED,
        model=ModelInfo(status=ModelStatus.NOT_DEPLOYED, note="chưa triển khai (G6)"),
        plan=plan,
        risk=risk,
        data=DataInfo(
            data_version=version,
            data_timestamp=None if newest is None else newest.bar_closed,
            stale=bool(state and state.data_quality in ("STALE", "UNKNOWN")),
        ),
        decision_id=d.decision_id,
        strategy_version=d.strategy_version,
        chain=d.reasons,
        warnings=d.warnings,
        expires_at=d.expiry,
        mtf=_mtf(d),
    )


CACHE_SECONDS = 1.0


def live_analysis(ctx: AppContext) -> Analysis | None:
    """Decision + execution for the present moment, shared for about a second between the page,
    the socket, the paper engine and the human layer (they ask for the same answer, and computing
    it is not free)."""
    cached = ctx.cache.get("analysis")
    if isinstance(cached, tuple) and time.monotonic() - cached[0] < CACHE_SECONDS:
        result: Analysis | None = cached[1]
        return result
    analysis = compute_analysis(ctx, datetime.now(UTC))
    ctx.cache["analysis"] = (time.monotonic(), analysis)
    return analysis


def live_decision(ctx: AppContext) -> Decision | None:
    """The strategy's decision for the present moment (see ``live_analysis``)."""
    analysis = live_analysis(ctx)
    return None if analysis is None else analysis.decision


def live_execution(ctx: AppContext) -> ExecutionAssessment | None:
    """The M1 execution assessment that goes with ``live_decision`` (same one-second cache)."""
    analysis = live_analysis(ctx)
    return None if analysis is None else analysis.execution


def m1_view(e: ExecutionAssessment | None) -> M1Execution:
    if e is None:
        return M1Execution(applicable=False, reason="chưa có đánh giá M1")
    return M1Execution(
        applicable=e.applicable,
        reason=e.reason,
        direction=None if e.direction == 0 else ("BUY" if e.direction > 0 else "SELL"),
        state=e.state,
        quality=e.quality,
        reasons=e.reasons,
        features=dict(e.features),
        planned_entry=e.planned_entry,
        planned_stop=e.planned_stop,
        planned_target=e.planned_target,
        net_rr_now=e.net_rr_now,
        price_now=e.price_now,
    )


def system_view(
    d: Decision, e: ExecutionAssessment | None, held: dict[str, object] | None
) -> SystemAdvice:
    """The SYSTEM layer: the advisory recommendation, with the strategy's own word kept apart."""
    advice = advise(d, e, held_side=None if held is None else str(held["side"]))
    return SystemAdvice(
        recommendation=advice.recommendation,
        reasons=advice.reasons,
        primary_blocker=advice.primary_blocker,
        blocker_text=None
        if advice.primary_blocker is None
        else blocker_text(advice.primary_blocker),
        secondary=advice.secondary,
        secondary_text=tuple(blocker_text(c) for c in advice.secondary),
        bias="BUY" if advice.bias == "BUY" else "SELL" if advice.bias == "SELL" else "NEUTRAL",
        setup_state=advice.setup_state,
        trigger_state=advice.trigger_state,
        strategy_action=advice.strategy_action,
        strategy_version=d.strategy_version,
        m1=m1_view(e),
    )


def human_view(row: dict[str, object]) -> HumanRecord:
    return HumanRecord(**{k: v for k, v in row.items() if k != "seq"})


def _hold(
    row: dict[str, object], d: Decision | None, now: datetime, version: str, ctx: AppContext
) -> StateSnapshot:
    """The state while a PAPER position is open: HOLD, with the position as the plan."""
    quote = ctx.live.quote(ctx.calendar, now)
    view = ctx.desk.view(row, quote.bid, quote.ask)
    floating = view.floating_pnl_usd or 0.0
    return StateSnapshot(
        generated_at=now,
        action=ActionCode.HOLD,
        readiness=Readiness.READY,
        readiness_level=6,
        bias=view.side,
        headline=f"GIỮ LỆNH PAPER {view.side} {view.lots:g} lot · PnL nổi ${floating:+.2f}",
        reason_codes=("POSITION_OPEN",),
        blocker=None,
        next_condition="Chờ chạm SL hoặc TP (PAPER, quản lý bằng nến M1 đã đóng)",
        evidence=EvidenceLabel.UNVALIDATED,
        model=ModelInfo(status=ModelStatus.NOT_DEPLOYED, note="chưa triển khai (G6)"),
        plan=TradePlan(
            side=view.side,
            entry=view.entry,
            stop_loss=view.stop_loss,
            take_profit_1=view.take_profit,
            take_profit_2=view.take_profit_2,
            net_rr=view.net_rr,
        ),
        risk=RiskInfo(
            risk_pct=view.risk_pct,
            lots=view.lots,
            risk_amount=view.risk_amount,
            cost_usd=None,
            cost_status="UNKNOWN",
            swap_note="swap GIẢ ĐỊNH theo số đọc 2026-10-08, tính khi đóng lệnh",
        ),
        data=DataInfo(
            data_version=version,
            data_timestamp=None,
            stale=bool(d and d.state and d.state.data_quality in ("STALE", "UNKNOWN")),
        ),
        decision_id=view.decision_id,
        strategy_version=d.strategy_version if d else None,
        chain=d.reasons if d else (),
        warnings=d.warnings if d else (),
        mtf=_mtf(d) if d else (),
    )


def _build_state(ctx: AppContext, now: datetime | None = None) -> StateSnapshot:
    moment = now or datetime.now(UTC)
    version = ctx.data_version(ctx.store.coverage(ORDER[0]))
    if not ctx.store.reachable():
        why = "Kho dữ liệu không truy cập được"
        return unavailable_state(moment, version, "STORE_UNAVAILABLE", why)
    if now is None:
        decision, execution = live_decision(ctx), live_execution(ctx)
    else:
        analysis = compute_analysis(ctx, moment)
        decision, execution = (
            (None, None) if analysis is None else (analysis.decision, analysis.execution)
        )
    held = ctx.desk.open_row()
    if held is not None:
        snapshot = _hold(held, decision, moment, version, ctx)
        if decision is not None:
            snapshot = snapshot.model_copy(
                update={"system": system_view(decision, execution, held)}
            )
        return snapshot
    if decision is None:
        return unavailable_state(moment, version, "NO_BARS", "Kho dữ liệu chưa có nến nào")
    snapshot = to_snapshot(decision, moment, version)
    latest = ctx.desk.store.latest_human(decision.setup_id) if decision.setup_id else None
    return snapshot.model_copy(
        update={
            "setup_id": decision.setup_id or None,
            "system": system_view(decision, execution, None),
            "human": None if latest is None else human_view(latest),
        }
    )


def build_state(ctx: AppContext, now: datetime | None = None) -> StateSnapshot:
    """The decision surface, carrying the real model status (no forecast, no authority)."""
    return _build_state(ctx, now).model_copy(update={"model": model_info(ctx)})


__all__ = [
    "Frame",
    "build_state",
    "compute_decision",
    "live_analysis",
    "live_decision",
    "live_execution",
    "to_snapshot",
    "unavailable_state",
]
