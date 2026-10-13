"""``GET /api/v2/intelligence``: the market described, the scenarios to watch, and why the strategy
waits, with the market's reason, the safety gates and the account governor each on their own line.

Read-only. The same one-second analysis the decision surface uses is reused (no second read of the
bars); every change of regime / scenario / authorization is also appended to ``decision_events``
by the engine, so the history exists even when nobody is looking at the page.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import UTC

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from xau_edge_v2.api.context import AppContext
from xau_edge_v2.api.state import BLOCKERS, Analysis, blocker_text, live_analysis
from xau_edge_v2.core.intelligence.funnel import build_authorization, real_gates, ungated_decision
from xau_edge_v2.core.intelligence.observe import IntelMemo, observe
from xau_edge_v2.domain.contract import ErrorBody
from xau_edge_v2.domain.intelligence import ChangeView, MarketIntelligence

router = APIRouter(prefix="/api/v2", tags=["intelligence"])

CACHE_SECONDS = 1.0
CHANGE_HISTORY = 100
SHOWN_CHANGES = 20
_LOCK = threading.Lock()


def describe(code: str) -> tuple[str, str | None]:
    text, nxt = BLOCKERS.get(code, (blocker_text(code), None))
    return text, nxt or None


def intelligence_for(
    ctx: AppContext, analysis: Analysis, previous: MarketIntelligence | None = None
) -> MarketIntelligence | None:
    """The intelligence document for one analysis (None when it carries no bars)."""
    if analysis.frames is None or analysis.state is None or analysis.context is None:
        return None
    assert analysis.config is not None
    assert analysis.at is not None
    memo = ctx.cache.get("intel_memo")
    if not isinstance(memo, IntelMemo):
        memo = IntelMemo()
        ctx.cache["intel_memo"] = memo
    ungated = ungated_decision(analysis.state, analysis.context, analysis.config)
    gate_codes = real_gates(analysis.state, analysis.context, analysis.config)
    auth = build_authorization(analysis.state, analysis.decision, ungated, gate_codes, describe)
    return observe(
        analysis.frames,
        analysis.at,
        analysis.state,
        analysis.decision,
        auth,
        memo,
        quote_age_s=analysis.quote_age_s,
        previous=previous,
    )


def _persist(ctx: AppContext, intel: MarketIntelligence, changes: tuple[ChangeView, ...]) -> None:
    auth = intel.authorization
    for c in changes:
        ctx.desk.store.log_event(
            {
                "at": c.at.astimezone(UTC).isoformat(),
                "kind": c.kind,
                "text": c.text,
                "action": auth.action,
                "chain_verdict": auth.chain_verdict,
                "strategy_version": auth.strategy_version,
            }
        )


def live_intelligence(ctx: AppContext) -> MarketIntelligence | None:
    """The intelligence for the present moment, shared for about a second (page, socket, engine)."""
    with _LOCK:
        cached = ctx.cache.get("intelligence")
        if isinstance(cached, tuple) and time.monotonic() - cached[0] < CACHE_SECONDS:
            result: MarketIntelligence | None = cached[1]
            return result
        analysis = live_analysis(ctx)
        if analysis is None:
            return None
        previous = ctx.cache.get("intel_prev")
        prev = previous if isinstance(previous, MarketIntelligence) else None
        intel = intelligence_for(ctx, analysis, prev)
        if intel is None:
            return None
        history = ctx.cache.setdefault("intel_changes", deque(maxlen=CHANGE_HISTORY))
        assert isinstance(history, deque)
        if prev is None:
            init = ChangeView(
                at=intel.generated_at,
                kind="INIT",
                text=f"quan sát bắt đầu: {intel.authorization.action} / {intel.authorization.chain_verdict}",
            )
            history.append(init)
            _persist(ctx, intel, (init,))
        for c in intel.changes:
            history.append(c)
        if intel.changes:
            _persist(ctx, intel, intel.changes)
        shown = tuple(reversed(list(history)[-SHOWN_CHANGES:]))
        intel = intel.model_copy(update={"changes": shown})
        ctx.cache["intel_prev"] = intel.model_copy(update={"changes": ()})
        ctx.cache["intelligence"] = (time.monotonic(), intel)
        return intel


def _ctx(request: Request) -> AppContext:
    ctx: AppContext = request.app.state.ctx
    return ctx


@router.get(
    "/intelligence",
    response_model=MarketIntelligence,
    responses={503: {"model": ErrorBody}},
)
def intelligence(request: Request) -> MarketIntelligence | JSONResponse:
    ctx = _ctx(request)
    if not ctx.store.reachable():
        return JSONResponse(
            status_code=503,
            content={
                "error_code": "STORE_UNAVAILABLE",
                "message": "Kho dữ liệu không truy cập được",
            },
        )
    result = live_intelligence(ctx)
    if result is None:
        return JSONResponse(
            status_code=503,
            content={"error_code": "NO_BARS", "message": "Kho dữ liệu chưa có nến nào"},
        )
    return result
