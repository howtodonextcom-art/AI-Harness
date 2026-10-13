"""Continuous, restartable replay of every candidate variant over the CLEAN store (signals only, no outcome).

One process walks the run window bar by bar; the lifecycle memory is never reset at a month boundary. After
each month it writes the month's signals, a digest of EVERY decision of that month, and a checkpoint. A
restart (``--resume``) restores the checkpoint and must produce exactly the digests of the continuous run;
if the checkpoint cannot be trusted the engine starts cold and C1 decisions are WAIT until the state is
provably the same.

    uv run python scripts/research/cand_replay.py --store data/clean_store --from 2011-03 --to 2011-04 \
        --out data/research/replay_a --checkpoint data/research/replay_a/cp.json [--resume] [--stop-after 2011-03]

Reads only the clean store (manifest and file hashes verified); refuses any month that is not PASS and any
month outside DEV' / VALIDATION' / RESERVED. It never reads Confirm-C, Test-H or Holdout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

for _v in ("POLARS_MAX_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "1"

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "src"))
sys.path.insert(0, str(HERE.parent))

import numpy as np  # noqa: E402
import polars as pl  # noqa: E402
from cand_signals import ShockCache  # noqa: E402

from xau_edge_v2.core.candidate import VARIANTS, Observation, config_for  # noqa: E402
from xau_edge_v2.core.decision import DecisionConfig, DecisionContext  # noqa: E402
from xau_edge_v2.core.frames import MultiFrames  # noqa: E402
from xau_edge_v2.core.intelligence.funnel import ungated_decision  # noqa: E402
from xau_edge_v2.core.market_state import (  # noqa: E402
    POINT,
    SnapshotMemo,
    build_market_state,
)
from xau_edge_v2.core.risk import SymbolSpec  # noqa: E402
from xau_edge_v2.data.frames import frame_from_polars  # noqa: E402
from xau_edge_v2.domain.contract import Timeframe  # noqa: E402
from xau_edge_v2.domain.market import BrokerClock  # noqa: E402
from xau_edge_v2.research.clean_store import CleanBarStore, CleanStoreError  # noqa: E402
from xau_edge_v2.research.replay import Replay, save_checkpoint  # noqa: E402

SPEC_FILE = HERE.parents[2] / "docs" / "research" / "cand_v2_spec.sha256"
SPEC = SymbolSpec()
BACK = {"M1": 3, "M5": 7, "M15": 14, "M30": 25, "H1": 40, "H4": 140}
ORDER = (Timeframe.M1, Timeframe.M5, Timeframe.M15, Timeframe.M30, Timeframe.H1, Timeframe.H4)
MINUTE = timedelta(minutes=1)
ALLOWED = ("DEV'", "VALIDATION'", "RESERVED")


def months_between(a: str, b: str) -> list[str]:
    out: list[str] = []
    y, m = int(a[:4]), int(a[5:])
    while f"{y:04d}-{m:02d}" <= b:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)  # noqa: PLR2004
    return out


def month_bounds(month: str) -> tuple[datetime, datetime]:
    y, m = int(month[:4]), int(month[5:])
    return datetime(y, m, 1, tzinfo=UTC), datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=UTC)  # noqa: PLR2004


def load_frames(store: CleanBarStore, month: str) -> dict[Timeframe, pl.DataFrame]:
    start, end = month_bounds(month)
    out: dict[Timeframe, pl.DataFrame] = {}
    for tf in ORDER:
        parts: list[pl.DataFrame] = []
        cursor = start - timedelta(days=BACK[tf.value])
        while True:
            df = store.window(tf, cursor, end, 5000)
            if df.height == 0:
                break
            parts.append(df)
            if df.height < 5000:  # noqa: PLR2004
                break
            cursor = df["timestamp"][-1] + timedelta(seconds=1)
        if parts:
            out[tf] = pl.concat(parts, how="vertical_relaxed")
    return out


def run_opens(store: CleanBarStore, months: list[str]) -> np.ndarray:
    """Open times (us) of every M5 bar of the run window, in order."""
    parts = [
        store._read_month(Timeframe.M5, m)["timestamp"].dt.epoch("us").to_numpy() for m in months
    ]  # noqa: SLF001
    return np.concatenate(parts).astype(np.int64)


def decision_line(open_us: int, name: str, d: object, info: object) -> str:
    return json.dumps(
        [open_us, name, getattr(d, "action"), getattr(d, "entry_price"), getattr(d, "stop_loss"), getattr(d, "take_profit"),  # noqa: B009
         list(getattr(d, "refusals")), getattr(info, "lifecycle"), getattr(info, "guard")],  # noqa: B009
        separators=(",", ":"),
    )  # fmt: skip


def main() -> None:  # noqa: PLR0912, PLR0915
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default="data/clean_store")
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--to", dest="end", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--stop-after", default="")
    a = ap.parse_args()
    if os.name == "nt":
        import ctypes  # noqa: PLC0415

        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    store = CleanBarStore(Path(a.store))
    months = months_between(a.start, a.end)
    for m in months:
        info = store.manifest["months"].get(m)
        if info is None or info["status"] != "PASS" or info["window"] not in ALLOWED:
            sys.exit(
                f"{m}: not a PASS month of an allowed window ({info and info['status']}, {info and info['window']})"
            )
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    spec_sha = SPEC_FILE.read_text(encoding="utf-8").strip()
    opens = run_opens(store, months)
    cfgs = {v: config_for(v) for v in VARIANTS}
    cp = Path(a.checkpoint)
    if a.resume:
        engine = Replay.restore(
            cp,
            cfgs,
            spec_sha256=spec_sha,
            store_manifest_sha256=store.manifest["manifest_sha256"],
            run_opens=opens,
        )
    else:
        engine = Replay(
            cfgs, spec_sha256=spec_sha, store_manifest_sha256=store.manifest["manifest_sha256"]
        )
    print("engine:", engine.status, flush=True)
    done = engine.resume_index(opens)
    clock = BrokerClock(ny_offset_hours=7)
    pos = 0
    for month in months:
        start, end = month_bounds(month)
        n_month = int(
            ((opens >= int(start.timestamp() * 1e6)) & (opens < int(end.timestamp() * 1e6))).sum()
        )
        if pos + n_month <= done:
            pos += n_month
            continue  # this month was processed before the checkpoint
        frames = load_frames(store, month)
        multi = MultiFrames(
            {tf: f for tf, df in frames.items() if (f := frame_from_polars(tf, df))}
        )
        m1 = frames[Timeframe.M1]
        m1_open = m1["timestamp"].dt.epoch("us").to_numpy().astype(np.int64)
        m1_close, m1_spread = m1["close"].to_numpy(), m1["spread"].fill_null(0.0).to_numpy()
        memo, shock_cache = SnapshotMemo(), ShockCache()
        digest = hashlib.sha256()
        signals: list[dict[str, object]] = []
        counters = {"bars": 0, "skipped": 0, "chain_ok_bars": 0, "gated_chain_ok_bars": 0}
        month_opens = opens[
            (opens >= int(start.timestamp() * 1e6)) & (opens < int(end.timestamp() * 1e6))
        ]
        for open_us in month_opens:
            if pos < done:
                pos += 1
                continue
            pos += 1
            bar_open = datetime.fromtimestamp(int(open_us) / 1e6, UTC)
            at = bar_open + timedelta(minutes=5)
            state = build_market_state(multi, at, broker_clock=clock, memo=memo)
            row = int(np.searchsorted(m1_open, int((at - MINUTE).timestamp() * 1e6)))
            has_m1 = row < len(m1_open) and m1_open[row] == int((at - MINUTE).timestamp() * 1e6)
            counters["bars"] += 1
            if state.h1_trend == "UNKNOWN" or state.price is None or not has_m1:
                counters["skipped"] += 1
                engine.skip(int(open_us))
                continue
            bid = float(m1_close[row])
            ctx = DecisionContext(
                spec=SPEC, equity=None, bid=bid, ask=bid + float(m1_spread[row]) * POINT
            )
            h1, m5 = state.snapshots.get("H1"), state.snapshots.get("M5")
            shock = bool(
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
            res = engine.step(int(open_us), state, ctx, obs)
            chain_ok = ungated_decision(state, ctx, DecisionConfig()).action != "WAIT"
            counters["chain_ok_bars"] += int(chain_ok)
            m15 = state.snapshots.get("M15")
            context = {
                "session": state.session,
                "h4_regime": state.h4_regime,
                "h1_trend": state.h1_trend,
                "m15_regime": None if m15 is None else m15.regime,
                "spread_points": state.spread,
                "atr_m15": state.atr_m15,
                "chain_ok": chain_ok,
            }
            for name, (d, info) in res.items():
                digest.update(decision_line(int(open_us), name, d, info).encode())
                if d.action != "WAIT":
                    signals.append(
                        {
                            "variant": name,
                            "ts": at,
                            "side": d.action,
                            "entry": d.entry_price,
                            "sl": d.stop_loss,
                            "tp": d.take_profit,
                            "net_rr": d.net_rr,
                            "lifecycle": info.lifecycle,
                            **context,
                        }
                    )
        pl.DataFrame(signals, infer_schema_length=None).write_parquet(
            out / f"signals_{month}.parquet"
        ) if signals else None
        (out / f"stats_{month}.json").write_text(json.dumps(counters) + "\n", encoding="utf-8")
        (out / f"digest_{month}.txt").write_text(digest.hexdigest() + "\n", encoding="utf-8")
        save_checkpoint(cp, engine.checkpoint())
        print(
            month,
            "bars",
            len(month_opens),
            "signals",
            len(signals),
            "digest",
            digest.hexdigest()[:16],
            flush=True,
        )
        if a.stop_after == month:
            print("stopped after", month)
            return
    print("done")


if __name__ == "__main__":
    try:
        main()
    except CleanStoreError as exc:
        sys.exit(f"CLEAN STORE: {exc}")
