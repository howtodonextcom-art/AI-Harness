"""The evidence gate: has THIS configuration passed the pre-registered validation on every period?

The gate is bound to one configuration (registry family plus exact parameters): evidence for one
strategy says nothing about another. A pass counts only if, for that configuration, the LATEST
record of each period (development, validation, test) passed, all three were produced on the same
datasets, and none was run from a dirty working tree. Re-running a period replaces its earlier
record, so a later failure revokes the evidence.
"""

from __future__ import annotations

import json
from typing import Any

from xau_edge.experiments.registry import ExperimentRecord, ExperimentRegistry
from xau_edge.signals.schema import EvidenceStatus
from xau_edge.signals.strategy_registry import StrategySpec, config_hash, dataset_hash

PERIODS = ("development", "validation", "test")


def _passed(record: ExperimentRecord) -> bool:
    if record.family == "backtest":
        return bool(record.metrics.get("verdict", {}).get("passed") is True)
    return record.metrics.get("passed") is True


def _key(params: dict[str, Any]) -> str:
    return json.dumps(params, sort_keys=True, default=str)


def evidence_status(
    registry: ExperimentRegistry, *, family: str, params: dict[str, Any]
) -> EvidenceStatus:
    """VALIDATED only for ``(family, params)`` meeting every condition in the module docstring."""
    wanted = _key(params)
    latest: dict[str, ExperimentRecord] = {}
    for record in registry.list(family):
        if _key(record.params) == wanted:
            latest[record.period] = record
    return _decide(latest, None)


def evidence_for_strategy(
    registry: ExperimentRegistry, spec: StrategySpec, *, dataset: str | None = None
) -> EvidenceStatus:
    """VALIDATED for ``spec`` (id + config hash) on one dataset hash (ADR-0021).

    Same conditions as :func:`evidence_status`; additionally the records must carry
    ``params["strategy"] == spec.strategy_id`` and the config hash of ``spec``, and, when
    ``dataset`` is given, the hash of the datasets they ran on must equal it.
    """
    latest: dict[str, ExperimentRecord] = {}
    for record in registry.list(spec.family):
        if (
            record.params.get("strategy") == spec.strategy_id
            and config_hash(record.params) == spec.config_hash
        ):
            latest[record.period] = record
    return _decide(latest, dataset)


def _decide(latest: dict[str, ExperimentRecord], dataset: str | None) -> EvidenceStatus:
    if not all(period in latest for period in PERIODS):
        return EvidenceStatus.NONE
    records = [latest[p] for p in PERIODS]
    same_data = len({_key(dict(r.dataset_ids)) for r in records}) == 1
    if dataset is not None and dataset_hash(records[0].dataset_ids) != dataset:
        return EvidenceStatus.NONE
    clean = not any(r.code_dirty for r in records)
    if same_data and clean and all(_passed(r) for r in records):
        return EvidenceStatus.VALIDATED
    return EvidenceStatus.NONE
