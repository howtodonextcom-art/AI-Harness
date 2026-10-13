"""The HUMAN decision layer (G9): the person is the final authority, and the system only advises.

What this module does, and does not do:

* it records what the human chose (ACCEPT / WAIT / REJECT) together with the system state that
  choice answered, in an APPEND-ONLY table (never edited, never deleted);
* it NEVER changes the system's signal, the strategy's decision or the model output (those are
  computed elsewhere and are not inputs it can write to);
* it NEVER opens a PAPER position and never touches a broker: ACCEPT means "the human accepts this
  candidate and will act manually"; nothing is sent anywhere. (The AUTO PAPER engine is a separate,
  research-only mechanism; this layer and that one share nothing but the read-only market state.)
* the page sends only {choice, setup_id, reason}: every number in the record (entry, stop, target,
  R:R, risk, M1 state) is taken from the server's own current analysis at the moment of the click.
  If the candidate changed since the person looked at it (another ``setup_id``), the request is
  refused (STALE_CANDIDATE) so the human never answers a plan they did not see.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from xau_edge_v2.api.context import AppContext
from xau_edge_v2.api.paper import same_origin
from xau_edge_v2.api.state import human_view, live_decision, live_execution
from xau_edge_v2.core.advice import advise
from xau_edge_v2.domain.contract import (
    ErrorBody,
    EvidenceLabel,
    HumanActionResult,
    HumanDecisionsResponse,
    HumanRequest,
)

router = APIRouter(prefix="/api/v2/human", tags=["human"])
ERRORS: dict[int | str, dict[str, Any]] = {
    403: {"model": ErrorBody},
    409: {"model": ErrorBody},
}
CONTROL = re.compile(r"[\x00-\x1f\x7f]+")
MESSAGES = {
    "ACCEPT": "Đã ghi nhận: bạn CHẤP NHẬN ứng viên này. Không có lệnh nào được gửi đi; bạn tự thực hiện thủ công.",
    "WAIT": "Đã ghi nhận: bạn chọn CHỜ.",
    "REJECT": "Đã ghi nhận: bạn BỎ QUA ứng viên này.",
}


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        ErrorBody(error_code=code, message=message).model_dump(), status_code=status
    )


def clean_reason(text: str) -> str:
    """One line of plain text: control characters become spaces, ends trimmed."""
    return CONTROL.sub(" ", text).strip()


@router.post(
    "/decision",
    response_model=HumanActionResult,
    responses=ERRORS,
    dependencies=[Depends(same_origin)],
)
def decide_candidate(request: Request, body: HumanRequest) -> HumanActionResult | JSONResponse:
    """Record the human's choice on the CURRENT candidate (and only on it)."""
    ctx: AppContext = request.app.state.ctx
    now = datetime.now(UTC)
    decision, execution = live_decision(ctx), live_execution(ctx)
    held = ctx.desk.open_row()
    if decision is None:
        return _error(409, "NO_DATA", "chưa có dữ liệu để đưa ra ứng viên")
    advice = advise(decision, execution, held_side=None if held is None else str(held["side"]))
    if advice.recommendation not in ("BUY_CANDIDATE", "SELL_CANDIDATE"):
        return _error(
            409,
            "NO_CANDIDATE",
            f"hiện không có ứng viên để quyết định (hệ thống khuyến nghị {advice.recommendation})",
        )
    if body.setup_id != decision.setup_id:
        return _error(
            409, "STALE_CANDIDATE", "ứng viên đã thay đổi từ lúc bạn xem: hãy xem lại kế hoạch mới"
        )
    if decision.expiry is not None and decision.expiry <= now:
        return _error(409, "EXPIRED", "ứng viên đã hết hạn")
    row: dict[str, Any] = {
        "id": uuid.uuid4().hex[:16],
        "timestamp": now.isoformat(),
        "decision_id": decision.decision_id,
        "setup_id": decision.setup_id,
        "system_action": decision.action,
        "system_recommendation": advice.recommendation,
        "system_bias": advice.bias,
        "setup_state": advice.setup_state,
        "trigger_state": advice.trigger_state,
        "m1_execution_state": None if execution is None else execution.state,
        "m1_quality": None if execution is None else execution.quality,
        "entry": decision.entry_price,
        "sl": decision.stop_loss,
        "tp": decision.take_profit,
        "rr": decision.net_rr,
        "risk_pct": decision.risk_pct,
        "risk_amount": decision.risk_amount,
        "price": None if decision.state is None else decision.state.price,
        "expiry": None if decision.expiry is None else decision.expiry.isoformat(),
        "human_choice": body.choice.value,
        "human_reason": clean_reason(body.reason),
        "paper_mode": "PAPER",
        "strategy_version": decision.strategy_version,
        "evidence_label": EvidenceLabel.UNVALIDATED.value,
    }
    ctx.desk.store.append_human(row)
    return HumanActionResult(ok=True, message=MESSAGES[body.choice.value], record=human_view(row))


@router.get("/decisions", response_model=HumanDecisionsResponse)
def decisions(
    request: Request, limit: Annotated[int, Query(ge=1, le=1000)] = 200
) -> HumanDecisionsResponse:
    ctx: AppContext = request.app.state.ctx
    return HumanDecisionsResponse(
        decisions=tuple(human_view(r) for r in ctx.desk.store.human_decisions(limit))
    )
