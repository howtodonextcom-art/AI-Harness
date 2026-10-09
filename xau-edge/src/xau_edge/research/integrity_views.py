"""Read-only views over the research-integrity artefacts (registration, Stage 1, lineage,
prospective ledger, rollout, gate calibration). Every view starts from a source artefact, re-checks
it with the verified parsers in ``xau_edge.integrity`` and fails closed ("unknown") when a source is
missing, malformed or inconsistent. Nothing here runs an experiment or writes a file.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import ValidationError

from xau_edge.funded.rollout import RolloutConfig
from xau_edge.integrity import lineage as lineage_mod
from xau_edge.integrity import prospective as prospective_mod
from xau_edge.integrity.canonical import canonical_hash
from xau_edge.integrity.evidence import EvidenceClass, Label, Proof, can_display
from xau_edge.integrity.identity import IdentityError, RunManifest
from xau_edge.integrity.registration import HypothesisRegistration, derive, validate
from xau_edge.research.paths import ResearchRoot, SourceUnavailableError, unknown

STAGE1_DIR = "experiments/edge_program_v2_stage1"
V2_HYP_DIR = "docs/research/edge-program-v2/hypotheses"
LINEAGE = "docs/research/edge-program-v2/lineage.json"
PROSPECTIVE = "data/forward/prospective.jsonl"
ROLLOUT = "configs/execution/rollout.yaml"
GATE_CAL = "docs/research/edge-program-v2/gate-calibration.json"
V2_LEDGER = "docs/research/edge-program-v2/ledger.md"
LEGACY_FORWARD_TRADES = 100
_STAGE1_KEYS = ("variant", "hypothesis", "window", "evidence_class", "k", "experiment_id", "study")


def _labels(proof: Proof) -> dict[str, dict[str, Any]]:
    """What the UI may say about a record, with the reasons for every refusal."""
    out: dict[str, dict[str, Any]] = {}
    for label in (Label.VALIDATED, Label.ADEQUATELY_POWERED, Label.REPRODUCIBLE):
        decision = can_display(label, proof)
        out[label.value] = {"allowed": decision.allowed, "reasons": list(decision.reasons)}
    return out


def registration(files: ResearchRoot, hypothesis_id: str) -> dict[str, Any]:
    """Structured pre-registration of one V2 hypothesis, with numbers recomputed here."""
    rel = f"{V2_HYP_DIR}/{hypothesis_id}.registration.json"
    try:
        raw = files.read_json(rel)
        reg = HypothesisRegistration.model_validate(raw)
    except (SourceUnavailableError, ValidationError, ValueError) as exc:
        return unknown(rel, f"không có đăng ký có cấu trúc hợp lệ: {str(exc)[:120]}")
    derived = derive(reg)
    return {
        "status": "ok",
        "source": rel,
        "evidence_class": "DESCRIPTIVE",
        "expected_event_count": reg.expected_event_count,
        "effective_event_count_estimate": reg.effective_event_count_estimate,
        "expected_sd": reg.expected_sd,
        "k_at_registration": reg.k_at_registration,
        "power_target": reg.power_target,
        "mde_raw": derived["mde_raw"],
        "mde_effective": derived["mde_effective"],
        "underpowered_by_design": derived["underpowered_by_design"],
        "required_effective_n_for_target": derived["required_effective_n_for_target"],
        "parameter_grid": reg.parameter_grid,
        "variant_ids": reg.variant_ids,
        "variant_count": derived["variant_count"],
        "dropped_variants": reg.dropped_variants,
        "economic_rationale": reg.economic_rationale,
        "mechanism_status": reg.mechanism_status.value,
        "observed_pattern": reg.observed_pattern,
        "hypothesized_explanation": reg.hypothesized_explanation,
        "falsification_condition": reg.falsification_condition,
        "problems": validate(reg),
    }


def _manifest_ids(files: ResearchRoot) -> dict[str, tuple[str, str]]:
    """Verified Stage 1 manifests: experiment_id -> (result hash, evidence class).

    The file name must equal the manifest's content id; the result hash is what the runner
    recorded for the result file, so a result edited afterwards no longer matches it.
    """
    ids: dict[str, tuple[str, str]] = {}
    try:
        names = files.list(f"{STAGE1_DIR}/manifests", "*.json")
    except SourceUnavailableError:
        return ids
    for rel in names:
        try:
            manifest = RunManifest.model_validate(files.read_json(rel))
        except (SourceUnavailableError, ValidationError, ValueError):
            continue
        if rel.rsplit("/", 1)[-1] == f"{manifest.manifest_id}.json":
            ids[manifest.identity.experiment_id] = (
                manifest.output_hashes.get("result", ""),
                manifest.identity.evidence_class.value,
            )
    return ids


def stage1(files: ResearchRoot, clock: datetime) -> dict[str, Any]:
    """Batch A / Stage 1 results (SCREENING): table with provenance and label permissions."""
    try:
        names = [
            n
            for n in files.list(STAGE1_DIR, "*_dev2.json")
            if not n.rsplit("/", 1)[-1].startswith("summary")
        ]
    except SourceUnavailableError as exc:
        return unknown(STAGE1_DIR, str(exc))
    if not names:
        return {"status": "empty", "source": STAGE1_DIR, "message": "chưa có kết quả Stage 1",
                "variants": [], "generated_at": clock.isoformat()}  # fmt: skip
    verified = _manifest_ids(files)
    rows: list[dict[str, Any]] = []
    problems: list[str] = []
    for rel in names:
        try:
            raw = files.read_json(rel)
        except SourceUnavailableError:
            problems.append(f"không đọc được {rel}")
            continue
        if not isinstance(raw, dict) or any(k not in raw for k in _STAGE1_KEYS):
            problems.append(f"{rel} không đúng cấu trúc")
            continue
        study = raw["study"]
        if study.get("status") == "TOO_FEW_EVENTS":
            rows.append({"variant": raw["variant"], "status": "TOO_FEW_EVENTS"})
            continue
        dep, power = study.get("dependence", {}), study.get("power", {})
        recorded = verified.get(raw["experiment_id"])
        intact = recorded is not None and canonical_hash(raw)[:16] == recorded[0]
        has_manifest = intact
        if recorded is not None and not intact:
            problems.append(f"{rel}: kết quả khác với hash đã ghi trong manifest (đã bị sửa)")
        # the class comes from the verified manifest, never from the editable result file
        cls = (
            EvidenceClass(recorded[1])
            if recorded is not None and intact
            else EvidenceClass.DESCRIPTIVE
        )
        proof = Proof(
            evidence_class=cls,
            ci_present=bool(study.get("ci95_net_base")),
            k_present=bool(raw.get("k")),
            effective_n_present=bool(dep.get("effective_n")),
            dataset_hashes_present=bool(raw.get("dataset_ids")) and has_manifest,
        )
        rows.append(
            {
                "variant": raw["variant"],
                "hypothesis": raw["hypothesis"],
                "window": raw["window"],
                "evidence_class": cls.value,
                "claimed_evidence_class": raw["evidence_class"],
                "k": raw["k"],
                "alpha_bonferroni": 0.05 / raw["k"],
                "result_intact": intact,
                "n_events": study.get("n_events"),
                "n_effective": dep.get("effective_n"),
                "unique_days": dep.get("unique_days"),
                "mean_gross_mid_r": study.get("mean_gross_mid_r"),
                "mean_net_base_r": study.get("mean_net_base_r"),
                "mean_net_pess_r": study.get("mean_net_pess_r"),
                "ci95_net_base": study.get("ci95_net_base"),
                "p_value_one_sided": study.get("p_value_one_sided"),
                "survivor": bool(raw["screening"]["stage1_survivor"]) and intact,
                "mde_effective": power.get("mde_effective"),
                "adequately_powered": power.get("adequately_powered"),
                "dependence_status": dep.get("sensitivity"),
                "intrabar_status": study.get("intrabar", {}).get("status"),
                "era_status": study.get("era", {}).get("status"),
                "attribution": study.get("attribution"),
                "placebo": study.get("placebo"),
                "by_year": study.get("by_year"),
                "dataset_ids": raw["dataset_ids"],
                "code_commit_sha": raw.get("code_commit_sha"),
                "experiment_id": raw["experiment_id"],
                "manifest_verified": has_manifest,
                "provenance": "REPRODUCIBLE" if has_manifest else "KHÔNG RÕ",
                "recorded_at": raw.get("recorded_at"),
                "labels": _labels(proof),
            }
        )
    return {
        "status": "unknown" if problems or not rows else "ok",
        "source": STAGE1_DIR,
        "generated_at": clock.isoformat(),
        "evidence_class": "SCREENING",
        "k": rows[0].get("k") if rows else None,
        "survivors": [r["variant"] for r in rows if r.get("survivor")],
        "variants": rows,
        "problems": problems,
        "note": "Stage 1 là sàng lọc: không tạo bằng chứng; chưa có Test-H hay holdout.",
    }


def lineage(files: ResearchRoot) -> dict[str, Any]:
    """The stored lineage graph, re-verified (ids re-derived, parents checked)."""
    try:
        raw = files.read_json(LINEAGE)
    except SourceUnavailableError as exc:
        return unknown(LINEAGE, str(exc))
    if not isinstance(raw, dict):
        return unknown(LINEAGE, "lineage không phải đối tượng JSON")
    try:
        nodes, mismatches = lineage_mod.from_json(raw)
    except (ValidationError, ValueError) as exc:
        return unknown(LINEAGE, f"lineage sai cấu trúc: {str(exc)[:120]}")
    report = lineage_mod.verify(nodes)
    ok = report.ok and not mismatches
    return {
        "status": "ok" if ok else "unknown",
        "source": LINEAGE,
        "stages": list(lineage_mod.STAGES),
        "empty_stages": list(report.empty_stages),
        "problems": [*report.problems, *mismatches],
        "nodes": [{"id": n.id, "parent_hash": n.parent_hash, **n.model_dump(mode="json")}
                  for n in nodes],
    }  # fmt: skip


def prospective(files: ResearchRoot, clock: datetime) -> dict[str, Any]:
    """Verification of the prospective ledger. "SEALED BEFORE OUTCOME" only when it verifies."""
    base = {"source": PROSPECTIVE, "generated_at": clock.isoformat(),
            "evidence_class": "PROSPECTIVE"}  # fmt: skip
    try:
        present = files.exists(PROSPECTIVE)
        path = files.resolve(PROSPECTIVE)
    except SourceUnavailableError:
        present = False
        path = None
    if not present or path is None:
        return {**base, "status": "empty", "label": "NO PROSPECTIVE EVIDENCE YET",
                "signals": 0, "outcomes": 0, "problems": []}  # fmt: skip
    result = prospective_mod.verify(path)
    if result.status == prospective_mod.UNKNOWN:
        return {**base, "status": "unknown", "label": "KHÔNG RÕ", "signals": 0, "outcomes": 0,
                "problems": list(result.problems)}  # fmt: skip
    if result.status == prospective_mod.INVALID:
        return {**base, "status": "invalid", "label": "PROVENANCE INVALID",
                "signals": result.signals, "outcomes": result.outcomes,
                "problems": list(result.problems[:20])}  # fmt: skip
    if result.signals == 0:
        return {**base, "status": "empty", "label": "NO PROSPECTIVE EVIDENCE YET",
                "signals": 0, "outcomes": result.outcomes, "problems": []}  # fmt: skip
    proof = Proof(EvidenceClass.PROSPECTIVE, chain_verified=True)
    return {
        **base,
        "status": "ok",
        "label": "SEALED BEFORE OUTCOME",
        "signals": result.signals,
        "outcomes": result.outcomes,
        "records": result.records,
        "head_hash_prefix": result.head_hash[:12],
        "labels": {"PROSPECTIVE_VALID": {
            "allowed": can_display(Label.PROSPECTIVE_VALID, proof).allowed, "reasons": []}},
        "problems": [],
    }  # fmt: skip


def rollout(files: ResearchRoot) -> dict[str, Any]:
    """Tier definitions from the committed config. The CURRENT tier lives in the funded state
    database, which the console never opens, so it is reported as unknown by design."""
    try:
        raw = files.read_text(ROLLOUT)
    except SourceUnavailableError as exc:
        return unknown(ROLLOUT, str(exc))
    import yaml  # noqa: PLC0415 - already a project dependency

    try:
        config = RolloutConfig.model_validate(yaml.safe_load(raw))
    except (ValidationError, yaml.YAMLError, ValueError) as exc:
        return unknown(ROLLOUT, f"rollout.yaml không hợp lệ: {str(exc)[:120]}")
    return {
        "status": "ok",
        "source": ROLLOUT,
        "current_tier": None,
        "current_tier_state": "KHÔNG RÕ",
        "current_tier_reason": (
            "tier hiện tại nằm trong cơ sở dữ liệu trạng thái funded, mà console không bao giờ mở"
        ),
        "tiers": [
            {
                "tier": t.tier,
                "name": t.name,
                "send_orders": t.send_orders,
                "lot_cap": t.lot_cap,
                "risk_pct": t.risk_pct,
                "requires_validated": t.requires_validated,
                "exit": t.exit.model_dump(),
                "progress": "KHÔNG RÕ",
            }
            for t in config.tiers
        ],
        "note": "funded vẫn bị chặn: cần ứng viên VALIDATED, luật đã xác minh, chủ dự án cho phép.",
    }


def gate_calibration(files: ResearchRoot) -> dict[str, Any]:
    """Planted-strategy calibration of the robustness gates and of the primary test's power."""
    try:
        raw = files.read_json(GATE_CAL)
    except SourceUnavailableError as exc:
        return unknown(GATE_CAL, str(exc))
    if not isinstance(raw, dict) or "gates" not in raw or "power" not in raw:
        return unknown(GATE_CAL, "gate-calibration.json sai cấu trúc")
    return {"status": "ok", "source": GATE_CAL, "evidence_class": "DESCRIPTIVE", **raw}


def ledger_fingerprint(files: ResearchRoot) -> str | None:
    """Hash of the V2 ledger text (lets a client detect that K changed)."""
    try:
        return canonical_hash(files.read_text(V2_LEDGER))[:16]
    except (SourceUnavailableError, IdentityError):
        return None
