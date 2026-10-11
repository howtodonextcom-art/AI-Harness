# ruff: noqa - one-off planning arithmetic for V3_RESEARCH_FOUNDATION_AND_HUMAN_DECISION.md (no data, no outcome)
"""Power, MDE and economic arithmetic for the three V3 families. Pure planning: reads no market data.

MDE = (z_alpha + z_beta) * sigma / sqrt(n), one-sided, power 0.80.
K_V3 = 3 (one variant per family) inside the V2 ledger cap (24, 20 used). Val alpha = 0.05 / 3.
Test-H alpha = 0.05 / K_total with K_total = 21 (Programme 1) + 20 (V2) + 3 (V3) = 44.
"""

import json
import os
from statistics import NormalDist

Z = NormalDist().inv_cdf
OUT = os.path.join(os.path.dirname(__file__), "power_v3.json")
Z_BETA = Z(0.80)
ALPHA = {"stage1_holm_fw0.10_first": 0.10 / 3, "val": 0.05 / 3, "test_h": 0.05 / 44}
SIGMAS = (1.0, 1.3)
YEARS = {"dev2": 8.0, "val2": 3.0, "test_h": 3.33, "holdout": 0.43}
# expected independent events per year (planning values, stated in the preregistrations; not measured outcomes)
RATE = {"F1_residual": 250, "F3_us_momentum": 250, "F2_macro_setB": 120, "F2_macro_setA": 32}


def mde(n: float, alpha: float, sigma: float) -> float:
    return (Z(1 - alpha) + Z_BETA) * sigma / n**0.5


def n_needed(delta: float, alpha: float, sigma: float) -> float:
    return ((Z(1 - alpha) + Z_BETA) * sigma / delta) ** 2


def main() -> None:
    res: dict = {"alpha": ALPHA, "years": YEARS, "rate_per_year": RATE, "families": {}}
    for fam, rate in RATE.items():
        row: dict = {}
        for part, yrs in YEARS.items():
            n = rate * yrs
            a = (
                ALPHA["val"]
                if part in ("val2", "holdout")
                else ALPHA["test_h"]
                if part == "test_h"
                else ALPHA["stage1_holm_fw0.10_first"]
            )
            row[part] = {"n": round(n), **{f"mde_sigma{s}": round(mde(n, a, s), 3) for s in SIGMAS}}
        for s in SIGMAS:
            row[f"forward_years_to_detect_0.15R_sigma{s}_at_val_alpha"] = round(
                n_needed(0.15, ALPHA["val"], s) / rate, 2
            )
        row["meets_150_per_year"] = rate >= 150
        res["families"][fam] = row
    econ = {}
    for risk_pct in (0.25, 0.5):
        for rate in (120, 250):
            econ[f"risk{risk_pct}_rate{rate}"] = {
                "edge_R": 0.15,
                "expected_annual_pct": round(0.15 * rate * risk_pct, 2),
            }
    res["economics_at_0.15R"] = econ
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
