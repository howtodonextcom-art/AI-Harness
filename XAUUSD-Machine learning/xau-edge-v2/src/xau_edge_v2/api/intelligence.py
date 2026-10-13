"""``GET /api/v2/intelligence`` and the engine's event recorder, kept strictly apart.

* The GET is a VIEW: it computes the description from the same one-second analysis as the decision
  surface and reads the recent changes from the database. It never writes, never advances any
  state, so opening the page (one client or fifty, or none) cannot change what is recorded.
* ``record_intelligence`` is the ONLY writer. The engine calls it once per pass; it diffs the new
  description against the engine's own previous one and appends the transitions to
  ``decision_events`` (idempotent, traceable: event id, strategy version, dataset version, decision,
  setup and the open PAPER position when there is one). It also records the start of the engine.
"""

from __future__ import annotations

import hashlib
import threading
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from xau_edge_v2.api.context import AppContext
from xau_edge_v2.api.state import BLOCKERS, Analysis, blocker_text, live_analysis
from xau_edge_v2.core.frames import ORDER
from xau_edge_v2.core.intelligence.funnel import (
    build_authorization,
    counterfactual_chain,
    real_gates,
)
from xau_edge_v2.core.intelligence.observe import IntelMemo, observe
from xau_edge_v2.domain.contract import ErrorBody
from xau_edge_v2.domain.intelligence import ChangeView, MarketIntelligence

router = APIRouter(prefix="/api/v2", tags=["intelligence"])

CACHE_SECONDS = 1.0
SHOWN_CHANGES = 20
_ENGINE_LOCK = threading.Lock()


def describe(code: str) -> tuple[str, str | None]:
    text, nxt = BLOCKERS.get(code, (blocker_text(code), None))
    return text, nxt or None


def _memo(ctx: AppContext) -> IntelMemo:
    memo = ctx.cache.get("intel_memo")
    if not isinstance(memo, IntelMemo):
        memo = ctx.cache.setdefault("intel_memo", IntelMemo())
    assert isinstance(memo, IntelMemo)
    return memo


def intelligence_for(
    ctx: AppContext, analysis: Analysis, previous: MarketIntelligence | None = None
) -> MarketIntelligence | None:
    """The description for one analysis (pure: no write, no state kept except the per-bar memo)."""
    if analysis.frames is None or analysis.state is None or analysis.context is None:
        return None
    assert analysis.config is not None
    assert analysis.at is not None
    cf = counterfactual_chain(analysis.state, analysis.context, analysis.config)
    gate_codes = real_gates(analysis.state, analysis.context, analysis.config)
    auth = build_authorization(analysis.state, analysis.decision, cf, gate_codes, describe)
    return observe(
        analysis.frames,
        analysis.at,
        analysis.state,
        analysis.decision,
        auth,
        _memo(ctx),
        quote_age_s=analysis.quote_age_s,
        previous=previous,
    )


# ---- the view (GET): read-only -----------------------------------------------------------------------
def _stored_changes(ctx: AppContext) -> tuple[ChangeView, ...]:
    out: list[ChangeView] = []
    for row in ctx.desk.store.events(SHOWN_CHANGES):
        out.append(
            ChangeView(
                event_id=row.get("event_id"),
                at=datetime.fromisoformat(str(row["at"])),
                kind=str(row["kind"]),
                text=str(row["text"]),
            )
        )
    return tuple(out)


def view_intelligence(ctx: AppContext) -> MarketIntelligence | None:
    """The document the page shows. Reads; never writes."""
    cached = ctx.cache.get("intel_view")
    if isinstance(cached, tuple) and time.monotonic() - cached[0] < CACHE_SECONDS:
        result: MarketIntelligence | None = cached[1]
        return result
    analysis = live_analysis(ctx)
    intel = None if analysis is None else intelligence_for(ctx, analysis)
    if intel is not None:
        intel = intel.model_copy(update={"changes": _stored_changes(ctx)})
    ctx.cache["intel_view"] = (time.monotonic(), intel)
    return intel


# ---- the recorder (engine only) ----------------------------------------------------------------------
def _key(kind: str, text: str, moment: datetime, version: str) -> str:
    raw = f"{kind}|{text}|{moment.astimezone(UTC).isoformat()}|{version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def record_event(  # noqa: PLR0913 - one row of the audit trail
    ctx: AppContext,
    *,
    kind: str,
    text: str,
    moment: datetime,
    action: str,
    chain_verdict: str,
    strategy_version: str,
    decision_id: str | None,
    setup_id: str | None,
    position_id: str | None,
) -> bool:
    version = ctx.data_version(ctx.store.coverage(ORDER[0]))
    return ctx.desk.store.log_event(
        {
            "at": moment.astimezone(UTC).isoformat(),
            "kind": kind,
            "text": text,
            "action": action,
            "chain_verdict": chain_verdict,
            "strategy_version": strategy_version,
            "dataset_version": version,
            "decision_id": decision_id,
            "setup_id": setup_id or None,
            "paper_position_id": position_id,
            "event_key": _key(kind, text, moment, strategy_version),
        }
    )


def record_intelligence(ctx: AppContext) -> int:
    """One engine pass: diff against the engine's previous description and append the transitions.
    Returns the number of NEW rows (0 when the same snapshot was already recorded)."""
    with _ENGINE_LOCK:
        analysis = live_analysis(ctx)
        if analysis is None or analysis.at is None:
            return 0
        previous = ctx.cache.get("intel_engine_prev")
        prev = previous if isinstance(previous, MarketIntelligence) else None
        intel = intelligence_for(ctx, analysis, prev)
        if intel is None:
            return 0
        held = ctx.desk.open_row()
        position = None if held is None else str(held["id"])
        auth = intel.authorization
        decision = analysis.decision
        rows = (
            [("ENGINE_START", "observation started")]
            if prev is None
            else [(c.kind, c.text) for c in intel.changes]
        )
        new = 0
        for kind, text in rows:
            new += int(
                record_event(
                    ctx,
                    kind=kind,
                    text=text,
                    moment=intel.generated_at,
                    action=auth.action,
                    chain_verdict=auth.chain_verdict,
                    strategy_version=auth.strategy_version,
                    decision_id=decision.decision_id,
                    setup_id=decision.setup_id,
                    position_id=position,
                )
            )
        ctx.cache["intel_engine_prev"] = intel.model_copy(update={"changes": ()})
        return new


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
    result = view_intelligence(ctx)
    if result is None:
        return JSONResponse(
            status_code=503,
            content={"error_code": "NO_BARS", "message": "Kho dữ liệu chưa có nến nào"},
        )
    return result
