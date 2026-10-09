"""Analyse gate-vector dumps: independent and conditional pass rates, redundancy, counterfactuals,
reachability, event sequence and volatility forensics. Diagnostic only: no PnL, no optimisation.

Usage: ``uv run python scripts/signal_funnel_analyze.py data/trade/reports/funnel/v1.1_*.jsonl``
"""

from __future__ import annotations

import itertools
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from xau_edge.trading.funnel import GATES

ORDER = [
    "market_open", "data_ok", "spec_ok", "spread_ok", "vol_not_high", "vol_not_low",
    "h4_regime_ok", "h1_directional", "h4_not_against", "m15_not_against", "m15_setup",
    "m5_trigger", "m1_not_volatile", "m1_not_quiet", "m1_not_noisy", "clearance_ok", "stop_ok",
    "rr_ok", "risk_ok",
]  # fmt: skip
SEQ_N = (3, 6, 12)


def load(paths: list[str]) -> dict[str, list[dict[str, Any]]]:
    return {
        Path(p).stem: [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines()]
        for p in paths
    }


def passes(row: dict[str, Any], gates: list[str]) -> bool:
    return all(row["gates"].get(g) is True for g in gates)


def rate(num: int, den: int) -> float:
    return round(100 * num / den, 1) if den else 0.0


def phi(a: list[bool], b: list[bool]) -> float:
    n11 = sum(1 for x, y in zip(a, b, strict=True) if x and y)
    n10 = sum(1 for x, y in zip(a, b, strict=True) if x and not y)
    n01 = sum(1 for x, y in zip(a, b, strict=True) if not x and y)
    n00 = len(a) - n11 - n10 - n01
    den = math.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
    return (n11 * n00 - n10 * n01) / den if den else 0.0


def classify(a: list[bool], b: list[bool]) -> tuple[str, dict[str, float]]:
    """a, b are FAIL indicators. Redundant when one fail implies the other; contradictory when
    passing both is impossible."""
    fa, fb, both = sum(a), sum(b), sum(1 for x, y in zip(a, b, strict=True) if x and y)
    pass_both = sum(1 for x, y in zip(a, b, strict=True) if not x and not y)
    p_b_given_a = both / fa if fa else 0.0
    p_a_given_b = both / fb if fb else 0.0
    union = fa + fb - both
    jac = both / union if union else 0.0
    f = phi(a, b)
    stats = {
        "phi": round(f, 2),
        "P(B|A)": round(p_b_given_a, 2),
        "P(A|B)": round(p_a_given_b, 2),
        "jaccard": round(jac, 2),
    }
    if fa and fb and pass_both == 0:
        return "CONTRADICTORY", stats
    if max(p_b_given_a, p_a_given_b) >= 0.8 and jac >= 0.5:
        return "STRONGLY REDUNDANT", stats
    if abs(f) >= 0.3 or max(p_b_given_a, p_a_given_b) >= 0.6:
        return "PARTIALLY REDUNDANT", stats
    return "INDEPENDENT", stats


