"""Stage A of the candidate evaluation: every variant's signals, month by month (no outcomes).

For each closed M5 bar it builds the market state ONCE, then runs every frozen variant of
``docs/research/cand_v2_spec.json`` (control included) through ``candidate_step``. It writes only
what the strategies SAID (side, entry quote, stop, target, net R:R, cost_R, lifecycle); it never
looks at what price did afterwards. Outcomes are Stage B (``cand_simulate.py``) and run only after
the spec hash is recorded.

Resumable: one output pair per month, existing months are skipped. Windows locked for confirmation
are refused (Test-H, Holdout; and Validation / Confirm-C unless --confirm is given, which the freeze
gate controls).

    uv run python scripts/research/cand_signals.py --window DEV --out data/research/cand --jobs 4
"""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

for _v in ("POLARS_MAX_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "1"

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "src"))
sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402
import polars as pl  # noqa: E402
from funnel_audit import load, locked  # noqa: E402

from xau_edge_v2.config import Settings  # noqa: E402
from xau_edge_v2.core import indicators as ind  # noqa: E402
from xau_edge_v2.core.candidate import (  # noqa: E402
    VARIANTS,
    Memory,
    Observation,
    candidate_step,
    config_for,
)
from xau_edge_v2.core.decision import DecisionContext  # noqa: E402
from xau_edge_v2.core.frames import Frame, MultiFrames  # noqa: E402
from xau_edge_v2.core.market_state import POINT, SnapshotMemo, build_market_state  # noqa: E402
from xau_edge_v2.core.risk import SymbolSpec  # noqa: E402
from xau_edge_v2.core.structure import SHOCK_RANGE_ATR  # noqa: E402
from xau_edge_v2.data.bar_store import BarStore  # noqa: E402
from xau_edge_v2.data.frames import frame_from_polars  # noqa: E402
from xau_edge_v2.domain.contract import Timeframe  # noqa: E402
from xau_edge_v2.domain.market import BrokerClock  # noqa: E402
from xau_edge_v2.research.clean_view import require_clean  # noqa: E402

SPEC = SymbolSpec()
WINDOWS = {
    "DEV": ((2011, 1), (2018, 12)),
    "VALIDATION": ((2019, 1), (2021, 12)),
    "CONFIRM_C": ((2025, 5), (2026, 4)),
}
WARMUP_BARS = 40
MINUTE = timedelta(minutes=1)


def months_of(window: str) -> list[tuple[int, int]]:
    (y0, m0), (y1, m1) = WINDOWS[window]
    out, y, m = [], y0, m0
    while (y, m) <= (y1, m1):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)  # noqa: PLR2004
    return out


class ShockCache:
    """SHOCK from the spec: a closed M15 (last 2) or H1 (last 1) bar with range >= 3 x the previous ATR."""

    def __init__(self) -> None:
        self._memo: dict[tuple[str, int], bool] = {}

    def recent(self, frame: Frame | None, bars: int) -> bool:
        if frame is None or frame.height < 20:  # noqa: PLR2004
            return False
        key = (frame.timeframe.value, int(frame.open_us[-1]))
        if key not in self._memo:
            t = frame.tail(60)
            atr = ind.atr(t.high, t.low, t.close, 14)
            rng = t.high - t.low
            hit = False
            for i in range(t.height - bars, t.height):
                prev = atr[i - 1]
                hit = hit or bool(
                    np.isfinite(prev) and prev > 0 and rng[i] >= SHOCK_RANGE_ATR * prev
                )
            if len(self._memo) > 4096:  # noqa: PLR2004
                self._memo.clear()
            self._memo[key] = hit
        return self._memo[key]


