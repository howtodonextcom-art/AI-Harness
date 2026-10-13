"""Descriptive study of the market-intelligence events on APPROVED development data (no outcomes).

What it measures (structure of the labels only, never what price did afterwards, never P&L):
* how often each price-action / structure event occurs (per 1000 bars);
* causality on real history: known_at is the close of the event's own bar, and cutting the history
  at random points never changes an event already emitted (repaint test);
* swing confirmation lag (bars between the pivot and the moment it is known);
* structural failure share: BOS/CHoCH followed by a lost break within 3 bars;
* regime occupancy and persistence (mean run length, switches per 1000 bars) of the strategy's
  own regime labels, and volatility-phase occupancy.

Window: DEV' months 2016-01..2018-12 of the CLEAN store (PASS months only, manifest and file hashes
verified by ``CleanBarStore``). Test-H, Holdout, Confirm-C, Validation and the quarantined months are
never read. The result is evidence about LABEL BEHAVIOUR; it says nothing about trading edge.

    uv run python scripts/research/intel_descriptive.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

for _v in ("POLARS_MAX_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "1"

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

from xau_edge_v2.core import indicators as ind  # noqa: E402
from xau_edge_v2.core import structure as st  # noqa: E402
from xau_edge_v2.core.intelligence import families as fam  # noqa: E402
from xau_edge_v2.core.intelligence import price_action as pa  # noqa: E402
from xau_edge_v2.core.intelligence import structure_events as se  # noqa: E402
from xau_edge_v2.core.intelligence import volatility as vol  # noqa: E402
from xau_edge_v2.data.frames import frame_from_polars  # noqa: E402
from xau_edge_v2.domain.contract import Timeframe  # noqa: E402
from xau_edge_v2.research.clean_store import CleanBarStore  # noqa: E402

START = datetime(2016, 1, 1, tzinfo=UTC)
END = datetime(2019, 1, 1, tzinfo=UTC)  # exclusive: DEV' ends 2018-12
WARMUP = timedelta(days=45)
SAMPLE_EVERY = 40
CUTS = 25
SEED = 20261013


def load(store: CleanBarStore, tf: Timeframe):  # type: ignore[no-untyped-def]
    parts: list[pl.DataFrame] = []
    cursor = START - WARMUP
    while True:
        df = store.window(tf, cursor, END - timedelta(seconds=1), 5000)
        if df.height == 0:
            break
        parts.append(df)
        if df.height < 5000:
            break
        cursor = df["timestamp"][-1] + timedelta(seconds=1)
    frame = frame_from_polars(tf, pl.concat(parts, how="vertical_relaxed"))
    assert frame is not None
    return frame


def runs(labels: np.ndarray) -> dict[str, float]:  # type: ignore[type-arg]
    lab = np.array([str(x) for x in labels])
    change = np.flatnonzero(lab[1:] != lab[:-1])
    lengths = np.diff(np.concatenate([[0], change + 1, [lab.size]]))
    return {
        "mean_run_bars": float(lengths.mean()),
        "median_run_bars": float(np.median(lengths)),
        "switches_per_1000_bars": float(1000.0 * change.size / lab.size),
    }


def study(store: CleanBarStore, tf: Timeframe, rng: np.random.Generator) -> dict[str, object]:
    f = load(store, tf)
    first = int(np.searchsorted(f.open_us, int(START.timestamp() * 1_000_000)))
    n_scored = f.height - first
    events = [e for e in pa.detect(f) if e.index >= first]
    counts: dict[str, int] = dict.fromkeys(pa.KINDS, 0)
    for e in events:
        counts[e.kind] += 1
        assert e.known_at_us == int(f.available_us[e.index])
    sev = [e for e in se.structure_events(f) if e.index >= first]
    scount: dict[str, int] = {}
    for e in sev:
        scount[e.kind] = scount.get(e.kind, 0) + 1
    breaks = sum(v for k, v in scount.items() if k.startswith(("BOS", "CHOCH")))
    failed = sum(v for k, v in scount.items() if k.startswith("FAILED_BREAK"))
    swings = [s for s in se.swings(f) if s.confirmed and s.index >= first]
    lags = {int(np.searchsorted(f.available_us, s.known_at_us)) - s.index for s in swings}

    # repaint test on real history: cut at random points, compare with the full run
    full_pa = pa.detect(f)
    full_se = se.structure_events(f)
    mismatches = 0
    for cut in rng.integers(first + 200, f.height - 5, CUTS):
        head = f.head(int(cut))
        if pa.detect(head) != [e for e in full_pa if e.index < cut]:
            mismatches += 1
        if se.structure_events(head) != [e for e in full_se if e.index < cut]:
            mismatches += 1

    atr = ind.atr(f.high, f.low, f.close, 14)
    adx = ind.adx(f.high, f.low, f.close, 14)
    regime = st.classify_regime(
        adx=adx.adx, plus_di=adx.plus_di, minus_di=adx.minus_di, atr=atr,
        high=f.high, low=f.low, vol_window=200, min_history=60,
    )  # fmt: skip
    scored = regime[first:]
    known = scored[np.array([x is not None for x in scored])]
    occupancy = {str(k): float((known == k).mean()) for k in sorted({str(x) for x in known})}

    phases: dict[str, int] = {}
    box_up = box_down = 0
    for i in range(first + 300, f.height, SAMPLE_EVERY):
        v = vol.analyse(f.head(i).tail(300))
        phases[v.phase] = phases.get(v.phase, 0) + 1
        box_up += int(v.box_breakout > 0)
        box_down += int(v.box_breakout < 0)
    sampled = sum(phases.values())
    opportunity: dict[str, object] = {}
    for name, signals in fam.all_families(f).items():
        kept = [x for x in signals if x.index >= first]
        risks = [x.risk_atr for x in kept]
        opportunity[name] = {
            "eligible_per_1000_bars": round(1000 * len(kept) / n_scored, 2),
            "n": len(kept),
            "buy_side": sum(1 for x in kept if x.side > 0),
            "sell_side": sum(1 for x in kept if x.side < 0),
            "median_risk_atr": None if not risks else round(float(np.median(risks)), 2),
            "p90_risk_atr": None if not risks else round(float(np.percentile(risks, 90)), 2),
        }
    return {
        "family_eligibility_no_outcomes": opportunity,
        "timeframe": tf.value,
        "bars_scored": int(n_scored),
        "price_action_per_1000_bars": {k: round(1000 * v / n_scored, 2) for k, v in counts.items()},
        "structure_events": scount,
        "structure_failure_share": None if breaks == 0 else round(failed / breaks, 4),
        "swing_confirmation_lag_bars": sorted(lags),
        "repaint_mismatches_in_random_cuts": mismatches,
        "random_cuts_tested": CUTS,
        "regime_occupancy": {k: round(v, 4) for k, v in occupancy.items()},
        "regime_persistence": runs(known),
        "volatility_phase_sample": {k: round(v / sampled, 4) for k, v in phases.items()},
        "volatility_phase_sample_size": sampled,
        "box_breakout_samples": {"up": box_up, "down": box_down},
    }


def main() -> None:
    store = CleanBarStore(ROOT / "data" / "clean_store")
    rng = np.random.default_rng(SEED)
    result = {
        "purpose": "label behaviour on approved development data; NOT an outcome, NOT edge",
        "window": "DEV' 2016-01..2018-12 (clean store, PASS months only)",
        "manifest_sha256": store.manifest.get("manifest_sha256"),
        "protected_windows_read": [],
        "outcomes_read": False,
        "seed": SEED,
        "timeframes": [study(store, tf, rng) for tf in (Timeframe.H1, Timeframe.M15)],
    }
    out = ROOT / "docs" / "research" / "intel_descriptive_dev.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
