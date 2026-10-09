"""Evidence classes and the rules that stop a weak class being shown as a strong one.

A class says HOW an observation was obtained. ``can_display`` is the single place that decides
whether a label such as VALIDATED or CONFIRMATORY PASS may be shown for a record; the UI and API
both call it, so a missing proof can never be rendered as a pass (roadmap section 29).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class EvidenceClass(StrEnum):
    """How an observation was obtained, weakest first."""

    DESCRIPTIVE = "DESCRIPTIVE"
    EXPLORATORY = "EXPLORATORY"
    SCREENING = "SCREENING"
    VALIDATION = "VALIDATION"
    CONFIRMATORY = "CONFIRMATORY"
    HOLDOUT = "HOLDOUT"
    PROSPECTIVE = "PROSPECTIVE"
    EXECUTION = "EXECUTION"


_RANK = {c: i for i, c in enumerate(EvidenceClass)}

# Classes that can never be shown as a validated result, whatever their numbers say.
NEVER_VALIDATING = frozenset({EvidenceClass.DESCRIPTIVE, EvidenceClass.EXPLORATORY})


class Label(StrEnum):
    """Labels the UI may ask permission to show."""

    VALIDATED = "VALIDATED"
    CONFIRMATORY_PASS = "CONFIRMATORY_PASS"  # noqa: S105 - a label, not a secret
    ADEQUATELY_POWERED = "ADEQUATELY_POWERED"
    REPRODUCIBLE = "REPRODUCIBLE"
    PROSPECTIVE_VALID = "PROSPECTIVE_VALID"
    EXECUTION_VALIDATED = "EXECUTION_VALIDATED"


@dataclass(frozen=True)
class Proof:
    """What a record can show. A field that is None or False is a missing proof."""

    evidence_class: EvidenceClass
    ci_present: bool = False
    k_present: bool = False
    effective_n_present: bool = False
    dataset_hashes_present: bool = False
    freeze_record_present: bool = False
    chain_verified: bool = False
    broker_evidence_present: bool = False
    extra: dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class Decision:
    """Whether a label may be shown and, if not, every reason."""

    allowed: bool
    reasons: tuple[str, ...]


def _need(missing: list[str], ok: bool, why: str) -> None:
    if not ok:
        missing.append(why)


def can_display(label: Label, proof: Proof) -> Decision:
    """Decide a label from the proof; every missing item is a reason to refuse."""
    miss: list[str] = []
    cls = proof.evidence_class
    if label is Label.VALIDATED:
        _need(miss, cls not in NEVER_VALIDATING, f"class {cls} cannot be validated")
        _need(
            miss, _RANK[cls] >= _RANK[EvidenceClass.VALIDATION], f"class {cls} is below VALIDATION"
        )
        _need(miss, proof.k_present, "missing K / multiple-testing metadata")
        _need(miss, proof.ci_present, "missing confidence interval")
    elif label is Label.CONFIRMATORY_PASS:
        _need(
            miss,
            cls in {EvidenceClass.CONFIRMATORY, EvidenceClass.HOLDOUT},
            "class is not confirmatory",
        )
        _need(miss, proof.ci_present, "missing confidence interval")
        _need(miss, proof.k_present, "missing K / multiple-testing metadata")
        _need(miss, proof.freeze_record_present, "missing freeze record")
    elif label is Label.ADEQUATELY_POWERED:
        _need(miss, proof.effective_n_present, "missing effective N")
    elif label is Label.REPRODUCIBLE:
        _need(miss, proof.dataset_hashes_present, "missing dataset hashes")
    elif label is Label.PROSPECTIVE_VALID:
        _need(miss, cls is EvidenceClass.PROSPECTIVE, "class is not prospective")
        _need(miss, proof.chain_verified, "hash chain not verified")
    elif label is Label.EXECUTION_VALIDATED:
        _need(miss, cls is EvidenceClass.EXECUTION, "class is not execution")
        _need(miss, proof.broker_evidence_present, "missing broker evidence")
    return Decision(not miss, tuple(miss))


def may_promote(source: EvidenceClass, target: EvidenceClass) -> bool:
    """A class never rises by relabelling: only equal or lower targets, or the next honest step.

    DESCRIPTIVE cannot become anything higher. SCREENING cannot jump to CONFIRMATORY (it must pass
    VALIDATION first). CONFIRMATORY and HOLDOUT need their own frozen-test records, so they are
    reached only by running that test, never by promotion.
    """
    if source is target:
        return True
    if source in NEVER_VALIDATING:
        return _RANK[target] <= _RANK[source]
    if target in {
        EvidenceClass.CONFIRMATORY,
        EvidenceClass.HOLDOUT,
        EvidenceClass.PROSPECTIVE,
        EvidenceClass.EXECUTION,
    }:
        return False
    return _RANK[target] <= _RANK[source] + 1
