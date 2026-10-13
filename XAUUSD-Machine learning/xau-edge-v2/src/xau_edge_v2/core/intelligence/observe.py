"""The market-intelligence engine: closed bars -> description, scenarios and what changed.

Everything is computed from bars that had CLOSED at ``at`` (``MultiFrames.as_of``), so a result is
a pure function of (bars, quote age, decision) and replays identically. Scenarios are conditional
descriptions with explicit confirm / invalidate levels, NOT probabilities and NOT permissions: the
strategy's authorization is carried separately (``funnel``) and this module never opens anything.
"""

from __future__ import annotations

from datetime import datetime

from xau_edge_v2.core.decision import Decision
from xau_edge_v2.core.frames import Frame, MultiFrames, from_micros
from xau_edge_v2.core.intelligence import price_action as pa
from xau_edge_v2.core.intelligence import structure_events as se
from xau_edge_v2.core.intelligence import volatility as vol
from xau_edge_v2.core.market_state import MarketState
from xau_edge_v2.domain.contract import Timeframe
from xau_edge_v2.domain.intelligence import (
    Authorization,
    ChangeView,
    Direction,
    EventView,
    LevelView,
    MarketIntelligence,
    ScenarioView,
    TimeframeView,
)

ROLES: dict[Timeframe, str] = {
    Timeframe.H4: "Chế độ thị trường",
    Timeframe.H1: "Hướng chính",
    Timeframe.M15: "Cấu trúc và nhịp hồi",
    Timeframe.M5: "Xác nhận",
    Timeframe.M1: "Thời điểm",
}
ANALYSED = tuple(ROLES)
STRUCTURE_BARS = 300
EVENT_RECENT_BARS = 3
STRUCTURE_RECENT_BARS = 12
SWEEP_RECENT_BARS = 6
MAX_EVENTS = 24
PER_TF_EVENTS: dict[Timeframe, int] = {
    Timeframe.H4: 5,
    Timeframe.H1: 5,
    Timeframe.M15: 6,
    Timeframe.M5: 5,
    Timeframe.M1: 3,
}
MAX_LEVELS = 10
FRESH_QUOTE_S = 5.0

_DIR: dict[int, Direction] = {1: "UP", -1: "DOWN", 0: "NONE"}


def _dt(us: int) -> datetime:
    return from_micros(us)


def _level(
    role: str,
    label: str,
    price: float,
    tf: Timeframe | None,
    *,
    confirmed: bool = True,
    known_at: int | None = None,
    ref: float | None = None,
    atr: float | None = None,
) -> LevelView:
    dist = None if ref is None or not atr else (price - ref) / atr
    return LevelView(
        role=role,
        label=label,
        price=price,
        timeframe=tf,
        confirmed=confirmed,
        known_at=None if known_at is None else _dt(known_at),
        distance_atr=dist,
    )


