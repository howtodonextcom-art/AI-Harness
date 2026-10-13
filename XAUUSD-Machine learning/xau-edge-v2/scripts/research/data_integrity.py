"""Data-integrity scan of the shared bar store: lag-1 autocorrelation of close-to-close log returns.

Real XAUUSD M5/H1 returns have a lag-1 autocorrelation within about +/-0.05. A value near -0.33 at
every timeframe is the signature of an artefact (a feed whose closes carry mean-reverting noise); any
pullback or mean-reversion rule looks profitable on it for no economic reason.

The test uses ONLY price data (never a strategy result), so it can be applied to every window
without opening any outcome. A month is VALID when |lag-1 autocorrelation of M5 returns| <= 0.10.

    uv run python scripts/research/data_integrity.py [--symbol XAUUSD] [--out docs/research/data_integrity_xauusd.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "src"))

import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

from xau_edge_v2.config import Settings  # noqa: E402

THRESHOLD = 0.10


def lag1(close: np.ndarray) -> float:
    r = np.diff(np.log(close))
    if r.size < 50:  # noqa: PLR2004
        return float("nan")
    return float(np.corrcoef(r[:-1], r[1:])[0, 1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    root = Settings().data_root / a.symbol
    months: dict[str, dict[str, float | int | bool]] = {}
    for f in sorted((root / "M5").glob("*.parquet")):
        d = pl.read_parquet(f)
        mon = f.stem
        row: dict[str, float | int | bool] = {
            "m5_lag1": round(lag1(d["close"].to_numpy()), 3),
            "real_volume_share": round(float((d["real_volume"] > 0).mean()), 2),
            "median_spread_pts": float(d["spread"].median() or 0.0),
            "bars": d.height,
        }
        h1 = root / "H1" / f.name
        if h1.exists():
            row["h1_lag1"] = round(lag1(pl.read_parquet(h1)["close"].to_numpy()), 3)
        row["valid"] = bool(abs(row["m5_lag1"]) <= THRESHOLD)  # type: ignore[arg-type]
        months[mon] = row
    bad = [m for m, r in months.items() if not r["valid"]]
    # runs of invalid months
    runs: list[list[str]] = []
    for m in sorted(months):
        if not months[m]["valid"]:
            if runs and _next(runs[-1][-1]) == m:
                runs[-1].append(m)
            else:
                runs.append([m])
    summary = {
        "symbol": a.symbol,
        "rule": f"month VALID iff |lag-1 autocorrelation of M5 log returns| <= {THRESHOLD}",
        "months": len(months),
        "invalid_months": len(bad),
        "invalid_runs": [{"from": r[0], "to": r[-1], "months": len(r)} for r in runs],
    }
    print(json.dumps(summary, indent=1))
    if a.out:
        Path(a.out).write_text(
            json.dumps({**summary, "detail": months}, indent=1), encoding="utf-8"
        )


def _next(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    return f"{y + (m == 12)}-{m % 12 + 1:02d}"


if __name__ == "__main__":
    main()
