"""One-off: amend the frozen ML V0 spec 1.0.0 -> 1.1.0 (k_accounting only), per the amendment rule.

The rule: a frozen spec is never edited in place; a change is a NEW spec_version with an
owner-approved reason, and the guard hash is replaced in the same commit. The 1.0.0 file and its
hash are kept next to it (``ml_v0_spec_v1.0.0.json`` / ``.sha256``). Run once; refuses to run twice.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ML = Path(__file__).resolve().parents[1] / "docs" / "ml"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from freeze_hash import canonical_hash  # noqa: E402

spec_path = ML / "ml_v0_spec.json"
archive = ML / "ml_v0_spec_v1.0.0.json"
spec = json.loads(spec_path.read_text(encoding="utf-8"))
if spec["spec_version"] != "1.0.0" or archive.exists():
    raise SystemExit("already amended (or not 1.0.0): nothing to do")

shutil.copyfile(spec_path, archive)
shutil.copyfile(spec_path.with_suffix(".sha256"), ML / "ml_v0_spec_v1.0.0.sha256")

spec["spec_version"] = "1.1.0"
spec["amendment"] = {
    "from_version": "1.0.0",
    "amended_on": "2026-10-13",
    "approved_by": "project owner (message of 2026-10-13: ADR-V2-007 approved, K locked per family, G6 ML V0 next)",
    "changed_keys": ["spec_version", "amendment", "k_accounting"],
    "reason": (
        "ADR-V2-007 locked the K policy: the selection candidates and the K accounting must be written "
        "into the spec before any confirmatory result is seen. Task, label, features, models, splits, "
        "metrics, interval and promotion criteria are unchanged (a test proves it)."
    ),
}
spec["k_accounting"] = {
    "consumes_k": True,
    "family": "K_V2_VOL_V0",
    "k": 2,
    "candidates": ["har_ridge", "lightgbm_regressor"],
    "candidate_note": "Ridge/HAR is ONE candidate (ridge regression on the HAR-style volatility features); LightGBM is the other. The three baselines are reference points, not candidates, and consume no K.",
    "selection_stage": "confirmatory evaluation on Test-H (one run); Validation is Class D and consumes no K",
    "alpha_family": 0.05,
    "alpha_per_comparison": 0.025,
    "confirmatory_ci_level": 0.975,
    "ci_note": "On Test-H each candidate-versus-baseline comparison is judged at the K-adjusted two-sided 97.5% level (Bonferroni, alpha/K). Validation reports both 95% and 97.5%.",
    "adding_a_candidate": "forbidden under this family: a new candidate, hyper-parameter variant chosen by results, task or timeframe needs a new ADR and family BEFORE any confirmatory result is seen",
    "reason": "ADR-V2-007 (locked 2026-10-13): K per family, 44 not inherited",
}
spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
digest = canonical_hash()
spec_path.with_suffix(".sha256").write_text(digest + "\n", encoding="utf-8")
print("amended to 1.1.0; hash", digest)
