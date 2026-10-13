"""Baseline v1.2: setup lifecycle transitions, the three pre-registered changes, version isolation,
the decision-derived funnel and signal telemetry."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.unit.trading import helpers
from tests.unit.trading.helpers import SPEC, aligned_state, multi_tf
from xau_edge.domain.timeframe import Timeframe
from xau_edge.trading import setup_machine
from xau_edge.trading.baseline import BaselineConfig, DecisionContext, decide
from xau_edge.trading.frames import MultiTfBars
from xau_edge.trading.funnel import STAGE_NAMES, stages_from_signal, waiting_for
from xau_edge.trading.market_state import SnapshotMemo, StateConfig
from xau_edge.trading.schema import Refusal, TradeDecision
from xau_edge.trading.setup_machine import SetupLifecycle, SetupPhase, lifecycle
from xau_edge.trading.telemetry import DecisionTelemetry

V11 = BaselineConfig(version="1.1.0")
V12 = BaselineConfig(version="1.2.0")
T0 = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)


def life(
    phase: SetupPhase, *, fires: bool = False, side: int = 1, age: int | None = 2
) -> SetupLifecycle:
    return SetupLifecycle(
        phase=phase, side=side, armed_at=T0, trigger_at=T0 + timedelta(minutes=10),
        bars_since_armed=age, fires=fires, reason="test",
    )  # fmt: skip


def ctx(lc: SetupLifecycle | None) -> DecisionContext:
    return DecisionContext(spec=SPEC, equity=100_000.0, lifecycle=lc)


# -- the lifecycle state machine (labels scripted per M5 close) ----------------------------------


def scripted(
    monkeypatch: pytest.MonkeyPatch, script: list[tuple[int, bool, bool, bool]]
) -> tuple[MultiTfBars, Callable[[int], datetime]]:
    """Replay ``script`` = (side, ready, against, trigger) per M5 close, oldest first."""
    bars = multi_tf(minutes=60 * 24 * 3)
    closes = bars.frames[Timeframe.M5]["available_at"].to_list()
    base = len(closes) - len(script)
    by_close = {closes[base + i]: script[i] for i in range(len(script))}

    def fake(
        _bars: MultiTfBars, at: datetime, _cfg: object, _memo: object, _strict: bool = False
    ) -> object:
        side, ready, against, trigger = by_close.get(at, (0, False, False, False))
        return setup_machine._Labels(side, ready, against, trigger)

    monkeypatch.setattr(setup_machine, "_labels_at", fake)

    def at(i: int) -> datetime:
        return datetime.fromtimestamp(closes[base + i].timestamp(), tz=UTC)

    return bars, at


def run(
    monkeypatch: pytest.MonkeyPatch,
    script: list[tuple[int, bool, bool, bool]],
    upto: int,
    **kw: Any,
) -> SetupLifecycle:
    bars, at = scripted(monkeypatch, script)
    return lifecycle(bars, at(upto), lookback=len(script), **kw)


N = (0, False, False, False)  # nothing
R = (1, True, False, False)  # setup ready
T = (1, False, False, True)  # trigger only
RT = (1, True, False, True)  # ready and trigger on the same bar
P = (1, False, False, False)  # pulled away (direction held, not ready)


def test_a_setup_arms_then_triggers_later_and_fires_only_on_the_trigger_bar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = [N, R, P, P, T, P]
    assert run(monkeypatch, script, 0).phase is SetupPhase.NONE
    armed = run(monkeypatch, script, 2)
    assert armed.phase is SetupPhase.ARMED and armed.bars_since_armed == 1 and not armed.fires
    fired = run(monkeypatch, script, 4)
    assert fired.phase is SetupPhase.TRIGGERED and fired.fires and fired.bars_since_armed == 3
    after = run(monkeypatch, script, 5)
    assert not after.fires  # the signal is not repeated; the finished pullback resets the machine
    assert after.phase is SetupPhase.NONE
    persisting = run(monkeypatch, [N, R, P, P, T, R], 5)  # still in the pullback zone
    assert persisting.phase is SetupPhase.TRIGGERED and not persisting.fires


def test_same_bar_setup_and_trigger_is_the_v11_special_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lc = run(monkeypatch, [N, RT], 1)
    assert lc.phase is SetupPhase.TRIGGERED and lc.fires and lc.bars_since_armed == 0


def test_an_armed_setup_expires_after_the_valid_window(monkeypatch: pytest.MonkeyPatch) -> None:
    script = [R, *([P] * 8), T]
    assert run(monkeypatch, script, 6).phase is SetupPhase.ARMED  # 6 bars after arming: still valid
    assert run(monkeypatch, script, 7).phase is SetupPhase.EXPIRED
    late = run(monkeypatch, script, 9)  # a trigger after expiry does not fire
    assert late.phase is SetupPhase.EXPIRED and not late.fires


def test_the_trigger_on_the_last_valid_bar_still_fires(monkeypatch: pytest.MonkeyPatch) -> None:
    script = [R, *([P] * 5), T]
    assert run(monkeypatch, script, 6).fires


def test_a_direction_change_or_a_structure_turning_against_invalidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flipped = run(monkeypatch, [R, P, (-1, False, False, False), T], 3)
    assert flipped.phase is SetupPhase.INVALIDATED and not flipped.fires
    against = run(monkeypatch, [R, P, (1, False, True, False), T], 3)
    assert against.phase is SetupPhase.INVALIDATED and not against.fires


def test_a_new_setup_needs_a_fresh_pullback_not_a_persisting_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisting = [R, R, R, R, R, R, R, R, R, T]  # ready never goes away: expired, no re-arm
    assert run(monkeypatch, persisting, 9).phase is SetupPhase.EXPIRED
    fresh = [R, P, P, P, P, P, P, P, P, R, T]  # expired, ready drops, then a new pullback
    lc = run(monkeypatch, fresh, 10)
    assert lc.phase is SetupPhase.TRIGGERED and lc.fires and lc.bars_since_armed == 1


def test_one_signal_per_pullback_even_if_momentum_flickers(monkeypatch: pytest.MonkeyPatch) -> None:
    script = [R, T, P, T, P, T]
    assert run(monkeypatch, script, 1).fires
    assert not run(monkeypatch, script, 3).fires
    assert not run(monkeypatch, script, 5).fires


def test_a_trigger_without_a_setup_does_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    lc = run(monkeypatch, [P, P, T, T], 3)
    assert lc.phase is SetupPhase.NONE and not lc.fires


def test_the_lifecycle_never_looks_ahead() -> None:
    bars = multi_tf(minutes=60 * 24 * 12, seed=11, drift=0.01, vol=0.4)
    closes = bars.frames[Timeframe.M5]["available_at"].to_list()
    for at in closes[-400::97]:
        assert lifecycle(bars, at) == lifecycle(bars.truncated(at), at)
    assert lifecycle(bars, closes[-5]) == lifecycle(bars.truncated(closes[-5]), closes[-5])


def test_the_lifecycle_is_deterministic() -> None:
    bars = multi_tf(minutes=60 * 24 * 12, seed=3)
    at = bars.frames[Timeframe.M5]["available_at"].to_list()[-50]
    assert lifecycle(bars, at) == lifecycle(bars, at)


# -- decide v1.2 ---------------------------------------------------------------------------------


def test_a_fired_setup_gives_a_buy_with_the_stop_in_the_trigger_time_scale() -> None:
    state = aligned_state()
    s = decide(state, ctx(life(SetupPhase.TRIGGERED, fires=True)), V12)
    assert s.decision is TradeDecision.BUY and s.strategy_version == "1.2.0"
    assert s.stop_loss is not None and s.entry_price is not None
    assert s.entry_price - s.stop_loss == pytest.approx(1.25 * (state.atr_m5 or 0), rel=1e-6)
    assert s.metadata["setup_phase"] == "TRIGGERED"
    assert s.risk_reward is not None and s.risk_reward >= 1.5


def test_v11_keeps_its_own_geometry_and_version() -> None:
    state = aligned_state()
    s = decide(state, DecisionContext(spec=SPEC, equity=100_000.0), V11)
    assert s.strategy_version == "1.1.0"
    assert s.entry_price is not None and s.stop_loss is not None
    assert s.entry_price - s.stop_loss == pytest.approx(1.25 * (state.atr_m15 or 0), rel=1e-6)
    assert BaselineConfig().version == "1.1.0"  # the default does not change silently


def test_versions_do_not_share_signal_or_setup_ids() -> None:
    state = aligned_state()
    a = decide(state, DecisionContext(spec=SPEC, equity=100_000.0), V11)
    b = decide(state, ctx(life(SetupPhase.TRIGGERED, fires=True)), V12)
    assert a.signal_id != b.signal_id and a.setup_id != b.setup_id


@pytest.mark.parametrize(
    ("phase", "fires", "refusal"),
    [
        (SetupPhase.NONE, False, Refusal.NO_SETUP),
        (SetupPhase.EXPIRED, False, Refusal.NO_SETUP),
        (SetupPhase.INVALIDATED, False, Refusal.NO_SETUP),
        (SetupPhase.ARMED, False, Refusal.NO_TRIGGER),
        (SetupPhase.TRIGGERED, False, Refusal.NO_SETUP),  # this pullback already signalled
    ],
)
def test_every_non_firing_phase_waits_with_its_own_reason(
    phase: SetupPhase, fires: bool, refusal: Refusal
) -> None:
    s = decide(aligned_state(), ctx(life(phase, fires=fires)), V12)
    assert s.decision is TradeDecision.WAIT and s.refusal_reasons[0] is refusal
    assert s.metadata["setup_phase"] == phase.value


def test_a_setup_for_the_other_side_or_a_missing_lifecycle_does_not_trade() -> None:
    wrong_side = decide(aligned_state(), ctx(life(SetupPhase.TRIGGERED, fires=True, side=-1)), V12)
    assert wrong_side.decision is TradeDecision.WAIT
    missing = decide(aligned_state(), ctx(None), V12)
    assert missing.refusal_reasons[0] is Refusal.UNKNOWN_STATE


def test_volatility_labels_are_context_in_v12_but_a_veto_in_v11() -> None:
    state = aligned_state(volatility_regime="HIGH")
    old = decide(state, DecisionContext(spec=SPEC, equity=100_000.0), V11)
    assert Refusal.VOLATILITY_TOO_HIGH in old.refusal_reasons
    new = decide(state, ctx(life(SetupPhase.TRIGGERED, fires=True)), V12)
    assert new.decision is TradeDecision.BUY and new.entry_quality == "CAUTION"
    assert any("VOLATILITY HIGH" in w for w in new.warnings)


def test_the_hard_protections_survive_in_v12() -> None:
    trig = ctx(life(SetupPhase.TRIGGERED, fires=True))
    assert (
        Refusal.SPREAD_TOO_WIDE
        in decide(aligned_state(execution_quality="POOR"), trig, V12).refusal_reasons
    )
    assert (
        Refusal.VOLATILITY_TOO_HIGH
        in decide(aligned_state(h4_regime="SHOCK"), trig, V12).refusal_reasons
    )
    assert (
        decide(aligned_state(m1_micro_state="ABNORMAL"), trig, V12).decision is TradeDecision.WAIT
    )
    assert (
        Refusal.MARKET_CLOSED
        in decide(
            aligned_state(market_open=False),
            DecisionContext(
                spec=SPEC, market_open=False, lifecycle=life(SetupPhase.TRIGGERED, fires=True)
            ),
            V12,
        ).refusal_reasons
    )


def test_the_clearance_gate_is_gone_and_the_net_rr_judges_the_room() -> None:
    state = aligned_state(distance_to_resistance=1.0)  # less than 1 ATR(M15) to resistance
    old = decide(state, DecisionContext(spec=SPEC, equity=100_000.0), V11)
    assert Refusal.TOO_CLOSE_TO_RESISTANCE in old.refusal_reasons
    new = decide(state, ctx(life(SetupPhase.TRIGGERED, fires=True)), V12)
    assert new.refusal_reasons == (Refusal.RR_TOO_LOW,)  # the room is judged by the R/R itself


# -- the "why WAIT" funnel is derived from the real decision -------------------------------------


def test_the_stage_report_marks_the_failing_stage_and_what_was_not_reached() -> None:
    wait = decide(aligned_state(), ctx(life(SetupPhase.NONE)), V12)
    stages = stages_from_signal(wait)
    assert [s["stage"] for s in stages] == list(STAGE_NAMES)
    status = {s["stage"]: s["status"] for s in stages}
    assert status["M15 setup"] == "FAIL"
    assert status["H1 direction"] == "PASS" and status["Market & data"] == "PASS"
    assert status["M5 trigger"] == status["Trade plan"] == "NOT_REACHED"
    assert "M15 pullback" in (waiting_for(wait) or "")


def test_a_trade_passes_every_stage_and_has_nothing_to_wait_for() -> None:
    buy = decide(aligned_state(), ctx(life(SetupPhase.TRIGGERED, fires=True)), V12)
    assert {s["status"] for s in stages_from_signal(buy)} == {"PASS"}
    assert waiting_for(buy) is None


def test_waiting_for_an_armed_setup_names_the_trigger_and_never_predicts() -> None:
    armed = decide(aligned_state(), ctx(life(SetupPhase.ARMED, age=3)), V12)
    text = waiting_for(armed) or ""
    assert "M5" in text and "trigger" in text and "armed 3" in text
    assert not any(w in text.lower() for w in ("will", "expect", "likely", "probab"))


# -- signal telemetry (the chart markers come from these records) --------------------------------


def test_actionable_decisions_are_logged_once_per_setup_and_survive_a_restart(
    tmp_path: Path,
) -> None:
    buy = decide(aligned_state(), ctx(life(SetupPhase.TRIGGERED, fires=True)), V12)
    at = datetime(2026, 3, 2, 10, 5, tzinfo=UTC)
    for _ in range(3):
        DecisionTelemetry(tmp_path).append_signal(buy, at=at)  # a new object each time = a restart
    records = DecisionTelemetry(tmp_path).read_signals(at)
    assert len(records) == 1
    assert records[0]["side"] == "BUY" and records[0]["entry"] == buy.entry_price
    assert records[0]["strategy_version"] == "1.2.0" and records[0]["setup_id"] == buy.setup_id


def test_helpers_import_is_used() -> None:
    assert helpers.T0 is not None


# -- v1.2.1: the review fixes (v1.2.0 keeps its pre-registered behaviour) -------------------------

V121 = BaselineConfig(version="1.2.1")


def test_a_choch_against_the_setup_is_against_in_121_but_not_in_120(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars = multi_tf(minutes=60 * 24 * 3)
    at = bars.frames[Timeframe.M5]["available_at"][-1]
    monkeypatch.setattr(setup_machine, "_h1_trend", lambda _s: "BULLISH")
    monkeypatch.setattr(setup_machine, "_structure_label", lambda _s: "REVERSAL_DOWN")
    monkeypatch.setattr(setup_machine, "_pullback", lambda _s: "NONE")
    monkeypatch.setattr(setup_machine, "_m5_momentum", lambda _s: "UP")
    memo = SnapshotMemo()
    cfg = StateConfig()
    old = setup_machine._labels_at(bars, at, cfg, memo)
    new = setup_machine._labels_at(bars, at, cfg, memo, True)
    assert old is not None and new is not None
    assert old.against is False and new.against is True


def test_a_buy_is_refused_after_a_bearish_choch_in_121_only() -> None:
    state = aligned_state(m15_structure="REVERSAL_DOWN")
    trig = ctx(life(SetupPhase.TRIGGERED, fires=True))
    assert decide(state, trig, V12).decision is TradeDecision.BUY  # the pre-registered behaviour
    refused = decide(state, trig, V121)
    assert refused.decision is TradeDecision.WAIT
    assert refused.refusal_reasons[0] is Refusal.TIMEFRAME_CONFLICT
    sell = aligned_state(h1_trend="BEARISH", m15_structure="REVERSAL_UP")
    assert decide(sell, ctx(life(SetupPhase.TRIGGERED, fires=True, side=-1)), V121).decision is (
        TradeDecision.WAIT
    )


def test_an_armed_setup_cannot_survive_a_gap_in_the_data_in_121(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars = multi_tf(minutes=60 * 24 * 8)
    m5 = bars.frames[Timeframe.M5]
    closes = m5["available_at"].to_list()
    a = len(closes) - 600
    gapped = m5.filter(
        (m5["available_at"] <= closes[a + 1]) | (m5["available_at"] >= closes[a + 500])
    )
    holed = MultiTfBars({**bars.frames, Timeframe.M5: gapped})
    kept = gapped["available_at"].to_list()
    i = kept.index(closes[a + 1])
    script = {kept[i - 1]: R, kept[i + 1]: T}  # armed before the hole, trigger just after it

    def fake(
        _bars: MultiTfBars, at: datetime, _cfg: object, _memo: object, _strict: bool = False
    ) -> object:
        side, ready, against, trigger = script.get(at, (1, False, False, False))
        return setup_machine._Labels(side, ready, against, trigger)

    monkeypatch.setattr(setup_machine, "_labels_at", fake)
    at = kept[i + 1]
    plain = lifecycle(holed, at)
    hard = lifecycle(holed, at, hardened=True)
    assert plain.fires  # 1.2.0 counts bars, so the trigger after the hole still fires
    assert not hard.fires and hard.phase is SetupPhase.EXPIRED


def test_an_abnormal_m1_is_reported_as_volatility_not_spread_in_121() -> None:
    state = aligned_state(m1_micro_state="ABNORMAL", execution_quality="POOR")
    trig = ctx(life(SetupPhase.TRIGGERED, fires=True))
    assert decide(state, trig, V12).refusal_reasons[0] is Refusal.SPREAD_TOO_WIDE
    assert decide(state, trig, V121).refusal_reasons[0] is Refusal.VOLATILITY_TOO_HIGH
    wide = aligned_state(execution_quality="POOR")  # a real spread problem keeps its own reason
    assert decide(wide, trig, V121).refusal_reasons[0] is Refusal.SPREAD_TOO_WIDE


def test_ablation_variants_never_share_ids_with_the_production_variant() -> None:
    trig = ctx(life(SetupPhase.TRIGGERED, fires=True))
    prod = decide(aligned_state(), trig, V121)
    plain = decide(aligned_state(), trig, BaselineConfig(version="1.2.1", v12_vol_warning=False))
    assert prod.signal_id != plain.signal_id and prod.setup_id != plain.setup_id
    assert (
        prod.metadata["variant_flags"] == "" and plain.metadata["variant_flags"] == "no_vol_warning"
    )
    no_lifecycle = BaselineConfig(version="1.2.1", v12_lifecycle=False)
    a = decide(aligned_state(), trig, no_lifecycle)
    b = decide(aligned_state(), trig, no_lifecycle)
    assert a.setup_id == b.setup_id  # stable, not derived from the polling time
