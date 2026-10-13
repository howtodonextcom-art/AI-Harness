"""Why the strategy waits, split into the MARKET's reason, the safety gates and the governor.

``decide`` lets a hard gate take precedence over the chain (as V1 did), so a WAIT shown as
SPREAD_TOO_WIDE may hide that H1 has no direction at all. Here the chain is asked again with every
gate switched off for THAT QUESTION ONLY (the real decision is never touched, and the strategy
code is the very same ``decide``): its first refusal is the market's reason. The gates are then
listed from the real state, and the account governor is reported on its own line.

Nothing here can create, size or open an order.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from xau_edge_v2.core.decision import (
    Decision,
    DecisionConfig,
    DecisionContext,
    _gates,
    decide,
)
from xau_edge_v2.core.market_state import MarketState
from xau_edge_v2.domain.intelligence import (
    Authorization,
    FunnelStep,
    GateCategory,
    GateView,
    StepStatus,
)

GOVERNOR_CODES = frozenset({"COOLDOWN", "DAILY_LIMIT", "RISK_LIMIT"})
DATA_CODES = frozenset({"STALE_DATA", "UNKNOWN_STATE", "MARKET_CLOSED", "BROKER_DISCONNECTED"})
VOLATILITY_CODES = frozenset({"VOLATILITY_TOO_HIGH", "VOLATILITY_TOO_LOW"})
NEWS_CODES = frozenset({"NEWS_UNKNOWN", "NEWS_WINDOW"})

Describe = Callable[[str], tuple[str, str | None]]
"""code -> (what blocks, what has to change)."""

_CHAIN_STEPS = (
    ("H1_DIRECTION", "H1 có hướng"),
    ("HTF_CONFLICT", "H4 / M15 không ngược H1"),
    ("M15_SETUP", "M15 có nhịp hồi cùng xu hướng"),
    ("M5_TRIGGER", "M5 xác nhận cùng chiều"),
    ("M1_TIMING", "M1 cho phép thực thi"),
    ("ROOM", "Còn khoảng trống tới cản"),
    ("STOP_RR", "SL hợp lệ và R:R ròng đủ"),
)


def gate_category(code: str) -> GateCategory:
    if code in GOVERNOR_CODES:
        return "GOVERNOR"
    if code == "SPREAD_TOO_WIDE":
        return "COST"
    if code in VOLATILITY_CODES:
        return "VOLATILITY"
    if code in DATA_CODES:
        return "DATA"
    if code in NEWS_CODES:
        return "NEWS"
    return "STRATEGY"


def ungated_decision(state: MarketState, ctx: DecisionContext, cfg: DecisionConfig) -> Decision:
    """The chain's own verdict with gates and governor off (a question, never an order)."""
    open_state = replace(
        state,
        execution_quality="GOOD",
        volatility_regime="NORMAL",
        data_quality="OK",
        market_open=True,
        news_state="UNKNOWN",
    )
    open_ctx = replace(
        ctx,
        feed_connected=True,
        cooldown_active=False,
        daily_limit_hit=False,
        risk_limit_hit=False,
        market_open=True,
        market_status="OPEN",
        data_ok=True,
        spec_known=True,
    )
    open_cfg = replace(
        cfg,
        block_high_volatility=False,
        block_low_volatility=False,
        blocked_regimes=(),
        allow_unknown_news=True,
    )
    return decide(open_state, open_ctx, open_cfg)


def _step_index(code: str, extra: str) -> int:  # noqa: PLR0911 - one return per chain link
    if code == "NO_DIRECTION":
        return 0
    if code == "TIMEFRAME_CONFLICT":
        return 1
    if code == "NO_SETUP":
        return 2
    if code == "NO_TRIGGER":
        return 4 if "M1" in extra else 3
    if code in ("VOLATILITY_TOO_HIGH", "VOLUME_TOO_LOW", "STALE_DATA"):
        return 4
    if code in ("TOO_CLOSE_TO_RESISTANCE", "TOO_CLOSE_TO_SUPPORT"):
        return 5
    return 6


def _observed(key: str, s: MarketState, m1: str) -> tuple[str, str]:  # noqa: PLR0911 - one per link
    if key == "H1_DIRECTION":
        return s.h1_trend, "BULLISH hoặc BEARISH"
    if key == "HTF_CONFLICT":
        return f"H4 {s.h4_regime} · M15 {s.m15_structure}", "không ngược hướng H1"
    if key == "M15_SETUP":
        return f"{s.m15_structure} / {s.m15_pullback}", "cùng chiều H1 và đang hồi"
    if key == "M5_TRIGGER":
        return s.m5_momentum, "cùng chiều H1"
    if key == "M1_TIMING":
        return m1, "GOOD (không QUIET / NOISY / VOLATILE)"
    if key == "ROOM":
        room = s.distance_to_resistance if s.h1_trend == "BULLISH" else s.distance_to_support
        atr = s.atr_m15
        text = "n/a" if room is None or not atr else f"{room / atr:.2f} ATR"
        return text, "≥ 1,0 ATR tới cản"
    return "-", "SL ≤ 3 ATR và R:R ròng ≥ 1,5"


