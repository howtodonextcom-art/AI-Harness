from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from xau_edge.integrity.registration import (
    HypothesisRegistration,
    MechanismStatus,
    derive,
    validate,
)
from xau_edge.research_v2.batch_a import K_BATCH_A, variants

REPO = Path(__file__).resolve().parents[3]
FOLDER = REPO / "docs" / "research" / "edge-program-v2" / "hypotheses"
IDS = ("H07", "H08", "H09", "H10")


def load(hid: str) -> HypothesisRegistration:
    raw = json.loads((FOLDER / f"{hid}.registration.json").read_text(encoding="utf-8"))
    return HypothesisRegistration.model_validate(raw)


def test_every_batch_a_registration_exists_validates_and_is_complete() -> None:
    for hid in IDS:
        reg = load(hid)
        assert validate(reg, k_cap=24) == [], hid
        assert (FOLDER / f"{hid}.md").exists()
        assert reg.mechanism_status is MechanismStatus.HYPOTHESIZED


def test_registered_variants_match_the_runner_minus_the_dropped_ones() -> None:
    registered: list[str] = []
    dropped: list[str] = []
    for hid in IDS:
        reg = load(hid)
        registered += reg.variant_ids
        dropped += reg.dropped_variants
    runner = [v.id for v in variants()]
    assert sorted(registered + dropped) == sorted(runner)
    assert len(runner) == K_BATCH_A
    assert len(registered) == load("H07").k_at_registration
    assert not set(registered) & set(dropped)


def test_k_is_the_same_everywhere_and_within_the_cap() -> None:
    assert {load(h).k_at_registration for h in IDS} == {20}
    assert sum(len(load(h).variant_ids) for h in IDS) == 20


def test_derived_numbers_are_recomputed_never_stored() -> None:
    raw = json.loads((FOLDER / "H07.registration.json").read_text(encoding="utf-8"))
    assert "mde" not in " ".join(raw)
    d = derive(load("H07"))
    assert d["variant_count"] == 6
    assert d["mde_effective"] is not None
    assert d["mde_effective"] > d["mde_raw"]
    assert d["underpowered_by_design"] is False


def test_an_underpowered_registration_is_refused() -> None:
    reg = load("H08").model_copy(
        update={"expected_event_count": 120, "effective_event_count_estimate": 100}
    )
    problems = validate(reg)
    assert any("underpowered by design" in p for p in problems)


def test_effective_n_above_raw_n_and_directly_observed_mechanisms_are_refused() -> None:
    base = load("H09")
    assert any(
        "above the raw" in p
        for p in validate(base.model_copy(update={"effective_event_count_estimate": 10**6}))
    )
    assert any(
        "cannot directly observe" in p
        for p in validate(
            base.model_copy(update={"mechanism_status": MechanismStatus.DIRECTLY_OBSERVED})
        )
    )


def test_missing_text_fields_are_refused() -> None:
    raw = json.loads((FOLDER / "H10.registration.json").read_text(encoding="utf-8"))
    raw["falsification_condition"] = ""
    with pytest.raises(ValidationError):
        HypothesisRegistration.model_validate(raw)
    raw = json.loads((FOLDER / "H10.registration.json").read_text(encoding="utf-8"))
    raw["unknown_field"] = 1
    with pytest.raises(ValidationError):
        HypothesisRegistration.model_validate(raw)


def test_the_markdown_states_what_is_observed_versus_hypothesized() -> None:
    for hid in IDS:
        text = (FOLDER / f"{hid}.md").read_text(encoding="utf-8")
        assert "HYPOTHESIZED" in text
        assert "Đã quan sát vs được giả thuyết" in text
        assert "Điều làm giả thuyết sai" in text
        assert "**Lưới.**" in text
