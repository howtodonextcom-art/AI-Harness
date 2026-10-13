"""The paper desk: opens PAPER positions from decisions, manages them on closed M1 bars, keeps the
books. It has no connection to any broker; its only side effect is writing V2's own SQLite file.

Inputs are explicit (``now``, quote, bars, decision, spec) so every behaviour is deterministic and
testable. The desk never invents a price: a position opens at the executable quote of the decision,
and is managed only with closed bars that open after the entry minute.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from xau_edge_v2.core import paper as rules
from xau_edge_v2.core.costs import SLIPPAGE_POINTS
from xau_edge_v2.core.decision import Decision
from xau_edge_v2.core.market_state import trading_session
from xau_edge_v2.core.risk import SymbolSpec
from xau_edge_v2.domain.contract import (
    GovernorStatus,
    JournalEventView,
    PaperPositionView,
    PaperSummary,
)
from xau_edge_v2.domain.market import BrokerClock
from xau_edge_v2.paper.store import PaperStore

_US = 1_000_000
ASSUMPTIONS = (
    "Equity paper là giả định cấu hình, không phải số dư tài khoản thật.",
    f"Vào lệnh tại ask/bid cộng trượt giá {SLIPPAGE_POINTS:g} điểm bất lợi (GIẢ ĐỊNH).",
    "Quản lý bằng nến M1 đã đóng sau phút vào lệnh; nến chạm cả SL và TP thì coi SL trước.",
    "SL khớp kèm trượt giá bất lợi; TP khớp đúng mức. Chỉ có SL/TP cố định, không dời SL.",
    "Hoa hồng 0 (GIẢ ĐỊNH); swap theo số đọc 2026-10-08 (GIẢ ĐỊNH), mỗi lần qua 17:00 New York.",
)


@dataclass(frozen=True)
class MinuteBar:
    """A closed M1 bar as the desk needs it."""

    open_us: int
    high: float
    low: float
    spread_points: float


def _dt(us: int) -> datetime:
    return datetime.fromtimestamp(us / _US, UTC)


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


class PaperDesk:
    def __init__(
        self,
        store: PaperStore,
        *,
        start_equity: float,
        auto: bool,
        clock: BrokerClock,
        governor: rules.GovernorConfig | None = None,
    ) -> None:
        self.store = store
        self.auto = auto
        self.clock = clock
        self.governor = governor or rules.GovernorConfig()
        self.start_equity = float(store.set_account_once("start_equity", repr(float(start_equity))))

    # ---- books --------------------------------------------------------------------------------
    def _day_start(self, now: datetime) -> datetime:
        wall = self.clock.to_server_wall(now)
        midnight = wall.replace(hour=0, minute=0, second=0, microsecond=0)
        return self.clock.server_to_utc(midnight, strict=False) or now - timedelta(hours=24)

    def _net(self, row: dict[str, Any]) -> float:
        return float(row["pnl_usd"] or 0.0) + float(row["swap_usd"] or 0.0)

    def _floating(self, row: dict[str, Any], bid: float | None, ask: float | None) -> float:
        if bid is None or ask is None:
            return 0.0
        return rules.floating_pnl(
            row["side"], row["entry"], bid, ask, row["lots"], row["tick_size"], row["tick_value"]
        )

    def books(self, now: datetime, bid: float | None, ask: float | None) -> dict[str, float]:
        rows = self.store.all_positions_oldest_first()
        day_start = self._day_start(now)
        realized = sum(self._net(r) for r in rows if r["status"] == "CLOSED")
        before_today = sum(
            self._net(r)
            for r in rows
            if r["status"] == "CLOSED" and _parse(r["closed_at"]) < day_start
        )
        floating = sum(self._floating(r, bid, ask) for r in rows if r["status"] == "OPEN")
        return {
            "realized": realized,
            "floating": floating,
            "equity": self.start_equity + realized + floating,
            "day_start_equity": self.start_equity + before_today,
        }

    def equity(self, now: datetime, bid: float | None = None, ask: float | None = None) -> float:
        return self.books(now, bid, ask)["equity"]

    def open_row(self) -> dict[str, Any] | None:
        rows = self.store.positions("OPEN", 1)
        return rows[0] if rows else None

    # ---- governor -----------------------------------------------------------------------------
    def _records(
        self, now: datetime
    ) -> tuple[list[rules.OpenRecord], list[rules.OpenRecord], list[rules.CloseRecord]]:
        rows = self.store.all_positions_oldest_first()
        day_start = self._day_start(now)
        opens = [
            rules.OpenRecord(
                _parse(r["opened_at"]), r["session"], r["risk_pct"], r["status"] == "CLOSED"
            )
            for r in rows
        ]
        today = [o for o in opens if o.opened_at >= day_start]
        closes = sorted(
            (
                rules.CloseRecord(_parse(r["closed_at"]), self._net(r))
                for r in rows
                if r["status"] == "CLOSED"
            ),
            key=lambda c: c.closed_at,
        )
        return opens, today, closes

    def governor_refusals(
        self,
        now: datetime,
        risk_pct: float,
        bid: float | None = None,
        ask: float | None = None,
    ) -> list[str]:
        opens, today, closes = self._records(now)
        b = self.books(now, bid, ask)
        return rules.governor_check(
            self.governor,
            now,
            trading_session(now),
            risk_pct,
            opens=opens,
            opens_today=today,
            closes=closes,
            day_start_equity=b["day_start_equity"],
            equity=b["equity"],
        )

    def governor_status(
        self, now: datetime, risk_pct: float, bid: float | None, ask: float | None
    ) -> GovernorStatus:
        opens, today, closes = self._records(now)
        b = self.books(now, bid, ask)
        cfg = self.governor
        return GovernorStatus(
            open_positions=sum(1 for o in opens if not o.closed),
            trades_today=len(today),
            trades_last_hour=sum(1 for o in opens if now - o.opened_at < timedelta(hours=1)),
            loss_streak=rules.loss_streak(closes),
            daily_loss_pct=round(rules.daily_loss_pct(b["day_start_equity"], b["equity"]), 4),
            daily_loss_stop_pct=cfg.daily_loss_stop_pct,
            cooldown_until=rules.cooldown_until(now, closes, cfg),
            refusals=tuple(self.governor_refusals(now, risk_pct, bid, ask)),
        )

    # ---- opening ------------------------------------------------------------------------------
    def open_position(
        self, now: datetime, decision: Decision, spec: SymbolSpec, source: str
    ) -> dict[str, Any] | None:
        """Open a PAPER position from a BUY/SELL decision; None when the setup was already used."""
        if decision.action not in ("BUY", "SELL"):
            msg = "only a BUY/SELL decision can open a paper position"
            raise ValueError(msg)
        if (
            decision.entry_price is None
            or decision.stop_loss is None
            or decision.take_profit is None
            or decision.lots is None
            or decision.net_rr is None
        ):
            msg = "the decision has no complete sized plan"
            raise ValueError(msg)
        side: rules.Side = "BUY" if decision.action == "BUY" else "SELL"
        fill = rules.entry_fill(side, decision.entry_price, spec.point)
        actual_risk = decision.lots * spec.loss_per_lot(abs(fill - decision.stop_loss))
        start = int(now.timestamp() // 60) * 60 * _US
        row: dict[str, Any] = {
            "id": uuid.uuid4().hex[:16],
            "setup_id": decision.setup_id,
            "decision_id": decision.decision_id,
            "side": side,
            "lots": decision.lots,
            "entry": fill,
            "quote_entry": decision.entry_price,
            "stop_loss": decision.stop_loss,
            "take_profit": decision.take_profit,
            "take_profit_2": decision.take_profit_2,
            "net_rr": decision.net_rr,
            "risk_amount": actual_risk,
            "risk_pct": decision.risk_pct or 0.0,
            "tick_size": spec.tick_size,
            "tick_value": spec.tick_value,
            "point": spec.point,
            "contract_size": spec.contract_size,
            "session": trading_session(now),
            "source": source,
            "opened_at": now.astimezone(UTC).isoformat(),
            "last_bar_us": start,
            "status": "OPEN",
        }
        detail = {
            "side": side,
            "lots": decision.lots,
            "quote_entry": decision.entry_price,
            "fill": fill,
            "stop_loss": decision.stop_loss,
            "take_profit": decision.take_profit,
            "risk_amount": round(actual_risk, 2),
            "source": source,
            "strategy": decision.strategy_version,
            "evidence": decision.evidence,
        }
        return self.store.position(row["id"]) if self.store.insert_position(row, detail) else None

    # ---- management --------------------------------------------------------------------------
    def _close(
        self,
        row: dict[str, Any],
        when: datetime,
        exit_price: float,
        reason: str,
        ambiguous: bool = False,
    ) -> bool:
        side = row["side"]
        pnl = rules.pnl_usd(
            side, row["entry"], exit_price, row["lots"], row["tick_size"], row["tick_value"]
        )
        nights = rules.rollover_nights(_parse(row["opened_at"]), when)
        swap = rules.swap_usd(side, row["lots"], nights, row["point"], row["contract_size"])
        net = pnl + swap
        fields = {
            "closed_at": when.astimezone(UTC).isoformat(),
            "exit_price": exit_price,
            "exit_reason": reason,
            "ambiguous": int(ambiguous),
            "pnl_usd": pnl,
            "swap_usd": swap,
        }
        detail = {
            "reason": reason,
            "exit_price": exit_price,
            "pnl_usd": round(pnl, 2),
            "swap_usd": round(swap, 2),
            "net_usd": round(net, 2),
            "r": round(net / row["risk_amount"], 3) if row["risk_amount"] else None,
            "ambiguous_bar": ambiguous,
            "nights": nights,
        }
        return self.store.close_position(row["id"], fields, detail)

    def manage(
        self,
        now: datetime,
        bars: Iterable[MinuteBar],
        bid: float | None,
        ask: float | None,
    ) -> list[str]:
        """Apply closed M1 bars to every open position; returns the ids closed (also flatten)."""
        closed: list[str] = []
        ordered = sorted(bars, key=lambda b: b.open_us)
        for row in self.store.positions("OPEN", 50):
            last, mae, mfe = int(row["last_bar_us"]), row["mae_points"], row["mfe_points"]
            done = False
            for bar in ordered:
                if bar.open_us <= last:
                    continue
                last = bar.open_us
                sign = 1 if row["side"] == "BUY" else -1
                worst = (bar.low if sign > 0 else bar.high) - row["entry"]
                best = (bar.high if sign > 0 else bar.low) - row["entry"]
                mae = max(mae, -sign * worst / row["point"]) if sign * worst < 0 else mae
                mfe = max(mfe, sign * best / row["point"]) if sign * best > 0 else mfe
                hit = rules.evaluate_bar(
                    row["side"],
                    row["stop_loss"],
                    row["take_profit"],
                    high=bar.high,
                    low=bar.low,
                    spread_points=bar.spread_points,
                    point=row["point"],
                )
                if hit is not None:
                    done = self._close(
                        row, _dt(bar.open_us + 60 * _US), hit.price, hit.reason, hit.ambiguous
                    )
                    if done:
                        closed.append(row["id"])
                    break
            if not done:
                self.store.touch_position(row["id"], last, mae, mfe)
        closed += self._flatten_if_needed(now, bid, ask)
        return closed

    def _flatten_if_needed(self, now: datetime, bid: float | None, ask: float | None) -> list[str]:
        if bid is None or ask is None:
            return []
        b = self.books(now, bid, ask)
        if not rules.flatten_required(self.governor, b["day_start_equity"], b["equity"]):
            return []
        out: list[str] = []
        for row in self.store.positions("OPEN", 50):
            price = rules.close_price_at_quote(row["side"], bid, ask)
            if self._close(row, now, price, "FLATTEN"):
                out.append(row["id"])
        return out

    def close_manual(
        self, position_id: str, now: datetime, bid: float, ask: float
    ) -> dict[str, Any] | None:
        row = self.store.position(position_id)
        if row is None or row["status"] != "OPEN":
            return None
        price = rules.close_price_at_quote(row["side"], bid, ask)
        return self.store.position(position_id) if self._close(row, now, price, "MANUAL") else None

    # ---- views --------------------------------------------------------------------------------
    def view(self, row: dict[str, Any], bid: float | None, ask: float | None) -> PaperPositionView:
        closed = row["status"] == "CLOSED"
        net = self._net(row) if closed else None
        return PaperPositionView(
            id=row["id"],
            setup_id=row["setup_id"],
            decision_id=row["decision_id"],
            side=row["side"],
            lots=row["lots"],
            entry=row["entry"],
            quote_entry=row["quote_entry"],
            stop_loss=row["stop_loss"],
            take_profit=row["take_profit"],
            take_profit_2=row["take_profit_2"],
            net_rr=row["net_rr"],
            risk_amount=row["risk_amount"],
            risk_pct=row["risk_pct"],
            source=row["source"],
            session=row["session"],
            opened_at=_parse(row["opened_at"]),
            status=row["status"],
            closed_at=_parse(row["closed_at"]) if row["closed_at"] else None,
            exit_price=row["exit_price"],
            exit_reason=row["exit_reason"],
            ambiguous=bool(row["ambiguous"]),
            pnl_usd=row["pnl_usd"],
            swap_usd=row["swap_usd"],
            net_pnl_usd=net,
            r_multiple=(net / row["risk_amount"])
            if net is not None and row["risk_amount"]
            else None,
            floating_pnl_usd=None if closed else self._floating(row, bid, ask),
            mae_points=row["mae_points"],
            mfe_points=row["mfe_points"],
        )

    def summary(
        self, now: datetime, risk_pct: float, bid: float | None, ask: float | None
    ) -> PaperSummary:
        b = self.books(now, bid, ask)
        rows = self.store.all_positions_oldest_first()
        closed = [r for r in rows if r["status"] == "CLOSED"]
        nets = [self._net(r) for r in closed]
        total_r = sum(
            n / r["risk_amount"] for n, r in zip(nets, closed, strict=True) if r["risk_amount"]
        )
        return PaperSummary(
            auto_paper=self.auto,
            start_equity=self.start_equity,
            realized_pnl_usd=b["realized"],
            floating_pnl_usd=b["floating"],
            equity=b["equity"],
            day_start_equity=b["day_start_equity"],
            day_pnl_usd=b["equity"] - b["day_start_equity"],
            open_count=len(rows) - len(closed),
            closed_count=len(closed),
            wins=sum(1 for n in nets if n > 0),
            losses=sum(1 for n in nets if n < 0),
            total_r=total_r,
            governor=self.governor_status(now, risk_pct, bid, ask),
            assumptions=ASSUMPTIONS,
        )

    def journal(self, limit: int = 200) -> list[JournalEventView]:
        return [
            JournalEventView(
                seq=j.seq,
                ts=j.ts,
                kind=j.kind,
                position_id=j.position_id,
                detail={
                    k: v if isinstance(v, (str, float, int, bool)) or v is None else str(v)
                    for k, v in j.detail.items()
                },
            )
            for j in self.store.journal(limit)
        ]
