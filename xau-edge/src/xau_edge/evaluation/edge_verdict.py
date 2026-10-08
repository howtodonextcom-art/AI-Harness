"""Edge Program verdict (T1.6): (A) or (B), and the ledger's pre-registered "best" rule.

Reads the JSON results written by ``evaluation/edge_program.py``. Only completed records count;
for each (variant, period) the most recent completed record is used (``ledger.md`` rule 11).

* Verdict (A) EDGE VALIDATED needs at least one variant whose Test-H record is a stage PASS.
  Anything else is (B) NO EDGE WITHIN BUDGET. A Test-H PASS still needs the independent review
  of ledger rule 5 before (A) is final; that is recorded by people, not by this module.
* Ledger rule 6 (fixed before results): among variants with >= 100 trades in BOTH Dev-H and Val-H,
  score = min(pessimistic mean net R on Dev-H, on Val-H); the highest score is "the best after
  pessimistic costs". A best score <= 0 means no variant is positive in both periods; the name is
  then a reference value, not a finding.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

MIN_TRADES = 100
Verdict = Literal["A", "B"]


@dataclass(frozen=True)
class StageResult:
    """One completed (variant, period) record, reduced to what the verdict needs."""

    variant: str
    period: str
    recorded_at: str
    registry_id: str
    trades: int
    mean_net_r: float | None
    pessimistic_mean_net_r: float | None
    stage_pass: bool
    failed_criteria: tuple[str, ...]


@dataclass(frozen=True)
class BestChoice:
    """The outcome of ledger rule 6."""

    variant: str | None
    score: float | None
    positive: bool
    eligible: tuple[str, ...]


def _mean(scenario: Mapping[str, Any] | None) -> float | None:
    if not scenario:
        return None
    value = scenario.get("mean_net_r")
    return float(value) if value is not None else None


def stage_from_payload(payload: Mapping[str, Any]) -> StageResult | None:
    """The stage result of one JSON payload; ``None`` unless the run completed."""
    if payload.get("status") != "completed":
        return None
    scenarios = payload.get("scenarios") or {}
    base = scenarios.get("base") or {}
    verdict = base.get("verdict") or {}
    failed = tuple(
        name
        for name, item in verdict.items()
        if isinstance(item, Mapping) and item.get("passed") is False
    )
    return StageResult(
        variant=str(payload["variant"]),
        period=str(payload["period"]["name"] if isinstance(payload["period"], Mapping) else ""),
        recorded_at=str(payload["recorded_at"]),
        registry_id=str(payload["registry_id"]),
        trades=int(base.get("trades") or 0),
        mean_net_r=_mean(base),
        pessimistic_mean_net_r=_mean(scenarios.get("pessimistic")),
        stage_pass=bool(payload.get("stage_pass")),
        failed_criteria=failed,
    )


def load_stage_results(results_dir: Path | str) -> list[StageResult]:
    """Every completed stage result in the folder (``*.json`` written by the runner)."""
    found: list[StageResult] = []
    for path in sorted(Path(results_dir).glob("H0*_*.json")):
        stage = stage_from_payload(json.loads(path.read_text(encoding="utf-8")))
        if stage is not None:
            found.append(stage)
    return found


def latest(results: Iterable[StageResult]) -> dict[tuple[str, str], StageResult]:
    """The most recent completed record per (variant, period)."""
    out: dict[tuple[str, str], StageResult] = {}
    for r in sorted(results, key=lambda s: s.recorded_at):
        out[(r.variant, r.period)] = r
    return out


def select_best_pessimistic(
    results: Iterable[StageResult], *, min_trades: int = MIN_TRADES
) -> BestChoice:
    """Ledger rule 6: maximin of the pessimistic mean net R over Dev-H and Val-H."""
    table = latest(results)
    variants = sorted({v for v, _ in table})
    scored: list[tuple[float, str]] = []
    for v in variants:
        dev, val = table.get((v, "dev")), table.get((v, "val"))
        if dev is None or val is None:
            continue
        if dev.trades < min_trades or val.trades < min_trades:
            continue
        if dev.pessimistic_mean_net_r is None or val.pessimistic_mean_net_r is None:
            continue
        scored.append((min(dev.pessimistic_mean_net_r, val.pessimistic_mean_net_r), v))
    if not scored:
        return BestChoice(None, None, positive=False, eligible=())
    score, best = max(scored, key=lambda item: (item[0], item[1]))
    return BestChoice(best, score, positive=score > 0, eligible=tuple(v for _, v in scored))


def program_verdict(results: Iterable[StageResult]) -> Verdict:
    """(A) when some variant has a Test-H stage PASS, otherwise (B)."""
    table = latest(results)
    return "A" if any(r.stage_pass for (_, p), r in table.items() if p == "test") else "B"
