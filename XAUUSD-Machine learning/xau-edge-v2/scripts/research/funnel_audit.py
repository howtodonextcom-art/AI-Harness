"""Signal-funnel audit of the V1-locked decision core (descriptive, no outcomes, no tuning).

For every closed M5 bar of the sampled months it records the hierarchical state, the hard gates,
the first failing link of the chain (hard gates neutralised) and the final action. It never looks
at what price did next, so it burns nothing: it only COUNTS how often each link passes.

Locked windows (Test-H 2022-01-01..2025-04-30, Holdout 2026-05-01..2026-10-07) are refused.

    uv run python scripts/research/funnel_audit.py --out data/research/funnel --jobs 6
"""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

for _v in ("POLARS_MAX_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "1"  # one core per worker: the machine must stay usable

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "src"))

import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

from xau_edge_v2.config import Settings  # noqa: E402
from xau_edge_v2.core import decision as dec  # noqa: E402
from xau_edge_v2.core.frames import ORDER, MultiFrames  # noqa: E402
from xau_edge_v2.core.market_state import SnapshotMemo, build_market_state  # noqa: E402
from xau_edge_v2.core.risk import SymbolSpec  # noqa: E402
from xau_edge_v2.data.bar_store import BarStore  # noqa: E402
from xau_edge_v2.data.frames import frame_from_polars  # noqa: E402
from xau_edge_v2.domain.contract import Timeframe  # noqa: E402
from xau_edge_v2.domain.market import BrokerClock  # noqa: E402

LOCKED = (
    (datetime(2022, 1, 1, tzinfo=UTC), datetime(2025, 5, 1, tzinfo=UTC)),
    (datetime(2026, 5, 1, tzinfo=UTC), datetime(2026, 10, 8, tzinfo=UTC)),
)
BACK = {"M1": 3, "M5": 7, "M15": 14, "M30": 25, "H1": 40, "H4": 140}
SPEC = SymbolSpec()
CTX = dec.DecisionContext(spec=SPEC, equity=10_000.0)
ORIGINAL_GATES = dec._gates


def locked(at: datetime) -> bool:
    return any(lo <= at < hi for lo, hi in LOCKED)


def load(store: BarStore, start: datetime, end: datetime) -> dict[Timeframe, pl.DataFrame]:
    out: dict[Timeframe, pl.DataFrame] = {}
    for tf in ORDER:
        lo = start - timedelta(days=BACK[tf.value])
        parts: list[pl.DataFrame] = []
        cursor = lo
        while True:
            df = store.window(tf, cursor, end, 5000)
            if df.height == 0:
                break
            parts.append(df)
            if df.height < 5000:
                break
            cursor = df["timestamp"][-1] + timedelta(seconds=1)
        if parts:
            out[tf] = pl.concat(parts, how="vertical_relaxed")
    return out


def run_month(args: tuple[str, int, int]) -> str:
    root, year, month = args
    start = datetime(year, month, 1, tzinfo=UTC)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=UTC)
    if locked(start) or locked(end - timedelta(seconds=1)):
        msg = f"{year}-{month:02d} touches a locked window"
        raise RuntimeError(msg)
    store = BarStore(Path(root), cache_seconds=0.0)
    frames = load(store, start, end)
    if Timeframe.M5 not in frames:
        return f"{year}-{month:02d}: no M5"
    multi = MultiFrames({tf: f for tf, df in frames.items() if (f := frame_from_polars(tf, df))})
    m5 = frames[Timeframe.M5]
    ts = m5["timestamp"].dt.epoch("us").to_numpy().astype(np.int64)
    closes = [t for t in ts if start <= datetime.fromtimestamp(t / 1e6, UTC) < end]
    clock = BrokerClock(ny_offset_hours=7)
    memo = SnapshotMemo()
    cfg = dec.DecisionConfig()
    rows: list[dict[str, object]] = []
    for open_us in closes:
        at = datetime.fromtimestamp(open_us / 1e6, UTC) + timedelta(minutes=5)
        state = build_market_state(multi, at, broker_clock=clock, memo=memo)
        if state.h1_trend == "UNKNOWN" or state.price is None:
            continue
        gates, _ = ORIGINAL_GATES(state, CTX, cfg)
        dec._gates = lambda *_a, **_k: ([], ())
        try:
            chain = dec.decide(state, CTX, cfg)
        finally:
            dec._gates = ORIGINAL_GATES
        real = dec.decide(state, CTX, cfg) if gates else chain
        rows.append(
            {
                "ts": at,
                "year": at.year,
                "session": state.session,
                "h4": state.h4_regime,
                "h1": state.h1_trend,
                "m15": state.m15_structure,
                "pullback": state.m15_pullback,
                "m5": state.m5_momentum,
                "m1micro": state.m1_micro_state,
                "m1exec": chain.m1_execution_state,
                "vol": state.volatility_regime,
                "execq": state.execution_quality,
                "spread": state.spread,
                "spread_pct": state.spread_percentile,
                "spread_atr": state.spread_to_atr_m5,
                "atr15": state.atr_m15,
                "price": state.price,
                "d_res": state.distance_to_resistance,
                "d_sup": state.distance_to_support,
                "gates": "|".join(sorted({g.value for g in gates})),
                "chain_action": chain.action,
                "chain_refusal": "|".join(chain.refusals),
                "level": chain.readiness_level,
                "real_action": real.action,
                "real_refusal": "|".join(real.refusals),
                "net_rr": chain.net_rr,
                "gross_rr": chain.gross_rr,
                "capped": chain.capped_by_structure,
                "stop_model": chain.stop_model,
                "entry": chain.entry_price,
                "sl": chain.stop_loss,
                "tp": chain.take_profit,
            }
        )
    out = Path(root).parent  # unused; keeps mypy quiet about the tuple
    del out
    path = OUT / f"{year}-{month:02d}.parquet"
    pl.DataFrame(rows, infer_schema_length=None).write_parquet(path) if rows else None
    return f"{year}-{month:02d}: {len(rows)} rows"


OUT = Path("data/research/funnel")


def main() -> None:
    global OUT  # noqa: PLW0603
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="data/research/funnel")
    p.add_argument("--jobs", type=int, default=4)
    p.add_argument("--months", default="", help="comma list YYYY-MM; default: the sample plan")
    a = p.parse_args()
    OUT = Path(a.out)
    OUT.mkdir(parents=True, exist_ok=True)
    if a.months:
        pairs = [tuple(map(int, m.split("-"))) for m in a.months.split(",")]
    else:
        pairs = [(y, m) for y in range(2011, 2022) for m in (2, 6, 10)]
        pairs += [(2025, m) for m in range(5, 13)] + [(2026, m) for m in range(1, 5)]
    root = str(Settings().data_root)
    jobs = [(root, y, m) for y, m in pairs if not (OUT / f"{y}-{m:02d}.parquet").exists()]
    with ProcessPoolExecutor(a.jobs, initializer=_init, initargs=(str(OUT),)) as ex:
        for line in ex.map(run_month, jobs):
            print(line, flush=True)


def _init(out: str) -> None:
    global OUT  # noqa: PLW0603
    OUT = Path(out)
    if os.name == "nt":  # BELOW_NORMAL_PRIORITY_CLASS
        import ctypes  # noqa: PLC0415

        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)


if __name__ == "__main__":
    main()
