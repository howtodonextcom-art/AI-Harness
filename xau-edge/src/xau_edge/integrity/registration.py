"""Machine-readable hypothesis pre-registration (roadmap sections 10, 11 and 41).

The Markdown file is for people; this sidecar is what the API reads. Numbers that can be derived
(variant count, MDE, underpowered flag) are NEVER stored: they are recomputed from the stored
inputs, so a registration cannot claim a power it does not have.
"""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from xau_edge.integrity.power2 import power_report
from xau_edge.research.power import UNDERPOWERED_MDE


class MechanismStatus(StrEnum):
    """How much of the explanation is observed, not just proposed."""

    HYPOTHESIZED = "HYPOTHESIZED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    OBSERVED_PROXY = "OBSERVED_PROXY"
    DIRECTLY_OBSERVED = "DIRECTLY_OBSERVED"


class HypothesisRegistration(BaseModel):
    """Everything a V2 hypothesis must state before any outcome is computed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    hypothesis_id: str = Field(pattern=r"^H\d{2}$")
    title: str = Field(min_length=3)
    batch: str = Field(pattern=r"^[AB]$")
    economic_rationale: str = Field(min_length=20)
    mechanism_status: MechanismStatus
    observed_pattern: str = Field(min_length=10)
    """What price data can show (a statistical behaviour)."""
    hypothesized_explanation: str = Field(min_length=10)
    """Why it might happen. OHLC cannot prove intent: this stays a hypothesis."""
    event_state_machine: str = Field(min_length=20)
    availability_timing: str = Field(min_length=10)
    entry_timing: str = Field(min_length=10)
    label: str = Field(min_length=10)
    barrier_rules: str = Field(min_length=10)
    expected_event_count: int = Field(ge=0)
    effective_event_count_estimate: int | None = Field(default=None, ge=0)
    expected_sd: float = Field(gt=0)
    power_target: float = Field(gt=0, lt=1)
    k_at_registration: int = Field(ge=1)
    parameter_grid: dict[str, list[float | str]]
    variant_ids: list[str] = Field(min_length=1)
    falsification_condition: str = Field(min_length=10)
    failure_conditions: str = Field(min_length=10)
    placebo_plan: str = Field(min_length=10)
    attribution_plan: str = Field(min_length=10)
    cost_scenarios: str = Field(min_length=10)
    structural_break_report: str = Field(min_length=10)
    intrabar_policy: str = Field(min_length=10)
    event_counts_source: str = Field(min_length=3)
    dropped_variants: list[str] = Field(default_factory=list)
    """Variants considered and dropped by the underpowered-by-design rule (not counted in K)."""


def derive(reg: HypothesisRegistration) -> dict[str, Any]:
    """Numbers recomputed from the registration's own inputs."""
    grid_product = (
        math.prod(len(v) for v in reg.parameter_grid.values()) if reg.parameter_grid else 1
    )
    report = power_report(
        raw_n=max(1, reg.expected_event_count),
        effective_n=reg.effective_event_count_estimate,
        k=reg.k_at_registration,
        sd=reg.expected_sd,
        power=reg.power_target,
    )
    mde_for_rule = report.mde_effective if report.mde_effective is not None else report.mde_raw
    return {
        "variant_count": len(reg.variant_ids),
        "grid_product": grid_product,
        "mde_raw": report.mde_raw,
        "mde_effective": report.mde_effective,
        "required_effective_n_for_target": report.required_effective_n_for_target,
        "underpowered_by_design": mde_for_rule > UNDERPOWERED_MDE,
        "mde_used_for_rule": mde_for_rule,
    }


def validate(reg: HypothesisRegistration, *, k_cap: int = 24) -> list[str]:
    """Problems that make a registration unfit to run. Empty list means complete and coherent."""
    problems: list[str] = []
    d = derive(reg)
    if len(set(reg.variant_ids)) != len(reg.variant_ids):
        problems.append("duplicate variant ids")
    if len(reg.variant_ids) > 6:
        problems.append("more than 6 variants for one hypothesis")
    if d["variant_count"] > d["grid_product"] + len(reg.dropped_variants) * 0:
        problems.append("more variants than the parameter grid allows")
    if reg.k_at_registration > k_cap:
        problems.append("K exceeds the programme cap")
    if d["underpowered_by_design"]:
        problems.append(
            f"underpowered by design: MDE {d['mde_used_for_rule']:.3f}R exceeds {UNDERPOWERED_MDE}R"
        )
    if (
        reg.effective_event_count_estimate is not None
        and reg.effective_event_count_estimate > reg.expected_event_count
    ):
        problems.append("effective event count above the raw event count")
    if reg.mechanism_status is MechanismStatus.DIRECTLY_OBSERVED:
        problems.append("OHLC data cannot directly observe a market mechanism")
    return problems
