from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from xau_edge.integrity.evidence import EvidenceClass, Label, Proof, can_display, may_promote
from xau_edge.research.lifecycle import STATES, LifecycleError, LifecycleStore
from xau_edge.research_v2.batch_a import LockedSplitError, window_bars
from xau_edge.research_v2.guards import check

SHA = "a" * 40
DATA = {"H1": "b" * 64}


def freeze(tmp_path: Path, **over: Any) -> Path:
    body: dict[str, Any] = {
        "candidate_id": "H09-x",
        "split": "testH",
        "code_commit_sha": SHA,
        "k_frozen": 20,
        "dataset_hashes": DATA,
        "rules_hash": "c" * 64,
        "stage2_passed_on": "Validation-2 2026-12-01",
        "independent_review": "review note committed in abc1234",
        "frozen_at": "2026-12-02T00:00:00+00:00",
    }
    body.update(over)
    path = tmp_path / "freeze.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def ok(path: Path, **over: Any) -> Any:
    args: dict[str, Any] = {
        "split": "testH",
        "candidate_id": "H09-x",
        "head_sha": SHA,
        "k_now": 20,
        "dataset_hashes": DATA,
        "stage2_survivors": {"H09-x"},
        "already_run": set(),
        "committed": True,
    }
    args.update(over)
    return check(path, **args)


def test_a_complete_freeze_for_a_stage2_survivor_is_the_only_way_to_allow(tmp_path: Path) -> None:
    assert ok(freeze(tmp_path)).allowed


@pytest.mark.parametrize(
    ("over", "reason"),
    [
        ({"stage2_survivors": set()}, "Stage 2"),
        ({"already_run": {("H09-x", "testH")}}, "one run only"),
        ({"committed": False}, "not committed"),
        ({"head_sha": "d" * 40}, "frozen commit"),
        ({"k_now": 21}, "K changed"),
        ({"dataset_hashes": {"H1": "e" * 64}}, "dataset hashes"),
        ({"split": "dev2"}, "not a locked split"),
    ],
)
def test_every_missing_condition_refuses(tmp_path: Path, over: dict[str, Any], reason: str) -> None:
    decision = ok(freeze(tmp_path), **over)
    assert not decision.allowed
    assert any(reason in r for r in decision.reasons)


def test_no_or_invalid_freeze_record_refuses(tmp_path: Path) -> None:
    assert not ok(tmp_path / "missing.json").allowed
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert not ok(bad).allowed
    assert not ok(freeze(tmp_path, k_frozen=0)).allowed
    assert not ok(freeze(tmp_path, candidate_id="other")).allowed


def test_the_batch_a_loader_cannot_reach_a_locked_split() -> None:
    empty = pl.DataFrame({"timestamp": []})
    for name in ("testH", "holdout", "test", "anything"):
        with pytest.raises(LockedSplitError):
            window_bars(empty, empty, name)


# -- property tests ------------------------------------------------------------------------


@given(
    steps=st.lists(
        st.tuples(
            st.sampled_from(["s1", "s2", "s3"]),
            st.sampled_from(STATES),
            st.sampled_from(["WATCH", "DEGRADED", "DISABLED", "VALIDATED", "FUNDED", "PAPER"]),
        ),
        max_size=25,
    )
)
@settings(max_examples=60, deadline=None)
def test_the_web_can_never_raise_a_strategy_state(
    steps: list[tuple[str, str, str]], tmp_path_factory: pytest.TempPathFactory
) -> None:
    rank = {
        "RESEARCH": 0, "REJECTED": 0, "RETIRED": 0, "DISABLED": 1, "DEGRADED": 2,
        "WATCH": 3, "PAPER": 4, "DEMO": 5, "VALIDATED": 6, "FUNDED": 7,
    }  # fmt: skip
    path = tmp_path_factory.mktemp("life") / "lifecycle.jsonl"
    seed = {"s1": "VALIDATED", "s2": "PAPER", "s3": "REJECTED"}
    store = LifecycleStore(path, seed)
    for strategy, _unused, target in steps:
        before = store.states()[strategy]
        try:
            store.demote(strategy, target, "reason", source="web")
        except LifecycleError:
            assert store.states()[strategy] == before
            continue
        assert rank[store.states()[strategy]] < rank[before]
    for name, state in store.states().items():
        assert rank[state] <= rank[seed[name]]
    assert store.states()["s3"] == "REJECTED"


@given(st.sampled_from(list(EvidenceClass)), st.sampled_from(list(EvidenceClass)))
def test_promotion_never_reaches_a_confirmatory_class_by_relabelling(
    source: EvidenceClass, target: EvidenceClass
) -> None:
    if target in {
        EvidenceClass.CONFIRMATORY,
        EvidenceClass.HOLDOUT,
        EvidenceClass.PROSPECTIVE,
        EvidenceClass.EXECUTION,
    }:
        assert may_promote(source, target) is (source is target)


@given(
    st.sampled_from(list(EvidenceClass)),
    st.booleans(),
    st.booleans(),
    st.booleans(),
    st.booleans(),
    st.booleans(),
    st.booleans(),
)
def test_a_label_is_never_allowed_while_a_required_proof_is_missing(  # noqa: PLR0917
    cls: EvidenceClass, ci: bool, k: bool, eff: bool, hashes: bool, freeze_rec: bool, chain: bool
) -> None:
    proof = Proof(
        cls,
        ci_present=ci,
        k_present=k,
        effective_n_present=eff,
        dataset_hashes_present=hashes,
        freeze_record_present=freeze_rec,
        chain_verified=chain,
    )
    if not eff:
        assert not can_display(Label.ADEQUATELY_POWERED, proof).allowed
    if not hashes:
        assert not can_display(Label.REPRODUCIBLE, proof).allowed
    if not (ci and k):
        assert not can_display(Label.VALIDATED, proof).allowed
    if not (ci and k and freeze_rec) or cls not in {
        EvidenceClass.CONFIRMATORY,
        EvidenceClass.HOLDOUT,
    }:
        assert not can_display(Label.CONFIRMATORY_PASS, proof).allowed
    if not chain or cls is not EvidenceClass.PROSPECTIVE:
        assert not can_display(Label.PROSPECTIVE_VALID, proof).allowed
    assert not can_display(Label.EXECUTION_VALIDATED, proof).allowed  # no broker evidence given
