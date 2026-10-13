"""Print (or --write) the canonical sha256 of docs/ml/ml_v0_spec.json (EOL-independent)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

SPEC = Path(__file__).resolve().parents[1] / "docs" / "ml" / "ml_v0_spec.json"
GUARD = SPEC.with_suffix(".sha256")


def canonical_hash(path: Path = SPEC) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    digest = canonical_hash()
    if "--write" in sys.argv:
        GUARD.write_text(digest + "\n", encoding="utf-8")
    print(digest)
