"""Model registry and status lifecycle (no activation by swapping a file).

Statuses (``contract.ModelStatus``): NOT_DEPLOYED < RESEARCH < VALIDATED_OFFLINE < SHADOW <
PAPER_ELIGIBLE < PAPER_ACTIVE < RETIRED. A model advances one step at a time and only with the
evidence that step needs:

* RESEARCH -> VALIDATED_OFFLINE: a recorded Test-H run (``run_id`` present in the K ledger) in which
  every pre-registered criterion passed;
* VALIDATED_OFFLINE -> SHADOW: the owner's approval record;
* later steps: the owner's approval record; ML never gets authority in V0 (``authority`` stays NONE).

The registry is a small tracked JSON file; every record carries the contract of spec section 36:
model id, version, algorithm, feature schema hash, label version, windows, git sha, dataset hash,
metrics, calibration metrics and status.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from xau_edge_v2.ml.guard import ML_DIR, load_ledger

REGISTRY = ML_DIR / "registry.json"
ORDER = (
    "RESEARCH",
    "VALIDATED_OFFLINE",
    "SHADOW",
    "PAPER_ELIGIBLE",
    "PAPER_ACTIVE",
    "RETIRED",
)
REQUIRED = [
    "model_id",
    "version",
    "algorithm",
    "feature_schema_hash",
    "label_version",
    "train_window",
    "validation_window",
    "calibration_window",
    "git_sha",
    "dataset_hash",
    "metrics",
    "calibration_metrics",
    "status",
    "authority",
]


class PromotionError(RuntimeError):
    """A status change that the lifecycle does not allow."""


def load(path: Path = REGISTRY) -> dict[str, Any]:
    if not path.exists():
        return {"models": []}
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _save(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def register_research(record: dict[str, Any], *, path: Path = REGISTRY) -> None:
    """Add (or replace the RESEARCH record of) a model. A model past RESEARCH cannot be replaced."""
    missing = [k for k in REQUIRED if k not in record]
    if missing:
        msg = f"registry record lacks: {', '.join(missing)}"
        raise PromotionError(msg)
    if record["status"] != "RESEARCH" or record["authority"] != "NONE":
        msg = "a new record starts as RESEARCH with authority NONE"
        raise PromotionError(msg)
    data = load(path)
    for i, existing in enumerate(data["models"]):
        if existing["model_id"] == record["model_id"] and existing["version"] == record["version"]:
            if existing["status"] != "RESEARCH":
                msg = f"{record['model_id']} {record['version']} is {existing['status']}: it cannot be replaced"
                raise PromotionError(msg)
            data["models"][i] = record
            _save(data, path)
            return
    data["models"].append(record)
    _save(data, path)


def promote(
    model_id: str,
    version: str,
    to: str,
    evidence: dict[str, Any],
    *,
    path: Path = REGISTRY,
    ledger: Path | None = None,
    now: datetime | None = None,
) -> None:
    """Advance one step. Raises ``PromotionError`` unless the evidence for that step is present."""
    data = load(path)
    record = next(
        (m for m in data["models"] if m["model_id"] == model_id and m["version"] == version), None
    )
    if record is None:
        msg = f"unknown model {model_id} {version}"
        raise PromotionError(msg)
    if to not in ORDER or ORDER.index(to) != ORDER.index(record["status"]) + 1:
        if to == "RETIRED" and record["status"] != "RETIRED":
            pass  # retirement is allowed from any live status
        else:
            msg = f"{record['status']} -> {to} is not a single allowed step"
            raise PromotionError(msg)
    if to == "VALIDATED_OFFLINE":
        run_id = evidence.get("test_h_run_id")
        ledger_events = (load_ledger(ledger) if ledger else load_ledger())["events"]
        known = any(
            e["kind"] == "CONFIRMATORY_LOOK" and e["detail"].get("run_id") == run_id
            for e in ledger_events
        )
        if not run_id or not known:
            msg = "VALIDATED_OFFLINE needs a Test-H run recorded in the K ledger"
            raise PromotionError(msg)
        if not evidence.get("criteria_all_passed"):
            msg = "VALIDATED_OFFLINE needs every pre-registered criterion to pass on Test-H"
            raise PromotionError(msg)
    elif not evidence.get("owner_approval"):
        msg = f"{to} needs the owner's approval record"
        raise PromotionError(msg)
    record["status"] = to
    record.setdefault("history", []).append(
        {"to": to, "at": (now or datetime.now(UTC)).isoformat(), "evidence": evidence}
    )
    _save(data, path)
