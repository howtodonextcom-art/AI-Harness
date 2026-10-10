"""Setup alerts: tell the owner when a plan appears, disappears or a paper trade ends.

Reuses the existing dispatcher (Telegram when configured, otherwise a file). Rules:

* a WAIT is never announced; each setup is announced ONCE (keyed by ``setup_id``, remembered across
  restarts), so a setup that stays valid for several M1 closes sends a single message;
* SETUP_INVALIDATED is sent only for a setup that WAS announced, was not taken, has not expired,
  and is no longer the current decision;
* the dispatcher's own rate limits still apply; delivery failure never raises into the engine.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from xau_edge.market_data.atomic import atomic_write_text
from xau_edge.ops.notifier import AlertEvent
from xau_edge.trading.schema import TradeDecision, TradingSignal

_LOG = logging.getLogger(__name__)
EVIDENCE_LINE = "Evidence: UNVALIDATED OPERATIONAL BASELINE (not a validated edge)"


class Dispatcher(Protocol):
    def dispatch(self, event: AlertEvent) -> Any: ...


def setup_message(signal: TradingSignal) -> str:
    return (
        f"XAUUSD {signal.decision.value} setup\n"
        f"Entry: {signal.entry_price:.2f}  SL: {signal.stop_loss:.2f}  "
        f"TP: {signal.take_profit:.2f}\n"
        f"RR: {signal.risk_reward:.2f}  Lot (at {signal.risk_pct}%): {signal.position_size}\n"
        f"H1: {signal.h1_bias}  M15: {signal.m15_setup}  M5: {signal.m5_trigger}\n"
        f"Valid until: {signal.signal_expiry:%H:%M} UTC\n"
        f"{EVIDENCE_LINE}"
        if signal.entry_price is not None
        and signal.stop_loss is not None
        and signal.take_profit is not None
        and signal.risk_reward is not None
        and signal.signal_expiry is not None
        else f"XAUUSD {signal.decision.value} setup"
    )


class SetupAlerts:
    def __init__(
        self,
        dispatcher: Dispatcher | None,
        state_path: Path | str,
        *,
        delivery: str = "FILE_FALLBACK",
    ) -> None:
        self.delivery = delivery
        """TELEGRAM when a bot is configured, otherwise FILE_FALLBACK (``alerts.jsonl``)."""
        self._dispatcher = dispatcher
        self._path = Path(state_path)
        self._announced: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._announced = dict(raw.get("announced", {}))
        except (OSError, ValueError):
            self._announced = {}

    def _save(self, now: datetime) -> None:
        # keep the memory small: forget setups that expired more than a day ago
        keep = {
            k: v for k, v in self._announced.items()
            if (now - datetime.fromisoformat(v["expires_at"])).total_seconds() < 86_400
        }  # fmt: skip
        self._announced = keep
        try:
            atomic_write_text(self._path, json.dumps({"announced": keep}))
        except OSError as exc:
            _LOG.warning("alert state not saved: %s", type(exc).__name__)

    def _send(self, code: str, severity: str, message: str, now: datetime, **details: Any) -> None:
        if self._dispatcher is None:
            return
        try:
            self._dispatcher.dispatch(
                AlertEvent(code=code, severity=severity, message=message, at=now, details=details)
            )
        except Exception as exc:
            _LOG.warning("alert dispatch failed: %s", type(exc).__name__)

    def on_decision(
        self, signal: TradingSignal, now: datetime, *, taken_setups: set[str], blocked: bool
    ) -> None:
        """Announce a new actionable setup; invalidate announced ones that vanished."""
        for setup_id, info in list(self._announced.items()):
            gone = signal.setup_id != setup_id or signal.decision is TradeDecision.WAIT
            live = (
                not info.get("closed")
                and datetime.fromisoformat(info["expires_at"]) > now
                and setup_id not in taken_setups
            )
            if gone and live:
                info["closed"] = "INVALIDATED"
                info["invalidated_at"] = now.isoformat()
                self._send(
                    f"SETUP_INVALIDATED:{setup_id[:8]}",
                    "info",
                    f"XAUUSD {info['side']} setup invalidated before its expiry "
                    f"({signal.decision.value} now)",
                    now,
                    setup_id=setup_id,
                )
        if (
            signal.decision is not TradeDecision.WAIT
            and signal.setup_id
            and signal.setup_id not in self._announced
            and signal.signal_expiry is not None
            and not blocked
        ):
            self._announced[signal.setup_id] = {
                "side": signal.decision.value,
                "expires_at": signal.signal_expiry.isoformat(),
                "announced_at": now.isoformat(),
            }
            self._send(
                f"{signal.decision.value}_SETUP_READY:{signal.setup_id[:8]}",
                "info",
                setup_message(signal),
                now,
                setup_id=signal.setup_id,
            )
        self._save(now)

    def status_of(self, setup_id: str) -> dict[str, Any] | None:
        """Was this setup announced, when and over which channel (None: not announced)."""
        info = self._announced.get(setup_id)
        if info is None:
            return None
        return {"announced": True, "at": info.get("announced_at"), "channel": self.delivery}

    def summary(self, now: datetime) -> dict[str, Any]:
        """What the UI shows about alerts: how many setups were announced today and the last one."""
        today = [
            (k, v) for k, v in self._announced.items()
            if v["announced_at"][:10] == now.date().isoformat()
        ]  # fmt: skip
        last = max(self._announced.items(), key=lambda kv: kv[1]["announced_at"], default=None)
        return {
            "announced_today": len(today),
            "last": None if last is None else {"setup_id": last[0], **last[1]},
            "delivery": self.delivery,
            "telegram_configured": self.delivery == "TELEGRAM",
            "file_fallback_active": self.delivery != "TELEGRAM",
            "last_invalidation": self._last_invalidation(),
        }

    def _last_invalidation(self) -> dict[str, Any] | None:
        hits = [
            {"setup_id": k, "side": v["side"], "at": v.get("invalidated_at")}
            for k, v in self._announced.items()
            if v.get("closed") == "INVALIDATED"
        ]
        return max(hits, key=lambda h: h["at"] or "", default=None)

    def on_paper_close(self, trade: dict[str, Any], now: datetime) -> None:
        """PAPER_SL / PAPER_TP (and the other exit reasons) once per trade."""
        reason = str(trade.get("exit_reason", "CLOSED"))
        code = {"STOP_LOSS": "PAPER_SL", "TAKE_PROFIT": "PAPER_TP"}.get(reason, f"PAPER_{reason}")
        self._send(
            f"{code}:{trade['trade_id']}",
            "info" if reason == "TAKE_PROFIT" else "warning",
            f"Paper trade {trade['trade_id']} {trade['side']} closed: {reason}, "
            f"R {trade.get('r_multiple')}, P&L {trade.get('net_pnl'):.2f} (simulated)",
            now,
            trade_id=trade["trade_id"],
        )
