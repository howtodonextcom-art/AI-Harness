"""Scientific fail-closed invariants (roadmap section 29), checked through the real views.

A missing proof can never be rendered as a pass: each case removes ONE proof from an otherwise
valid record and asserts that the matching label is refused (with a reason) or the view is unknown.
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from tests.unit.integrity.test_prospective import signal
from tests.unit.research.helpers import make_repo, write
from tests.unit.research.test_integrity_views import _registry, _stage1_payload
from xau_edge.integrity.prospective import ProspectiveLedger
from xau_edge.research.service import ResearchService

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


def _service(root: Path) -> ResearchService:
    return ResearchService(root, clock=lambda: NOW)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return make_repo(tmp_path)


def _row(repo: Path, payload: dict[str, Any]) -> dict[str, Any]:
    write(repo, "experiments/edge_program_v2_stage1/v_dev2.json", json.dumps(payload))
    view = _service(repo).stage1()
    return view["variants"][0] if view["variants"] else view


def test_missing_ci_blocks_a_validated_label(repo: Path) -> None:
    payload: dict[str, Any] = copy.deepcopy(_stage1_payload())
    payload["study"]["ci95_net_base"] = None
    row = _row(repo, payload)
    labels = row["labels"]
    assert labels["VALIDATED"]["allowed"] is False
    assert any("confidence interval" in r for r in labels["VALIDATED"]["reasons"])


def test_missing_k_makes_the_whole_record_unknown(repo: Path) -> None:
    payload: dict[str, Any] = copy.deepcopy(_stage1_payload())
    del payload["k"]
    write(repo, "experiments/edge_program_v2_stage1/v_dev2.json", json.dumps(payload))
    assert _service(repo).stage1()["status"] == "unknown"


def test_missing_effective_n_blocks_adequately_powered(repo: Path) -> None:
    payload: dict[str, Any] = copy.deepcopy(_stage1_payload())
    payload["study"]["dependence"] = {}
    labels = _row(repo, payload)["labels"]
    assert labels["ADEQUATELY_POWERED"]["allowed"] is False
    assert any("effective N" in r for r in labels["ADEQUATELY_POWERED"]["reasons"])


def test_missing_dataset_hashes_block_reproducible(repo: Path) -> None:
    payload: dict[str, Any] = copy.deepcopy(_stage1_payload())
    payload["dataset_ids"] = {}
    labels = _row(repo, payload)["labels"]
    assert labels["REPRODUCIBLE"]["allowed"] is False
    assert any("dataset hashes" in r for r in labels["REPRODUCIBLE"]["reasons"])


def test_a_test_h_result_without_a_freeze_record_is_unknown_not_a_pass(repo: Path) -> None:
    for n in range(1, 5):
        _registry(repo, f"t{n}", "edge-program", "test")
    write(repo, "experiments/edge_program_v2/testH-outcome.json", json.dumps({"state": "PASS"}))
    states = {x["id"]: x["outcome_state"] for x in _service(repo).locks()["locks"]}
    assert states["testH"] == "UNKNOWN"
    write(repo, "docs/research/edge-program-v2/freeze-H0X.md", "# freeze\n")
    states = {x["id"]: x["outcome_state"] for x in _service(repo).locks()["locks"]}
    assert states["testH"] == "PASS"


def test_a_broken_prospective_chain_blocks_the_prospective_valid_label(repo: Path) -> None:
    path = repo / "data" / "forward" / "prospective.jsonl"
    ledger = ProspectiveLedger(path)
    ledger.append(signal(1))
    ledger.append(signal(2, "2026-10-09T10:15:00+00:00"))
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(lines[1] + "\n", encoding="utf-8")  # first record removed: chain broken
    view = _service(repo).prospective()
    assert view["status"] == "invalid"
    assert view["label"] != "SEALED BEFORE OUTCOME"
    assert "labels" not in view


def test_screening_only_evidence_is_never_validated_whatever_the_numbers(repo: Path) -> None:
    payload: dict[str, Any] = copy.deepcopy(_stage1_payload())
    payload["study"]["mean_net_base_r"] = 5.0
    payload["screening"] = {"stage1_survivor": True}
    labels = _row(repo, payload)["labels"]
    assert labels["VALIDATED"]["allowed"] is False


def test_missing_broker_evidence_blocks_execution_validated(repo: Path) -> None:
    view = _service(repo).calibration()
    assert view["status"] == "unknown"
    assert view["labels"]["EXECUTION_VALIDATED"]["allowed"] is False
    write(repo, "data/execution/calibration.json", json.dumps({"slippage_points_p50": 2.0}))
    measured = _service(repo).calibration()
    assert measured["labels"]["EXECUTION_VALIDATED"]["allowed"] is True


def test_every_view_with_a_missing_source_says_unknown_or_empty(tmp_path: Path) -> None:
    service = _service(tmp_path)  # an empty directory: nothing exists
    for name in ("lineage", "gate_calibration", "rollout"):
        assert getattr(service, name)()["status"] == "unknown", name
    assert service.stage1()["status"] in {"unknown", "empty"}
    assert service.prospective()["status"] == "empty"
    assert service.data()["status"] == "unknown"
    assert service.locks()["status"] == "unknown"
