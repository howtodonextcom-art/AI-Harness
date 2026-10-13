"""Write the RESEARCH registry records (and the default-model artifact) from the official V0 run.

    uv run python scripts/ml_register.py [run.json]

Reads ``docs/ml/runs/v0_dev_validation_run.json``; writes ``docs/ml/artifacts/har_ridge_0.1.0.json``
and ``docs/ml/registry.json``. Statuses start at RESEARCH with authority NONE; promotion is a
separate, guarded step (``xau_edge_v2.ml.registry.promote``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from xau_edge_v2.ml import registry
from xau_edge_v2.ml.guard import ML_DIR

run_path = (
    Path(sys.argv[1]) if len(sys.argv) > 1 else ML_DIR / "runs" / "v0_dev_validation_run.json"
)
run = json.loads(run_path.read_text(encoding="utf-8"))
ident = run["identities"]
val = run["validation_2019_2021"]
dev = run["development_diagnostic_2012_2018"]

artifact = run["artifact"]
artifact_path = ML_DIR / "artifacts" / "har_ridge_0.1.0.json"
artifact_path.parent.mkdir(parents=True, exist_ok=True)
artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")

common = {
    "version": "0.1.0",
    "feature_schema_hash": ident["feature_schema_hash"],
    "label_version": ident["label_version"],
    "train_window": f"{ident['first_bar']} .. {artifact['trained_through']} (walk-forward, expanding)",
    "validation_window": "2019-01-01 .. 2021-12-31",
    "calibration_window": "the most recent 25% of each fold's training rows (embargo 25 bars)",
    "git_sha": ident["git_sha"],
    "dataset_hash": ident["dataset_hash"],
    "spec_hash": ident["spec_hash"],
    "spec_version": ident["spec_version"],
    "status": "RESEARCH",
    "authority": "NONE",
    "run": str(run_path.relative_to(ML_DIR.parent.parent)).replace("\\", "/"),
}
for model_id, algorithm in (
    ("har_ridge", "StandardScaler + Ridge(alpha=10), intercept unpenalised (NumPy)"),
    ("lightgbm_regressor", "LightGBM regressor (200 trees, 8 leaves, lr 0.05, seed 7)"),
):
    registry.register_research(
        {
            **common,
            "model_id": model_id,
            "algorithm": algorithm,
            "metrics": {
                "validation_2019_2021": {
                    "mse": val["metrics"]["mse"][model_id],
                    "skill_vs_atr14": val["metrics"]["skill_vs_atr14"][model_id],
                    "qlike": val["metrics"]["qlike"][model_id],
                },
                "development_2012_2018": {
                    "mse": dev["metrics"]["mse"][model_id],
                    "skill_vs_atr14": dev["metrics"]["skill_vs_atr14"][model_id],
                },
            },
            "calibration_metrics": {
                "coverage_80_validation": val["metrics"]["coverage_80"][model_id],
                "coverage_80_development": dev["metrics"]["coverage_80"][model_id],
            },
            "artifact": (
                {
                    "path": "docs/ml/artifacts/har_ridge_0.1.0.json",
                    "sha256": ident["artifact_sha256"],
                }
                if model_id == "har_ridge"
                else None
            ),
            "role": "default" if model_id == "har_ridge" else "challenger",
        }
    )
print("registered 2 RESEARCH records; artifact", artifact_path.name)