class TfIntel:
    """One timeframe's descriptive result, cached per closed bar (it cannot change afterwards)."""

    __slots__ = ("events", "frame_n", "swings", "view", "vol")

    def __init__(self, frame: Frame, state: MarketState) -> None:
        tf = frame.timeframe
        self.frame_n = frame.height
        window = frame.tail(STRUCTURE_BARS)
        self.swings = se.swings(window)
        self.vol = vol.analyse(window)
        snap = state.snapshots.get(tf.value)
        atr = self.vol.atr
        confirmed_hi = se.last_swing(self.swings, "HIGH")
        confirmed_lo = se.last_swing(self.swings, "LOW")
        prov_hi = se.last_swing(self.swings, "HIGH", confirmed_only=False)
        prov_lo = se.last_swing(self.swings, "LOW", confirmed_only=False)

        def lv(role: str, s: se.Swing | None) -> LevelView | None:
            if s is None:
                return None
            return _level(
                role,
                f"{tf.value} {role.replace('_', ' ').lower()}",
                s.price,
                tf,
                confirmed=s.confirmed,
                known_at=s.known_at_us,
            )

        self.view = TimeframeView(
            timeframe=tf,
            role=ROLES.get(tf, ""),
            available=True,
            last_closed=_dt(int(window.available_us[-1])),
            regime=None if snap is None else snap.regime,
            trend=_DIR[
                0
                if snap is None
                else (1 if snap.structure_trend > 0 else -1 if snap.structure_trend < 0 else 0)
            ],
            volatility_phase=self.vol.phase,
            atr=atr,
            atr_ratio=self.vol.atr_ratio,
            last_swing_high=lv("SWING_HIGH", confirmed_hi),
            last_swing_low=lv("SWING_LOW", confirmed_lo),
            provisional_high=lv(
                "PROVISIONAL_HIGH", prov_hi if prov_hi and not prov_hi.confirmed else None
            ),
            provisional_low=lv(
                "PROVISIONAL_LOW", prov_lo if prov_lo and not prov_lo.confirmed else None
            ),
        )
        self.events = self._events(window, tf)

    def _events(self, window: Frame, tf: Timeframe) -> list[EventView]:
        n = window.height
        out: list[EventView] = []
        for e in pa.detect(window, last=EVENT_RECENT_BARS):
            out.append(
                EventView(
                    scope="PRICE_ACTION",
                    timeframe=tf,
                    kind=e.kind,
                    text=pa.DESCRIPTION[e.kind],
                    bar_open=_dt(e.bar_open_us),
                    known_at=_dt(e.known_at_us),
                    level=e.level,
                    invalidation=e.invalidation,
                    strength=round(e.strength, 2),
                    age_bars=n - 1 - e.index,
                )
            )
        for s in se.structure_events(window):
            if n - 1 - s.index <= STRUCTURE_RECENT_BARS:
                out.append(
                    EventView(
                        scope="STRUCTURE",
                        timeframe=tf,
                        kind=s.kind,
                        text=_STRUCTURE_TEXT[s.kind],
                        bar_open=_dt(s.bar_open_us),
                        known_at=_dt(s.known_at_us),
                        level=s.level,
                        age_bars=n - 1 - s.index,
                    )
                )
        if self.vol.box_breakout != 0 and self.vol.box_known_at_us is not None:
            up = self.vol.box_breakout > 0
            out.append(
                EventView(
                    scope="VOLATILITY",
                    timeframe=tf,
                    kind="BOX_BREAKOUT_UP" if up else "BOX_BREAKOUT_DOWN",
                    text="đóng cửa vượt hộp nén " + ("lên trên" if up else "xuống dưới"),
                    bar_open=_dt(int(window.open_us[-1])),
                    known_at=_dt(self.vol.box_known_at_us),
                    level=self.vol.box_high if up else self.vol.box_low,
                    invalidation=self.vol.box_low if up else self.vol.box_high,
                    age_bars=0,
                )
            )
        return out


IMPLIED: dict[str, int] = {
    "CHOCH_UP": 1,
    "CHOCH_DOWN": -1,
    "FAILED_BREAKOUT_UP": -1,
    "FAILED_BREAKOUT_DOWN": 1,
    "FAILED_BREAK_UP": -1,
    "FAILED_BREAK_DOWN": 1,
}
"""Direction a reversal-type event points to (a description of the bar, not a forecast)."""

_STRUCTURE_TEXT = {
    "BOS_UP": "phá cấu trúc lên theo xu hướng (BOS)",
    "BOS_DOWN": "phá cấu trúc xuống theo xu hướng (BOS)",
    "CHOCH_UP": "đổi tính chất cấu trúc lên (CHoCH)",
    "CHOCH_DOWN": "đổi tính chất cấu trúc xuống (CHoCH)",
    "FAILED_BREAK_UP": "phá lên rồi mất lại mức đã phá",
    "FAILED_BREAK_DOWN": "phá xuống rồi mất lại mức đã phá",
}


