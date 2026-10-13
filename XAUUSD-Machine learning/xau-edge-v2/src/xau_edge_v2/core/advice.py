"""The SYSTEM's advisory recommendation (G9): what the system suggests, never what it commands.

The recommendation sits on top of two things that stay untouched:

1. the strategy's decision (``core.decision``, locked byte for byte), and
2. the M1 execution assessment (``core.execution``, timing only).

It can only be MORE cautious than the strategy, never less: a strategy WAIT stays WAIT; a strategy
BUY/SELL becomes a CANDIDATE only when M1 says the moment is right (CONFIRMED or EXECUTION_WINDOW
with acceptable quality), otherwise WAIT with the reason. M1 never creates a candidate and never
changes direction. The human is the only authority that can ACCEPT; nothing here executes anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from xau_edge_v2.core.decision import Decision
from xau_edge_v2.core.execution import ExecutionAssessment

Recommendation = Literal["BUY_CANDIDATE", "SELL_CANDIDATE", "WAIT", "HOLD", "EXIT_WATCH"]
MOMENT_OK = ("CONFIRMED", "EXECUTION_WINDOW")


@dataclass(frozen=True)
class SystemAdvice:
    recommendation: Recommendation
    reasons: tuple[str, ...]
    primary_blocker: str | None
    """A refusal code of the strategy, or ``M1_<STATE>`` when only the M1 timing holds it back."""
    secondary: tuple[str, ...]
    bias: str
    setup_state: str
    trigger_state: str
    strategy_action: str
    """What the strategy itself said (BUY/SELL/WAIT): kept visible, never overwritten."""


def setup_state(decision: Decision) -> str:
    level = decision.readiness_level
    return "ARMED" if level >= 3 else "WATCHING" if level == 2 else "NONE"


def trigger_state(decision: Decision) -> str:
    level = decision.readiness_level
    return "CONFIRMED" if level >= 4 else "WAITING" if level == 3 else "NONE"


def advise(
    decision: Decision, execution: ExecutionAssessment | None, *, held_side: str | None = None
) -> SystemAdvice:
    """The recommendation for the present moment (``held_side``: an open PAPER position, if any)."""
    common = {
        "bias": decision.bias,
        "setup_state": setup_state(decision),
        "trigger_state": trigger_state(decision),
        "strategy_action": decision.action,
    }
    if held_side is not None:
        opposite = decision.bias in ("BUY", "SELL") and decision.bias != held_side
        if opposite:
            return SystemAdvice(
                "EXIT_WATCH",
                (
                    f"H1 đã nghiêng {decision.bias}, ngược với lệnh PAPER {held_side} đang giữ: "
                    "điều kiện vô hiệu của kế hoạch (cần con người xem xét)",
                ),
                None,
                (),
                **common,
            )
        return SystemAdvice(
            "HOLD", ("đang giữ lệnh PAPER; chờ chạm SL hoặc TP",), None, (), **common
        )
    if decision.action not in ("BUY", "SELL"):
        refusals = decision.refusals
        return SystemAdvice(
            "WAIT",
            (f"chiến lược chưa có kế hoạch hợp lệ: {', '.join(refusals) or 'chưa đủ điều kiện'}",),
            refusals[0] if refusals else None,
            tuple(refusals[1:]),
            **common,
        )
    # the strategy has a valid plan: does M1 say the moment is right?
    if execution is None or not execution.applicable:
        why = "M1 chưa đánh giá được" + (f": {execution.reason}" if execution else "")
        return SystemAdvice("WAIT", (why,), "M1_UNKNOWN", tuple(decision.warnings), **common)
    assert execution.state is not None and execution.quality is not None
    if execution.state in MOMENT_OK and execution.quality != "BAD":
        side: Recommendation = "BUY_CANDIDATE" if decision.action == "BUY" else "SELL_CANDIDATE"
        return SystemAdvice(
            side,
            (
                f"khung lớn ủng hộ {decision.action}; M1 {execution.state} (chất lượng {execution.quality}): "
                "đây là ứng viên để CON NGƯỜI quyết định, không phải lệnh",
                *execution.reasons,
            ),
            None,
            tuple(decision.warnings),
            **common,
        )
    return SystemAdvice(
        "WAIT",
        (
            f"khung lớn ủng hộ {decision.action} nhưng M1 {execution.state} "
            f"(chất lượng {execution.quality}): chưa phải thời điểm thực thi",
            *execution.reasons,
        ),
        f"M1_{execution.state}",
        tuple(decision.warnings),
        **common,
    )
