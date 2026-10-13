"""G4 golden parity: does the V2 core compute exactly what V1's trading core computes?

Run with the V1 interpreter (it has V1's code), V2's sources on the path:

    <V1>/.venv/Scripts/python.exe scripts/parity/golden_core.py [--out results.json]
        [--fixtures tests/golden/core_golden.json] [--quick]

TOOLING: it imports V1 only to compare outputs. The V2 package never imports V1.

Sections
  A  numeric kernels on seeded random walks: indicators, structure, regime, patterns, stops,
     targets, THE size function (V1 sizing vs V2 risk);
  B  market state from real closed bars (every TF snapshot field the chain reads);
  C  the decision (BUY/SELL/WAIT, refusals, chain, levels, size, ids) under varied contexts.

Locked windows are NOT sampled: Test-H (2022-01-01..2025-04-30) and Holdout (2026-05-01..2026-10-07).
This compares two implementations of the same arithmetic; it measures no performance. Only
development-era months and the gap 2025-05-01..2026-04-30 are used.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "src"))

import numpy as np  # noqa: E402
import polars as pl  # noqa: E402
from xau_edge.domain.timeframe import Timeframe as V1Tf  # noqa: E402
from xau_edge.features import indicators as v1_ind  # noqa: E402
from xau_edge.features.volume import volume_zscore as v1_vz  # noqa: E402
from xau_edge.market_data.broker_clock import BrokerClock as V1Clock  # noqa: E402
from xau_edge.structure.regime import RegimeConfig  # noqa: E402
from xau_edge.structure.regime import classify_regime as v1_regime
from xau_edge.structure.swings import analyse_structure as v1_structure  # noqa: E402
from xau_edge.trading import levels as v1_levels  # noqa: E402
from xau_edge.trading import patterns as v1_patterns  # noqa: E402
from xau_edge.trading import sizing as v1_sizing  # noqa: E402
from xau_edge.trading.baseline import BaselineConfig  # noqa: E402
from xau_edge.trading.baseline import DecisionContext as V1Ctx
from xau_edge.trading.baseline import decide as v1_decide
from xau_edge.trading.frames import from_frames  # noqa: E402
from xau_edge.trading.market_state import build_market_state as v1_build  # noqa: E402

from xau_edge_v2.core import indicators as ind  # noqa: E402
from xau_edge_v2.core import risk as v2_risk  # noqa: E402
from xau_edge_v2.core import structure as st  # noqa: E402
from xau_edge_v2.core.decision import DecisionConfig  # noqa: E402
from xau_edge_v2.core.decision import DecisionContext as V2Ctx
from xau_edge_v2.core.decision import decide as v2_decide
from xau_edge_v2.core.frames import ORDER, MultiFrames  # noqa: E402
from xau_edge_v2.core.market_state import SnapshotMemo  # noqa: E402
from xau_edge_v2.core.market_state import build_market_state as v2_build
from xau_edge_v2.data.bar_store import BarStore  # noqa: E402
from xau_edge_v2.data.frames import frame_from_polars  # noqa: E402
from xau_edge_v2.domain.contract import Timeframe  # noqa: E402
from xau_edge_v2.domain.market import BrokerClock  # noqa: E402

DATA = Path("Z:/Coding/Projects/AI-Harness/xau-edge/data/market")
SEED = 20261013
TOL = 1e-9
LOCKED = (
    (datetime(2022, 1, 1, tzinfo=UTC), datetime(2025, 5, 1, tzinfo=UTC)),
    (datetime(2026, 5, 1, tzinfo=UTC), datetime(2026, 10, 8, tzinfo=UTC)),
)
V1_TF = {tf: V1Tf(tf.value) for tf in Timeframe}


class Tally:
    def __init__(self) -> None:
        self.rows: dict[str, list[int]] = {}
        self.max_diff: dict[str, float] = {}
        self.samples: dict[str, list[str]] = {}

    def check(self, group: str, ok: bool, detail: str = "", diff: float = 0.0) -> None:
        row = self.rows.setdefault(group, [0, 0])
        row[0] += 1
        self.max_diff[group] = max(self.max_diff.get(group, 0.0), diff)
        if not ok:
            row[1] += 1
            bucket = self.samples.setdefault(group, [])
            if len(bucket) < 5:
                bucket.append(detail)

    def eq(self, group: str, a: object, b: object, detail: str = "") -> None:
        if isinstance(a, float) or isinstance(b, float):
            self.close(group, a, b, detail)
            return
        self.check(group, a == b, f"{detail}: v1={a!r} v2={b!r}")

    def close(self, group: str, a: object, b: object, detail: str = "") -> None:
        if a is None or b is None:
            self.check(group, a is None and b is None, f"{detail}: v1={a!r} v2={b!r}")
            return
        x, y = float(a), float(b)  # type: ignore[arg-type]
        if math.isnan(x) or math.isnan(y):
            self.check(group, math.isnan(x) and math.isnan(y), f"{detail}: v1={x} v2={y}")
            return
        diff = abs(x - y)
        scale = max(1.0, abs(x), abs(y))
        self.check(group, diff <= TOL * scale, f"{detail}: v1={x!r} v2={y!r}", diff)

    def array(self, group: str, a: Any, b: Any, detail: str = "") -> None:
        x, y = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
        if x.shape != y.shape:
            self.check(group, False, f"{detail}: shape {x.shape} vs {y.shape}")
            return
        both_nan = np.isnan(x) & np.isnan(y)
        same_nan = bool((np.isnan(x) == np.isnan(y)).all())
        diff = float(np.abs(np.where(both_nan, 0.0, x - y)).max()) if x.size else 0.0
        scale = max(1.0, float(np.nanmax(np.abs(x))) if x.size and not np.isnan(x).all() else 1.0)
        self.check(group, same_nan and diff <= TOL * scale, f"{detail}: max diff {diff}", diff)

    def report(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for group, (n, bad) in self.rows.items():
            out[group] = {
                "checks": n,
                "mismatches": bad,
                "max_abs_diff": self.max_diff.get(group, 0.0),
                "samples": self.samples.get(group, []),
            }
        return out


# ---------------------------------------------------------------------------------------------
# A. numeric kernels
# ---------------------------------------------------------------------------------------------
def random_bars(rng: np.random.Generator, n: int) -> tuple[np.ndarray, ...]:
    step = rng.normal(0, 1.0, n) * rng.choice([0.2, 1.0, 4.0], n, p=[0.5, 0.4, 0.1])
    close = 2000 + np.cumsum(step)
    open_ = np.concatenate([[close[0]], close[:-1]]) + rng.normal(0, 0.1, n)
    spread_up = np.abs(rng.normal(0, 0.8, n))
    spread_dn = np.abs(rng.normal(0, 0.8, n))
    high = np.maximum(open_, close) + spread_up
    low = np.minimum(open_, close) - spread_dn
    volume = np.maximum(1.0, rng.gamma(4.0, 50.0, n))
    return open_, high, low, close, volume


def section_a(t: Tally, cases: int) -> None:
    rng = np.random.default_rng(SEED)
    for case in range(cases):
        n = int(rng.integers(80, 900))
        o, h, lo, c, vol = random_bars(rng, n)
        tag = f"case{case} n={n}"
        for p in (5, 14, 20, 50):
            t.array("A indicators: ema", v1_ind.ema(c, p), ind.ema(c, p), f"{tag} p={p}")
        t.array("A indicators: rsi", v1_ind.rsi(c, 14), ind.rsi(c, 14), tag)
        t.array("A indicators: atr", v1_ind.atr(h, lo, c, 14), ind.atr(h, lo, c, 14), tag)
        a1, a2 = v1_ind.adx(h, lo, c, 14), ind.adx(h, lo, c, 14)
        for name in ("adx", "plus_di", "minus_di"):
            t.array(f"A indicators: {name}", getattr(a1, name), getattr(a2, name), tag)
        t.array("A indicators: volume_zscore", v1_vz(vol, 20), ind.volume_zscore(vol, 20), tag)
        s1, s2 = v1_structure(h, lo, c), st.analyse_structure(h, lo, c)
        for name in (
            "last_swing_high",
            "last_swing_low",
            "trend",
            "bos",
            "choch",
            "support",
            "resistance",
        ):
            t.array(f"A structure: {name}", getattr(s1, name), getattr(s2, name), tag)
        atr = v1_ind.atr(h, lo, c, 14)
        vw, mh = min(200, n), min(60, n)
        r1 = v1_regime(
            adx=a1.adx, plus_di=a1.plus_di, minus_di=a1.minus_di, atr=atr, high=h, low=lo,
            config=RegimeConfig(vol_window=vw, min_history=mh),
        )  # fmt: skip
        r2 = st.classify_regime(
            adx=a2.adx, plus_di=a2.plus_di, minus_di=a2.minus_di, atr=atr, high=h, low=lo,
            vol_window=vw, min_history=mh,
        )  # fmt: skip
        t.check("A regime labels", list(r1) == list(r2), f"{tag}")
        t.array(
            "A patterns: strong_body",
            v1_patterns.strong_body(o, h, lo, c),
            st.strong_body(o, h, lo, c),
            tag,
        )
        t.array(
            "A patterns: range_expansion",
            v1_patterns.range_expansion(h, lo, atr),
            st.range_expansion(h, lo, atr),
            tag,
        )

    cfg = v1_levels.LevelConfig()
    for case in range(cases * 20):
        direction = int(rng.choice([-1, 1]))
        entry = float(rng.uniform(1500, 4500))
        atr_v = float(rng.uniform(0.3, 12.0))
        swing = (
            None if rng.random() < 0.2 else entry - direction * float(rng.uniform(-1, 4)) * atr_v
        )
        s1 = v1_levels.compute_stop(direction, entry, swing, atr_v, cfg)
        s2 = v2_risk.compute_stop(direction, entry, swing, atr_v)
        tag = f"stop{case}"
        t.check("A stop: existence", (s1 is None) == (s2 is None), tag)
        if s1 is not None and s2 is not None:
            t.close("A stop: price", s1.price, s2.price, tag)
            t.close("A stop: distance", s1.distance, s2.distance, tag)
            t.eq("A stop: model", s1.model, s2.model, tag)
            spread = float(rng.uniform(0, 0.8))
            opposing = (
                None
                if rng.random() < 0.3
                else entry + direction * float(rng.uniform(-0.5, 8)) * atr_v
            )
            g1 = v1_levels.compute_targets(
                direction, entry, s1, cfg, spread=spread, atr=atr_v, opposing_level=opposing
            )
            g2 = v2_risk.compute_targets(
                direction, entry, s2, spread=spread, atr=atr_v, opposing_level=opposing
            )
            t.check("A targets: existence", (g1 is None) == (g2 is None), tag)
            if g1 is not None and g2 is not None:
                for f in ("tp1", "tp2", "gross_rr", "net_rr", "required_win_rate"):
                    t.close(f"A targets: {f}", getattr(g1, f), getattr(g2, f), tag)
                t.eq("A targets: capped", g1.capped_by_structure, g2.capped_by_structure, tag)

    for case in range(cases * 40):
        spec_kw = {
            "point": 0.01,
            "tick_size": float(rng.choice([0.01, 0.001])),
            "tick_value": float(rng.uniform(0.5, 1.5)),
            "contract_size": 100.0,
            "volume_min": float(rng.choice([0.01, 0.1])),
            "volume_max": float(rng.choice([50.0, 100.0])),
            "volume_step": float(rng.choice([0.01, 0.1])),
            "stops_level_points": int(rng.integers(0, 40)),
            "freeze_level_points": 0,
            "digits": 2,
        }
        sp1, sp2 = v1_sizing.SymbolSpec(**spec_kw), v2_risk.SymbolSpec(**spec_kw)
        equity = float(rng.choice([float("nan"), -5.0, 100.0, 5000.0, 10000.0, 200000.0]))
        pct = float(rng.choice([0.0, 0.1, 0.25, 0.5, 1.0, 2.0, 3.0]))
        entry = float(rng.uniform(1800, 4500))
        stop = entry - float(rng.choice([0.0, 0.05, 0.5, 2.0, 5.0, 12.0])) * float(
            rng.choice([-1, 1])
        )
        a = v1_sizing.size_for_risk(equity, pct, entry, stop, sp1)
        b = v2_risk.size_for_risk(equity, pct, entry, stop, sp2)
        tag = f"size{case}"
        t.eq("A size: lots", a.lots, b.lots, tag)
        t.eq("A size: risk_amount", a.risk_amount, b.risk_amount, tag)
        t.eq("A size: reasons", a.reasons, b.reasons, tag)
        t.eq("A size: allowed", a.allowed, b.allowed, tag)


# ---------------------------------------------------------------------------------------------
# B / C. real bars
# ---------------------------------------------------------------------------------------------
def allowed(at: datetime) -> bool:
    return not any(lo <= at < hi for lo, hi in LOCKED)


def pick_months(rng: random.Random, count: int) -> list[tuple[int, int]]:
    pool = [(y, m) for y in range(2008, 2022) for m in range(1, 13)]
    pool += [(2025, m) for m in range(5, 13)] + [(2026, m) for m in range(1, 5)]
    rng.shuffle(pool)
    return sorted(pool[:count])


def load_month(store: BarStore, year: int, month: int) -> dict[Timeframe, pl.DataFrame]:
    start = datetime(year, month, 1, tzinfo=UTC)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=UTC)
    out: dict[Timeframe, pl.DataFrame] = {}
    for tf in ORDER:
        back = {"M1": 3, "M5": 7, "M15": 14, "M30": 25, "H1": 40, "H4": 140}[tf.value]
        df = store.window(tf, start - timedelta(days=back), end, 5000)
        parts = [df]
        while df.height == 5000:
            nxt = df["timestamp"][-1] + timedelta(seconds=1)
            df = store.window(tf, nxt, end, 5000)
            parts.append(df)
        full = pl.concat(parts, how="vertical_relaxed") if len(parts) > 1 else parts[0]
        if full.height:
            out[tf] = full
    return out


def build_pair(
    frames: dict[Timeframe, pl.DataFrame],
) -> tuple[Any, MultiFrames]:
    v1 = from_frames(
        {
            V1_TF[tf]: df.select(
                "timestamp", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"
            )
            for tf, df in frames.items()
        }
    )
    v2 = MultiFrames(
        {tf: f for tf, df in frames.items() if (f := frame_from_polars(tf, df)) is not None}
    )
    return v1, v2


def compare_state(t: Tally, s1: Any, s2: Any, tag: str) -> None:
    for f in [
        "h4_regime",
        "h1_trend",
        "m30_structure",
        "m15_structure",
        "m15_pullback",
        "m5_momentum",
        "m1_micro_state",
        "session",
        "bos_state",
        "choch_state",
        "volatility_regime",
        "data_quality",
        "news_state",
        "execution_quality",
        "spread_state",
        "volume_state",
        "volume_type",
        "market_open",
        "available_timeframes",
        "stale_timeframes",
    ]:
        t.eq(f"B state: {f}", getattr(s1, f), getattr(s2, f), tag)
    for f in [
        "atr_m5",
        "atr_m15",
        "volume_zscore_m1",
        "spread",
        "spread_percentile",
        "spread_to_atr_m5",
        "price",
        "distance_to_support",
        "distance_to_resistance",
        "recent_swing_high",
        "recent_swing_low",
        "pdh",
        "pdl",
    ]:
        t.close(f"B state: {f}", getattr(s1, f), getattr(s2, f), tag)
    t.eq("B state: snapshot keys", sorted(s1.snapshots), sorted(s2.snapshots), tag)
    for key, a in s1.snapshots.items():
        b = s2.snapshots.get(key)
        if b is None:
            continue
        for f in [
            "close",
            "atr",
            "atr_percentile",
            "ema_fast",
            "ema_slow",
            "price_vs_ema_atr",
            "rsi",
            "roc",
            "last_swing_high",
            "last_swing_low",
            "support",
            "resistance",
            "volume_zscore",
            "tick_volume",
        ]:
            t.close(f"B snapshot: {f}", getattr(a, f), getattr(b, f), f"{tag} {key}")
        for f in [
            "structure_trend",
            "bos_recent",
            "choch_recent",
            "regime",
            "bars_used",
            "bar_open",
            "bar_closed",
        ]:
            t.eq(f"B snapshot: {f}", getattr(a, f), getattr(b, f), f"{tag} {key}")
        for p in ("strong_body", "range_expansion"):
            t.eq(f"B snapshot: pattern {p}", a.patterns[p], b.patterns[p], f"{tag} {key}")


DECISION_FIELDS_FLOAT = [
    "entry_price",
    "stop_loss",
    "take_profit",
    "take_profit_2",
    "risk_reward",
    "required_win_rate",
    "risk_amount",
    "position_size",
    "atr",
]


def compare_decision(t: Tally, d1: Any, d2: Any, tag: str) -> None:
    t.eq("C decision: action", d1.decision.value, d2.action, tag)
    t.eq("C decision: refusals", tuple(r.value for r in d1.refusal_reasons), d2.refusals, tag)
    t.eq("C decision: reasons chain", tuple(d1.reasons), d2.reasons, tag)
    t.eq("C decision: warnings", tuple(d1.warnings), d2.warnings, tag)
    t.eq("C decision: m1_execution_state", d1.m1_execution_state, d2.m1_execution_state, tag)
    t.eq("C decision: decision_id (signal_id)", d1.signal_id, d2.decision_id, tag)
    t.close("C decision: atr", d1.atr, d2.atr, tag)
    if d1.decision.value != "WAIT" and d2.action != "WAIT":
        pairs = {
            "entry_price": d2.entry_price, "stop_loss": d2.stop_loss, "take_profit": d2.take_profit,
            "take_profit_2": d2.take_profit_2, "risk_reward": d2.net_rr,
            "required_win_rate": d2.required_win_rate, "risk_amount": d2.risk_amount,
            "position_size": d2.lots,
        }  # fmt: skip
        for name, value in pairs.items():
            t.close(f"C decision: {name}", getattr(d1, name), value, tag)
        t.eq("C decision: stop_model", d1.stop_model, d2.stop_model, tag)
        t.eq("C decision: expiry", d1.signal_expiry, d2.expiry, tag)
        t.eq("C decision: entry_quality", d1.entry_quality, d2.entry_quality, tag)
        t.eq("C decision: setup_id", d1.setup_id, d2.setup_id, tag)
        t.close("C decision: gross_rr", d1.metadata.get("gross_rr"), d2.gross_rr, tag)
        t.eq(
            "C decision: capped_by_structure",
            d1.metadata.get("capped_by_structure"),
            str(d2.capped_by_structure),
            tag,
        )


def context_variants(rng: random.Random, last_spread: float, price: float) -> list[dict[str, Any]]:
    """Mostly the happy path, plus every guard flag the chain knows about."""
    base = {
        "spread_points": last_spread,
        "news_state": "UNKNOWN",
        "equity": 10000.0,
        "bid": price - 0.1,
        "ask": price + 0.1,
        "market_open": True,
        "data_ok": True,
        "spec_known": True,
        "feed": True,
        "cooldown": False,
        "daily": False,
        "risk": False,
    }
    out = [base]
    out.append({**base, "equity": None, "bid": None, "ask": None})
    out.append({**base, "spread_points": None})
    out.append({**base, "spread_points": 1.0})
    out.append({**base, "spread_points": rng.choice([5.0, 40.0, 120.0])})
    flag = rng.choice(["market_open", "data_ok", "spec_known", "feed", "cooldown", "daily", "risk"])
    flipped = {
        "market_open": False,
        "data_ok": False,
        "spec_known": False,
        "feed": False,
        "cooldown": True,
        "daily": True,
        "risk": True,
    }
    out.append({**base, flag: flipped[flag]})
    out.append({**base, "news_state": rng.choice(["BLOCKED", "OK"])})
    return out


def v1_ctx(spec: v1_sizing.SymbolSpec, v: dict[str, Any]) -> V1Ctx:
    return V1Ctx(
        spec=spec, equity=v["equity"], broker_connected=v["feed"], cooldown_active=v["cooldown"],
        daily_limit_hit=v["daily"], risk_limit_hit=v["risk"], market_open=v["market_open"],
        market_status="OPEN" if v["market_open"] else "CLOSED", data_ok=v["data_ok"],
        spec_known=v["spec_known"], bid=v["bid"], ask=v["ask"],
    )  # fmt: skip


def v2_ctx(spec: v2_risk.SymbolSpec, v: dict[str, Any]) -> V2Ctx:
    return V2Ctx(
        spec=spec, equity=v["equity"], feed_connected=v["feed"], cooldown_active=v["cooldown"],
        daily_limit_hit=v["daily"], risk_limit_hit=v["risk"], market_open=v["market_open"],
        market_status="OPEN" if v["market_open"] else "CLOSED", data_ok=v["data_ok"],
        spec_known=v["spec_known"], bid=v["bid"], ask=v["ask"],
    )  # fmt: skip


def section_bc(
    t: Tally,
    months: int,
    per_month: int,
    scan_per_month: int,
    fixtures: list[dict[str, Any]],
    fixture_cap: int,
    relaxed: bool = False,
) -> dict[str, Any]:
    rng = random.Random(SEED)
    store = BarStore(DATA)
    spec_kw = {
        "point": 0.01, "tick_size": 0.01, "tick_value": 1.0, "contract_size": 100.0,
        "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01,
        "stops_level_points": 0, "freeze_level_points": 0, "digits": 2,
    }  # fmt: skip
    sp1, sp2 = v1_sizing.SymbolSpec(**spec_kw), v2_risk.SymbolSpec(**spec_kw)
    clock1, clock2 = V1Clock(ny_offset_hours=7), BrokerClock(ny_offset_hours=7)
    # relaxed: the volatility-percentile labels stop vetoing, so the plan path (stop, targets,
    # size, cost) is reached far more often; the arithmetic under test is the same
    cfg1 = BaselineConfig(
        allow_unknown_news=True, block_high_volatility=not relaxed, block_low_volatility=not relaxed
    )
    cfg2 = DecisionConfig(block_high_volatility=not relaxed, block_low_volatility=not relaxed)
    stats = {"months": [], "instants": 0, "actionable_found": 0, "actionable_compared": 0}
    for year, month in pick_months(rng, months):
        frames = load_month(store, year, month)
        if Timeframe.M5 not in frames or Timeframe.H4 not in frames:
            continue
        b1, b2 = build_pair(frames)
        m5 = frames[Timeframe.M5]
        start = datetime(year, month, 1, tzinfo=UTC)
        in_month = m5.filter(
            (pl.col("timestamp") >= start) & (pl.col("timestamp") < start + timedelta(days=28))
        )
        if in_month.height < 200:
            continue
        stamps = in_month["timestamp"].to_list()
        spreads = dict(zip(stamps, in_month["spread"].to_list(), strict=True))
        memo = SnapshotMemo()
        # stage 1: V2-only scan to find the actionable instants (they are rare)
        scan = rng.sample(stamps, min(scan_per_month, len(stamps)))
        chosen: list[datetime] = []
        for s in scan:
            at = s + timedelta(minutes=5, seconds=rng.randrange(0, 290))
            if not allowed(at):
                continue
            probe = 1.0 if relaxed else spreads[s]  # a clearly narrow spread: the plan path
            st2 = v2_build(b2, at, spread_points=probe, broker_clock=clock2, memo=memo)
            ctx = v2_ctx(sp2, context_variants(rng, probe, st2.price or 2000.0)[0])
            found = v2_decide(st2, ctx, cfg2)
            if found.action != "WAIT" or (relaxed and found.readiness_level >= 4):
                chosen.append(at)
        stats["actionable_found"] += len(chosen)
        randoms = [
            s + timedelta(minutes=5, seconds=rng.randrange(0, 290))
            for s in rng.sample(stamps, min(per_month, len(stamps)))
        ]
        instants = [(at, True) for at in chosen] + [(at, False) for at in randoms if allowed(at)]
        for at, is_action in instants:
            row = in_month.filter(pl.col("timestamp") <= at - timedelta(minutes=5))
            if row.height == 0:
                continue
            last_spread = float(row["spread"][-1])
            tag = f"{at.isoformat()}"
            news = rng.choice(["UNKNOWN", "UNKNOWN", "UNKNOWN", "BLOCKED", "OK"])
            s1 = v1_build(
                b1,
                at,
                spread_points=last_spread,
                news_state=news,
                broker_clock=clock1,
                market_open=True,
            )
            s2 = v2_build(
                b2, at, spread_points=last_spread, news_state=news, broker_clock=clock2, memo=memo
            )
            compare_state(t, s1, s2, tag)
            stats["instants"] += 1
            price = s2.price or 2000.0
            for i, v in enumerate(context_variants(rng, last_spread, price)):
                sx1 = v1_build(
                    b1,
                    at,
                    spread_points=v["spread_points"],
                    news_state=v["news_state"],
                    broker_clock=clock1,
                    market_open=v["market_open"],
                )
                sx2 = v2_build(
                    b2,
                    at,
                    spread_points=v["spread_points"],
                    news_state=v["news_state"],
                    broker_clock=clock2,
                    market_open=v["market_open"],
                    memo=memo,
                )
                d1 = v1_decide(sx1, v1_ctx(sp1, v), cfg1)
                d2 = v2_decide(sx2, v2_ctx(sp2, v), cfg2)
                compare_decision(t, d1, d2, f"{tag} variant{i}")
                if d1.decision.value != "WAIT":
                    stats["actionable_compared"] += 1
                if len(fixtures) < fixture_cap and (
                    d1.decision.value != "WAIT" or rng.random() < 0.05
                ):
                    fixtures.append(fixture(sx1, v, d1))
        stats["months"].append(f"{year}-{month:02d}")
    return stats


def fixture(state: Any, v: dict[str, Any], d1: Any) -> dict[str, Any]:
    """A self-contained decision case: the V1 state fields the chain reads + V1's answer."""
    snaps = {
        k: {
            "bar_open": s.bar_open.isoformat(),
            "bar_closed": s.bar_closed.isoformat(),
            "last_swing_high": s.last_swing_high,
            "last_swing_low": s.last_swing_low,
        }
        for k, s in state.snapshots.items()
        if k == "M5"
    }
    keys = [
        "symbol",
        "volume_type",
        "h4_regime",
        "h1_trend",
        "m30_structure",
        "m15_structure",
        "m15_pullback",
        "m5_momentum",
        "m1_micro_state",
        "atr_m5",
        "atr_m15",
        "volume_zscore_m1",
        "spread",
        "spread_percentile",
        "spread_to_atr_m5",
        "session",
        "price",
        "distance_to_support",
        "distance_to_resistance",
        "recent_swing_high",
        "recent_swing_low",
        "bos_state",
        "choch_state",
        "volatility_regime",
        "data_quality",
        "news_state",
        "execution_quality",
        "available_timeframes",
        "stale_timeframes",
        "spread_state",
        "volume_state",
        "market_open",
    ]
    sd = {
        k: (list(getattr(state, k)) if isinstance(getattr(state, k), tuple) else getattr(state, k))
        for k in keys
    }
    sd["timestamp"] = state.timestamp.isoformat()
    sd["snapshots"] = snaps
    expected = {
        "action": d1.decision.value,
        "refusals": [r.value for r in d1.refusal_reasons],
        "reasons": list(d1.reasons),
        "warnings": list(d1.warnings),
        "m1_execution_state": d1.m1_execution_state,
        "decision_id": d1.signal_id,
        "atr": d1.atr,
        "entry_price": d1.entry_price,
        "stop_loss": d1.stop_loss,
        "take_profit": d1.take_profit,
        "take_profit_2": d1.take_profit_2,
        "net_rr": d1.risk_reward,
        "required_win_rate": d1.required_win_rate,
        "risk_amount": d1.risk_amount,
        "lots": d1.position_size,
        "stop_model": d1.stop_model,
        "expiry": None if d1.signal_expiry is None else d1.signal_expiry.isoformat(),
        "entry_quality": d1.entry_quality,
        "setup_id": d1.setup_id,
    }
    return {"state": sd, "context": v, "expected": expected}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--fixtures", type=Path, default=None)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument(
        "--plans", action="store_true", help="relaxed volatility vetoes, plan-path coverage"
    )
    args = ap.parse_args()
    t = Tally()
    t0 = time.time()
    if not args.plans:
        section_a(t, 12 if args.quick else 60)
    print(f"A done {time.time() - t0:.0f}s", flush=True)
    fixtures: list[dict[str, Any]] = []
    stats = section_bc(
        t,
        months=4 if args.quick else (10 if args.plans else 30),
        per_month=12 if args.quick else (10 if args.plans else 40),
        scan_per_month=60 if args.quick else (3000 if args.plans else 400),
        fixtures=fixtures,
        fixture_cap=400,
        relaxed=args.plans,
    )
    elapsed = time.time() - t0
    report = t.report()
    total = sum(r["checks"] for r in report.values())
    bad = sum(r["mismatches"] for r in report.values())
    for group, r in report.items():
        flag = "OK " if r["mismatches"] == 0 else "BAD"
        print(
            f"[{flag}] {r['checks']:7d} checks {r['mismatches']:4d} mismatches  max|d|={r['max_abs_diff']:.2e}  {group}"
        )
        for sample in r["samples"]:
            print("      ", sample)
    print(f"stats: {json.dumps(stats)}")
    print(f"total {total} checks, {bad} mismatches, {elapsed:.0f}s")
    if args.out:
        args.out.write_text(
            json.dumps(
                {
                    "groups": report,
                    "stats": stats,
                    "total": total,
                    "mismatches": bad,
                    "seed": SEED,
                    "elapsed_s": elapsed,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    if args.fixtures and fixtures:
        args.fixtures.parent.mkdir(parents=True, exist_ok=True)
        args.fixtures.write_text(json.dumps({"seed": SEED, "cases": fixtures}), encoding="utf-8")
        print(f"wrote {len(fixtures)} decision fixtures to {args.fixtures}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
