"""Immutable experiment identity and run manifest (roadmap sections 7 and 8)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from xau_edge.integrity.canonical import canonical_hash, canonical_json
from xau_edge.integrity.evidence import EvidenceClass

_SHA = re.compile(r"^[0-9a-f]{40}$")
_HASH = re.compile(r"^[0-9a-f]{16,64}$")


class IdentityError(ValueError):
    """The identity is incomplete or inconsistent."""


class ExperimentIdentity(BaseModel):
    """Everything that makes two experiments the same experiment.

    ``created_at`` is deliberately NOT part of the hash: the same inputs reproduce the same id.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    programme_id: str = Field(min_length=1)
    hypothesis_id: str = Field(min_length=1)
    variant_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    config_hash: str
    dataset_hashes: dict[str, str] = Field(min_length=1)
    feature_version: str = Field(min_length=1)
    label_version: str = Field(min_length=1)
    cost_model_version: str = Field(min_length=1)
    code_commit_sha: str
    runner_version: str = Field(min_length=1)
    evidence_class: EvidenceClass

    @field_validator("config_hash")
    @classmethod
    def _config(cls, value: str) -> str:
        if not _HASH.match(value):
            msg = "config_hash must be a lowercase hex digest"
            raise ValueError(msg)
        return value

    @field_validator("code_commit_sha")
    @classmethod
    def _sha(cls, value: str) -> str:
        if not _SHA.match(value) or value == "0" * 40:
            msg = "code_commit_sha must be a real full 40-hex commit id"
            raise ValueError(msg)
        return value

    @field_validator("dataset_hashes")
    @classmethod
    def _datasets(cls, value: dict[str, str]) -> dict[str, str]:
        for name, digest in value.items():
            if not name or not _HASH.match(digest):
                msg = f"dataset hash for {name!r} is not a hex digest"
                raise ValueError(msg)
        return value

    @property
    def experiment_id(self) -> str:
        """Deterministic id: same identity, same id."""
        return canonical_hash(self.model_dump(mode="json"))[:32]


class RunManifest(BaseModel):
    """The immutable record of one run (never overwritten; a new run gets a new manifest)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    identity: ExperimentIdentity
    parameters: dict[str, Any]
    split: str = Field(min_length=1)
    random_seeds: dict[str, int]
    environment_lock_hash: str
    started_at: str
    finished_at: str
    output_hashes: dict[str, str]
    warnings: tuple[str, ...] = ()
    status: str = Field(pattern=r"^(OK|FAILED|INCONCLUSIVE|BLOCKED)$")

    @property
    def manifest_id(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))[:32]


def write_manifest(directory: Path, manifest: RunManifest) -> Path:
    """Write ``<manifest_id>.json`` once. An existing file with other content is an error."""
    path = directory / f"{manifest.manifest_id}.json"
    text = canonical_json(manifest.model_dump(mode="json"))
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            msg = "manifest already exists with different content (manifests are immutable)"
            raise IdentityError(msg)
        return path
    directory.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(text)
    return path


def read_manifest(path: Path) -> RunManifest:
    """Read and verify a manifest: the file name must equal its content id."""
    manifest = RunManifest.model_validate_json(path.read_text(encoding="utf-8"))
    if path.stem != manifest.manifest_id:
        msg = "manifest content does not match its id (modified)"
        raise IdentityError(msg)
    return manifest
