"""P0 cost attribution for Batch A variants on Development-2 (Class D: descriptive only).

Question: were the Stage 1 results decided by costs? For each registered variant it recomputes the
mean R under benign and harsh cost profiles from the SAME events and the SAME barrier paths:

* gross-mid          no costs at all
* recorded spread    spread as recorded (no 30-point floor), slippage 3 points, swap 0
* swap 0             programme cost rule but swap 0
* swap -20 / -4.2    programme cost rule with a mid swap on longs
* as run             programme cost rule (floor 30, slippage 3, swap -76.05 / -4.2)

It never revives a variant (Class D, not counted in K, cannot confer evidence). It only tells us
whether costs, rather than the signal, explain the sign of the result.

    uv run python scripts/p0_cost_attribution.py [--write]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.evaluation.edge_program import load_research_data  # noqa: E402
from xau_edge.research_v2 import barrier  # noqa: E402
from xau_edge.research_v2.barrier import Outcomes, compute_outcomes  # noqa: E402
from xau_edge.research_v2.batch_a import frame_for, in_window, variants  # noqa: E402
from xau_edge.research_v2.frame import H1Frame, weekday_of_key  # noqa: E402

RAW = ROOT / "data" / "research_history"
MANIFEST = ROOT / "docs" / "research" / "edge-program" / "data-manifest.json"
HYP = ROOT / "docs" / "research" / "edge-program-v2" / "hypotheses"
OUT = ROOT / "docs" / "research" / "edge-program-v2" / "cost-attribution-dev2.json"

PROFILES = {
    "gross_mid": {"floor": None, "slip": 0.0, "swap_long": 0.0, "swap_short": 0.0},
    "recorded_spread_swap0": {"floor": 0.0, "slip": 3.0, "swap_long": 0.0, "swap_short": 0.0},
    "swap0": {"floor": 30.0, "slip": 3.0, "swap_long": 0.0, "swap_short": 0.0},
    "swap_mid": {"floor": 30.0, "slip": 3.0, "swap_long": -20.0, "swap_short": -4.2},
    "as_run": {"floor": 30.0, "slip": 3.0, "swap_long": -76.05, "swap_short": -4.2},
}


def nights(entry_key: int, exit_key: int) -> int:
    if exit_key <= entry_key:
        return 0
    ks = np.arange(entry_key + 1, exit_key + 1, dtype=np.int64)
    return int(np.sum(weekday_of_key(ks) < 5))


def mean_r(  # noqa: PLR0917
    f: H1Frame,
    d: NDArray[np.int64],
    s: NDArray[np.int64],
    longs: Outcomes,
    shorts: Outcomes,
    profile: dict[str, float | None],
) -> float:
    out = []
    for i, direction in zip(d, s, strict=True):
        res = longs if direction > 0 else shorts
        if not res.valid[i]:
            continue
        gross = res.gross_mid[i]
        if profile["floor"] is None:
            out.append(gross)
            continue
        e, x = i + 1, int(res.exit_idx[i])
        unit = barrier.DN_MULT * f.atr[i]
        spread = (
            (max(f.spread[e], profile["floor"]) + max(f.spread[x], profile["floor"])) / 2
        ) * barrier.POINT
        cost = spread + 2 * profile["slip"] * barrier.POINT
        swap_pts = profile["swap_long"] if direction > 0 else profile["swap_short"]
        swap = swap_pts * barrier.POINT * nights(int(f.day[e]), int(f.day[x]))
        out.append(gross - cost / unit + swap / unit)
    return float(np.mean(out)) if out else float("nan")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    registered = {
        v
        for hid in ("H07", "H08", "H09", "H10")
        for v in json.loads((HYP / f"{hid}.registration.json").read_text(encoding="utf-8"))[
            "variant_ids"
        ]
    }
    data = load_research_data(RAW, MANIFEST)
    frame, h4, first = frame_for(data.h1, data.h4, "dev2")
    longs, shorts = compute_outcomes(frame)
    rows = []
    print(f"{'variant':22s} " + " ".join(f"{p[:14]:>14s}" for p in PROFILES))
    for variant in variants():
        if variant.id not in registered:
            continue
        ev = in_window(variant.build(frame, h4), first)
        vals = {
            name: mean_r(frame, ev.decision, ev.direction, longs, shorts, prof)
            for name, prof in PROFILES.items()
        }
        rows.append({"variant": variant.id, "events": ev.n, **vals})
        print(f"{variant.id:22s} " + " ".join(f"{v:14.3f}" for v in vals.values()))
    if args.write:
        OUT.write_text(
            json.dumps(
                {
                    "class": "D (cost attribution; not counted in K; cannot confer evidence)",
                    "profiles": PROFILES,
                    "variants": rows,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
