"""Ask the freeze guard whether a locked split could be opened for a candidate. It never opens one.

    uv run python scripts/check_freeze.py <candidate_id> <testH|holdout>

Exit code 0 only if EVERY condition holds; otherwise 2 with the reasons. There is no runner for the
locked splits in this repository: this command is the checklist a future runner must pass.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.research_v2.guards import GuardDecision, check  # noqa: E402

V2 = ROOT / "docs" / "research" / "edge-program-v2"
MANIFEST = ROOT / "docs" / "research" / "edge-program" / "data-manifest.json"


def _git(*args: str) -> str:
    out = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return out.stdout.strip()


def decide(candidate: str, split: str) -> GuardDecision:
    """Gather the real inputs and evaluate the guard (read-only)."""
    freeze = V2 / f"freeze-{candidate}-{split}.json"
    head = _git("rev-parse", "HEAD")
    committed = bool(
        freeze.exists() and _git("log", "-1", "--format=%H", "--", str(freeze))
    ) and not (_git("status", "--porcelain", "--", str(freeze)))
    k_now = 0
    ledger = (V2 / "ledger.md").read_text(encoding="utf-8")
    for token in ledger.split("K = "):
        tail = token.split("=")
        if len(tail) >= 2 and tail[1].split(";")[0].strip().isdigit():
            k_now = int(tail[1].split(";")[0].strip())
            break
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    datasets = {
        tf: v["sha256"] for tf, v in manifest.items() if isinstance(v, dict) and "sha256" in v
    }
    survivors: set[str] = set()  # Stage 2 survivors are recorded by the Stage 2 runner (none yet)
    return check(
        freeze,
        split=split,
        candidate_id=candidate,
        head_sha=head,
        k_now=k_now,
        dataset_hashes=datasets,
        stage2_survivors=survivors,
        already_run=set(),
        committed=committed,
    )


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 1
    decision = decide(sys.argv[1], sys.argv[2])
    print("ALLOWED" if decision.allowed else "REFUSED")
    for reason in decision.reasons:
        print(" -", reason)
    return 0 if decision.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
