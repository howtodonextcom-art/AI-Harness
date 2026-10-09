"""Data and experiment lineage (roadmap section 9), as a verifiable content-addressed graph.

RAW SOURCE -> RAW DATASET -> CERTIFIED DATASET -> DERIVED DATASET -> EVENT DATASET -> EXPERIMENT
-> RESULT -> CANDIDATE -> FORWARD SIGNAL -> EXECUTION.

A node's id is the hash of its own content, and it names its parents by id, so a change anywhere
upstream changes every id downstream. ``verify`` re-derives all ids and reports dangling parents,
duplicate ids and stage-order violations. A stage with no node is reported as EMPTY, never faked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

from xau_edge.integrity.canonical import canonical_hash

STAGES: Final = (
    "RAW_SOURCE",
    "RAW_DATASET",
    "CERTIFIED_DATASET",
    "DERIVED_DATASET",
    "EVENT_DATASET",
    "EXPERIMENT",
    "RESULT",
    "CANDIDATE",
    "FORWARD_SIGNAL",
    "EXECUTION",
)
_RANK: Final = {s: i for i, s in enumerate(STAGES)}


class LineageNode(BaseModel):
    """One artefact in the lineage. ``id`` is derived, never trusted from input."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stage: str
    label: str = Field(min_length=1)
    parents: tuple[str, ...] = ()
    source: str | None = None
    broker: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    timezone: str | None = None
    broker_clock: str | None = None
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    fetched_at: str | None = None
    raw_hash: str | None = None
    transformation: str | None = None
    transform_version: str | None = None
    validator_result: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)

    @property
    def id(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))[:16]

    @property
    def parent_hash(self) -> str | None:
        """Hash binding the node to its parents (None for a root)."""
        return canonical_hash(sorted(self.parents)) if self.parents else None


@dataclass(frozen=True)
class LineageReport:
    """Graph check result."""

    ok: bool
    problems: tuple[str, ...]
    empty_stages: tuple[str, ...]
    nodes: int


def verify(nodes: list[LineageNode]) -> LineageReport:
    """Duplicate ids, unknown stages, dangling parents and parents that are not upstream."""
    problems: list[str] = []
    by_id: dict[str, LineageNode] = {}
    for node in nodes:
        if node.stage not in _RANK:
            problems.append(f"unknown stage {node.stage}")
            continue
        if node.id in by_id:
            problems.append(f"duplicate node {node.label}")
        by_id[node.id] = node
    for node in by_id.values():
        for parent in node.parents:
            upstream = by_id.get(parent)
            if upstream is None:
                problems.append(f"{node.label}: parent {parent} not found")
            elif _RANK[upstream.stage] >= _RANK[node.stage]:
                problems.append(f"{node.label}: parent {upstream.label} is not upstream")
    present = {n.stage for n in by_id.values()}
    empty = tuple(s for s in STAGES if s not in present)
    return LineageReport(not problems, tuple(problems), empty, len(by_id))


def as_json(nodes: list[LineageNode]) -> dict[str, Any]:
    """Serialisable form with derived ids and parent hashes."""
    report = verify(nodes)
    return {
        "stages": list(STAGES),
        "ok": report.ok,
        "problems": list(report.problems),
        "empty_stages": list(report.empty_stages),
        "nodes": [
            {"id": n.id, "parent_hash": n.parent_hash, **n.model_dump(mode="json")} for n in nodes
        ],
    }


def from_json(raw: dict[str, Any]) -> tuple[list[LineageNode], list[str]]:
    """Rebuild nodes from a stored artefact; returns nodes and any stored-id mismatches."""
    nodes: list[LineageNode] = []
    mismatches: list[str] = []
    for item in raw.get("nodes", []):
        stored_id = item.get("id")
        stored_parent = item.get("parent_hash")
        body = {k: v for k, v in item.items() if k not in {"id", "parent_hash"}}
        node = LineageNode.model_validate(body)
        if stored_id != node.id:
            mismatches.append(f"{node.label}: stored id does not match its content")
        if stored_parent != node.parent_hash:
            mismatches.append(f"{node.label}: stored parent hash does not match its parents")
        nodes.append(node)
    return nodes, mismatches
