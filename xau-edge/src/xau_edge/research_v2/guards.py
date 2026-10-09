"""Freeze guard for the locked splits (roadmap 13.2 and 43).

Test-H may be opened ONLY for a candidate that passed Stage 2 on Validation-2, with a committed
freeze record that pins the code, K, datasets and rules, and only once. Nothing in this module opens
a split: it decides whether opening would be allowed and says why not. The default answer is no.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

_SHA = re.compile(r"^[0-9a-f]{40}$")
_HEX = re.compile(r"^[0-9a-f]{16,64}$")
REQUIRED_SPLITS = ("testH", "holdout")


class FreezeRecord(BaseModel):
    """What must be pinned before a locked split is opened."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str = Field(min_length=1)
    split: str = Field(pattern=r"^(testH|holdout)$")
    code_commit_sha: str
    k_frozen: int = Field(ge=1)
    dataset_hashes: dict[str, str] = Field(min_length=1)
    rules_hash: str
    stage2_passed_on: str = Field(min_length=3)
    independent_review: str = Field(min_length=10)
    frozen_at: str


@dataclass(frozen=True)
class GuardDecision:
    """Whether the locked split may be opened, and every reason it may not."""

    allowed: bool
    reasons: tuple[str, ...]


def check(
    freeze_file: Path,
    *,
    split: str,
    candidate_id: str,
    head_sha: str,
    k_now: int,
    dataset_hashes: dict[str, str],
    stage2_survivors: set[str],
    already_run: set[tuple[str, str]],
    committed: bool,
) -> GuardDecision:
    """Evaluate every condition; a missing or inconsistent one is a reason to refuse."""
    reasons: list[str] = []
    if split not in REQUIRED_SPLITS:
        reasons.append(f"{split} is not a locked split")
    if candidate_id not in stage2_survivors:
        reasons.append("the candidate did not pass Stage 2 on Validation-2")
    if (candidate_id, split) in already_run:
        reasons.append("this candidate was already run on this split (one run only)")
    raw: Any = None
    try:
        raw = json.loads(freeze_file.read_text(encoding="utf-8"))
        record = FreezeRecord.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError):
        reasons.append("no valid freeze record")
        return GuardDecision(False, tuple(reasons))
    if not committed:
        reasons.append("the freeze record is not committed")
    if record.candidate_id != candidate_id or record.split != split:
        reasons.append("the freeze record is for another candidate or split")
    if not _SHA.match(record.code_commit_sha) or record.code_commit_sha != head_sha:
        reasons.append("the code at HEAD differs from the frozen commit")
    if record.k_frozen != k_now:
        reasons.append("K changed after the freeze")
    if record.dataset_hashes != dataset_hashes or not all(
        _HEX.match(v) for v in record.dataset_hashes.values()
    ):
        reasons.append("dataset hashes differ from the frozen ones")
    if not _HEX.match(record.rules_hash):
        reasons.append("the rules hash is not a digest")
    return GuardDecision(not reasons, tuple(reasons))
