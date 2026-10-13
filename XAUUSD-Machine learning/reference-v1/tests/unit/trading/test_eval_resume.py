"""The batch evaluator: bounded fan-out, and an interrupted run resumes to the SAME result.

The resume test runs ``scripts/trade_v12_eval.py`` three times over a burned window (needs
``data/market``): once straight through, once interrupted at a day checkpoint and then resumed.
The final report of the resumed run must equal the uninterrupted one, field by field.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from xau_edge.ops.priority import default_workers

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "trade_v12_eval.py"
MARKET = ROOT / "data" / "market"
WINDOW = ("2025-12-01T00:00", "2025-12-04T00:00")
VARIANTS = ["v1.1", "ABC1"]
INTERRUPTED = 75
COMPARED = (
    "decisions",
    "counts",
    "distinct_setups",
    "setup_phase_counts",
    "first_refusals",
    "plan_violations",
    "day_hashes_sha",
    "days_with_any_close",
    "signals",
)


def test_default_fanout_leaves_most_of_the_machine_free() -> None:
    assert 1 <= default_workers() <= max(1, (os.cpu_count() or 4) // 4)


def run(out: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - our own script, fixed arguments
        [
            sys.executable,
            str(SCRIPT),
            "--start",
            WINDOW[0],
            "--end",
            WINDOW[1],
            "--variants",
            *VARIANTS,
            "--workers",
            "1",
            "--out-dir",
            str(out),
            "--root",
            str(MARKET),
            *extra,
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=900,
        check=False,
    )


def reports(out: Path) -> dict[str, dict[str, object]]:
    tag = f"{WINDOW[0]}_{WINDOW[1]}".replace(":", "")
    result = {}
    for name in VARIANTS:
        data = json.loads((out / f"eval_{name}_{tag}.json").read_text(encoding="utf-8"))
        result[name] = {key: data[key] for key in COMPARED}
    return result


@pytest.mark.skipif(not MARKET.exists(), reason="burned market data is not here")
def test_an_interrupted_evaluation_resumes_to_the_same_final_result(tmp_path: Path) -> None:
    straight = tmp_path / "straight"
    assert run(straight).returncode == 0

    resumed = tmp_path / "resumed"
    cut = run(resumed, "--stop-after-days", "2")
    assert cut.returncode == INTERRUPTED  # stopped at a checkpoint, no final report yet
    tag = f"{WINDOW[0]}_{WINDOW[1]}".replace(":", "")
    assert (resumed / f"ckpt_{tag}.json").exists()
    assert not (resumed / f"eval_{VARIANTS[0]}_{tag}.json").exists()

    finished = run(resumed, "--resume")
    assert finished.returncode == 0
    assert not (resumed / f"ckpt_{tag}.json").exists()  # the checkpoint is cleaned up

    assert reports(resumed) == reports(straight)
