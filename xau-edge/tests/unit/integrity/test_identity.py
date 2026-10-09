from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from xau_edge.integrity.canonical import canonical_hash, canonical_json
from xau_edge.integrity.evidence import (
    EvidenceClass,
    Label,
    Proof,
    can_display,
    may_promote,
)
from xau_edge.integrity.identity import (
    ExperimentIdentity,
    IdentityError,
    RunManifest,
    read_manifest,
    write_manifest,
)

SHA = "a" * 40


def identity(**over: object) -> ExperimentIdentity:
    base: dict[str, object] = {
        "programme_id": "edge-v2",
        "hypothesis_id": "H07",
        "variant_id": "H07-a",
        "strategy_id": "H07-a",
        "config_hash": "b" * 16,
        "dataset_hashes": {"H1": "c" * 16},
        "feature_version": "f1",
        "label_version": "l1",
        "cost_model_version": "c1",
        "code_commit_sha": SHA,
        "runner_version": "r1",
        "evidence_class": EvidenceClass.SCREENING,
    }
    base.update(over)
    return ExperimentIdentity(**base)


def manifest(**over: object) -> RunManifest:
    base: dict[str, object] = {
        "identity": identity(),
        "parameters": {"theta": 0.3},
        "split": "dev",
        "random_seeds": {"main": 1},
        "environment_lock_hash": "d" * 32,
        "started_at": "2026-10-09T00:00:00+00:00",
        "finished_at": "2026-10-09T00:01:00+00:00",
        "output_hashes": {"result": "e" * 32},
        "status": "OK",
    }
    base.update(over)
    return RunManifest(**base)


def test_the_same_identity_gives_the_same_id_and_a_change_gives_another() -> None:
    assert identity().experiment_id == identity().experiment_id
    assert identity().experiment_id != identity(feature_version="f2").experiment_id
    assert identity().experiment_id != identity(dataset_hashes={"H1": "d" * 16}).experiment_id


def test_dict_order_does_not_change_the_hash() -> None:
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash({"b": 2, "a": 1})


def test_non_finite_numbers_are_refused() -> None:
    with pytest.raises(ValueError, match="non-finite"):
        canonical_json({"x": float("nan")})


@pytest.mark.parametrize(
    "bad",
    [
        {"code_commit_sha": "unknown"},
        {"code_commit_sha": "abc"},
        {"code_commit_sha": "0" * 40},
        {"config_hash": "XYZ"},
        {"dataset_hashes": {}},
        {"dataset_hashes": {"H1": "not-hex"}},
        {"feature_version": ""},
    ],
)
def test_an_incomplete_identity_is_refused(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        identity(**bad)


def test_a_manifest_is_written_once_and_a_modified_one_is_detected(tmp_path: Path) -> None:
    m = manifest()
    path = write_manifest(tmp_path, m)
    assert write_manifest(tmp_path, m) == path
    assert read_manifest(path).manifest_id == m.manifest_id
    path.write_text(path.read_text(encoding="utf-8").replace('"OK"', '"FAILED"'), encoding="utf-8")
    with pytest.raises(IdentityError):
        read_manifest(path)
    with pytest.raises(IdentityError):
        write_manifest(tmp_path, m)


def test_an_unknown_status_is_refused() -> None:
    with pytest.raises(ValidationError):
        manifest(status="PASS")


# -- evidence classes ----------------------------------------------------------------------


def test_descriptive_and_exploratory_can_never_be_validated() -> None:
    for cls in (EvidenceClass.DESCRIPTIVE, EvidenceClass.EXPLORATORY):
        proof = Proof(cls, ci_present=True, k_present=True, effective_n_present=True)
        assert not can_display(Label.VALIDATED, proof).allowed


def test_only_screening_evidence_cannot_display_validated() -> None:
    proof = Proof(EvidenceClass.SCREENING, ci_present=True, k_present=True)
    assert not can_display(Label.VALIDATED, proof).allowed


def test_each_missing_proof_blocks_its_label() -> None:
    cls = EvidenceClass.CONFIRMATORY
    full = Proof(cls, ci_present=True, k_present=True, freeze_record_present=True)
    assert can_display(Label.CONFIRMATORY_PASS, full).allowed
    assert not can_display(
        Label.CONFIRMATORY_PASS, Proof(cls, k_present=True, freeze_record_present=True)
    ).allowed
    assert not can_display(
        Label.CONFIRMATORY_PASS, Proof(cls, ci_present=True, freeze_record_present=True)
    ).allowed
    assert not can_display(
        Label.CONFIRMATORY_PASS, Proof(cls, ci_present=True, k_present=True)
    ).allowed
    assert not can_display(Label.ADEQUATELY_POWERED, Proof(EvidenceClass.VALIDATION)).allowed
    assert not can_display(Label.REPRODUCIBLE, Proof(EvidenceClass.VALIDATION)).allowed
    assert not can_display(Label.PROSPECTIVE_VALID, Proof(EvidenceClass.PROSPECTIVE)).allowed
    assert not can_display(Label.EXECUTION_VALIDATED, Proof(EvidenceClass.EXECUTION)).allowed
    assert can_display(
        Label.PROSPECTIVE_VALID, Proof(EvidenceClass.PROSPECTIVE, chain_verified=True)
    ).allowed


def test_a_class_cannot_be_promoted_by_relabelling() -> None:
    assert not may_promote(EvidenceClass.DESCRIPTIVE, EvidenceClass.SCREENING)
    assert not may_promote(EvidenceClass.SCREENING, EvidenceClass.CONFIRMATORY)
    assert not may_promote(EvidenceClass.VALIDATION, EvidenceClass.HOLDOUT)
    assert not may_promote(EvidenceClass.SCREENING, EvidenceClass.PROSPECTIVE)
    assert may_promote(EvidenceClass.SCREENING, EvidenceClass.VALIDATION)
