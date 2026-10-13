"""The official ML V0 run on Development + Validation (never Test-H or Holdout).

    uv run --group ml python -m xau_edge_v2.ml.run_v0 [--data-root PATH] [--out FILE]

It re-executes the frozen spec (``ml_v0_spec.json``) on bars whose labels complete before
2022-01-01, walk-forward by calendar year, and writes one JSON record: per-stage metrics,
confidence intervals at 95% and at the K-adjusted 97.5%, the pre-registered criteria evaluation,
the exported default-model candidate and the data/spec/code identities. Hyper-parameters are fixed
a priori; nothing is selected on these results (Validation is Class D: burned for descriptive use).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from xau_edge_v2.config import DEFAULT_DATA_ROOT
from xau_edge_v2.ml import features as F
from xau_edge_v2.ml import metrics as M
from xau_edge_v2.ml.data import dataset_hash, load_h1
from xau_edge_v2.ml.guard import DEV_UNTIL, FAMILY, ML_DIR, spec_hash
from xau_edge_v2.ml.models import BASELINES, CANDIDATES, HarRidge, atr_percentile
from xau_edge_v2.ml.walkforward import EMBARGO, WalkForward, walk_forward, years_of

DEV_YEARS = list(range(2012, 2019))
VAL_YEARS = [2019, 2020, 2021]
K = 2
ALPHA = 0.05
LEVELS = (0.95,)  # two-sided, for reference
K_ADJUSTED_ONE_SIDED = (1 - ALPHA / K,)  # 97.5% ONE-sided lower bound (alpha/K per comparison)
K_KEY = f"lower{K_ADJUSTED_ONE_SIDED[0] * 100:g}_one_sided"
MIN_SKILL_VS_ATR14 = 0.05
COVERAGE_BAND = (0.75, 0.85)
MIN_SHARE_OF_YEARS_POSITIVE = 0.75


def git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=ML_DIR
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def stage_metrics(
    wf: WalkForward,
    y: np.ndarray,
    ok: np.ndarray,
    years: np.ndarray,
    months: np.ndarray,
    stage_years: list[int],
) -> dict[str, Any]:
    mask = ok & np.isin(years, stage_years) & np.isfinite(wf.preds["lightgbm_regressor"])
    names = list(wf.preds)
    mse = {k: M.mse(wf.preds[k], y, mask) for k in names}
    base = wf.preds["atr14_one_feature"]
    per_year: dict[str, dict[str, float]] = {}
    for yr in stage_years:
        m = mask & (years == yr)
        if m.any():
            e_atr = M.mse(base, y, m)
            per_year[str(yr)] = {
                "n": int(m.sum()),
                "mse_atr14": e_atr,
                "skill_har_ridge": M.skill(M.mse(wf.preds["har_ridge"], y, m), e_atr),
                "skill_lightgbm": M.skill(M.mse(wf.preds["lightgbm_regressor"], y, m), e_atr),
            }
    out: dict[str, Any] = {
        "n": int(mask.sum()),
        "mse": mse,
        "r2_vs_mean_expanding": {k: M.skill(v, mse["mean_expanding"]) for k, v in mse.items()},
        "skill_vs_atr14": {k: M.skill(v, mse["atr14_one_feature"]) for k, v in mse.items()},
        "qlike": {k: M.qlike(wf.preds[k], y, mask) for k in names},
        "coverage_80": {k: M.coverage(wf.lower[k], wf.upper[k], y, mask) for k in wf.lower},
        "per_year": per_year,
        "ci_har_ridge_vs_atr14": M.block_ci(
            wf.preds["har_ridge"], base, y, mask, months, LEVELS, K_ADJUSTED_ONE_SIDED
        ),
        "ci_lightgbm_vs_atr14": M.block_ci(
            wf.preds["lightgbm_regressor"], base, y, mask, months, LEVELS, K_ADJUSTED_ONE_SIDED
        ),
        "ci_lightgbm_vs_har_ridge": M.block_ci(
            wf.preds["lightgbm_regressor"],
            wf.preds["har_ridge"],
            y,
            mask,
            months,
            LEVELS,
            K_ADJUSTED_ONE_SIDED,
        ),
    }
    return out


def criteria(stage: dict[str, Any]) -> dict[str, Any]:
    """The pre-registered offline criteria (spec ``promotion_criteria``), per stage. Parity is separate."""
    skill = stage["skill_vs_atr14"]["har_ridge"]
    ci95 = stage["ci_har_ridge_vs_atr14"]["ci95"]
    lower_adj = stage["ci_har_ridge_vs_atr14"][K_KEY]
    cover = stage["coverage_80"]["har_ridge"]
    years = list(stage["per_year"].values())
    positive = sum(1 for y in years if y["skill_har_ridge"] > 0) / max(len(years), 1)
    lgbm_vs_ridge = stage["ci_lightgbm_vs_har_ridge"]["ci95"]
    low, high = COVERAGE_BAND
    return {
        "skill_vs_atr14": skill,
        "skill_at_least_5pct": skill >= MIN_SKILL_VS_ATR14,
        "ci95_lower_above_0": ci95[0] > 0,
        "k_adjusted_one_sided_lower_above_0": lower_adj > 0,
        "coverage_80": cover,
        "coverage_within_75_85": bool(low <= cover <= high),
        "share_of_years_positive": positive,
        "years_positive_at_least_75pct": positive >= MIN_SHARE_OF_YEARS_POSITIVE,
        "lightgbm_beats_ridge_95ci": lgbm_vs_ridge[0] > 0,
    }


def run(root: Path) -> dict[str, Any]:
    bars = load_h1(root, DEV_UNTIL)
    x = F.build_features(bars)
    y = F.build_label(bars)
    ok = F.valid_rows(x, y)
    aux = atr_percentile(x)
    ok &= np.isfinite(aux)
    years = years_of(bars.open_s)
    months = M.month_keys(bars.open_s)
    wf = walk_forward(x, y, aux, ok, years, DEV_YEARS + VAL_YEARS)
    dev = stage_metrics(wf, y, ok, years, months, DEV_YEARS)
    val = stage_metrics(wf, y, ok, years, months, VAL_YEARS)
    # the candidate that would be evaluated on Test-H: fit on every label-complete row before 2022
    fit_rows = np.flatnonzero(ok)
    candidate = HarRidge().fit(x[fit_rows], y[fit_rows])
    artifact = {
        "model_id": "har_ridge",
        "version": "0.1.0",
        "spec_hash": spec_hash(),
        "feature_names": list(F.FEATURE_NAMES),
        "feature_schema_hash": F.feature_schema_hash(),
        "label_version": F.LABEL_VERSION,
        "trained_rows": int(fit_rows.size),
        "trained_through": datetime.fromtimestamp(
            float(bars.open_s[fit_rows[-1]]), UTC
        ).isoformat(),
        **candidate.export(),
    }
    artifact_text = json.dumps(artifact, sort_keys=True)
    result: dict[str, Any] = {
        "run": "ml-v0-rng24 development + validation (Test-H and Holdout NOT touched)",
        "generated_at": datetime.now(UTC).isoformat(),
        "identities": {
            "spec_hash": spec_hash(),
            "spec_version": json.loads((ML_DIR / "ml_v0_spec.json").read_text(encoding="utf-8"))[
                "spec_version"
            ],
            "feature_schema_hash": F.feature_schema_hash(),
            "label_version": F.LABEL_VERSION,
            "dataset_hash": dataset_hash(bars),
            "git_sha": git_sha(),
            "bars": int(bars.size),
            "first_bar": datetime.fromtimestamp(float(bars.open_s[0]), UTC).isoformat(),
            "last_bar": datetime.fromtimestamp(float(bars.open_s[-1]), UTC).isoformat(),
            "usable_rows": int(ok.sum()),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
            "lightgbm": _version("lightgbm"),
            "artifact_sha256": hashlib.sha256(artifact_text.encode()).hexdigest(),
        },
        "k_accounting": {
            "family": FAMILY,
            "k": K,
            "alpha": ALPHA,
            "adjusted_level": K_ADJUSTED_ONE_SIDED[0],
            "adjusted_kind": "one-sided lower bound, Bonferroni alpha/K",
            "note": "Validation is Class D (burned); K is consumed only by the Test-H confirmatory run.",
        },
        "embargo_bars": EMBARGO,
        "folds": wf.folds,
        "development_diagnostic_2012_2018": {"metrics": dev, "criteria": criteria(dev)},
        "validation_2019_2021": {"metrics": val, "criteria": criteria(val)},
        "models": {"baselines": list(BASELINES), "candidates": list(CANDIDATES)},
    }
    result["artifact"] = artifact
    return result


def _version(module: str) -> str:
    try:
        mod = __import__(module)
        return str(getattr(mod, "__version__", "unknown"))
    except ImportError:
        return "not installed"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--out", type=Path, default=ML_DIR / "runs" / "v0_dev_validation_run.json")
    args = parser.parse_args()
    result = run(args.data_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    for stage in ("development_diagnostic_2012_2018", "validation_2019_2021"):
        print(stage, json.dumps(result[stage]["criteria"], indent=1))


if __name__ == "__main__":
    main()
