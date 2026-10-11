"""Entry authorization: a research DESIGN, not a trading component. WAIT is the default answer.

Nothing imports this module and it cannot place or recommend an order: its strongest output is
``BUY_CANDIDATE`` / ``SELL_CANDIDATE``, meaning "every gate of a future, separately validated
programme would be satisfied", and it can only reach that with a probability object that came from a
calibrated out-of-sample study (see ``probability.py``). Today none exists, so every call
ends in WAIT.

Gates, in order (the first failure of a side is its reason; both sides are always reported):

1. data trustworthy, no blocker;
2. pattern CONFIRMED or ACTIONABLE (a developing pattern is never enough);
3. levels coherent;
4. net R:R after costs at least ``min_net_rr`` (1.5 by default);
5. credible room to the target (opposing structure leaves the reward distance free);
6. thresholds preregistered;
7. a publishable probability (sample, interval, calibration, horizon);
8. probability above break-even plus the preregistered margins;
9. expected value in R above the preregistered threshold.

If both sides pass, the answer is WAIT (conflict), never a vote.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from xau_edge.decision_research.probability import DecisionProbability, publication_problems
from xau_edge.decision_research.rr import (
    CostModel,
    expected_value_r,
    net_payoff,
    required_probability,
    round_levels_to_tick,
)


class PatternStage(StrEnum):
    NO_PATTERN = "NO_PATTERN"
    POSSIBLE = "POSSIBLE"
    DEVELOPING = "DEVELOPING"
    NEAR_CONFIRMATION = "NEAR_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    ACTIONABLE = "ACTIONABLE"
    INVALIDATED = "INVALIDATED"


class _Resolved(NamedTuple):
    min_sample: int
    max_ci_width: float
    calibration_margin: float
    uncertainty_margin: float
    min_ev_r: float


class Thresholds(BaseModel):
    """Everything numeric a future programme must fix BEFORE it reads an outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    min_net_rr: float = Field(default=1.5, ge=1.5, allow_inf_nan=False)
    min_sample: int | None = None
    max_ci_width: float | None = None
    calibration_margin: float | None = None
    uncertainty_margin: float | None = None
    min_ev_r: float | None = None
    preregistration_ref: str | None = None  # the committed record that fixed the numbers above

    def resolved(self) -> _Resolved | None:
        """The preregistered numbers, or ``None`` until all are fixed and referenced."""
        if self.preregistration_ref is None:
            return None
        if (
            self.min_sample is None
            or self.max_ci_width is None
            or self.calibration_margin is None
            or self.uncertainty_margin is None
            or self.min_ev_r is None
        ):
            return None
        return _Resolved(
            self.min_sample, self.max_ci_width, self.calibration_margin,
            self.uncertainty_margin, self.min_ev_r,
        )  # fmt: skip

    def complete(self) -> bool:
        return self.preregistration_ref is not None and None not in (
            self.min_sample, self.max_ci_width, self.calibration_margin,
            self.uncertainty_margin, self.min_ev_r,
        )  # fmt: skip