class IntelMemo:
    """(timeframe, bars, last bar) -> TfIntel; a closed bar's description never changes."""

    def __init__(self, limit: int = 64) -> None:
        self._data: dict[tuple[str, int, int], TfIntel] = {}
        self._limit = limit

    def get(self, frame: Frame, state: MarketState) -> TfIntel:
        key = (frame.timeframe.value, frame.height, int(frame.open_us[-1]))
        hit = self._data.get(key)
        if hit is None:
            if len(self._data) >= self._limit:
                self._data.clear()
            hit = TfIntel(frame, state)
            self._data[key] = hit
        return hit


def _summary(state: MarketState, tfs: dict[str, TfIntel]) -> str:
    h4 = {
        "TREND_UP": "xu hướng tăng",
        "TREND_DOWN": "xu hướng giảm",
        "RANGE": "đi ngang",
        "LOW_VOLATILITY": "biến động thấp",
        "HIGH_VOLATILITY": "biến động cao",
        "SHOCK": "sốc",
    }.get(state.h4_regime, "chưa rõ")
    h1 = {"BULLISH": "nghiêng tăng", "BEARISH": "nghiêng giảm", "NEUTRAL": "trung lập"}.get(
        state.h1_trend, "chưa rõ"
    )
    m15 = {
        "UP": "cấu trúc tăng",
        "DOWN": "cấu trúc giảm",
        "RANGE": "đi ngang",
        "REVERSAL_UP": "đảo chiều lên (CHoCH)",
        "REVERSAL_DOWN": "đảo chiều xuống (CHoCH)",
    }.get(state.m15_structure, "chưa rõ")
    phase = tfs["M15"].vol.phase if "M15" in tfs else "UNKNOWN"
    phase_t = {"COMPRESSION": "đang nén", "EXPANSION": "đang mở rộng", "NORMAL": "bình thường"}.get(
        phase, "chưa rõ"
    )
    return f"H4 {h4}; H1 {h1}; M15 {m15}; biến động M15 {phase_t}."


