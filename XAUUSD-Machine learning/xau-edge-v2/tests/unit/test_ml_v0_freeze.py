"""ML V0 is frozen (docs/ml/ML_V0_FREEZE.md). Editing the spec in place must fail this test."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs" / "ml" / "ml_v0_spec.json"
REQUIRED_FEATURE_FIELDS = {
    "name", "version", "unit", "source_timeframe", "lookback", "available_at",
    "missing_rule", "normalization", "live_availability", "rationale",
}  # fmt: skip


def _hash() -> str:
    spec = importlib.util.spec_from_file_location(
        "freeze_hash", ROOT / "scripts" / "freeze_hash.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return str(module.canonical_hash())


def _spec() -> dict[str, object]:
    return json.loads(SPEC.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_spec_is_unchanged_since_the_freeze() -> None:
    recorded = (SPEC.with_suffix(".sha256")).read_text(encoding="utf-8").strip()
    assert _hash() == recorded, "ml_v0_spec.json changed: a frozen spec needs a NEW spec_version"


def test_every_feature_has_the_full_contract() -> None:
    features = _spec()["features"]
    assert isinstance(features, list) and len(features) == 13
    for feature in features:
        assert set(feature) >= REQUIRED_FEATURE_FIELDS


def test_protected_windows_are_locked_and_authority_is_none() -> None:
    spec = _spec()
    splits = spec["splits"]
    assert isinstance(splits, dict)
    assert splits["test_h"]["state"] == "LOCKED" and splits["test_h"]["runs_allowed"] == 1
    assert splits["holdout"]["state"] == "LOCKED" and splits["holdout"]["runs_allowed"] == 1
    assert str(spec["authority"]).startswith("NONE")
    assert spec["role"] == "A"


def test_forbidden_list_and_k_accounting() -> None:
    spec = _spec()
    forbidden = " ".join(spec["forbidden"])  # type: ignore[arg-type]
    for needle in ("online learning", "directional prediction", "random train/test shuffling"):
        assert needle in forbidden
    k = spec["k_accounting"]
    assert k["consumes_k"] is True and k["family"] == "K_V2_VOL_V0" and k["k"] == 2  # type: ignore[index]
    assert k["candidates"] == ["har_ridge", "lightgbm_regressor"]  # type: ignore[index]
    assert k["alpha_per_comparison"] == 0.025 and k["confirmatory_ci_level"] == 0.975  # type: ignore[index]


def test_the_amendment_changed_only_k_accounting_and_the_archive_is_intact() -> None:
    """spec 1.1.0 vs 1.0.0: everything except the keys it declares is byte-identical in content."""
    archive = ROOT / "docs" / "ml" / "ml_v0_spec_v1.0.0.json"
    old = json.loads(archive.read_text(encoding="utf-8"))
    new = _spec()
    declared = set(new["amendment"]["changed_keys"])  # type: ignore[index]
    assert old["spec_version"] == "1.0.0" and new["spec_version"] == "1.1.0"
    assert declared == {"spec_version", "amendment", "k_accounting"}
    for key in set(old) | set(new):
        if key not in declared:
            assert old[key] == new[key], f"{key} changed outside the declared amendment"
    spec_mod = importlib.util.spec_from_file_location("fh", ROOT / "scripts" / "freeze_hash.py")
    assert spec_mod and spec_mod.loader
    module = importlib.util.module_from_spec(spec_mod)
    spec_mod.loader.exec_module(module)
    recorded = (
        (ROOT / "docs" / "ml" / "ml_v0_spec_v1.0.0.sha256").read_text(encoding="utf-8").strip()
    )
    assert str(module.canonical_hash(archive)) == recorded  # the 1.0.0 record was not touched
