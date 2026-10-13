"""Record the owner's decision of 2026-10-13: ML V0 is REJECTED at Validation (Test-H not opened).

Retires both registry records (RETIRED, authority NONE), closes the K family in the ledger (no
confirmatory look was ever taken) and writes the policy clarification event. Idempotent.
"""

from __future__ import annotations

from xau_edge_v2.ml import guard, registry

REASON = (
    "V0 rejected at Validation: pre-registered criterion 'improvement positive in >= 75% of years' "
    "not met (2 of 3 years). Criteria kept unchanged; Test-H NOT opened (owner decision 2026-10-13)."
)
APPROVAL = "project owner message 2026-10-13: 'Mo Test-H? KHONG. Giu nguyen preregistered criterion va reject V0 tai Validation.'"

data = registry.load()
for model in data["models"]:
    if model["status"] == "RESEARCH":
        registry.promote(
            model["model_id"], model["version"], "RETIRED",
            {"owner_approval": APPROVAL, "reason": REASON, "confirmatory_run": None},
        )  # fmt: skip
ledger = guard.load_ledger()
family = ledger["families"].get(guard.FAMILY, {})
if family.get("status") != "CLOSED":
    guard.append_event(
        "POLICY_CLARIFICATION",
        {
            "family": guard.FAMILY,
            "text": (
                "K=2 with family alpha 0.05 (Bonferroni): per-comparison alpha 0.025. For the claim "
                "'improvement > 0' the criterion is a 97.5% ONE-sided lower bound (the 2.5th bootstrap "
                "percentile), not a two-sided 97.5% interval. Spec 1.1.0's wording 'two-sided 97.5%' is "
                "superseded for future families; no result depended on it."
            ),
            "decided_by": "project owner 2026-10-13",
        },
    )
    guard.close_family(guard.FAMILY, REASON)
print(
    "V0 rejected; family closed; registry:",
    [(m["model_id"], m["status"]) for m in registry.load()["models"]],
)