def _scenarios(  # noqa: PLR0912, PLR0915 - one block per scenario
    state: MarketState, tfs: dict[str, TfIntel], price: float | None
) -> list[ScenarioView]:
    out: list[ScenarioView] = []
    m15, m5, h1 = tfs.get("M15"), tfs.get("M5"), tfs.get("H1")
    shock = [k for k, t in tfs.items() if t.view.regime == "SHOCK"]
    cautious: list[str] = []
    if shock:
        cautious.append("sốc ở " + ", ".join(shock))
    if state.data_quality in ("STALE", "UNKNOWN"):
        cautious.append("dữ liệu cũ hoặc thiếu")
    if not state.market_open:
        cautious.append("thị trường đóng cửa")
    if state.execution_quality == "POOR":
        cautious.append("chi phí thực thi xấu")
    out.append(
        ScenarioView(
            key="NO_TRADE",
            title="Thận trọng / không giao dịch",
            direction="NONE",
            status="BLOCKED" if cautious else "INACTIVE",
            why=tuple(cautious) or ("không có điều kiện bất thường",),
            confirm="Điều kiện bất thường hết hiệu lực" if cautious else "-",
            invalidate="-",
        )
    )
    # continuation: H1 owns the direction (same hierarchy as the strategy; description only)
    side = 1 if state.h1_trend == "BULLISH" else -1 if state.h1_trend == "BEARISH" else 0
    if side != 0 and m15 is not None:
        pb = state.m15_pullback in ("PULLBACK_IN_UPTREND", "PULLBACK_IN_DOWNTREND")
        with_trend = state.m15_structure == ("UP" if side > 0 else "DOWN")
        confirm_swing = (
            m5.view.last_swing_high
            if (m5 and side > 0)
            else (m5.view.last_swing_low if m5 else None)
        )
        stop_swing = m15.view.last_swing_low if side > 0 else m15.view.last_swing_high
        levels = tuple(x for x in (confirm_swing, stop_swing) if x is not None)
        name = "tăng" if side > 0 else "giảm"
        out.append(
            ScenarioView(
                key="CONTINUATION",
                title=f"Tiếp diễn xu hướng {name}",
                direction=_DIR[side],
                status="WATCH" if (pb and with_trend) else "CONTEXT" if with_trend else "INACTIVE",
                why=(
                    f"H1 {state.h1_trend}",
                    f"M15 {state.m15_structure} / {state.m15_pullback}",
                ),
                confirm=(
                    f"M5 đóng cửa {'trên' if side > 0 else 'dưới'} swing M5 gần nhất"
                    + ("" if confirm_swing is None else f" ({confirm_swing.price:.2f})")
                ),
                invalidate=(
                    f"M15 đóng cửa {'dưới' if side > 0 else 'trên'} swing M15"
                    + ("" if stop_swing is None else f" ({stop_swing.price:.2f})")
                ),
                levels=levels,
            )
        )
    else:
        out.append(
            ScenarioView(
                key="CONTINUATION",
                title="Tiếp diễn xu hướng",
                direction="NONE",
                status="INACTIVE",
                why=("H1 chưa có hướng rõ",),
                confirm="H1 chuyển tăng hoặc giảm rõ ràng",
                invalidate="-",
            )
        )
    # breakout from compression (two-sided)
    if m15 is not None:
        v = m15.vol
        comp = v.phase == "COMPRESSION" or (
            v.box_valid and v.box_breakout == 0 and v.phase != "EXPANSION"
        )
        broke = v.box_breakout != 0
        lv = []
        if v.box_high is not None and v.box_low is not None:
            lv = [
                _level(
                    "BOX_HIGH", "Đỉnh hộp nén M15", v.box_high, Timeframe.M15, ref=price, atr=v.atr
                ),
                _level(
                    "BOX_LOW", "Đáy hộp nén M15", v.box_low, Timeframe.M15, ref=price, atr=v.atr
                ),
            ]
        out.append(
            ScenarioView(
                key="BREAKOUT",
                title="Phá vỡ khỏi vùng nén",
                direction=_DIR[v.box_breakout] if broke else "NONE",
                status="WATCH" if (comp and v.box_valid) or broke else "INACTIVE",
                why=(
                    f"biến động M15 {v.phase}",
                    "đã đóng cửa vượt hộp"
                    if broke
                    else ("hộp nén hợp lệ" if v.box_valid else "chưa có hộp nén"),
                ),
                confirm="M15 đóng cửa ngoài hộp nén cùng với mở rộng biên độ",
                invalidate="giá đóng cửa quay lại trong hộp trong 3 nến",
                levels=tuple(lv),
            )
        )
    # reversal: evidence that points AGAINST the H1 side (or, with H1 neutral, M15 evidence only)
    if m15 is not None:
        against = -side if side != 0 else 0
        pool = m15.events + (m5.events if (m5 and side != 0) else [])
        hits = [
            e
            for e in pool
            if e.age_bars <= SWEEP_RECENT_BARS
            and e.kind in IMPLIED
            and (IMPLIED[e.kind] == against if against else True)
        ]
        hits.sort(key=lambda e: e.known_at, reverse=True)
        why = [f"{e.timeframe.value} {e.text}" for e in hits[:4]]
        lean = _DIR[against] if against else (_DIR[IMPLIED[hits[0].kind]] if hits else "NONE")
        lv2: list[LevelView] = []
        ext = next((e for e in hits if e.invalidation is not None), None)
        if ext is not None and ext.invalidation is not None:
            lv2.append(
                _level(
                    "SWEEP_EXTREME",
                    "Cực trị bị quét",
                    float(ext.invalidation),
                    ext.timeframe,
                    ref=price,
                    atr=m15.vol.atr,
                )
            )
        out.append(
            ScenarioView(
                key="REVERSAL",
                title="Đảo chiều (ngược H1)" if against else "Đảo chiều",
                direction=lean,
                status="WATCH" if hits else "INACTIVE",
                why=tuple(why) or ("chưa có CHoCH hay phá vỡ thất bại ngược hướng gần đây",),
                confirm="M15 phá cấu trúc (BOS) theo hướng mới",
                invalidate="giá vượt cực trị của nến quét / phá vỡ thất bại",
                levels=tuple(lv2),
            )
        )
    # range interaction
    if m15 is not None:
        rng = state.m15_structure == "RANGE" or m15.view.regime in ("RANGE", "LOW_VOLATILITY")
        lv3 = [
            x
            for x in (
                _level(
                    "RESISTANCE",
                    "Kháng cự M15",
                    state.snapshots["M15"].resistance,
                    Timeframe.M15,
                    ref=price,
                    atr=m15.vol.atr,
                )
                if "M15" in state.snapshots and state.snapshots["M15"].resistance is not None
                else None,
                _level(
                    "SUPPORT",
                    "Hỗ trợ M15",
                    state.snapshots["M15"].support,
                    Timeframe.M15,
                    ref=price,
                    atr=m15.vol.atr,
                )
                if "M15" in state.snapshots and state.snapshots["M15"].support is not None
                else None,
            )
            if x is not None
        ]
        out.append(
            ScenarioView(
                key="RANGE",
                title="Dao động trong biên",
                direction="NONE",
                status="WATCH" if rng and lv3 else "INACTIVE",
                why=(f"M15 {state.m15_structure}, chế độ {m15.view.regime or 'chưa rõ'}",),
                confirm="nến từ chối (bấc dài) tại biên rồi đóng lại trong biên",
                invalidate="M15 đóng cửa ngoài biên",
                levels=tuple(lv3),
            )
        )
    del h1
    have = {s.key for s in out}
    titles = {
        "BREAKOUT": "Phá vỡ khỏi vùng nén",
        "REVERSAL": "Đảo chiều",
        "RANGE": "Dao động trong biên",
    }
    for key, title in titles.items():  # a missing timeframe is shown as missing, never invented
        if key not in have:
            out.append(
                ScenarioView(
                    key=key,
                    title=title,
                    direction="NONE",
                    status="INACTIVE",
                    why=("thiếu dữ liệu M15",),
                    confirm="-",
                    invalidate="-",
                )
            )
    return out


