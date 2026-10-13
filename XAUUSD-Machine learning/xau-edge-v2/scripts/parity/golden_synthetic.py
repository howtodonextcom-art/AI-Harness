"""G4.1 synthetic reachability: drive EVERY branch of the decision chain, V1 against V2.

Real bars rarely reach a BUY/SELL (spread and volatility gates block most of the time), so the
plan path (stop, targets, size, cost, expiry, ids) was thin in the real-bar golden run. Here the
market state itself is generated (seeded, constructed field by field, mostly coherent with the
chosen direction), the same values are put into V1's ``MarketState`` and V2's, and both
``decide`` functions are compared. No bars, no windows, no performance: only arithmetic and
branching. A reachability table is printed and the run FAILS when a branch is never reached.

    <V1>/.venv/Scripts/python.exe scripts/parity/golden_synthetic.py [--cases N] [--out file.json]
        [--fixtures tests/golden/core_golden_synthetic.json]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "src"))
sys.path.insert(0, str(HERE.parent))

from golden_core import Tally, compare_decision  # noqa: E402
from xau_edge.trading import sizing as v1_sizing  # noqa: E402
from xau_edge.trading.baseline import BaselineConfig, decide as v1_decide  # noqa: E402
from xau_edge.trading.baseline import DecisionContext as V1Ctx  # noqa: E402
from xau_edge.trading.market_state import MarketState as V1State  # noqa: E402
from xau_edge.trading.market_state import TfSnapshot as V1Snap  # noqa: E402
from xau_edge.trading.schema import Refusal as V1Refusal  # noqa: E402

from xau_edge_v2.core import risk as v2_risk  # noqa: E402
from xau_edge_v2.core.decision import DecisionConfig, decide as v2_decide  # noqa: E402
from xau_edge_v2.core.decision import DecisionContext as V2Ctx  # noqa: E402
from xau_edge_v2.core.market_state import MarketState as V2State  # noqa: E402
from xau_edge_v2.core.market_state import TfSnapshot as V2Snap  # noqa: E402

SEED = 20261014
T0 = datetime(2026, 3, 2, 8, 0, tzinfo=UTC)
ALL_TF = ("M1", "M5", "M15", "M30", "H1", "H4")


def pick(rng: random.Random, options: list[tuple[Any, float]]) -> Any:
    return rng.choices([o for o, _ in options], weights=[w for _, w in options])[0]


def gen_state(rng: random.Random) -> dict[str, Any]:
    """Field values of one state (the common subset both implementations share)."""
    d = rng.choice([1, -1])
    up, down = ("UP", "DOWN") if d > 0 else ("DOWN", "UP")
    p = rng.uniform(1800, 4500)
    atr15 = rng.uniform(0.4, 10.0)
    atr5 = atr15 * rng.uniform(0.25, 0.85) if rng.random() > 0.03 else None
    h1 = pick(rng, [("BULLISH" if d > 0 else "BEARISH", 90), ("NEUTRAL", 6), ("UNKNOWN", 2)])
    h4 = pick(rng, [
        ("TREND_UP" if d > 0 else "TREND_DOWN", 28), ("TREND_DOWN" if d > 0 else "TREND_UP", 8),
        ("RANGE", 40), ("SHOCK", 4), ("HIGH_VOLATILITY", 5), ("LOW_VOLATILITY", 12), ("UNKNOWN", 3),
    ])  # fmt: skip
    m15s = pick(rng, [
        (up, 70), (down, 6), ("RANGE", 10), (f"REVERSAL_{up}", 5), (f"REVERSAL_{down}", 5),
        ("UNKNOWN", 4),
    ])  # fmt: skip
    pull = "PULLBACK_IN_UPTREND" if d > 0 else "PULLBACK_IN_DOWNTREND"
    m15p = pick(rng, [(pull, 82), ("NONE", 14), ("UNKNOWN", 4)])
    m5 = pick(rng, [(up, 82), (down, 6), ("FLAT", 10), ("UNKNOWN", 2)])
    m1 = pick(rng, [
        ("NEUTRAL", 60), ("ACTIVE_UP", 9), ("ACTIVE_DOWN", 9), ("QUIET", 8), ("ABNORMAL", 5),
        ("UNKNOWN", 4),
    ])  # fmt: skip
    opposing = None if rng.random() < 0.18 else rng.uniform(0.2, 7.0) * atr15
    other = None if rng.random() < 0.3 else rng.uniform(0.2, 7.0) * atr15
    dist_res, dist_sup = (opposing, other) if d > 0 else (other, opposing)
    swing = None if rng.random() < 0.12 else rng.uniform(-0.6, 4.2) * atr5 if atr5 else None
    swing_low = p - swing if swing is not None else None
    swing_high = p + swing if swing is not None else None
    avail = list(ALL_TF) if rng.random() < 0.92 else rng.sample(list(ALL_TF), rng.randint(2, 5))
    stale = [tf for tf in avail if rng.random() < 0.03]
    spread = None if rng.random() < 0.04 else rng.uniform(4, 70)
    z = None if rng.random() < 0.1 else rng.uniform(-2.5, 3.5)
    return {
        "symbol": "XAUUSD",
        "volume_type": pick(rng, [("TICK_VOLUME", 95), ("UNKNOWN", 5)]),
        "h4_regime": h4, "h1_trend": h1, "m30_structure": rng.choice(["UP", "DOWN", "RANGE"]),
        "m15_structure": m15s, "m15_pullback": m15p, "m5_momentum": m5, "m1_micro_state": m1,
        "atr_m5": atr5, "atr_m15": None if rng.random() < 0.02 else atr15,
        "volume_zscore_m1": z, "spread": spread,
        "spread_percentile": None if spread is None else rng.random(),
        "spread_to_atr_m5": None if spread is None or not atr5 else spread * 0.01 / atr5,
        "session": rng.choice(["ASIA", "LONDON", "NEW_YORK", "LONDON_NY_OVERLAP", "OFF_HOURS"]),
        "price": None if rng.random() < 0.02 else p,
        "distance_to_support": dist_sup, "distance_to_resistance": dist_res,
        "recent_swing_high": swing_high, "recent_swing_low": swing_low,
        "bos_state": "NONE", "choch_state": "NONE",
        "volatility_regime": pick(rng, [("NORMAL", 84), ("HIGH", 8), ("LOW", 7), ("UNKNOWN", 1)]),
        "data_quality": pick(rng, [("OK", 92), ("DEGRADED", 3), ("STALE", 4), ("UNKNOWN", 1)]),
        "news_state": pick(rng, [("UNKNOWN", 70), ("OK", 24), ("BLOCKED", 6)]),
        "execution_quality": pick(rng, [("GOOD", 86), ("POOR", 10), ("UNKNOWN", 4)]),
        "available_timeframes": avail, "stale_timeframes": stale,
        "spread_state": "GOOD", "volume_state": "NORMAL", "market_open": rng.random() > 0.02,
        "_m5": {"low": swing_low, "high": swing_high},
        "_dir": d,
    }  # fmt: skip


def snap_kwargs(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "timeframe": "M5",
        "bar_open": T0,
        "bar_closed": T0 + timedelta(minutes=5),
        "bars_used": 400,
        "close": 0.0,
        "atr": None,
        "atr_percentile": None,
        "ema_fast": None,
        "ema_slow": None,
        "price_vs_ema_atr": None,
        "rsi": None,
        "roc": None,
        "structure_trend": 0,
        "bos_recent": 0,
        "choch_recent": 0,
        "last_swing_high": raw["_m5"]["high"],
        "last_swing_low": raw["_m5"]["low"],
        "support": None,
        "resistance": None,
        "patterns": {},
        "volume_zscore": None,
        "tick_volume": 0.0,
        "regime": None,
    }


def v1_snapshot(raw: dict[str, Any]) -> V1Snap:
    extra = {
        "ema_slope_atr": None, "adx": None, "plus_di": None, "minus_di": None,
        "range_percentile": None, "volume_percentile": None, "volume_ratio": None,
        "volume_acceleration": None,
    }  # fmt: skip
    return V1Snap(**snap_kwargs(raw), **extra)


def make_states(raw: dict[str, Any], at: datetime) -> tuple[V1State, V2State]:
    common = {k: v for k, v in raw.items() if not k.startswith("_")}
    common["available_timeframes"] = tuple(common["available_timeframes"])
    common["stale_timeframes"] = tuple(common["stale_timeframes"])
    snaps = {"M5": None} if "M5" in common["available_timeframes"] else {}
    v1_only = {
        "atr_m1": None, "atr_h1": None, "tick_volume_m1": None, "volume_ratio_m1_m5": None,
        "distance_to_recent_high": None, "distance_to_recent_low": None,
    }  # fmt: skip
    s1 = V1State(
        timestamp=at, **common, **v1_only,
        snapshots={k: v1_snapshot(raw) for k in snaps},
    )  # fmt: skip
    s2 = V2State(
        timestamp=at, **common,
        snapshots={k: V2Snap(**snap_kwargs(raw)) for k in snaps},
    )  # fmt: skip
    return s1, s2


def gen_context(rng: random.Random, raw: dict[str, Any]) -> dict[str, Any]:
    spec = {
        "point": 0.01,
        "tick_size": rng.choice([0.01, 0.01, 0.01, 0.001]),
        "tick_value": rng.choice([1.0, 1.0, 0.87, 1.21]),
        "contract_size": 100.0,
        "volume_min": rng.choice([0.01, 0.01, 0.1]),
        "volume_max": rng.choice([100.0, 100.0, 5.0]),
        "volume_step": rng.choice([0.01, 0.01, 0.1]),
        "stops_level_points": rng.choice([0, 0, 0, 20, 80, 400]),
        "freeze_level_points": 0,
        "digits": 2,
    }
    p = raw["price"] or 2000.0
    quote = rng.random() < 0.7
    half = rng.uniform(0.05, 0.4)
    return {
        "spec": spec,
        "equity": pick(rng, [(10_000.0, 55), (200_000.0, 15), (500.0, 12), (50.0, 5), (None, 9), (-5.0, 2), (float("nan"), 2)]),
        "bid": p - half if quote else None, "ask": p + half if quote else None,
        "market_open": pick(rng, [(True, 97), (False, 3)]),
        "data_ok": pick(rng, [(True, 96), (False, 4)]),
        "spec_known": pick(rng, [(True, 97), (False, 3)]),
        "feed": pick(rng, [(True, 97), (False, 3)]),
        "cooldown": rng.random() < 0.03, "daily": rng.random() < 0.02, "risk": rng.random() < 0.02,
        "allow_news": rng.random() < 0.85,
        "quiet_block": rng.random() < 0.9,
        "min_clear_atr": rng.choice([1.0, 1.0, 1.0, 0.5, 2.0]),
        "risk_pct": rng.choice([0.25, 0.25, 0.25, 0.1, 0.5, 1.0]),
    }  # fmt: skip


def coverage_keys(d1: Any) -> list[str]:
    keys = [f"action:{d1.decision.value}"]
    keys += [f"refusal:{r.value}" for r in d1.refusal_reasons]
    if d1.decision.value != "WAIT":
        keys.append(f"entry_quality:{d1.entry_quality}")
        keys.append(f"stop_model:{d1.stop_model}")
        keys.append(f"capped:{d1.metadata.get('capped_by_structure')}")
        keys.append(f"tp2:{'none' if d1.take_profit_2 is None else 'set'}")
        keys.append(f"sized:{'no_equity' if d1.position_size is None else 'sized'}")
        keys.append(f"warnings:{len(d1.warnings)}")
    keys.append(f"m1:{d1.m1_execution_state}")
    if any("strongly against" in r for r in d1.reasons):
        keys.append("m1:NOISY (chain refusal)")
    return keys


def fixture(raw: dict[str, Any], ctx: dict[str, Any], d1: Any, at: datetime) -> dict[str, Any]:
    state = {k: v for k, v in raw.items() if not k.startswith("_")}
    state["timestamp"] = at.isoformat()
    state["snapshots"] = (
        {"M5": {"bar_open": T0.isoformat(), "bar_closed": (T0 + timedelta(minutes=5)).isoformat(),
                "last_swing_high": raw["_m5"]["high"], "last_swing_low": raw["_m5"]["low"]}}
        if "M5" in raw["available_timeframes"] else {}
    )  # fmt: skip
    expected = {
        "action": d1.decision.value, "refusals": [r.value for r in d1.refusal_reasons],
        "reasons": list(d1.reasons), "warnings": list(d1.warnings),
        "m1_execution_state": d1.m1_execution_state, "decision_id": d1.signal_id, "atr": d1.atr,
        "entry_price": d1.entry_price, "stop_loss": d1.stop_loss, "take_profit": d1.take_profit,
        "take_profit_2": d1.take_profit_2, "net_rr": d1.risk_reward,
        "required_win_rate": d1.required_win_rate, "risk_amount": d1.risk_amount,
        "lots": d1.position_size, "stop_model": d1.stop_model,
        "expiry": None if d1.signal_expiry is None else d1.signal_expiry.isoformat(),
        "entry_quality": d1.entry_quality, "setup_id": d1.setup_id,
    }  # fmt: skip
    return {"state": state, "context": ctx, "expected": expected, "synthetic": True}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=60_000)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--fixtures", type=Path, default=None)
    ap.add_argument("--per-key", type=int, default=6, help="fixtures kept per reachability key")
    args = ap.parse_args()
    rng = random.Random(SEED)
    t = Tally()
    reach: Counter[str] = Counter()
    kept: Counter[str] = Counter()
    fixtures: list[dict[str, Any]] = []
    levels: Counter[int] = Counter()
    t0 = time.time()
    for i in range(args.cases):
        raw = gen_state(rng)
        ctx = gen_context(rng, raw)
        at = T0 + timedelta(minutes=6, seconds=i % 59)
        s1, s2 = make_states(raw, at)
        sp1, sp2 = v1_sizing.SymbolSpec(**ctx["spec"]), v2_risk.SymbolSpec(**ctx["spec"])
        c1 = V1Ctx(
            spec=sp1, equity=ctx["equity"], broker_connected=ctx["feed"],
            cooldown_active=ctx["cooldown"], daily_limit_hit=ctx["daily"],
            risk_limit_hit=ctx["risk"], market_open=ctx["market_open"],
            market_status="OPEN" if ctx["market_open"] else "CLOSED", data_ok=ctx["data_ok"],
            spec_known=ctx["spec_known"], bid=ctx["bid"], ask=ctx["ask"],
        )  # fmt: skip
        c2 = V2Ctx(
            spec=sp2, equity=ctx["equity"], feed_connected=ctx["feed"],
            cooldown_active=ctx["cooldown"], daily_limit_hit=ctx["daily"],
            risk_limit_hit=ctx["risk"], market_open=ctx["market_open"],
            market_status="OPEN" if ctx["market_open"] else "CLOSED", data_ok=ctx["data_ok"],
            spec_known=ctx["spec_known"], bid=ctx["bid"], ask=ctx["ask"],
        )  # fmt: skip
        cfg1 = BaselineConfig(
            allow_unknown_news=ctx["allow_news"], block_quiet_m1=ctx["quiet_block"],
            min_clear_atr=ctx["min_clear_atr"], risk_pct=ctx["risk_pct"],
        )  # fmt: skip
        cfg2 = DecisionConfig(
            allow_unknown_news=ctx["allow_news"], block_quiet_m1=ctx["quiet_block"],
            min_clear_atr=ctx["min_clear_atr"], risk_pct=ctx["risk_pct"],
        )  # fmt: skip
        d1 = v1_decide(s1, c1, cfg1)
        d2 = v2_decide(s2, c2, cfg2)
        compare_decision(t, d1, d2, f"case{i}")
        levels[d2.readiness_level] += 1
        t.check(
            "G4.1 readiness: READY iff BUY/SELL",
            (d2.readiness_level == 6) == (d2.action != "WAIT"),
            f"case{i}",
        )
        t.check(
            "G4.1 readiness: gate caps at 5",
            d2.action != "WAIT" or d2.readiness_level <= 5,
            f"case{i}",
        )
        keys = coverage_keys(d1)
        reach.update(keys)
        want = [k for k in keys if kept[k] < args.per_key]
        if want and (args.fixtures is not None):
            fixtures.append(fixture(raw, ctx, d1, at))
            for k in keys:
                kept[k] += 1
    required = (
        [f"action:{a}" for a in ("BUY", "SELL", "WAIT")]
        + [f"refusal:{r.value}" for r in V1Refusal]
        + [f"entry_quality:{q}" for q in ("STRONG", "ACCEPTABLE")]
        + ["stop_model:HYBRID", "capped:True", "capped:False", "tp2:none", "tp2:set", "sized:no_equity", "sized:sized"]
        + [f"m1:{s}" for s in ("GOOD", "QUIET", "SPREAD_WIDE", "VOLATILE", "STALE", "NOISY (chain refusal)")]
    )  # fmt: skip
    missing = [k for k in required if reach[k] == 0]
    report = t.report()
    total = sum(r["checks"] for r in report.values())
    bad = sum(r["mismatches"] for r in report.values())
    print("reachability (decisions reaching each branch):")
    for k in sorted(reach):
        print(f"  {k:42s} {reach[k]:7d}")
    print("readiness levels:", dict(sorted(levels.items())))
    for group, r in report.items():
        flag = "OK " if r["mismatches"] == 0 else "BAD"
        print(
            f"[{flag}] {r['checks']:7d} checks {r['mismatches']:4d} mismatches  max|d|={r['max_abs_diff']:.2e}  {group}"
        )
        for sample in r["samples"]:
            print("      ", sample)
    print(f"unreached required branches: {missing or 'none'}")
    print(f"total {total} checks, {bad} mismatches, {args.cases} cases, {time.time() - t0:.0f}s")
    if args.out:
        args.out.write_text(
            json.dumps(
                {
                    "groups": report,
                    "reach": dict(reach),
                    "levels": dict(levels),
                    "missing": missing,
                    "total": total,
                    "mismatches": bad,
                    "cases": args.cases,
                    "seed": SEED,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    if args.fixtures and fixtures:
        args.fixtures.parent.mkdir(parents=True, exist_ok=True)
        args.fixtures.write_text(json.dumps({"seed": SEED, "cases": fixtures}), encoding="utf-8")
        print(f"wrote {len(fixtures)} synthetic fixtures to {args.fixtures}")
    sys.exit(1 if (bad or missing) else 0)


if __name__ == "__main__":
    main()