def _gate(code: str, describe: Describe) -> GateView:
    text, _ = describe(code)
    return GateView(code=code, text=text, category=gate_category(code))


def build_authorization(
    state: MarketState,
    decision: Decision,
    ungated: Decision,
    gate_codes: tuple[str, ...],
    describe: Describe,
) -> Authorization:
    """The strategy's authorization with every reason in its own layer."""
    gates = tuple(_gate(c, describe) for c in gate_codes if c not in GOVERNOR_CODES)
    held = tuple(_gate(c, describe) for c in gate_codes if c in GOVERNOR_CODES)
    sizing_hold = (
        ungated.action == "WAIT" and bool(ungated.refusals) and ungated.refusals[0] == "RISK_LIMIT"
    )
    if sizing_hold:
        held = (*held, _gate("RISK_LIMIT", describe))
    chain_ok = ungated.action in ("BUY", "SELL") or sizing_hold
    m1 = ungated.m1_execution_state
    failing = -1
    chain_blocker: GateView | None = None
    next_condition: str | None = None
    if not chain_ok:
        code = ungated.refusals[0] if ungated.refusals else "NO_SETUP"
        extra = ungated.reasons[len(ungated.reasons) - 1] if len(ungated.reasons) > 8 else ""
        failing = _step_index(code, extra)
        chain_blocker = _gate(code, describe)
        next_condition = describe(code)[1]
    steps: list[FunnelStep] = []
    for i, (key, label) in enumerate(_CHAIN_STEPS):
        observed, required = _observed(key, state, m1)
        status: StepStatus = (
            "PASS" if chain_ok or i < failing else "FAIL" if i == failing else "NOT_REACHED"
        )
        steps.append(
            FunnelStep(key=key, label=label, status=status, observed=observed, required=required)
        )
    by_cat: dict[str, list[str]] = {}
    for g in (*gates, *held):
        by_cat.setdefault(g.category, []).append(g.code)
    for key, label, cat, obs in (
        ("GATE_COST", "Chi phí (spread)", "COST", f"spread {state.spread_state}"),
        (
            "GATE_VOLATILITY",
            "Biến động trong dải",
            "VOLATILITY",
            f"{state.volatility_regime} · H4 {state.h4_regime}",
        ),
        ("GATE_DATA", "Dữ liệu và thị trường mở", "DATA", f"dữ liệu {state.data_quality}"),
        ("GATE_GOVERNOR", "Bộ giới hạn tài khoản (không phải thị trường)", "GOVERNOR", "ổn"),
    ):
        hit = by_cat.get(cat, [])
        steps.append(
            FunnelStep(
                key=key,
                label=label,
                status="FAIL" if hit else "PASS",
                observed=", ".join(hit) if hit else obs,
                required="không chặn",
            )
        )
    return Authorization(
        strategy_id=decision.strategy_id,
        strategy_version=decision.strategy_version,
        action=decision.action,
        chain_verdict="CHAIN_OK"
        if chain_ok
        else (chain_blocker.code if chain_blocker else "CHAIN_OK"),
        chain_blocker=chain_blocker,
        next_condition=next_condition,
        gates=gates,
        system_hold=held,
        funnel=tuple(steps),
        explanation=_explain(chain_blocker, next_condition, gates, held, decision.action),
    )


def _explain(
    chain: GateView | None,
    nxt: str | None,
    gates: tuple[GateView, ...],
    held: tuple[GateView, ...],
    action: str,
) -> str:
    parts: list[str] = []
    if chain is not None:
        parts.append(f"Chiến lược chưa có kế hoạch vì thị trường: {chain.text}.")
        if nxt:
            parts.append(f"Cần: {nxt}.")
    elif action in ("BUY", "SELL"):
        parts.append("Chuỗi chiến lược đủ điều kiện và không bị cổng nào chặn.")
    else:
        parts.append("Chuỗi chiến lược đã đủ điều kiện, nhưng việc vào lệnh đang bị chặn.")
    if gates:
        parts.append("Cổng an toàn đang chặn: " + "; ".join(g.text for g in gates) + ".")
    if held:
        parts.append("Bộ giới hạn tài khoản giữ lại: " + "; ".join(g.text for g in held) + ".")
    return " ".join(parts)


def real_gates(state: MarketState, ctx: DecisionContext, cfg: DecisionConfig) -> tuple[str, ...]:
    """The gate codes that hold the real decision (same list ``decide`` uses)."""
    codes, _ = _gates(state, ctx, cfg)
    return tuple(dict.fromkeys(c.value for c in codes))
