"""Research integrity views: forward readiness, prospective ledger, lineage, stage 1, locks."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from tests.unit.integrity.test_prospective import signal
from tests.unit.research.helpers import make_repo, write
from xau_edge.integrity.lineage import LineageNode, as_json
from xau_edge.integrity.prospective import ProspectiveLedger
from xau_edge.research.service import ResearchService

REAL = Path(__file__).parents[3]
NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


def _service(root: Path) -> ResearchService:
    return ResearchService(root, clock=lambda: NOW)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return make_repo(tmp_path)


def _registry(repo: Path, name: str, family: str, period: str) -> None:
    write(
        repo,
        f"experiments/runs/{name}.json",
        json.dumps({"id": name, "family": family, "period": period}),
    )


def _forward(n: int, days: list[int], **over: object) -> str:
    base: dict[str, object] = {
        "n_trades": n,
        "mean_r_expected": {"value": 0.1, "lo": 0.02, "hi": 0.2},
        "validated_max_dd_r": 10,
        "cost_drift": 1.0,
        "trades_net_r": [0.12, 0.08] * (n // 2),
        "trade_day_ids": days,
        "calendar_days": 200,
        "regimes_seen": 3,
        "target_effect": 0.10,
        "expected_sd": 1.3,
    }
    base.update(over)
    return json.dumps(base)


# -- forward readiness ---------------------------------------------------------------------


def test_a_hundred_raw_trades_never_conclude(repo: Path) -> None:
    write(repo, "data/forward/s1/summary.json", _forward(100, list(range(100))))
    view = _service(repo).forward("s1")
    assert view["readiness"]["raw_n"] == 100
    assert view["conclusion"] == "INCONCLUSIVE"
    assert any("effective N" in r for r in view["readiness"]["reasons"])
    assert view["legacy_reference_trades"] == 100


def test_enough_effective_n_calendar_and_regimes_can_conclude(repo: Path) -> None:
    n = 2400
    write(repo, "data/forward/s1/summary.json", _forward(n, list(range(n))))
    view = _service(repo).forward("s1")
    assert view["readiness"]["effective_n"] > 1045
    assert view["conclusion"] in {"CONSISTENT", "INCONSISTENT"}


def test_clustered_days_reduce_effective_n_and_block_the_conclusion(repo: Path) -> None:
    n = 2400
    days = [i // 40 for i in range(n)]
    trades = [0.5 if (i // 40) % 2 else -0.3 for i in range(n)]
    write(repo, "data/forward/s1/summary.json", _forward(n, days, trades_net_r=trades))
    view = _service(repo).forward("s1")
    assert view["readiness"]["effective_n"] < n / 5
    assert view["conclusion"] == "INCONCLUSIVE"


def test_short_calendar_or_one_regime_blocks_the_conclusion(repo: Path) -> None:
    n = 2400
    write(repo, "data/forward/s1/summary.json", _forward(n, list(range(n)), calendar_days=20))
    assert _service(repo).forward("s1")["conclusion"] == "INCONCLUSIVE"
    write(repo, "data/forward/s1/summary.json", _forward(n, list(range(n)), regimes_seen=1))
    assert _service(repo).forward("s1")["conclusion"] == "INCONCLUSIVE"


def test_day_ids_of_the_wrong_length_are_inconclusive_not_a_crash(repo: Path) -> None:
    write(repo, "data/forward/s1/summary.json", _forward(2400, [1, 2, 3]))
    view = _service(repo).forward("s1")
    assert view["conclusion"] == "INCONCLUSIVE"


# -- prospective ---------------------------------------------------------------------------


def test_prospective_missing_ledger_says_no_evidence_yet(repo: Path) -> None:
    view = _service(repo).prospective()
    assert view["status"] == "empty"
    assert view["label"] == "NO PROSPECTIVE EVIDENCE YET"


def test_prospective_valid_chain_is_sealed_and_a_tampered_one_is_invalid(repo: Path) -> None:
    path = repo / "data" / "forward" / "prospective.jsonl"
    ProspectiveLedger(path).append(signal(1))
    view = _service(repo).prospective()
    assert view["status"] == "ok"
    assert view["label"] == "SEALED BEFORE OUTCOME"
    assert view["labels"]["PROSPECTIVE_VALID"]["allowed"] is True
    path.write_text(path.read_text(encoding="utf-8").replace('"SELL"', '"BUY"'), encoding="utf-8")
    bad = _service(repo).prospective()
    assert bad["status"] == "invalid"
    assert bad["label"] == "PROVENANCE INVALID"
    assert "labels" not in bad


# -- lineage -------------------------------------------------------------------------------


def test_lineage_is_unknown_without_the_artefact_and_detects_a_tampered_node(repo: Path) -> None:
    assert _service(repo).lineage()["status"] == "unknown"
    root = LineageNode(stage="RAW_SOURCE", label="src")
    raw = LineageNode(stage="RAW_DATASET", label="raw", parents=(root.id,), raw_hash="a" * 64)
    doc = as_json([root, raw])
    write(repo, "docs/research/edge-program-v2/lineage.json", json.dumps(doc))
    view = _service(repo).lineage()
    assert view["status"] == "ok"
    assert "CANDIDATE" in view["empty_stages"]
    doc["nodes"][1]["raw_hash"] = "b" * 64
    write(repo, "docs/research/edge-program-v2/lineage.json", json.dumps(doc))
    tampered = _service(repo).lineage()
    assert tampered["status"] == "unknown"
    assert any("stored id" in p for p in tampered["problems"])


def test_the_real_lineage_artefact_is_consistent() -> None:
    view = ResearchService(REAL).lineage()
    assert view["status"] == "ok"
    assert {"CANDIDATE", "FORWARD_SIGNAL", "EXECUTION"} <= set(view["empty_stages"])


# -- rollout and gates ---------------------------------------------------------------------


def test_the_rollout_config_is_shown_with_an_unknown_current_tier() -> None:
    view = ResearchService(REAL).rollout()
    assert view["status"] == "ok"
    assert view["current_tier_state"] == "KHÔNG RÕ"
    tiers = [t["tier"] for t in view["tiers"]]
    assert tiers == sorted(tiers)
    assert all(t["progress"] == "KHÔNG RÕ" for t in view["tiers"])


def test_gate_calibration_requires_its_artefact(repo: Path) -> None:
    assert _service(repo).gate_calibration()["status"] == "unknown"
    real = ResearchService(REAL).gate_calibration()
    assert real["status"] == "ok"
    assert {g["gate"] for g in real["gates"]} == {"temporal", "parameter", "broker"}


# -- stage 1 -------------------------------------------------------------------------------


def _stage1_payload() -> dict[str, Any]:
    study = {
        "n_events": 500,
        "mean_gross_mid_r": 0.05,
        "mean_net_base_r": -0.05,
        "mean_net_pess_r": -0.07,
        "ci95_net_base": [-0.1, 0.0],
        "p_value_one_sided": 0.9,
        "dependence": {"effective_n": 480, "unique_days": 480, "sensitivity": "DEPENDENCE_STABLE"},
        "power": {"mde_effective": 0.18, "adequately_powered": True},
        "intrabar": {"status": "INTRABAR_ROBUST"},
        "era": {"status": "UNKNOWN"},
    }
    return {
        "variant": "H09-x",
        "hypothesis": "H09",
        "window": "dev2",
        "evidence_class": "SCREENING",
        "k": 20,
        "experiment_id": "e" * 32,
        "dataset_ids": {"H1": "f" * 16},
        "code_commit_sha": "a" * 40,
        "screening": {"stage1_survivor": False},
        "study": study,
    }


def test_stage1_is_empty_then_screening_and_never_validated(repo: Path) -> None:
    assert _service(repo).stage1()["status"] == "empty"
    write(repo, "experiments/edge_program_v2_stage1/H09-x_dev2.json", json.dumps(_stage1_payload()))
    view = _service(repo).stage1()
    row = view["variants"][0]
    assert view["status"] == "ok"
    assert row["evidence_class"] == "SCREENING"
    assert row["labels"]["VALIDATED"]["allowed"] is False
    assert row["manifest_verified"] is False
    assert row["provenance"] == "KHÔNG RÕ"
    assert row["labels"]["REPRODUCIBLE"]["allowed"] is False
    assert row["alpha_bonferroni"] == 0.05 / 20
    write(repo, "experiments/edge_program_v2_stage1/bad_dev2.json", "{}")
    assert _service(repo).stage1()["status"] == "unknown"


def test_the_real_stage1_results_are_screening_with_verified_manifests() -> None:
    view = ResearchService(REAL).stage1()
    assert view["status"] == "ok"
    assert view["survivors"] == []
    assert len(view["variants"]) == 20
    assert all(r["evidence_class"] == "SCREENING" for r in view["variants"])
    assert all(r["manifest_verified"] for r in view["variants"])
    assert all(not r["labels"]["VALIDATED"]["allowed"] for r in view["variants"])


# -- locks ---------------------------------------------------------------------------------


def test_test_h_outcome_state_is_locked_when_pristine_and_unknown_when_inconsistent(
    repo: Path,
) -> None:
    for n in range(1, 5):
        _registry(repo, f"a{n}", "edge-program", "dev")
    states = {lock["id"]: lock["outcome_state"] for lock in _service(repo).locks()["locks"]}
    assert states["testH"] == "LOCKED"
    assert states["dev2"] is None
    write(repo, "experiments/edge_program_v2/testH-outcome.json", json.dumps({"state": "PASS"}))
    states = {lock["id"]: lock["outcome_state"] for lock in _service(repo).locks()["locks"]}
    assert states["testH"] == "UNKNOWN"


def test_the_real_repository_locks_test_h_and_holdout() -> None:
    view = ResearchService(REAL).locks()
    states = {lock["id"]: lock["state"] for lock in view["locks"]}
    assert states["testH"] in {"NGUYÊN VẸN", "KHÔNG RÕ"}
    assert states["holdout"] in {"NGUYÊN VẸN", "KHÔNG RÕ"}
    assert states["testH"] != "ĐÃ DÙNG"


# -- hypotheses ----------------------------------------------------------------------------


def test_the_real_v2_hypotheses_expose_mde_and_expected_n() -> None:
    view = ResearchService(REAL).hypotheses()
    rows = {r["id"]: r for r in view["hypotheses"] if r["programme"] == "V2"}
    assert {"H07", "H08", "H09", "H10"} <= set(rows)
    for hid in ("H07", "H08", "H09", "H10"):
        reg = rows[hid]["registration"]
        assert reg["status"] == "ok"
        assert reg["expected_event_count"] > 0
        assert reg["mde_effective"] is not None
        assert reg["underpowered_by_design"] is False
        assert reg["mechanism_status"] == "HYPOTHESIZED"
    assert rows["H08"]["registration"]["dropped_variants"]
