"""Deterministic canonical serialisation and hashing."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def canonical_json(value: Any) -> str:
    """Stable JSON: sorted keys, no spaces, no NaN/inf, ASCII only.

    The same logical value always gives the same text, so the same input identity always gives the
    same hash. Non-finite floats are refused rather than serialised.
    """
    _check_finite(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _check_finite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        msg = "non-finite number cannot be part of a canonical record"
        raise ValueError(msg)
    if isinstance(value, dict):
        for item in value.values():
            _check_finite(item)
    elif isinstance(value, list | tuple):
        for item in value:
            _check_finite(item)


def sha256_hex(text: str) -> str:
    """Full SHA-256 of UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_hash(value: Any) -> str:
    """Full SHA-256 of the canonical JSON of ``value``."""
    return sha256_hex(canonical_json(value))
