"""Write ``docs/research/edge-program-v2/gate-calibration.json`` (planted-strategy simulation).

Deterministic (fixed seed). The numbers are a DIAGNOSTIC of the gates' behaviour under stated
assumptions (see ``docs/research/gate-calibration.md``); they change no threshold.

    uv run python scripts/build_calibration_artifact.py [--write]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.integrity.gates import calibrate  # noqa: E402
from xau_edge.integrity.power2 import planted_edge_table  # noqa: E402

OUT = ROOT / "docs" / "research" / "edge-program-v2" / "gate-calibration.json"
SEED = 20261009


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    gates = calibrate(sims=1500, seed=SEED)
    power = planted_edge_table(k=21, sims=600, seed=SEED)
    payload = {
        "seed": SEED,
        "assumptions": {
            "sd_per_trade_r": 1.3,
            "gates": "8 years x 150 trades; neighbour correlation 0.8; broker correlation 0.7",
            "power": "K=21; 250 days x 3 trades; clustered rho 0.3; overlapping hold 4",
        },
        "gates": [
            {
                "gate": g.gate,
                "pass_rate": g.pass_rate,
                "classification": g.classification,
                "reason": g.reason,
            }
            for g in gates
        ],
        "power": power,
        "note": "Class D diagnostic; no threshold was changed.",
    }
    text = json.dumps(payload, indent=2) + "\n"
    print(text)
    if args.write:
        OUT.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
