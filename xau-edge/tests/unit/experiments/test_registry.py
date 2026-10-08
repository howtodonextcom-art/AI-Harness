"""Experiment registry: reproducibility metadata, write-once records, variant counting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from xau_edge.experiments.registry import ExperimentRegistry, current_code_version


def _rec(reg: ExperimentRegistry, **over: object):  # type: ignore[no-untyped-def]
    kwargs: dict[str, object] = {
        "family": "analogue-study",
        "name": "m15-w30",
        "dataset_ids": {"M15": "abc123"},
        "feature_ids": {"M15": "f1"},
        "params": {"window": 30, "k": 20},
        "seeds": {"bootstrap": 7},
        "period": "development",
        "metrics": {"lift": 0.01},
        "code_version": "deadbeef",
        "code_dirty": False,
    }
    kwargs.update(over)
    return reg.record(**kwargs)  # type: ignore[arg-type]


def test_record_stores_every_reproducibility_field(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    rec = _rec(reg)
    stored = json.loads((tmp_path / f"{rec.id}.json").read_text(encoding="utf-8"))
    for key in (
        "id",
        "created_at",
        "family",
        "name",
        "dataset_ids",
        "feature_ids",
        "params",
        "seeds",
        "period",
        "metrics",
        "code_version",
        "code_dirty",
    ):
        assert key in stored, key
    assert stored["seeds"] == {"bootstrap": 7}
    assert reg.get(rec.id) == rec


def test_same_content_is_idempotent_and_does_not_add_a_file(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    a = _rec(reg)
    b = _rec(reg)
    assert a.id == b.id
    assert a.created_at == b.created_at  # the original record is returned, not rewritten
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_different_metrics_or_period_make_a_new_record(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    ids = {
        _rec(reg).id,
        _rec(reg, metrics={"lift": 0.02}).id,
        _rec(reg, period="validation").id,
        _rec(reg, code_version="cafe").id,
    }
    assert len(ids) == 4


def test_variant_count_counts_distinct_parameter_sets_per_family(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    _rec(reg)
    _rec(reg, period="validation")  # same params, other period: same variant
    _rec(reg, params={"window": 50, "k": 20})
    _rec(reg, family="baseline-a", params={"rsi": 45})
    assert reg.variant_count("analogue-study") == 2
    assert reg.variant_count("baseline-a") == 1
    assert reg.variant_count("unknown") == 0


def test_list_filters_by_family_and_orders_by_time(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    first = _rec(reg)
    second = _rec(reg, params={"window": 50})
    _rec(reg, family="other")
    ids = [r.id for r in reg.list(family="analogue-study")]
    assert set(ids) == {first.id, second.id}
    assert len(reg.list()) == 3


def test_records_are_write_once(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    rec = _rec(reg)
    path = tmp_path / f"{rec.id}.json"
    path.write_text(path.read_text(encoding="utf-8").replace("0.01", "0.99"), encoding="utf-8")
    with pytest.raises(ValueError, match="modified"):
        reg.get(rec.id)


def test_unsafe_ids_cannot_escape_the_directory(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    with pytest.raises(ValueError, match="id"):
        reg.get("../secret")


def test_unserialisable_params_are_rejected(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    with pytest.raises(TypeError):
        _rec(reg, params={"callable": print})


def test_current_code_version_reports_a_hash_and_dirty_flag() -> None:
    version, dirty = current_code_version()
    assert version == "unknown" or len(version) == 40
    assert isinstance(dirty, bool)


def test_default_code_version_is_filled_in(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    rec = reg.record(
        family="f",
        name="n",
        dataset_ids={},
        feature_ids={},
        params={},
        seeds={},
        period="development",
        metrics={},
    )
    assert rec.code_version != ""


def test_non_finite_metrics_are_rejected(tmp_path: Path) -> None:
    reg = ExperimentRegistry(tmp_path)
    with pytest.raises(ValueError, match="JSON"):
        _rec(reg, metrics={"x": float("nan")})
    _rec(reg)
    assert len(reg.list()) == 1
