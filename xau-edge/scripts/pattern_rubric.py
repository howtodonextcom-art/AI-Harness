"""Score the pattern candidates with the pre-written rubric and test how robust the ranking is.

    uv run python scripts/pattern_rubric.py        # rubric v1 (phase 2)
    uv run python scripts/pattern_rubric.py v2     # rubric v2 (pattern intelligence)

Reads docs/video-intelligence/pattern-research/{rubric,scores}.json. Pure arithmetic: no data, no
network. The rubric (criteria, weights, selection rule) was written before the scores.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

DOCS = Path(__file__).resolve().parents[1] / "docs"
BASES = {
    "v1": (DOCS / "video-intelligence" / "pattern-research", "rubric.json", "scores.json"),
    "v2": (DOCS / "pattern-intelligence", "rubric_v2.json", "scores_v2.json"),
}
DRAWS = 2000
SEED = 11


def normalized(scores: dict[str, int], weights: dict[str, float]) -> float:
    total = sum(weights.values()) * 5
    return 100.0 * sum(scores[name] * w for name, w in weights.items()) / total


def disqualified(scores: dict[str, int]) -> str | None:
    novelty = scores.get("research_novelty", scores.get("novelty_vs_closed_research_and_baseline"))
    clarity = scores.get("definition_clarity", scores.get("formal_definability"))
    if novelty == 0:
        return "already tested and closed in V1-V3"
    if clarity is not None and clarity <= 1:
        return "no formal definition without discretion"
    return None


def main() -> int:
    version = sys.argv[1] if len(sys.argv) > 1 else "v1"
    base, rubric_file, scores_file = BASES[version]
    rubric = json.loads((base / rubric_file).read_text(encoding="utf-8"))
    cands = json.loads((base / scores_file).read_text(encoding="utf-8"))["candidates"]
    weights = {k: float(v["weight"]) for k, v in rubric["criteria"].items()}
    rows = []
    for name, entry in cands.items():
        score = normalized(entry["scores"], weights)
        rows.append((name, score, disqualified(entry["scores"])))
    rows.sort(key=lambda r: -r[1])
    print(f"{'candidate':<46}{'score':>7}  status")
    eligible = [r for r in rows if r[2] is None]
    top2 = {r[0] for r in eligible[:2]}
    for name, score, why in rows:
        status = f"DISQUALIFIED: {why}" if why else ("top 2" if name in top2 else "")
        flag = " (meets 70)" if why is None and score >= 70 else ""
        print(f"{name:<46}{score:>7.1f}  {status}{flag}")
    rng = np.random.default_rng(SEED)
    names = [r[0] for r in eligible]
    keys = list(weights)
    matrix = np.array([[cands[n]["scores"][k] for k in keys] for n in names], dtype=float)
    hits = dict.fromkeys(names, 0)
    first = dict.fromkeys(names, 0)
    for _ in range(DRAWS):
        w = np.array([weights[k] for k in keys]) * rng.uniform(0.5, 1.5, len(keys))
        s = matrix @ w / (w.sum() * 5) * 100
        order = np.argsort(-s)
        first[names[order[0]]] += 1
        for i in order[:2]:
            hits[names[i]] += 1
    print(f"\nRobustness over {DRAWS} random weightings (each weight x U(0.5, 1.5), seed {SEED}):")
    print(f"{'candidate':<46}{'in top 2':>9}{'rank 1':>9}")
    for n in sorted(names, key=lambda x: -hits[x]):
        print(f"{n:<46}{100 * hits[n] / DRAWS:>8.1f}%{100 * first[n] / DRAWS:>8.1f}%")
    hits2 = dict.fromkeys(names, 0)
    base_w = np.array([weights[k] for k in keys])
    for _ in range(DRAWS):
        noise = rng.choice([-1, 0, 1], size=matrix.shape, p=[0.15, 0.7, 0.15])
        s = np.clip(matrix + noise, 0, 5) @ base_w / (base_w.sum() * 5) * 100
        for i in np.argsort(-s)[:2]:
            hits2[names[i]] += 1
    print(f"\nRobustness to scoring error (each cell +-1 with probability 0.3, {DRAWS} draws):")
    for n in sorted(names, key=lambda x: -hits2[x])[:4]:
        print(f"{n:<46}{100 * hits2[n] / DRAWS:>8.1f}% in top 2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
