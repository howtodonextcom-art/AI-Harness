"""Benchmark the similarity methods on local data (not part of CI).

Usage: ``uv run python scripts/benchmark_similarity.py [--timeframe M15] [--window 30] [--queries 20]``

For random query bars it times each method through ``PatternIndex`` and compares the vectorised
Euclidean search with a plain per-window NumPy loop (the baseline the plan asks for), and checks
that both return the same neighbours. Results are printed; copy them into the research note.
"""

from __future__ import annotations

import argparse
import time

import numpy as np

from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.catalog import DatasetCatalog
from xau_edge.patterns.distances import METHODS
from xau_edge.patterns.representation import pattern_values
from xau_edge.patterns.search import PatternIndex, SearchConfig


def _loop_euclid(values: np.ndarray, q: int, window: int, horizon: int) -> list[int]:
    query = values[q - window + 1 : q + 1]
    best: list[tuple[float, int]] = []
    for e in range(window - 1, q - window - horizon + 1):
        cand = values[e - window + 1 : e + 1]
        if np.isfinite(cand).all():
            best.append((float(np.sqrt(((cand - query) ** 2).sum())), e))
    best.sort()
    return [e for _, e in best[:1]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="data/raw")
    parser.add_argument("--timeframe", default="M15")
    parser.add_argument("--window", type=int, default=30)
    parser.add_argument("--horizon", type=int, default=60)
    parser.add_argument("--queries", type=int, default=20)
    args = parser.parse_args()

    tf = Timeframe.parse(args.timeframe)
    bars = DatasetCatalog(args.root).load("XAUUSD", tf).frame
    values = pattern_values(bars)
    rng = np.random.default_rng(0)
    queries = rng.integers(values.shape[0] // 2, values.shape[0], size=args.queries)
    print(f"{tf.value}: {values.shape[0]} bars, window={args.window}, horizon={args.horizon}")
    for name in METHODS:
        cfg = SearchConfig(
            window=args.window, horizon=args.horizon, k=10, method=name, dtw_radius=5
        )
        index = PatternIndex(values, cfg)
        start = time.perf_counter()
        for q in queries:
            index.search(int(q))
        per_query = (time.perf_counter() - start) / len(queries)
        print(f"  {name:11s} {per_query * 1000:9.1f} ms/query")

    cfg = SearchConfig(window=args.window, horizon=args.horizon, k=1, method="euclidean")
    index = PatternIndex(values, cfg)
    sample = queries[:3]
    start = time.perf_counter()
    loops = [_loop_euclid(values, int(q), args.window, args.horizon) for q in sample]
    loop_ms = (time.perf_counter() - start) / len(sample) * 1000
    start = time.perf_counter()
    fast = [[m.end_index for m in index.search(int(q)).matches] for q in sample]
    fast_ms = (time.perf_counter() - start) / len(sample) * 1000
    print(f"  plain loop  {loop_ms:9.1f} ms/query   vectorised {fast_ms:9.1f} ms/query")
    print(f"  same nearest neighbour as the loop: {loops == fast}")


if __name__ == "__main__":
    main()
