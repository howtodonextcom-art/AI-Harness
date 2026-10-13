"""Model artifacts with the metadata required by the brief (section 38).

A folder per model version holds ``metadata.json`` and ``model.joblib``. The metadata records the
model name, version, training period, feature version, hyperparameters, evaluation metrics,
training timestamp, git commit, and the SHA-256 of the model file. joblib is pickle-based: only
load artifacts this project wrote, and ``load_model`` refuses a file whose hash does not match.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import joblib
from pydantic import BaseModel, ConfigDict


class ModelArtifact(BaseModel):
    """Metadata of one trained model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    version: str
    training_period: tuple[str, str]
    feature_version: str
    hyperparameters: dict[str, Any]
    metrics: dict[str, Any]
    trained_at: str
    git_commit: str


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_artifact(root: Path | str, artifact: ModelArtifact, model: object) -> Path:
    """Write ``root/<name>/<version>/{model.joblib, metadata.json}`` and return the folder."""
    folder = Path(root) / artifact.name / artifact.version
    folder.mkdir(parents=True, exist_ok=True)
    model_path = folder / "model.joblib"
    joblib.dump(model, model_path)
    meta = {**artifact.model_dump(mode="json"), "model_sha256": _sha256(model_path)}
    (folder / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return folder


def load_artifact_metadata(folder: Path | str, *, verify_model: bool = False) -> dict[str, Any]:
    """Read the metadata; with ``verify_model`` also check the model file against its hash."""
    path = Path(folder)
    meta: dict[str, Any] = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    if verify_model and _sha256(path / "model.joblib") != meta["model_sha256"]:
        msg = f"model file in {path} does not match its recorded hash"
        raise ValueError(msg)
    return meta


def load_model(folder: Path | str) -> object:
    """Load the model after verifying its hash (trusted local files only)."""
    load_artifact_metadata(folder, verify_model=True)
    return joblib.load(Path(folder) / "model.joblib")