class Proposal(BaseModel):
    """One side of a possible trade, as a future detector plus exit rule would state it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    side: Literal["BUY", "SELL"]
    stage: PatternStage
    entry: float = Field(allow_inf_nan=False)
    stop: float = Field(allow_inf_nan=False)
    target: float = Field(allow_inf_nan=False)
    tick_size: float = Field(gt=0.0, allow_inf_nan=False)
    entry_causal: bool = False
    stop_structurally_valid: bool = False
    target_structurally_valid: bool = False
    risk_ok: bool = False
    room_to_target: float | None = Field(default=None, ge=0.0, allow_inf_nan=False)
    # Free distance to the nearest opposing structure.
    data_ok: bool = True
    blockers: tuple[str, ...] = ()


class Reason(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    side: Literal["BUY", "SELL", "BOTH"]
    code: str
    message: str  # Vietnamese, for a human reading /trade


class Authorization(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    action: Literal["WAIT", "BUY_CANDIDATE", "SELL_CANDIDATE"]
    reasons: tuple[Reason, ...]
    net_rr: dict[str, float] = Field(default_factory=dict)
    break_even: dict[str, float] = Field(default_factory=dict)


_SIDES = ("BUY", "SELL")
_NOT_READY = {
    PatternStage.NO_PATTERN: ("NO_PATTERN", "chưa có mẫu hình"),
    PatternStage.POSSIBLE: ("PATTERN_POSSIBLE", "mẫu hình mới chỉ có thể xảy ra"),
    PatternStage.DEVELOPING: ("PATTERN_DEVELOPING", "mẫu hình đang hình thành"),
    PatternStage.NEAR_CONFIRMATION: (
        "PATTERN_NOT_CONFIRMED",
        "mẫu hình sắp xác nhận nhưng chưa xác nhận",
    ),
    PatternStage.INVALIDATED: ("PATTERN_INVALIDATED", "mẫu hình đã bị vô hiệu"),
}


@dataclass
class _Context:
    costs: CostModel
    probabilities: DecisionProbability
    thresholds: Thresholds
    net_rr: dict[str, float]
    break_even: dict[str, float]


def _reason(side: Literal["BUY", "SELL"], code: str, message: str) -> Reason:
    return Reason(side=side, code=code, message=message)


def _side_verdict(p: Proposal, ctx: _Context) -> Reason | None:  # noqa: PLR0911, PLR0912
    side = p.side
    th = ctx.thresholds
    if not p.data_ok:
        return _reason(side, "DATA_NOT_TRUSTED", "CHỜ: dữ liệu chưa đáng tin.")
    if p.blockers:
        return _reason(side, "BLOCKED", f"CHỜ: có chặn ({', '.join(p.blockers)}).")
    if p.stage in _NOT_READY:
        code, text = _NOT_READY[p.stage]
        return _reason(side, code, f"CHỜ: {text}.")
    if not p.entry_causal:
        return _reason(side, "ENTRY_NOT_CAUSAL", "CHỜ: entry chưa có quy tắc nhân quả.")
    if not p.stop_structurally_valid:
        return _reason(side, "INVALID_STOP", "CHỜ: stop chưa được xác nhận theo cấu trúc.")
    if not p.target_structurally_valid:
        return _reason(side, "INVALID_TARGET", "CHỜ: target chưa được xác nhận theo cấu trúc.")
    if not p.risk_ok:
        return _reason(side, "RISK_GUARD", "CHỜ: risk guard chưa xác nhận.")
    if not ctx.costs.verified:
        return _reason(side, "COST_MODEL_UNVERIFIED", "CHỜ: mô hình chi phí chưa được xác minh.")
    entry, stop, target = round_levels_to_tick(side, p.entry, p.stop, p.target, p.tick_size)
    payoff = net_payoff(side, entry, stop, target, ctx.costs)
    if payoff is None:
        return _reason(side, "LEVELS_INVALID", "CHỜ: mức vào, cắt lỗ, chốt lời không hợp lệ.")
    ctx.net_rr[side] = payoff.net_rr
    ctx.break_even[side] = payoff.net_break_even_probability
    if payoff.net_rr < th.min_net_rr:
        message = f"CHỜ: Net R:R hiện {payoff.net_rr:.2f}R, dưới ngưỡng {th.min_net_rr:g}R."
        return _reason(side, "NET_RR_BELOW_MIN", message)
    room = None if p.room_to_target is None else int(p.room_to_target / p.tick_size) * p.tick_size
    if room is None or room < payoff.gross_reward + p.tick_size:
        return _reason(
            side, "NO_ROOM_TO_TARGET", "CHỜ: cấu trúc đối diện không chừa đủ chỗ tới mục tiêu."
        )
    fixed = th.resolved()
    if fixed is None:
        return _reason(
            side,
            "THRESHOLDS_NOT_PREREGISTERED",
            "CHỜ: các ngưỡng xác suất và EV chưa được đăng ký trước.",
        )
    prob = ctx.probabilities.buy_success if side == "BUY" else ctx.probabilities.sell_success
    problems = publication_problems(
        prob, min_sample=fixed.min_sample, max_ci_width=fixed.max_ci_width
    )
    if prob is None or problems:
        return _reason(
            side, problems[0], "CHỜ: chưa có xác suất đủ bằng chứng (" + ", ".join(problems) + ")."
        )
    needed = required_probability(
        payoff.net_rr,
        calibration_margin=fixed.calibration_margin,
        uncertainty_margin=fixed.uncertainty_margin,
    )
    if prob.estimate < needed:
        return _reason(
            side,
            "PROBABILITY_BELOW_REQUIRED",
            f"CHỜ: xác suất {prob.estimate:.0%} dưới mức cần {needed:.0%}.",
        )
    if expected_value_r(prob.estimate, payoff.net_rr) <= fixed.min_ev_r:
        return _reason(side, "EV_NOT_POSITIVE", "CHỜ: kỳ vọng (EV) không đủ dương.")
    return None


def authorize(
    proposals: list[Proposal],
    costs: CostModel,
    probabilities: DecisionProbability,
    thresholds: Thresholds,
) -> Authorization:
    """WAIT unless exactly one side clears every gate."""
    ctx = _Context(costs, probabilities, thresholds, {}, {})
    reasons: list[Reason] = []
    passed: list[str] = []
    for p in proposals:
        verdict = _side_verdict(p, ctx)
        if verdict is None:
            passed.append(p.side)
        else:
            reasons.append(verdict)
    if len(passed) == len(_SIDES):
        reasons.append(
            Reason(
                side="BOTH",
                code="CONFLICT",
                message="CHỜ: MUA và BÁN cùng đủ điều kiện, không chọn bừa.",
            )
        )
        passed = []
    if not proposals:
        reasons.append(
            Reason(side="BOTH", code="NO_PROPOSAL", message="CHỜ: không có đề xuất nào.")
        )
    if len(passed) == 1:
        action: Literal["WAIT", "BUY_CANDIDATE", "SELL_CANDIDATE"] = (
            "BUY_CANDIDATE" if passed[0] == "BUY" else "SELL_CANDIDATE"
        )
        return Authorization(
            action=action, reasons=(), net_rr=ctx.net_rr, break_even=ctx.break_even
        )
    return Authorization(
        action="WAIT", reasons=tuple(reasons), net_rr=ctx.net_rr, break_even=ctx.break_even
    )
