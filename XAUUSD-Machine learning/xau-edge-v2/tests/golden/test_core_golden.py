"""Frozen V1 answers: V2's decision must reproduce them exactly, without importing V1.

``core_golden.json`` / ``core_golden_plans.json`` are written by ``scripts/parity/golden_core.py``
(run with the V1 interpreter on real closed bars outside the locked windows). Each case holds the
V1 market-state fields the chain reads, the context, and V1's answer. The ``plans`` file relaxes the
two volatility-percentile vetoes so the stop/target/size path is reached often.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from xau_edge_v2.core.decision import DecisionConfig, DecisionContext, Refusal, decide
from xau_edge_v2.core.market_state import MarketState, TfSnapshot
from xau_edge_v2.core.risk import SymbolSpec

HERE = Path(__file__).parent
FILES = {
    "core_golden.json": False,
    "core_golden_plans.json": True,
    "core_golden_synthetic.json": False,
}
SPEC = SymbolSpec()


def _snapshot(raw: dict[str, Any]) -> TfSnapshot:
    return TfSnapshot(
        timeframe="M5",
        bar_open=datetime.fromisoformat(raw["bar_open"]),
        bar_closed=datetime.fromisoformat(raw["bar_closed"]),
        bars_used=400, close=0.0, atr=None, atr_percentile=None, ema_fast=None, ema_slow=None,
        price_vs_ema_atr=None, rsi=None, roc=None, structure_trend=0, bos_recent=0,
        choch_recent=0, last_swing_high=raw["last_swing_high"],
        last_swing_low=raw["last_swing_low"], support=None, resistance=None, patterns={},
        volume_zscore=None, tick_volume=0.0, regime=None,
    )  # fmt: skip


def _state(raw: dict[str, Any]) -> MarketState:
    data = dict(raw)
    data["timestamp"] = datetime.fromisoformat(data["timestamp"])
    data["snapshots"] = {k: _snapshot(v) for k, v in data["snapshots"].items()}
    for key in ("available_timeframes", "stale_timeframes"):
        data[key] = tuple(data[key])
    return MarketState(**data)


def _cases() -> list[tuple[str, int, dict[str, Any], bool]]:
    out: list[tuple[str, int, dict[str, Any], bool]] = []
    for name, relaxed in FILES.items():
        path = HERE / name
        if path.exists():
            for i, case in enumerate(json.loads(path.read_text(encoding="utf-8"))["cases"]):
                out.append((name, i, case, relaxed))
    return out


CASES = _cases()


def test_fixtures_exist_and_cover_the_plan_path() -> None:
    assert len(CASES) >= 600
    actions = {c["expected"]["action"] for _, _, c, _ in CASES}
    assert "WAIT" in actions
    plans = [c for _, _, c, _ in CASES if c["expected"]["action"] != "WAIT"]
    assert len(plans) >= 100, "the golden set must exercise BUY/SELL plans, not only WAIT"
    assert {c["expected"]["action"] for c in plans} == {"BUY", "SELL"}


@pytest.mark.parametrize(("name", "index", "case", "relaxed"), CASES, ids=lambda v: str(v)[:24])
def test_v2_reproduces_the_frozen_v1_answer(
    name: str, index: int, case: dict[str, Any], relaxed: bool
) -> None:
    v = case["context"]
    spec = SymbolSpec(**v["spec"]) if "spec" in v else SPEC
    ctx = DecisionContext(
        spec=spec, equity=v["equity"], feed_connected=v["feed"], cooldown_active=v["cooldown"],
        daily_limit_hit=v["daily"], risk_limit_hit=v["risk"], market_open=v["market_open"],
        market_status="OPEN" if v["market_open"] else "CLOSED", data_ok=v["data_ok"],
        spec_known=v["spec_known"], bid=v["bid"], ask=v["ask"],
    )  # fmt: skip
    cfg = DecisionConfig(
        block_high_volatility=not relaxed,
        block_low_volatility=not relaxed,
        allow_unknown_news=v.get("allow_news", True),
        block_quiet_m1=v.get("quiet_block", True),
        min_clear_atr=v.get("min_clear_atr", 1.0),
        risk_pct=v.get("risk_pct", 0.25),
    )
    d = decide(_state(case["state"]), ctx, cfg)
    e = case["expected"]
    assert d.action == e["action"]
    assert list(d.refusals) == e["refusals"]
    assert list(d.reasons) == e["reasons"]
    assert list(d.warnings) == e["warnings"]
    assert d.m1_execution_state == e["m1_execution_state"]
    assert d.decision_id == e["decision_id"]
    if e["action"] != "WAIT":
        for ours, key in (
            (d.entry_price, "entry_price"), (d.stop_loss, "stop_loss"),
            (d.take_profit, "take_profit"), (d.take_profit_2, "take_profit_2"),
            (d.net_rr, "net_rr"), (d.required_win_rate, "required_win_rate"),
            (d.risk_amount, "risk_amount"), (d.lots, "lots"),
        ):  # fmt: skip
            assert ours == pytest.approx(e[key], rel=1e-9, abs=1e-12), key
        assert d.stop_model == e["stop_model"] and d.entry_quality == e["entry_quality"]
        assert d.setup_id == e["setup_id"]
        assert d.expiry is not None and d.expiry.isoformat() == e["expiry"]


def test_synthetic_fixtures_reach_every_refusal_and_the_plan_variants() -> None:
    synthetic = [c for n, _, c, _ in CASES if n == "core_golden_synthetic.json"]
    refusals = {r for c in synthetic for r in c["expected"]["refusals"]}
    assert refusals == {r.value for r in Refusal}  # every refusal code is reachable and frozen
    plans = [c["expected"] for c in synthetic if c["expected"]["action"] != "WAIT"]
    assert {p["entry_quality"] for p in plans} == {"STRONG", "ACCEPTABLE"}
    assert any(p["take_profit_2"] is None for p in plans) and any(p["lots"] is None for p in plans)
