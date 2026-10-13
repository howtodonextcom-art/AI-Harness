"""Stage A of MULTIFAMILY_RESEARCH_0.1.0 on DEV': signal-only report (NO outcome, NO PnL).

Reads M15 of the CLEAN store (PASS months of DEV' 2005-06..2018-12, manifest and file hashes verified),
builds the complete contract of families B, C and D (``research/multifamily.py``) and reports:
raw eligibility, episodes, signals after the cost and structural gates, direction balance,
regime/session distribution, overlap between families, geometry feasibility, a research power
estimate, and the dedicated Family D study (RANGE persistence, boundary causality and stability).

The Family D persistence study looks at labels that come AFTER a signal bar (does the RANGE label
persist?). That is a description of label stability for this report only; it never feeds a signal.

    uv run python scripts/research/multifamily_stage_a.py
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
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
from xau_edge_v2.core.frames import Frame  # noqa: E402
from xau_edge_v2.core.intelligence import families as fam  # noqa: E402
from xau_edge_v2.data.frames import frame_from_polars  # noqa: E402
from xau_edge_v2.domain.contract import Timeframe  # noqa: E402
from xau_edge_v2.research import multifamily as mf  # noqa: E402
from xau_edge_v2.research.clean_store import CleanBarStore  # noqa: E402
from xau_edge_v2.research.stats import n_required  # noqa: E402

START = datetime(2005, 11, 1, tzinfo=UTC)
END = datetime(2019, 1, 1, tzinfo=UTC)
WARMUP = timedelta(days=45)
PERSIST_AHEAD = (6, 12, 24)
DELTAS = (0.20, 0.30)


def load(store: CleanBarStore) -> Frame:
    parts: list[pl.DataFrame] = []
    cursor = datetime(2005, 6, 1, tzinfo=UTC)
    while True:
        df = store.window(Timeframe.M15, cursor, END - timedelta(seconds=1), 5000)
        if df.height == 0:
            break
        parts.append(df)
        if df.height < 5000:  # noqa: PLR2004
            break
        cursor = df["timestamp"][-1] + timedelta(seconds=1)
    frame = frame_from_polars(Timeframe.M15, pl.concat(parts, how="vertical_relaxed"))
    assert frame is not None
    return frame


def q(values: list[float], p: float) -> float | None:
    return None if not values else round(float(np.percentile(values, p)), 3)


def dist(values: list[float]) -> dict[str, float | None]:
    return {"p10": q(values, 10), "p50": q(values, 50), "p90": q(values, 90), "n": len(values)}  # type: ignore[dict-item]


def balance(rs: list[mf.MfRecord]) -> dict[str, int]:
    return {"buy": sum(1 for r in rs if r.side > 0), "sell": sum(1 for r in rs if r.side < 0)}


def runs(mask: np.ndarray) -> list[int]:
    out, n = [], 0
    for x in mask:
        if x:
            n += 1
        elif n:
            out.append(n)
            n = 0
    if n:
        out.append(n)
    return out


def d_study(f: Frame, recs: list[mf.MfRecord], first: int) -> dict[str, object]:
    atr = ind.atr(f.high, f.low, f.close, 14)
    adx = ind.adx(f.high, f.low, f.close, 14)
    regime = st.classify_regime(
        adx=adx.adx, plus_di=adx.plus_di, minus_di=adx.minus_di, atr=atr,
        high=f.high, low=f.low, vol_window=200, min_history=60,
    )  # fmt: skip
    is_range = np.array([x == "RANGE" for x in regime])
    rr = runs(is_range[first:])
    heads = [r for r in recs if r.family == "D" and r.episode_head and r.index >= first]
    age: list[float] = []
    ahead: dict[int, list[bool]] = {k: [] for k in PERSIST_AHEAD}
    width: list[float] = []
    stable: list[bool] = []
    touches: list[int] = []
    for r in heads:
        i = r.index
        j = i
        while j > 0 and is_range[j - 1]:
            j -= 1
        age.append(i - j + 1)
        for k in PERSIST_AHEAD:
            if i + k < f.height:
                ahead[k].append(bool(is_range[i : i + k + 1].all()))
        top = float(f.high[i - fam.RANGE_LOOKBACK : i].max())
        bottom = float(f.low[i - fam.RANGE_LOOKBACK : i].min())
        a = float(atr[i])
        width.append((top - bottom) / a)
        if i + 6 < f.height:
            top6 = float(f.high[i + 6 - fam.RANGE_LOOKBACK : i + 6].max())
            bot6 = float(f.low[i + 6 - fam.RANGE_LOOKBACK : i + 6].min())
            stable.append(top6 == top and bot6 == bottom)
        edge = bottom if r.side > 0 else top
        win = (
            f.low[i - fam.RANGE_LOOKBACK : i] if r.side > 0 else f.high[i - fam.RANGE_LOOKBACK : i]
        )
        touches.append(int((np.abs(win - edge) <= fam.RANGE_TOUCH_ATR * a).sum()))
    return {
        "note": "labels AFTER the signal bar are used only to describe RANGE stability; never in a signal",
        "range_label_share": round(float(is_range[first:].mean()), 4),
        "range_runs": {
            "n_runs": len(rr),
            "median_bars": q([float(x) for x in rr], 50),
            "p25_bars": q([float(x) for x in rr], 25),
            "p75_bars": q([float(x) for x in rr], 75),
            "share_of_runs_ge_12_bars": None
            if not rr
            else round(sum(x >= 12 for x in rr) / len(rr), 4),  # noqa: PLR2004
            "share_of_runs_ge_24_bars": None
            if not rr
            else round(sum(x >= 24 for x in rr) / len(rr), 4),  # noqa: PLR2004
            "share_of_range_bars_in_runs_ge_24": None
            if not rr
            else round(sum(x for x in rr if x >= 24) / sum(rr), 4),  # noqa: PLR2004
        },
        "d_episode_heads": len(heads),
        "range_age_at_signal_bars": dist(age),
        "range_persists_after_signal": {
            f"next_{k}_bars": None if not v else round(sum(v) / len(v), 4) for k, v in ahead.items()
        },
        "boundary_causality": "top/bottom of the 20 bars BEFORE the signal bar (tested by head-cut equality)",
        "boundary_width_atr": dist(width),
        "boundary_unchanged_6_bars_later_share": None
        if not stable
        else round(sum(stable) / len(stable), 4),
        "prior_touches_of_the_edge_within_0.25_atr": dist([float(t) for t in touches]),
        "valid_order_share_of_heads": None
        if not heads
        else round(sum(1 for r in heads if r.accepted) / len(heads), 4),
        "first_refusal_of_heads": dict(Counter(r.first_refusal or "ACCEPTED" for r in heads)),
    }


def main() -> None:
    store = CleanBarStore(ROOT / "data" / "clean_store")
    f = load(store)
    first = int(np.searchsorted(f.open_us, int(START.timestamp() * 1_000_000)))
    n_scored = f.height - first
    years = n_scored * 900 / (365.25 * 86400) / (5 / 7) / 1.0
    recs = [r for r in mf.evaluate_frame(f) if r.index >= first]
    out: dict[str, object] = {
        "purpose": "Stage A signal-only report for MULTIFAMILY_RESEARCH_0.1.0 (no outcome, no PnL)",
        "window": "DEV' 2005-11..2018-12 (clean store, PASS months)",
        "manifest_sha256": store.manifest.get("manifest_sha256"),
        "protected_windows_read": [],
        "outcomes_read": False,
        "bars_scored_m15": n_scored,
        "approx_trading_years": round(years, 2),
        "contract": "docs/research/multifamily_0.1.0.spec.json",
    }
    families: dict[str, object] = {}
    for name in fam.FAMILIES:
        rs = [r for r in recs if r.family == name]
        heads = [r for r in rs if r.episode_head]
        acc = [r for r in heads if r.accepted]
        free = [r for r in acc if not r.overlap]
        survive: dict[str, int] = {"RAW": len(rs), "EPISODES": len(heads)}
        alive = heads
        for gate in mf.GATES[1:]:
            alive = [r for r in alive if r.first_refusal != gate]
            survive[f"AFTER_{gate}"] = len(alive)
        refused = Counter(r.first_refusal or "ACCEPTED" for r in heads)
        per_year = Counter(datetime.fromtimestamp(r.known_at_us / 1e6, UTC).year for r in free)
        rate = len(free) / years if years else 0.0
        families[name] = {
            "raw_eligibility": {
                "n": len(rs),
                "per_1000_bars": round(1000 * len(rs) / n_scored, 2),
                **balance(rs),
            },
            "episodes": {"n": len(heads), **balance(heads)},
            "funnel_survivors": survive,
            "first_refusal_of_episodes": dict(refused),
            "accepted_signals": {"n": len(acc), **balance(acc)},
            "accepted_without_overlap": {
                "n": len(free),
                **balance(free),
                "per_year": rate and round(rate, 2),
            },
            "overlap_flagged": len(acc) - len(free),
            "regime_of_raw": dict(Counter(r.regime or "NONE" for r in rs)),
            "regime_of_accepted": dict(Counter(r.regime or "NONE" for r in acc)),
            "session_of_raw": dict(Counter(r.session for r in rs)),
            "session_of_accepted": dict(Counter(r.session for r in acc)),
            "per_year_accepted_without_overlap": {str(k): v for k, v in sorted(per_year.items())},
            "geometry_feasibility": {
                "episodes_with_valid_stop_share": round(
                    sum(r.stop is not None for r in heads) / max(1, len(heads)), 4
                ),
                "risk_atr_of_valid_stops": dist(
                    [r.risk_atr for r in heads if r.risk_atr is not None]
                ),
                "opposing_level_distance_atr": dist(
                    [r.opposing_atr for r in heads if r.opposing_atr is not None]
                ),
                "with_target_share_of_valid_stops": round(
                    sum(r.target is not None for r in heads)
                    / max(1, sum(r.stop is not None for r in heads)),
                    4,
                ),
                "net_rr_of_valid_targets": dist([r.net_rr for r in heads if r.net_rr is not None]),
                "target_capped_by_structure_share": round(
                    sum(r.capped_by_structure for r in heads if r.target is not None)
                    / max(1, sum(r.target is not None for r in heads)),
                    4,
                ),
                "cost_r_of_valid_orders": dist([r.cost_r for r in heads if r.cost_r is not None]),
            },
            "research_power": {f"n_required_for_{d:.2f}R": n_required(d) for d in DELTAS}
            | {
                f"years_to_reach_n_for_{d:.2f}R": None
                if rate <= 0
                else round(n_required(d) / rate, 1)
                for d in DELTAS
            }
            | {"accepted_without_overlap_available": len(free)},
        }
    out["families"] = families
    # overlap between families (accepted episode heads, same side within 6 bars)
    accepted = [r for r in recs if r.episode_head and r.accepted]
    pairs: dict[str, dict[str, int]] = {}
    for a_name, b_name in (("B", "C"), ("B", "D"), ("C", "D")):
        a_list = [r for r in accepted if r.family == a_name]
        b_idx: dict[int, list[int]] = {}
        for r in accepted:
            if r.family == b_name:
                b_idx.setdefault(r.index, []).append(r.side)
        same = opposite = 0
        for r in a_list:
            sides = [s for k in range(r.index - 6, r.index + 7) for s in b_idx.get(k, [])]
            same += int(any(s == r.side for s in sides))
            opposite += int(any(s == -r.side for s in sides))
        pairs[f"{a_name}x{b_name}"] = {
            f"{a_name}_accepted": len(a_list),
            "same_side_within_6_bars": same,
            "opposite_side_within_6_bars": opposite,
        }
    out["overlap_between_families"] = pairs
    out["family_D_study"] = d_study(f, recs, first)
    pq = ROOT / "data" / "research" / "multifamily_signals_dev.parquet"
    pq.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        [
            {
                "family": r.family,
                "side": r.side,
                "index": r.index,
                "known_at_us": r.known_at_us,
                "episode_head": r.episode_head,
                "entry": r.entry,
                "stop": r.stop,
                "target": r.target,
                "risk_atr": r.risk_atr,
                "net_rr": r.net_rr,
                "cost_r": r.cost_r,
                "opposing_atr": r.opposing_atr,
                "session": r.session,
                "regime": r.regime,
                "first_refusal": r.first_refusal,
                "overlap": r.overlap,
                "expiry_us": r.expiry_us,
            }
            for r in recs
        ],
        infer_schema_length=None,
    ).write_parquet(pq)
    path = ROOT / "docs" / "research" / "multifamily_stage_a_dev.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
