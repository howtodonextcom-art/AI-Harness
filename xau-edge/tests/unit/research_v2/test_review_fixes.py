"""Regression tests for the independent red-team findings."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from tests.unit.integrity.test_gates_dof import entry
from tests.unit.research.helpers import make_repo, write
from xau_edge.integrity.dependence import effective_n
from xau_edge.integrity.dof import DesignLedger
from xau_edge.research.service import ResearchService
from xau_edge.research_v2.study import VariantStudy, one_sided_p, screen


def test_effective_n_uses_the_size_weighted_cluster_size() -> None:
    rng = np.random.default_rng(0)
    sizes = [1] * 300 + [12] * 100
    days = np.concatenate([np.full(s, i) for i, s in enumerate(sizes)]).astype(np.int64)
    day_effect = rng.standard_normal(len(sizes))
    values = np.array([day_effect[d] + rng.standard_normal() for d in days])  # ICC about 0.5
    n = len(values)
    eff = effective_n(values, days)
    assert eff < 0.5 * n  # the old unweighted mean size overstated it by about 2x


def test_a_p_value_from_too_few_days_is_never_a_rejection() -> None:
    values = np.full(200, 1.0) + np.random.default_rng(1).standard_normal(200) * 0.1
    days = np.repeat(np.arange(10), 20).astype(np.int64)
    assert one_sided_p(values, days) == 1.0


def test_holm_family_size_is_the_declared_one_not_the_qualifying_one() -> None:
    def study(name: str, p: float, events: int = 100) -> VariantStudy:
        return VariantStudy(name, events, p, 0.1, 0.1, {})

    studies = [study("a", 0.004), study("b", 0.9, events=5)]
    narrow = screen(studies)["a"]["holm_rejects_null"]
    wide = screen(studies, family_size=40)["a"]["holm_rejects_null"]
    assert narrow is True  # 0.004 <= 0.10 / 2
    assert wide is False  # 0.004 > 0.10 / 40


def test_the_design_ledger_stamps_its_own_time(tmp_path: Path) -> None:
    ledger = DesignLedger(tmp_path / "d.jsonl")
    ledger.append(entry("H20"))
    stored = ledger.entries()[0].recorded_at
    assert stored != "2026-10-09T00:00:00+00:00"
    assert datetime.fromisoformat(stored).tzinfo is not None
    assert abs((datetime.now(UTC) - datetime.fromisoformat(stored)).total_seconds()) < 60


def test_a_stage1_window_or_ledger_period_marks_the_locks_as_used(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    for n in range(1, 5):
        write(
            repo,
            f"experiments/runs/a{n}.json",
            json.dumps({"id": f"a{n}", "family": "edge-program", "period": "dev"}),
        )
    service = ResearchService(repo)
    before = {x["id"]: x["state"] for x in service.locks()["locks"]}
    assert before["holdout"] == "NGUYÊN VẸN"
    write(
        repo,
        "experiments/edge_program_v2_stage1/x_holdout.json",
        json.dumps({"variant": "x", "window": "holdout"}),
    )
    after = {x["id"]: x["state"] for x in ResearchService(repo).locks()["locks"]}
    assert after["holdout"] == "ĐÃ DÙNG"
    assert after["testH"] == "NGUYÊN VẸN"


def test_the_freeze_checklist_command_refuses_every_candidate_today() -> None:
    import importlib.util  # noqa: PLC0415

    path = Path(__file__).parents[3] / "scripts" / "check_freeze.py"
    spec = importlib.util.spec_from_file_location("check_freeze", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for split in ("testH", "holdout"):
        decision = module.decide("H09-ASIA_LONDON-t0.2", split)
        assert decision.allowed is False
        assert any("Stage 2" in r for r in decision.reasons)


def test_doctoring_both_the_result_and_its_manifest_is_caught_by_the_ledger(tmp_path: Path) -> None:
    import shutil  # noqa: PLC0415

    from xau_edge.integrity.canonical import canonical_hash, canonical_json  # noqa: PLC0415
    from xau_edge.integrity.identity import RunManifest  # noqa: PLC0415

    real = Path(__file__).parents[3]
    root = tmp_path / "repo"
    shutil.copytree(
        real / "experiments" / "edge_program_v2_stage1",
        root / "experiments" / "edge_program_v2_stage1",
    )
    shutil.copytree(
        real / "docs" / "research" / "edge-program-v2",
        root / "docs" / "research" / "edge-program-v2",
    )
    folder = root / "experiments" / "edge_program_v2_stage1"
    target = folder / "H07-PD-e0_dev2.json"
    doc = json.loads(target.read_text(encoding="utf-8"))
    old_id = doc["experiment_id"]
    doc["screening"]["stage1_survivor"] = True
    target.write_text(json.dumps(doc), encoding="utf-8")
    for path in (folder / "manifests").glob("*.json"):
        manifest = RunManifest.model_validate_json(path.read_text(encoding="utf-8"))
        if manifest.identity.experiment_id != old_id:
            continue
        forged = manifest.model_copy(update={"output_hashes": {"result": canonical_hash(doc)[:16]}})
        path.unlink()
        (folder / "manifests" / f"{forged.manifest_id}.json").write_text(
            canonical_json(forged.model_dump(mode="json")), encoding="utf-8"
        )
    view = ResearchService(root).stage1()
    row = next(r for r in view["variants"] if r["variant"] == "H07-PD-e0")
    assert row["result_intact"] is False
    assert row["survivor"] is False
