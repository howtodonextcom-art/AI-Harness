"""Decision telemetry: why does (or does not) the baseline trade? Counts only; no outcomes.

One JSON line per NEW decision (one per closed M1 bar), in a file per UTC day so nothing grows
without bound. It records the chain states and the refusal reasons, never prices of the future, and
nothing here is ever used to tune a threshold (that would be tuning on outcomes: forbidden in this
sprint). ``summary`` answers the owner's "why does it never trade?" with counts for today.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from xau_edge.trading.schema import TradingSignal


def record_of(signal: TradingSignal, *, at: datetime) -> dict[str, Any]:
    return {
        "at": at.isoformat(),
        "decision_id": signal.decision_id,
        "setup_id": signal.setup_id or None,
        "decision": signal.decision.value,
        "refusals": [r.value for r in signal.refusal_reasons],
        "h4": signal.h4_bias,
        "h1": signal.h1_bias,
        "m30": signal.m30_state,
        "m15": signal.m15_setup,
        "m5": signal.m5_trigger,
        "m1": signal.m1_execution_state,
        "volume": signal.volume_state,
        "spread_state": signal.spread_state,
        "volatility": signal.volatility_regime,
        "news": signal.news_state,
        "strategy_version": signal.strategy_version,
        "setup_phase": signal.metadata.get("setup_phase"),
    }


def signal_record(signal: TradingSignal, *, at: datetime) -> dict[str, Any]:
    """An actionable decision exactly as served (the chart markers come from these)."""
    return {
        "at": at.isoformat(),
        "bar_time": signal.timestamp.isoformat(),
        "setup_id": signal.setup_id,
        "decision_id": signal.decision_id,
        "side": signal.decision.value,
        "entry": signal.entry_price,
        "sl": signal.stop_loss,
        "tp1": signal.take_profit,
        "tp2": signal.take_profit_2,
        "rr": signal.risk_reward,
        "lots": signal.position_size,
        "expires_at": None if signal.signal_expiry is None else signal.signal_expiry.isoformat(),
        "strategy_version": signal.strategy_version,
    }


class DecisionTelemetry:
    """Append-only daily files ``decisions-YYYYMMDD.jsonl`` under ``root``."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def _path(self, day: datetime) -> Path:
        return self.root / f"decisions-{day.astimezone(UTC):%Y%m%d}.jsonl"

    def append(self, signal: TradingSignal, *, at: datetime) -> None:
        path = self._path(at)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record_of(signal, at=at), sort_keys=True) + "\n")

    def _signals_path(self, day: datetime) -> Path:
        return self.root / f"signals-{day.astimezone(UTC):%Y%m%d}.jsonl"

    def append_signal(self, signal: TradingSignal, *, at: datetime) -> None:
        """Log an actionable decision once per setup (restart-safe: ids are read back)."""
        path = self._signals_path(at)
        if signal.setup_id in {r.get("setup_id") for r in self.read_signals(at)}:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(signal_record(signal, at=at), sort_keys=True) + "\n")

    def read_signals(self, day: datetime) -> list[dict[str, Any]]:
        path = self._signals_path(day)
        if not path.exists():
            return []
        out: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                out.append(value)
        return out

    def read_day(self, day: datetime) -> list[dict[str, Any]]:
        path = self._path(day)
        if not path.exists():
            return []
        out: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue  # a torn last line is skipped, never trusted
            if isinstance(value, dict):
                out.append(value)
        return out

    def summary(self, day: datetime) -> dict[str, Any]:
        rows = self.read_day(day)
        decisions = Counter(r["decision"] for r in rows)
        refusals: Counter[str] = Counter()
        for r in rows:
            refusals.update(r.get("refusals", []))
        setups = {r["setup_id"] for r in rows if r.get("setup_id")}
        total = len(rows)
        return {
            "day": f"{day.astimezone(UTC):%Y-%m-%d}",
            "decisions": total,
            "buy": decisions.get("BUY", 0),
            "sell": decisions.get("SELL", 0),
            "wait": decisions.get("WAIT", 0),
            "wait_pct": round(100 * decisions.get("WAIT", 0) / total, 1) if total else None,
            "distinct_setups": len(setups),
            "top_refusals": refusals.most_common(8),
            "trigger_counts": dict(Counter(r["m5"] for r in rows)),
            "volume_counts": dict(Counter(r["volume"] for r in rows)),
            "spread_counts": dict(Counter(r["spread_state"] for r in rows)),
            "m1_counts": dict(Counter(r["m1"] for r in rows)),
            "setup_counts": dict(Counter(r["m15"] for r in rows)),
            "setup_phases": dict(Counter(r.get("setup_phase") or "-" for r in rows)),
            "most_common_blocker": refusals.most_common(1)[0][0] if refusals else None,
        }