def _critical_levels(
    state: MarketState, tfs: dict[str, TfIntel], price: float | None
) -> list[LevelView]:
    atr = tfs["M15"].vol.atr if "M15" in tfs else None
    items: list[LevelView] = []
    for name in ("H1", "M15", "M5"):
        t = tfs.get(name)
        if t is None:
            continue
        for lvl in (
            t.view.last_swing_high,
            t.view.last_swing_low,
            t.view.provisional_high,
            t.view.provisional_low,
        ):
            if lvl is not None:
                items.append(
                    lvl.model_copy(
                        update={
                            "distance_atr": None
                            if price is None or not atr
                            else (lvl.price - price) / atr
                        }
                    )
                )
    for role, label, p in (
        ("PDH", "Đỉnh ngày trước", state.pdh),
        ("PDL", "Đáy ngày trước", state.pdl),
    ):
        if p is not None:
            items.append(_level(role, label, p, None, ref=price, atr=atr))
    items.sort(key=lambda x: abs(x.distance_atr) if x.distance_atr is not None else 1e9)
    return items[:MAX_LEVELS]


def observe(
    frames: MultiFrames,
    at: datetime,
    state: MarketState,
    decision: Decision,
    authorization: Authorization,
    memo: IntelMemo,
    *,
    quote_age_s: float | None,
    previous: MarketIntelligence | None = None,
) -> MarketIntelligence:
    tfs: dict[str, TfIntel] = {}
    for tf in ANALYSED:
        frame = frames.as_of(tf, at)
        if frame is not None and frame.height >= vol.MIN_BARS:
            tfs[tf.value] = memo.get(frame, state)
    views = tuple(
        tfs[tf.value].view.model_copy(update={"stale": tf.value in state.stale_timeframes})
        if tf.value in tfs
        else TimeframeView(timeframe=tf, role=ROLES[tf], available=False)
        for tf in ANALYSED
    )
    events: list[EventView] = []
    for t in tfs.values():  # a busy M1 must not push the higher timeframes out of the list
        ranked = sorted(t.events, key=lambda e: (e.known_at, e.age_bars), reverse=True)
        events += ranked[: PER_TF_EVENTS[t.view.timeframe]]
    events = sorted(events, key=lambda e: (e.known_at, e.timeframe.seconds), reverse=True)[
        :MAX_EVENTS
    ]
    m5 = state.snapshots.get("M5")
    intel = MarketIntelligence(
        generated_at=at,
        last_closed_m5=None if m5 is None else m5.bar_closed,
        quote_age_s=quote_age_s,
        data_state=state.data_quality,
        market_open=state.market_open,
        price=state.price,
        summary=_summary(state, tfs),
        timeframes=views,
        levels=tuple(_critical_levels(state, tfs, state.price)),
        events=tuple(events),
        scenarios=tuple(_scenarios(state, tfs, state.price)),
        authorization=authorization,
    )
    del decision
    if previous is not None:
        intel = intel.model_copy(update={"changes": tuple(diff(previous, intel))})
    return intel