def main() -> None:
    windows = load(sys.argv[1:])
    rows = [r for w in windows.values() for r in w]
    print(f"## Decisions: {len(rows)} in {len(windows)} windows ({', '.join(windows)})\n")
    print("### Actual v1.1 decisions", dict(Counter(r["decision"] for r in rows)))

    print(
        "\n### Independent pass rate of each gate (all decisions; direction gates need H1 direction)"
    )
    for g in GATES:
        evald = [r for r in rows if r["gates"].get(g) is not None]
        ok = sum(1 for r in evald if r["gates"][g])
        print(
            f"- {g}: pass {rate(ok, len(rows))}% of all; {rate(ok, len(evald))}% of {len(evald)} evaluable"
        )

    print("\n### Sequential survival in chain order (cumulative; each row = rows still alive)")
    alive = rows
    for g in ORDER:
        nxt = [r for r in alive if r["gates"].get(g) is True]
        print(
            f"- after {g}: {len(nxt)} alive ({rate(len(nxt), len(rows))}% of all; "
            f"conditional {rate(len(nxt), len(alive))}%)"
        )
        alive = nxt

    print("\n### Gate redundancy (fail indicators, pairs with >=2% fails each)")
    fails = {g: [r["gates"].get(g) is False for r in rows] for g in ORDER}
    for g1, g2 in itertools.combinations(
        list(filter(lambda g: sum(fails[g]) >= 0.02 * len(rows), ORDER)), 2
    ):
        label, st = classify(fails[g1], fails[g2])
        if label != "INDEPENDENT":
            print(f"- {g1} x {g2}: {label} {st}")

    print("\n### Counterfactuals (signal count = decisions where every ENABLED gate passes)")
    base = list(ORDER)
    cfs: dict[str, list[str]] = {
        "all v1.1 gates": base,
        "minus vol_not_high": [g for g in base if g != "vol_not_high"],
        "minus vol_not_low": [g for g in base if g != "vol_not_low"],
        "minus both volatility gates": [g for g in base if g not in ("vol_not_high", "vol_not_low")],
        "minus m1_not_quiet": [g for g in base if g != "m1_not_quiet"],
        "minus spread_ok": [g for g in base if g != "spread_ok"],
        "minus H4 gates": [g for g in base if g not in ("h4_regime_ok", "h4_not_against")],
        "minus m5_trigger (setup only)": [g for g in base if g != "m5_trigger"],
        "minus m15_setup (trigger only)": [g for g in base if g not in ("m15_setup", "m15_not_against")],
        "minus both volatility + m1_quiet": [g for g in base if g not in ("vol_not_high", "vol_not_low", "m1_not_quiet")],
        "minus both volatility + spread": [g for g in base if g not in ("vol_not_high", "vol_not_low", "spread_ok")],
        "minus all context gates (vol, spread, m1 quiet, H4)": [g for g in base if g not in ("vol_not_high", "vol_not_low", "spread_ok", "m1_not_quiet", "h4_regime_ok", "h4_not_against")],
    }  # fmt: skip
    for name, gates in cfs.items():
        n = sum(1 for r in rows if passes(r, gates))
        print(f"- {name}: {n} ({rate(n, len(rows))}% of decisions)")

    print("\n### Reachability: M15 setup ready, M5 trigger, and both on the same bar")
    for name, w in windows.items():
        dir_rows = [r for r in w if r["gates"]["h1_directional"]]
        setup = sum(1 for r in dir_rows if r["gates"]["m15_setup"])
        trig = sum(1 for r in dir_rows if r["gates"]["m5_trigger"])
        both = sum(1 for r in dir_rows if r["gates"]["m15_setup"] and r["gates"]["m5_trigger"])
        exp = setup * trig / len(dir_rows) if dir_rows else 0
        print(
            f"- {name}: H1 directional {len(dir_rows)}; setup {setup}; trigger {trig}; "
            f"both {both} (independence would give {exp:.1f})"
        )

    print(
        "\n### Event sequence: trigger now AND setup ready within the previous N M5 closes (same side)"
    )
    for n in SEQ_N:
        count = 0
        examples: list[str] = []
        for w in windows.values():
            for i, r in enumerate(w):
                if not (r["gates"]["h1_directional"] and r["gates"]["m5_trigger"]):
                    continue
                side = r["f"]["labels"]["h1"]
                armed = any(
                    p["gates"]["m15_setup"] and p["f"]["labels"]["h1"] == side
                    for p in w[max(0, i - n) : i + 1]
                )
                if armed:
                    count += 1
                    if len(examples) < 3:
                        examples.append(r["at"])
        print(f"- N={n}: {count} trigger bars preceded by a ready setup; e.g. {examples}")

    print(
        "\n### Near-misses: decisions with exactly ONE failing evaluable gate (among chain gates)"
    )
    single: Counter[str] = Counter()
    for r in rows:
        bad = [g for g in ORDER if r["gates"].get(g) is False]
        if len(bad) == 1:
            single[bad[0]] += 1
    print(dict(single.most_common()))

    print("\n### Volatility forensics")
    pct = [r["f"]["atr_pct_m15"] for r in rows if r["f"]["atr_pct_m15"] is not None]
    hist = Counter(min(9, int(p * 10)) for p in pct)
    print(
        "- ATR(M15) percentile deciles (share %):",
        {k: rate(v, len(pct)) for k, v in sorted(hist.items())},
    )
    for name, w in windows.items():
        lows = sum(1 for r in w if r["f"]["labels"]["vol"] == "LOW")
        highs = sum(1 for r in w if r["f"]["labels"]["vol"] == "HIGH")
        print(
            f"- {name}: LOW {rate(lows, len(w))}%, HIGH {rate(highs, len(w))}%, NORMAL {rate(len(w) - lows - highs, len(w))}%"
        )
    by_sess: dict[str, Counter[str]] = defaultdict(Counter)
    for r in rows:
        by_sess[r["f"]["labels"]["session"]][r["f"]["labels"]["vol"]] += 1
    for s, c in sorted(by_sess.items()):
        tot = sum(c.values())
        print(f"- session {s}: n={tot} LOW {rate(c['LOW'], tot)}% HIGH {rate(c['HIGH'], tot)}%")
    runs: list[int] = []
    cur, prev = 0, None
    for r in rows:
        v = r["f"]["labels"]["vol"]
        if v == "LOW" and prev == "LOW":
            cur += 1
        elif v == "LOW":
            cur = 1
        elif prev == "LOW" and cur:
            runs.append(cur)
            cur = 0
        prev = v
    print(
        f"- mean LOW run length {sum(runs) / len(runs):.1f} M5 bars over {len(runs)} runs"
        if runs
        else "- no LOW runs"
    )
    atr = sorted(r["f"]["atr_m15"] for r in rows if r["f"]["atr_m15"])
    if atr:
        q = lambda p: atr[int(p * (len(atr) - 1))]  # noqa: E731
        print(f"- absolute ATR(M15) USD: p10 {q(0.1):.2f} p50 {q(0.5):.2f} p90 {q(0.9):.2f}")
    low_atr = sorted(
        r["f"]["atr_m15"] for r in rows if r["f"]["atr_m15"] and r["f"]["labels"]["vol"] == "LOW"
    )
    high_atr = sorted(
        r["f"]["atr_m15"] for r in rows if r["f"]["atr_m15"] and r["f"]["labels"]["vol"] == "HIGH"
    )
    if low_atr and high_atr:
        print(
            f"- ATR(M15) median when labelled LOW {low_atr[len(low_atr) // 2]:.2f}, when HIGH {high_atr[len(high_atr) // 2]:.2f}"
        )

    print("\n### Spread gate forensics")
    sp = [r["f"]["spread"] for r in rows if r["f"]["spread"] is not None]
    ratio = [r["f"]["spread_to_atr_m5"] for r in rows if r["f"]["spread_to_atr_m5"] is not None]
    if sp and ratio:
        ratio.sort()
        print(
            f"- spread points median {sorted(sp)[len(sp) // 2]:.0f}; spread/ATR(M5) p50 {ratio[len(ratio) // 2]:.3f} p90 {ratio[int(0.9 * len(ratio))]:.3f} (limit 0.15)"
        )
    exec_poor = sum(1 for r in rows if r["f"]["labels"]["exec"] == "POOR")
    print(f"- execution_quality POOR in {rate(exec_poor, len(rows))}% of decisions")
    abn = sum(1 for r in rows if r["f"]["labels"]["m1"] == "ABNORMAL")
    print(f"- M1 ABNORMAL (which makes execution POOR) in {rate(abn, len(rows))}%")

    print("\n### M15 pullback / trigger definitions")
    dirs = [r for r in rows if r["gates"]["h1_directional"]]
    st = sum(1 for r in dirs if r["gates"]["m15_structure_with"])
    pb = sum(1 for r in dirs if r["gates"]["m15_pullback"])
    both = sum(1 for r in dirs if r["gates"]["m15_setup"])
    print(
        f"- H1 directional {len(dirs)}: M15 structure with trend {rate(st, len(dirs))}%, pullback zone {rate(pb, len(dirs))}%, both {rate(both, len(dirs))}%"
    )
    trig = sum(1 for r in dirs if r["gates"]["m5_trigger"])
    print(f"- M5 trigger (in H1 direction) {rate(trig, len(dirs))}%")
    choch = sum(1 for r in dirs if r["f"]["m15_choch"])
    print(
        f"- M15 CHOCH within last 6 bars (turns structure label into REVERSAL_*): {rate(choch, len(dirs))}%"
    )
    labels = Counter((r["f"]["labels"]["m15s"], r["f"]["labels"]["m15p"]) for r in dirs)
    print("- (M15 structure, pullback) combos among H1-directional:", labels.most_common(8))


if __name__ == "__main__":
    main()
