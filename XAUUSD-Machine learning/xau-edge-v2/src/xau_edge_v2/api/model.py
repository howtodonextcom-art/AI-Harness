"""ML V0 status for the page: what the registry and the official run say. Never a forecast.

The model has NO authority and, below SHADOW, its forecast is not shown anywhere (spec ``display``).
This module only reads the tracked registry, the K ledger and the last run record.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request

from xau_edge_v2.api.context import AppContext
from xau_edge_v2.domain.contract import (
    ModelCriterion,
    ModelDetail,
    ModelInfo,
    ModelStage,
    ModelStatus,
)
from xau_edge_v2.ml import guard, registry

router = APIRouter(prefix="/api/v2", tags=["model"])
RUN = guard.ML_DIR / "runs" / "v0_dev_validation_run.json"
NO_FORECAST = (
    "Dự báo biên độ KHÔNG được hiển thị: mô hình không ở mức SHADOW trở lên và không có thẩm quyền."
)
REJECTED = "V0 bị LOẠI tại Kiểm định theo tiêu chí đăng ký trước (quyết định chủ dự án 2026-10-13); Test-H không được mở."


def _read(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _stage(name: str, block: dict[str, Any]) -> ModelStage:
    m, c = block["metrics"], block["criteria"]
    adj = m["ci_har_ridge_vs_atr14"]["lower97.5_one_sided"]
    pct = f"{c['share_of_years_positive'] * 100:.0f}%"
    criteria = (
        ModelCriterion(
            id="skill",
            label="Cải thiện MSE so với ATR14 ≥ 5%",
            value=f"{c['skill_vs_atr14'] * 100:.1f}%",
            passed=c["skill_at_least_5pct"],
        ),
        ModelCriterion(
            id="ci95",
            label="Cận dưới CI 95% > 0",
            value=f"{m['ci_har_ridge_vs_atr14']['ci95'][0]:.4f}",
            passed=c["ci95_lower_above_0"],
        ),
        ModelCriterion(
            id="ci_adjusted",
            label="Cận dưới MỘT PHÍA 97,5% (Bonferroni α/K, K=2) > 0",
            value=f"{adj:.4f}",
            passed=c["k_adjusted_one_sided_lower_above_0"],
        ),
        ModelCriterion(
            id="coverage",
            label="Độ phủ dải 80% trong 75–85%",
            value=f"{c['coverage_80'] * 100:.1f}%",
            passed=c["coverage_within_75_85"],
        ),
        ModelCriterion(
            id="years",
            label="Cải thiện dương ≥ 75% số năm",
            value=pct,
            passed=c["years_positive_at_least_75pct"],
        ),
    )
    return ModelStage(
        name=name,
        n=m["n"],
        skill_vs_atr14=c["skill_vs_atr14"],
        ci95=tuple(m["ci_har_ridge_vs_atr14"]["ci95"]),
        lower_adjusted=adj,
        coverage_80=c["coverage_80"],
        criteria=criteria,
    )


def model_detail(ml_dir: Path = guard.ML_DIR) -> ModelDetail:
    reg = registry.load(ml_dir / "registry.json")
    record = next((m for m in reg["models"] if m["model_id"] == "har_ridge"), None)
    run = _read(ml_dir / "runs" / "v0_dev_validation_run.json")
    if record is None or run is None:
        return ModelDetail(available=False, status=ModelStatus.NOT_DEPLOYED, display=NO_FORECAST)
    ledger = guard.load_ledger(ml_dir / "k_ledger.json")
    family = ledger["families"].get(guard.FAMILY, {})
    stages = (
        _stage("Phát triển 2012–2018 (chẩn đoán)", run["development_diagnostic_2012_2018"]),
        _stage("Kiểm định 2019–2021 (Class D)", run["validation_2019_2021"]),
    )
    ledger_path = ml_dir / "k_ledger.json"
    val = run["validation_2019_2021"]["criteria"]
    notes = [
        "Ridge/HAR là ứng viên mặc định; LightGBM chỉ là challenger và "
        + ("đã thắng" if val["lightgbm_beats_ridge_95ci"] else "chưa thắng")
        + " ridge (CI 95% của chênh lệch MSE chứa 0 thì không thăng).",
        "Kiểm định 2019–2021 đã bị đốt (Class D): số liệu mô tả, không phải bằng chứng. Chỉ Test-H (một lần) là bằng chứng.",
        "Test-H và Holdout khóa bằng mã: cần tệp duyệt của chủ dự án và một dòng sổ cái K; mỗi cửa sổ chỉ mở một lần.",
    ]
    failed = [c.label for c in stages[1].criteria if c.passed is False]
    if record["status"] == "RETIRED":
        notes.insert(0, REJECTED)
    if failed:
        notes.insert(0, "Tiêu chí đăng ký trước KHÔNG đạt ở kiểm định: " + "; ".join(failed) + ".")
    return ModelDetail(
        available=True,
        model_id=record["model_id"],
        version=record["version"],
        status=ModelStatus(record["status"]),
        role=record.get("role"),
        label_version=record["label_version"],
        spec_version=record["spec_version"],
        spec_hash=record["spec_hash"],
        k_family=guard.FAMILY,
        k=family.get("k"),
        candidates=tuple(family.get("candidates", ())),
        stages=stages,
        lightgbm_promoted=False,
        test_h="RUN" if guard.looks_at("TEST_H", path=ledger_path) else "LOCKED",
        holdout="RUN" if guard.looks_at("HOLDOUT", path=ledger_path) else "LOCKED",
        display=NO_FORECAST,
        notes=tuple(notes),
    )


def model_info(ctx: AppContext) -> ModelInfo:
    """The short model line carried by every state (cached; the files change rarely)."""
    import time  # noqa: PLC0415

    cached = ctx.cache.get("model_info")
    if isinstance(cached, tuple) and time.monotonic() - cached[0] < 30.0:
        info: ModelInfo = cached[1]
        return info
    detail = model_detail()
    info = ModelInfo(
        status=detail.status,
        task=detail.task if detail.available else None,
        version=detail.version,
        note=f"{detail.status.value}: V0 bị loại tại Kiểm định, không hiển thị dự báo, không thẩm quyền"
        if detail.available
        else "chưa triển khai",
    )
    ctx.cache["model_info"] = (time.monotonic(), info)
    return info


@router.get("/model", response_model=ModelDetail)
def model(_: Request) -> ModelDetail:
    return model_detail()
