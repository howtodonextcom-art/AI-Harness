"""Aggregate the per-bar funnel records into the numbers of the audit (descriptive only).

uv run python scripts/research/funnel_report.py data/research/funnel [--json out.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import polars as pl


def pct(a: int, b: int) -> float:
    return round(100.0 * a / b, 3) if b else 0.0


def main() -> None:  # noqa: PLR0915 - one block per audit table
    src = Path(sys.argv[1])
    df = pl.concat(
        [pl.read_parquet(p) for p in sorted(src.glob("*.parquet"))], how="vertical_relaxed"
    )
    n = df.height
    out: dict[str, object] = {"bars": n, "months": len(list(src.glob("*.parquet")))}

    # 1. what the product actually says
    out["real_action"] = {k: v for k, v in df["real_action"].value_counts().iter_rows()}
    out["chain_action_without_gates"] = {
        k: v for k, v in df["chain_action"].value_counts().iter_rows()
    }

    # 2. direction mix and the sequential funnel, per side (chain order, hard gates removed)
    seq: dict[str, list[tuple[str, int]]] = {}
    for side, h1 in (("BUY", "BULLISH"), ("SELL", "BEARISH")):
        d = df.filter(pl.col("h1") == h1)
        up = "UP" if side == "BUY" else "DOWN"
        down = "DOWN" if side == "BUY" else "UP"
        pb = "PULLBACK_IN_UPTREND" if side == "BUY" else "PULLBACK_IN_DOWNTREND"
        steps: list[tuple[str, int]] = [("H1 bias = side", d.height)]
        d = d.filter(pl.col("h4") != ("TREND_DOWN" if side == "BUY" else "TREND_UP"))
        steps.append(("H4 does not veto", d.height))
        d = d.filter(pl.col("m15") != down)
        steps.append(("M15 not against", d.height))
        d = d.filter(pl.col("m15") == up)
        steps.append(("M15 structure with trend", d.height))
        d = d.filter(pl.col("pullback") == pb)
        steps.append(("M15 pullback band (SETUP_ARMED)", d.height))
        d = d.filter(pl.col("m5") == up)
        steps.append(("M5 momentum with trend (TRIGGER)", d.height))
        d = d.filter(
            ~pl.col("chain_refusal").str.contains(
                "VOLATILITY_TOO_HIGH|VOLUME_TOO_LOW|NO_TRIGGER|STALE_DATA"
            )
        )
        steps.append(("M1 execution ok", d.height))
        room = "TOO_CLOSE_TO_RESISTANCE" if side == "BUY" else "TOO_CLOSE_TO_SUPPORT"
        d = d.filter(pl.col("chain_refusal") != room)
        steps.append(("room >= 1 ATR to opposing swing", d.height))
        d = d.filter(pl.col("chain_refusal") != "INVALID_STOP_DISTANCE")
        steps.append(("stop valid (<= 3 ATR)", d.height))
        d = d.filter(pl.col("chain_refusal") != "RR_TOO_LOW")
        steps.append(("net R:R >= 1.5 (geometry)", d.height))
        d_all = d  # chain says BUY/SELL ignoring hard gates
        d = d.filter(pl.col("gates") == "")
        steps.append(("no hard gate (spread/vol/data...)", d.height))
        seq[side] = steps
        out[f"chain_signals_{side}"] = d_all.height
        out[f"final_signals_{side}"] = d.height
    out["funnel"] = {s: [(k, v, pct(v, steps[0][1])) for k, v in steps] for s, steps in seq.items()}

    # 3. hard gates: how often each fires on its own across ALL bars (regime/vol gates by construction)
    gate_counts: dict[str, int] = {}
    for g in df["gates"].to_list():
        for part in g.split("|") if g else []:
            gate_counts[part] = gate_counts.get(part, 0) + 1
    out["hard_gate_bars"] = {
        k: (v, pct(v, n)) for k, v in sorted(gate_counts.items(), key=lambda x: -x[1])
    }
    out["any_hard_gate"] = (
        df.filter(pl.col("gates") != "").height,
        pct(df.filter(pl.col("gates") != "").height, n),
    )

    # 4. volatility regime split and symmetry of the raw conditions
    out["vol_regime_share"] = {k: pct(v, n) for k, v in df["vol"].value_counts().iter_rows()}
    out["h1_share"] = {k: pct(v, n) for k, v in df["h1"].value_counts().iter_rows()}
    out["h4_share"] = {k: pct(v, n) for k, v in df["h4"].value_counts().iter_rows()}
    out["m15_share"] = {k: pct(v, n) for k, v in df["m15"].value_counts().iter_rows()}
    out["pullback_share"] = {k: pct(v, n) for k, v in df["pullback"].value_counts().iter_rows()}
    out["m5_share"] = {k: pct(v, n) for k, v in df["m5"].value_counts().iter_rows()}
    out["m1exec_share"] = {k: pct(v, n) for k, v in df["m1exec"].value_counts().iter_rows()}
    out["execq_share"] = {k: pct(v, n) for k, v in df["execq"].value_counts().iter_rows()}

    # 5. readiness depth reached (no gates)
    out["readiness_depth"] = {
        int(k): (v, pct(v, n)) for k, v in sorted(df["level"].value_counts().iter_rows())
    }

    # 6. per-year signals (chain, no gates) and final
    per_year = (
        df.group_by("year")
        .agg(
            pl.len().alias("bars"),
            (pl.col("chain_action") != "WAIT").sum().alias("chain_signals"),
            (pl.col("real_action") != "WAIT").sum().alias("final_signals"),
            (pl.col("chain_action") == "BUY").sum().alias("chain_buy"),
            (pl.col("chain_action") == "SELL").sum().alias("chain_sell"),
        )
        .sort("year")
    )
    out["per_year"] = per_year.to_dicts()

    # 7. a signal is a persistent state: count distinct episodes (new setup per M5 bar is the same idea)
    sig = df.filter(pl.col("chain_action") != "WAIT").sort("ts")
    out["chain_signal_by_session"] = {k: v for k, v in sig["session"].value_counts().iter_rows()}

    # 8. first-failure attribution of the chain (hard gates removed), per H1 side
    first = (
        df.filter(pl.col("chain_action") == "WAIT")
        .with_columns(pl.col("chain_refusal").alias("r"))
        .group_by(["h1", "r"])
        .len()
        .sort("len", descending=True)
    )
    out["first_failure"] = first.head(24).to_dicts()

    # 9. geometry: when everything upstream passes, how far from valid are room/RR?
    geo = df.filter(
        pl.col("chain_refusal").is_in(
            [
                "TOO_CLOSE_TO_RESISTANCE",
                "TOO_CLOSE_TO_SUPPORT",
                "RR_TOO_LOW",
                "INVALID_STOP_DISTANCE",
            ]
        )
    )
    out["geometry_failures"] = {k: v for k, v in geo["chain_refusal"].value_counts().iter_rows()}

    text = json.dumps(out, indent=1, ensure_ascii=True, default=str)
    if len(sys.argv) > 3 and sys.argv[2] == "--json":
        Path(sys.argv[3]).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
