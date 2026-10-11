"""Descriptive pattern study: how often, how big, how late. NEVER what happens next.

    uv run python scripts/pattern_descriptive.py random_walk
    uv run python scripts/pattern_descriptive.py dev2_h1

Reads no outcome. The statistics module receives detections only, so returns, win rates and target
hits cannot be computed here. Parameters are the library defaults, fixed before the run and never
swept on market data (counts under other parameters are shown on synthetic data only).

The dataset must pass ``descriptive_data.require_descriptive``: random_walk (synthetic) and dev2_h1
(Development-2 2011-2018, BURNED, counts only) are the only open ones; Validation-2, Test-H,
Holdout, the live ledger and anything unknown are refused.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np

from xau_edge.structure.descriptive_data import (
    DEV2_END,
    DEV2_START,
    ForbiddenDatasetError,
    block_shuffled_null,
    load_dev2_h1,
    require_descriptive,
)
from xau_edge.structure.detection import PatternDetection
from xau_edge.structure.formation import track_double_formations
from xau_edge.structure.pattern_stats import describe, describe_formations
from xau_edge.structure.reversal import ReversalConfig, detect_reversals
from xau_edge.structure.wolfe import WolfeConfig, detect_wolfe_patterns

ROOT = Path(__file__).resolve().parents[1]
NULL_BLOCK = 48
OUT = ROOT / "docs" / "video-intelligence" / "pattern-research"
HISTORY = ROOT / "data" / "research_history"


def _double(h: np.ndarray, lo: np.ndarray, c: np.ndarray) -> list[PatternDetection]:  # type: ignore[type-arg,unused-ignore]
    return detect_reversals(h, lo, c, kinds=("DOUBLE",))


def _head_shoulders(h: np.ndarray, lo: np.ndarray, c: np.ndarray) -> list[PatternDetection]:  # type: ignore[type-arg,unused-ignore]
    return detect_reversals(h, lo, c, kinds=("HNS",))


def detectors() -> dict[str, Callable[..., list[PatternDetection]]]:
    return {
        "wolfe": detect_wolfe_patterns,
        "double_top_bottom": _double,
        "head_and_shoulders": _head_shoulders,
    }


def parameters() -> dict[str, object]:
    return {
        "wolfe": WolfeConfig().model_dump(),
        "reversal": ReversalConfig().model_dump(),
        "tuned_on_market_data": False,
    }


def random_walk_series(seed: int, bars: int, sigma: float, noise: float) -> tuple[np.ndarray, ...]:  # type: ignore[type-arg,unused-ignore]
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, sigma, bars))
    return (
        close + np.abs(rng.normal(0, noise, bars)),
        close - np.abs(rng.normal(0, noise, bars)),
        close,
    )


def _quant(values: list[float] | list[int]) -> dict[str, float] | None:
    if not values:
        return None
    return {
        "p25": float(np.percentile(values, 25)),
        "median": float(np.median(values)),
        "p75": float(np.percentile(values, 75)),
        "max": float(np.max(values)),
    }


def reclaim_timing(seeds: int, bars: int) -> dict[str, object]:
    """Wolfe entry timing, SYNTHETIC data only: entering at P5's confirmation versus waiting for a
    close back inside line 1-3. Pairs each geometry found in both modes (same P5) and reports how
    long the wait is and how much the risk distance (entry to the P5 stop) grows. Which share of
    geometries ever reclaim is price behaviour after the pattern, so it is not reported for real
    market data; on a random walk it only illustrates the mechanics."""
    waits: list[int] = []
    growth: list[float] = []
    geometries = reclaimed = 0
    for seed in range(seeds):
        h, lo, c = random_walk_series(seed, bars, 0.3, 0.1)
        early = {(d.bias, d.points[4].bar): d for d in detect_wolfe_patterns(h, lo, c)}
        late = {
            (d.bias, d.points[4].bar): d
            for d in detect_wolfe_patterns(h, lo, c, WolfeConfig(entry_trigger="LINE13_RECLAIM"))
        }
        geometries += len(early)
        for key, first in early.items():
            second = late.get(key)
            if second is None:
                continue
            reclaimed += 1
            waits.append(second.detected_at - first.detected_at)
            risk_first = abs(
                first.reference_levels["entry_reference"] - first.reference_levels["stop_reference"]
            )
            risk_second = abs(
                second.reference_levels["entry_reference"]
                - second.reference_levels["stop_reference"]
            )
            growth.append(risk_second / risk_first)
    return {
        "note": "synthetic random walk only; matches the same P5 in both modes",
        "geometries_at_p5_confirmation": geometries,
        "also_found_with_reclaim_trigger": reclaimed,
        "extra_bars_waited_after_p5_confirmed": _quant(waits),
        "risk_distance_ratio_reclaim_over_p5": _quant(growth),
    }


def run_random_walk(seeds: int, bars: int) -> dict[str, object]:
    require_descriptive("random_walk")
    result: dict[str, object] = {
        "dataset": "random_walk",
        "classification": "SYNTHETIC",
        "seeds": seeds,
        "bars_per_seed": bars,
        "parameters": parameters(),
        "outcome_analysis": "NONE",
    }
    # the first noise setting is the one behind the earlier "about 46 per 10,000 bars" report
    for label, sigma, noise in (("baseline", 0.3, 0.1), ("wide_bar_ranges", 0.3, 0.3)):
        per_detector: dict[str, object] = {}
        for name, detect in detectors().items():
            counts, pooled = [], []
            for seed in range(seeds):
                h, lo, c = random_walk_series(seed, bars, sigma, noise)
                found = detect(h, lo, c)
                counts.append(10_000 * len(found) / bars)
                pooled.extend(found)
            per_detector[name] = {
                "per_10k_bars_mean": round(float(np.mean(counts)), 2),
                "per_10k_bars_min": round(float(np.min(counts)), 2),
                "per_10k_bars_max": round(float(np.max(counts)), 2),
                "pooled": describe(pooled, bars * seeds),
            }
        result[label] = {"sigma": sigma, "bar_range_noise": noise, "detectors": per_detector}
    result["wolfe_entry_timing_synthetic"] = reclaim_timing(seeds, bars)
    tracks = []
    for seed in range(seeds):
        hh, ll, cc = random_walk_series(seed, bars, 0.3, 0.1)
        tracks.extend(track_double_formations(hh, ll, cc))
    result["double_formation_lifecycle"] = describe_formations(tracks, bars * seeds)
    return result


def run_dev2() -> dict[str, object]:
    policy = require_descriptive("dev2_h1")
    files = sorted((HISTORY / "XAUUSD" / "H1").glob("*.parquet"))
    if len(files) != 1:
        raise ForbiddenDatasetError(f"expected exactly one H1 history file, found {len(files)}")
    manifest = json.loads((HISTORY / "MANIFEST.json").read_text(encoding="utf-8"))
    entry = next(f for f in manifest["files"] if f["path"].endswith(files[0].name))
    frame = load_dev2_h1(files[0])
    h, lo, c = (frame[col].to_numpy().astype(np.float64) for col in ("high", "low", "close"))
    stamps = frame["timestamp"].to_list()
    per_detector: dict[str, object] = {}
    for name, detect in detectors().items():
        found = detect(h, lo, c)
        per_detector[name] = describe(found, int(frame.height), stamps)
    null: dict[str, object] = {}
    for name, detect in detectors().items():
        rates = []
        for seed in range(20):
            hs, ls, cs = block_shuffled_null(h, lo, c, seed, NULL_BLOCK)
            rates.append(10_000 * len(detect(hs, ls, cs)) / frame.height)
        null[name] = {
            "per_10k_bars_mean": round(float(np.mean(rates)), 2),
            "per_10k_bars_min": round(float(np.min(rates)), 2),
            "per_10k_bars_max": round(float(np.max(rates)), 2),
        }
    formation = describe_formations(
        track_double_formations(h, lo, c, timeframe="H1"), int(frame.height)
    )
    return {
        "dataset": "dev2_h1",
        "classification": policy.classification,
        "reason": policy.reason,
        "window": [DEV2_START.isoformat(), DEV2_END.isoformat()],
        "bars": int(frame.height),
        "first_bar": stamps[0].isoformat(),
        "last_bar": stamps[-1].isoformat(),
        "source_file": files[0].name,
        "source_sha256_from_manifest": entry["sha256"],
        "parameters": parameters(),
        "outcome_analysis": "NONE",
        "clock_note": "broker clock is certified only for some years; hour-of-day counts are informational",
        "detectors": per_detector,
        "double_formation_lifecycle": formation,
        "block_shuffled_null": {"block_bars": NULL_BLOCK, "shuffles": 20, "per_detector": null},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("dataset")
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--bars", type=int, default=10_000)
    args = parser.parse_args(argv)
    try:
        if args.dataset == "random_walk":
            report = run_random_walk(args.seeds, args.bars)
        elif args.dataset == "dev2_h1":
            report = run_dev2()
        else:
            require_descriptive(args.dataset)  # raises with the classification and the reason
            raise ForbiddenDatasetError(f"no study is defined for {args.dataset!r}")
    except ForbiddenDatasetError as exc:
        print(f"REFUSED: {exc}")
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"{args.dataset}_descriptive.json"
    target.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str)[:3000])
    print(f"\nwritten: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