def diff(old: MarketIntelligence, new: MarketIntelligence) -> list[ChangeView]:
    """What changed between two evaluations (regime, phase, scenario, authorization, new events)."""
    at = new.generated_at
    out: list[ChangeView] = []
    old_tf = {t.timeframe: t for t in old.timeframes}
    for t in new.timeframes:
        o = old_tf.get(t.timeframe)
        if o is None or not t.available:
            continue
        if o.regime != t.regime:
            out.append(
                ChangeView(
                    at=at,
                    kind="REGIME",
                    text=f"{t.timeframe.value}: chế độ {o.regime} → {t.regime}",
                )
            )
        if o.volatility_phase != t.volatility_phase:
            out.append(
                ChangeView(
                    at=at,
                    kind="VOLATILITY",
                    text=f"{t.timeframe.value}: biến động {o.volatility_phase} → {t.volatility_phase}",
                )
            )
    old_sc = {s.key: s for s in old.scenarios}
    for s in new.scenarios:
        o2 = old_sc.get(s.key)
        if o2 is not None and o2.status != s.status:
            out.append(
                ChangeView(at=at, kind="SCENARIO", text=f"{s.title}: {o2.status} → {s.status}")
            )
    a0, a1 = old.authorization, new.authorization
    if a0.action != a1.action:
        out.append(
            ChangeView(at=at, kind="AUTHORIZATION", text=f"chiến lược: {a0.action} → {a1.action}")
        )
    if a0.chain_verdict != a1.chain_verdict:
        out.append(
            ChangeView(
                at=at,
                kind="CHAIN",
                text=f"lý do thị trường: {a0.chain_verdict} → {a1.chain_verdict}",
            )
        )
    g0, g1 = {g.code for g in a0.gates}, {g.code for g in a1.gates}
    if g0 != g1:
        out.append(ChangeView(at=at, kind="GATES", text=f"cổng chặn: {sorted(g0)} → {sorted(g1)}"))
    h0, h1_ = {g.code for g in a0.system_hold}, {g.code for g in a1.system_hold}
    if h0 != h1_:
        out.append(
            ChangeView(
                at=at, kind="GOVERNOR", text=f"giới hạn tài khoản: {sorted(h0)} → {sorted(h1_)}"
            )
        )
    seen = {(e.timeframe, e.kind, e.known_at) for e in old.events}
    for e in new.events:
        if (e.timeframe, e.kind, e.known_at) not in seen:
            out.append(ChangeView(at=at, kind="EVENT", text=f"{e.timeframe.value}: {e.text}"))
    return out