def run_month(args: tuple[str, int, int, str]) -> str:  # noqa: PLR0915 - one pass over the bars
    root, year, month, out_dir = args
    out = Path(out_dir)
    sig_path, bar_path = (
        out / f"sig_{year}-{month:02d}.parquet",
        out / f"bars_{year}-{month:02d}.parquet",
    )
    if sig_path.exists() and bar_path.exists():
        return f"{year}-{month:02d}: skipped"
    start = datetime(year, month, 1, tzinfo=UTC)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=UTC)  # noqa: PLR2004
    if locked(start) or locked(end - timedelta(seconds=1)):
        msg = f"{year}-{month:02d} touches a locked window"
        raise RuntimeError(msg)
    frames = load(BarStore(Path(root), cache_seconds=0.0), start - timedelta(days=2), end)
    if Timeframe.M5 not in frames or Timeframe.M1 not in frames:
        return f"{year}-{month:02d}: missing M1/M5"
    if (
        os.environ.get("XAU_ALLOW_DEFECTIVE") != "1"
    ):  # ADR-V2-018: never evaluate on the pseudo-bar months
        for tf in (Timeframe.M1, Timeframe.M5, Timeframe.H1):
            require_clean(frames[tf], f"{year}-{month:02d} {tf.value}")
    multi = MultiFrames({tf: f for tf, df in frames.items() if (f := frame_from_polars(tf, df))})
    m1 = frames[Timeframe.M1]
    m1_open = m1["timestamp"].dt.epoch("us").to_numpy().astype(np.int64)
    m1_close, m1_spread = m1["close"].to_numpy(), m1["spread"].fill_null(0.0).to_numpy()
    m5_open = frames[Timeframe.M5]["timestamp"].dt.epoch("us").to_numpy().astype(np.int64)
    first = int(np.searchsorted(m5_open, int(start.timestamp() * 1e6)))
    closes = m5_open[max(0, first - WARMUP_BARS) :]
    clock, memo, shock_cache = BrokerClock(ny_offset_hours=7), SnapshotMemo(), ShockCache()
    cfgs = {v: config_for(v) for v in VARIANTS}
    mems = {v: Memory() for v in VARIANTS}
    signals: list[dict[str, object]] = []
    bars: list[dict[str, object]] = []
    for idx, open_us in enumerate(closes):
        bar_open = datetime.fromtimestamp(open_us / 1e6, UTC)
        if bar_open >= end:
            break
        at = bar_open + timedelta(minutes=5)
        live = bar_open >= start
        state = build_market_state(multi, at, broker_clock=clock, memo=memo)
        row = int(np.searchsorted(m1_open, int((at - MINUTE).timestamp() * 1e6)))
        has_m1 = row < len(m1_open) and m1_open[row] == int((at - MINUTE).timestamp() * 1e6)
        if state.h1_trend == "UNKNOWN" or state.price is None or not has_m1:
            mems = {
                v: Memory() for v in VARIANTS
            }  # missing data: no lifecycle is carried across it
            continue
        bid = float(m1_close[row])
        ask = bid + float(m1_spread[row]) * POINT
        ctx = DecisionContext(spec=SPEC, equity=None, bid=bid, ask=ask)
        h1, m5 = state.snapshots.get("H1"), state.snapshots.get("M5")
        shock = (
            shock_cache.recent(multi.as_of(Timeframe.M15, at), 2)
            or shock_cache.recent(multi.as_of(Timeframe.H1, at), 1)
            or state.h4_regime == "SHOCK"
            or state.m1_micro_state == "ABNORMAL"
        )
        obs = Observation(
            shock=shock,
            h1_resistance=None if h1 is None else h1.resistance,
            h1_support=None if h1 is None else h1.support,
            m5_close=None if m5 is None else m5.close,
        )
        armed_any = False
        for name, cfg in cfgs.items():
            d, mems[name], info = candidate_step(mems[name], state, ctx, cfg, obs, idx)
            armed_any = armed_any or info.armed_now
            if live and d.action != "WAIT":
                risk = abs((d.entry_price or 0.0) - (d.stop_loss or 0.0))
                signals.append(
                    {
                        "variant": name, "ts": at, "side": d.action, "entry": d.entry_price, "sl": d.stop_loss,
                        "tp": d.take_profit, "tp2": d.take_profit_2, "net_rr": d.net_rr, "gross_rr": d.gross_rr,
                        "capped": d.capped_by_structure, "risk_dist": risk, "atr15": d.atr,
                        "spread_pts": state.spread, "bid": bid, "ask": ask, "session": state.session,
                        "lifecycle": info.lifecycle, "substituted": info.substituted, "cost_r": info.cost_r,
                        "risk_pct": d.risk_pct, "m1": d.m1_execution_state, "vol": state.volatility_regime,
                    }
                )  # fmt: skip
        if live:
            bars.append(
                {
                    "ts": at, "side": state.h1_trend, "armed_now": armed_any, "shock": shock,
                    "vol": state.volatility_regime, "session": state.session,
                    "spread_pct": state.spread_percentile, "execq": state.execution_quality,
                }
            )  # fmt: skip
    out.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(signals, infer_schema_length=None).write_parquet(
        sig_path
    ) if signals else pl.DataFrame({"variant": []}).write_parquet(sig_path)
    pl.DataFrame(bars, infer_schema_length=None).write_parquet(bar_path)
    return f"{year}-{month:02d}: {len(bars)} bars, {len(signals)} signal rows"


def _init() -> None:
    if os.name == "nt":
        import ctypes  # noqa: PLC0415

        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--window", choices=sorted(WINDOWS), default="DEV")
    p.add_argument("--out", default="data/research/cand")
    p.add_argument("--jobs", type=int, default=4)
    p.add_argument("--months", default="", help="comma list YYYY-MM (overrides the window)")
    p.add_argument("--confirm", action="store_true", help="allowed only after the freeze gate")
    a = p.parse_args()
    if a.window != "DEV" and not a.confirm:
        sys.exit("Validation / Confirm-C need --confirm (freeze gate): refusing")
    pairs = (
        [tuple(map(int, m.split("-"))) for m in a.months.split(",")]
        if a.months
        else months_of(a.window)
    )
    root = str(Settings().data_root)
    jobs = [(root, y, m, a.out) for y, m in pairs]
    with ProcessPoolExecutor(min(a.jobs, 4), initializer=_init) as ex:
        for line in ex.map(run_month, jobs):
            print(line, flush=True)


if __name__ == "__main__":
    main()
