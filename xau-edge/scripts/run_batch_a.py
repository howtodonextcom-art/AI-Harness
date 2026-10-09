"""Run Edge Program V2 Batch A, Stage 1, on Development-2 EXACTLY as pre-registered.

Refuses to run unless: the git tree is clean, every H07-H10 registration validates and was
committed before now, and the window is ``dev2``. Test-H and holdout are not reachable from here.
Every variant is recorded (ledger row + result file + manifest), including failures.

    uv run python scripts/run_batch_a.py --window dev2 [--write]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.evaluation.edge_program import load_research_data  # noqa: E402
from xau_edge.integrity.canonical import canonical_hash  # noqa: E402
from xau_edge.integrity.evidence import EvidenceClass  # noqa: E402
from xau_edge.integrity.identity import (  # noqa: E402
    ExperimentIdentity,
    RunManifest,
    write_manifest,
)
from xau_edge.integrity.registration import HypothesisRegistration, validate  # noqa: E402
from xau_edge.research_v2 import barrier  # noqa: E402
from xau_edge.research_v2.barrier import compute_outcomes  # noqa: E402
from xau_edge.research_v2.batch_a import (  # noqa: E402
    LOCKED,
    frame_for,
    in_window,
    variants,
)
from xau_edge.research_v2.study import screen, study_variant  # noqa: E402

RAW = ROOT / "data" / "research_history"
MANIFEST = ROOT / "docs" / "research" / "edge-program" / "data-manifest.json"
HYP = ROOT / "docs" / "research" / "edge-program-v2" / "hypotheses"
LEDGER = ROOT / "docs" / "research" / "edge-program-v2" / "ledger.md"
OUT = ROOT / "experiments" / "edge_program_v2_stage1"
RUNNER_VERSION = "research_v2-1"
PERIOD_LABEL = {"dev2": "dev2"}


def git(*args: str) -> str:
    out = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def preflight() -> tuple[str, dict[str, HypothesisRegistration]]:
    """Clean tree, valid and already-committed registrations; returns HEAD and the registrations."""
    if git("status", "--porcelain", "--", "src", "scripts", "docs", "configs"):
        sys.exit("refused: the working tree has uncommitted changes in src/scripts/docs/configs")
    head = git("rev-parse", "HEAD")
    regs: dict[str, HypothesisRegistration] = {}
    for hid in ("H07", "H08", "H09", "H10"):
        path = HYP / f"{hid}.registration.json"
        md = HYP / f"{hid}.md"
        for file in (path, md):
            if not git("log", "-1", "--format=%ct", "--", str(file)):
                sys.exit(f"refused: {file.name} is not committed")
        reg = HypothesisRegistration.model_validate_json(path.read_text(encoding="utf-8"))
        problems = validate(reg, k_cap=24)
        if problems:
            sys.exit(f"refused: {hid} registration problems: {problems}")
        regs[hid] = reg
    return head, regs


def next_row_number() -> int:
    rows = [ln for ln in LEDGER.read_text(encoding="utf-8").splitlines() if ln.startswith("| ")]
    numbers = [int(ln.split("|")[1]) for ln in rows if ln.split("|")[1].strip().isdigit()]
    return max(numbers, default=0) + 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window", default="dev2")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.window in LOCKED or args.window not in PERIOD_LABEL:
        sys.exit("refused: only the dev2 window can be run here (Test-H and holdout are locked)")
    head, regs = preflight()
    registered = {v for r in regs.values() for v in r.variant_ids}
    k = sum(len(r.variant_ids) for r in regs.values())
    data = load_research_data(RAW, MANIFEST)
    frame, h4, first = frame_for(data.h1, data.h4, args.window)
    print(f"frame bars={frame.n} first_in_window={first} k={k} head={head[:10]}")
    longs, shorts = compute_outcomes(frame)
    started = datetime.now(UTC)
    studies = []
    for variant in variants():
        if variant.id not in registered:
            continue
        events = in_window(variant.build(frame, h4), first)
        studies.append((variant, study_variant(frame, events, longs, shorts, k=k)))
    verdicts = screen([s for _, s in studies])
    finished = datetime.now(UTC)
    config = {
        "barrier": {
            "up": barrier.UP_MULT,
            "dn": barrier.DN_MULT,
            "horizon": barrier.HORIZON,
            "spread_floor": barrier.SPREAD_FLOOR,
            "slip_base": barrier.SLIP_BASE,
            "slip_pess": barrier.SLIP_PESS,
            "swap_long": barrier.SWAP_LONG,
            "swap_short": barrier.SWAP_SHORT,
        },
        "window": args.window,
        "holm_family_alpha": 0.10,
        "resamples": 20000,
        "seed": 7,
    }
    lock = ROOT / "uv.lock"
    env_hash = hashlib.sha256(lock.read_bytes()).hexdigest() if lock.exists() else "0" * 64
    rows: list[str] = []
    number = next_row_number()
    print(f"{'variant':22s} {'n':>5s} {'gross':>7s} {'base':>7s} {'pess':>7s} {'p':>7s}  verdict")
    for variant, study in studies:
        verdict = verdicts[study.name]
        s = study.summary
        survivor = verdict["stage1_survivor"]
        print(
            f"{study.name:22s} {study.n_events:5d} "
            f"{s.get('mean_gross_mid_r', float('nan')):7.3f} {study.mean_net_base:7.3f} "
            f"{study.mean_net_pess:7.3f} {study.p_value:7.4f}  "
            f"{'SURVIVOR' if survivor else 'FAIL'}"
        )
        identity = ExperimentIdentity(
            programme_id="edge-program-v2",
            hypothesis_id=variant.hypothesis,
            variant_id=variant.id,
            strategy_id=variant.id,
            config_hash=canonical_hash(config)[:32],
            dataset_hashes=dict(data.sha256),
            feature_version="atr14-wilder;levels-v1;events-v1",
            label_version="triple-barrier-2to1-h24-v1",
            cost_model_version="p1-costs:spread30;slip3/6;swap-current",
            code_commit_sha=head,
            runner_version=RUNNER_VERSION,
            evidence_class=EvidenceClass.SCREENING,
        )
        payload: dict[str, Any] = {
            "variant": variant.id,
            "hypothesis": variant.hypothesis,
            "window": args.window,
            "evidence_class": "SCREENING",
            "k": k,
            "experiment_id": identity.experiment_id,
            "dataset_ids": data.dataset_ids,
            "code_commit_sha": head,
            "recorded_at": finished.isoformat(),
            "screening": verdict,
            "study": study.summary,
        }
        text = json.dumps(payload, indent=2, default=float) + "\n"
        registry_id = canonical_hash(payload)[:16]
        if args.write:
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / f"{variant.id}_{args.window}.json").write_text(text, encoding="utf-8")
            manifest = RunManifest(
                identity=identity,
                parameters=config,
                split=args.window,
                random_seeds={"bootstrap": 7, "placebo": 7},
                environment_lock_hash=env_hash,
                started_at=started.isoformat(),
                finished_at=finished.isoformat(),
                output_hashes={"result": registry_id},
                warnings=(),
                status="OK",
            )
            write_manifest(OUT / "manifests", manifest)
            stamp = finished.strftime("%Y-%m-%d %H:%M:%S UTC")
            note = (
                f"{study.n_events} lệnh, mean net R {study.mean_net_base:+.4f} / bi quan "
                f"{study.mean_net_pess:+.4f}; gross-mid {s.get('mean_gross_mid_r', float('nan')):+.4f}; "
                f"p={study.p_value:.4f}; {'SURVIVOR' if survivor else 'FAIL'}"
            )
            rows.append(
                f"| {number} | {stamp} | {variant.id} | {args.window}-2 | base + bi quan | {note} | `{registry_id}` |"
            )
            number += 1
    if args.write:
        with LEDGER.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(rows) + "\n")
        summary = {
            "window": args.window,
            "k": k,
            "code_commit_sha": head,
            "survivors": [n for n, v in verdicts.items() if v["stage1_survivor"]],
            "verdicts": verdicts,
        }
        (OUT / f"summary_{args.window}.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        print("survivors:", summary["survivors"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
