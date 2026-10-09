"""``/research/*`` and ``/lifecycle/*``: read-only views for the research console (ADR-0024).

Every route is GET. They read files that already exist (ledger, results, manifests, logs) through
``ResearchRoot``, which allows only fixed folders and never a secret or a database. The one write
the console can make, demoting a strategy, lives under ``/control`` with the control guard.
"""

from __future__ import annotations

import re
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query

from xau_edge.research.service import ResearchService

_ID = re.compile(r"^[A-Za-z0-9_.\-]{1,60}$")


def add_research_routes(app: FastAPI, service: ResearchService | None) -> None:
    """Register the GET-only routes (503 when the console is not configured)."""

    def need() -> ResearchService:
        if service is None:
            raise HTTPException(status_code=503, detail="the research console is not configured")
        return service

    def stamp(view: dict[str, Any]) -> dict[str, Any]:
        """Add where and when the view was produced (no path, no secret)."""
        view.setdefault("provenance", need().provenance())
        return view

    @app.get("/research/overview")
    def overview() -> dict[str, Any]:
        return stamp(need().overview())

    @app.get("/research/ledger")
    def ledger(
        programme: Annotated[str, Query(pattern="^(v1|v2)$")] = "v1",
        hypothesis: Annotated[str | None, Query(pattern=r"^H\d{2}$")] = None,
        period: Annotated[str | None, Query(max_length=20)] = None,
        scenario: Annotated[str | None, Query(max_length=20)] = None,
    ) -> dict[str, Any]:
        return stamp(need().ledger(programme, hypothesis, period, scenario))

    @app.get("/research/power")
    def power(
        k: Annotated[int, Query(ge=1, le=1000)] = 21,
        n: Annotated[int, Query(ge=1, le=1_000_000)] = 500,
        sd: Annotated[float, Query(gt=0.05, le=10.0)] = 1.3,
    ) -> dict[str, Any]:
        return stamp(need().power(k, n, sd))

    @app.get("/research/hypotheses")
    def hypotheses() -> dict[str, Any]:
        return stamp(need().hypotheses())

    @app.get("/research/candidates")
    def candidates() -> dict[str, Any]:
        return stamp(need().candidates())

    @app.get("/research/candidates/{variant}")
    def candidate(variant: str) -> dict[str, Any]:
        if not _ID.match(variant):
            raise HTTPException(status_code=422, detail="invalid variant id")
        return stamp(need().candidate(variant))

    @app.get("/research/data")
    def data() -> dict[str, Any]:
        return stamp(need().data())

    @app.get("/research/locks")
    def locks() -> dict[str, Any]:
        return stamp(need().locks())

    @app.get("/research/calibration")
    def calibration() -> dict[str, Any]:
        return stamp(need().calibration())

    @app.get("/research/soak")
    def soak() -> dict[str, Any]:
        return stamp(need().soak())

    @app.get("/research/stage1")
    def stage1() -> dict[str, Any]:
        return stamp(need().stage1())

    @app.get("/research/stage1/{variant}")
    def stage1_variant(variant: str) -> dict[str, Any]:
        if not _ID.match(variant):
            raise HTTPException(status_code=422, detail="invalid variant id")
        view = need().stage1()
        rows = [r for r in view.get("variants", []) if r.get("variant") == variant]
        if not rows:
            return stamp({"status": "unknown", "source": view.get("source"), "variant": variant,
                          "reason": "không có kết quả Stage 1 cho biến thể này"})  # fmt: skip
        return stamp({**{k: v for k, v in view.items() if k != "variants"}, "variant": rows[0]})

    @app.get("/research/lineage")
    def lineage() -> dict[str, Any]:
        return stamp(need().lineage())

    @app.get("/research/prospective")
    def prospective() -> dict[str, Any]:
        return stamp(need().prospective())

    @app.get("/research/rollout")
    def rollout() -> dict[str, Any]:
        return stamp(need().rollout())

    @app.get("/research/gates")
    def gates() -> dict[str, Any]:
        return stamp(need().gate_calibration())

    @app.get("/lifecycle/strategies")
    def strategies() -> dict[str, Any]:
        return stamp(need().strategies())

    @app.get("/lifecycle/{strategy_id}/forward")
    def forward(strategy_id: str) -> dict[str, Any]:
        return stamp(need().forward(strategy_id))
