"""RunPlan: the T4.6 matrix (mode x whitelist x flags x rules x override x tier x evidence).

The matrix proves two things over every combination:

* a FUNDED plan that may call ``order_send`` exists only when EVERY condition holds (funded flag
  alone, funded-whitelisted login, funded server, all ``must_verify`` rules verified,
  ``--confirm-mode FUNDED``, a sending tier allowed for the strategy's evidence);
* on the funded account, anything that is not VALIDATED risks at most 0.25% per trade.
"""

from __future__ import annotations

import itertools
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from xau_edge.config import Settings
from xau_edge.funded.identity import AccountIdentity, ModeError, RunMode
from xau_edge.funded.plan import (
    UNVALIDATED_RISK_CAP_PCT,
    PlanError,
    RunPlan,
    build_run_plan,
)
from xau_edge.funded.rollout import TierConstraints, load_rollout
from xau_edge.funded.rules import FundedRule, FundedRules, FundedRulesNotVerifiedError

ROOT = Path(__file__).parents[3]
ROLLOUT = load_rollout(ROOT / "configs" / "execution" / "rollout.yaml")
TIERS = {
    t.tier: TierConstraints(t.tier, t.name, t.send_orders, t.lot_cap, t.risk_pct)
    for t in ROLLOUT.tiers
}

DEMO_LOGIN, FUNDED_LOGIN, OTHER_LOGIN = "111", "999", "555"
DEMO_SERVER, FUNDED_SERVER = "Demo-Server", "Funded-Server"
STRATEGY = "h03_london_open"


def _rules(state: str) -> FundedRules | None:
    if state == "missing":
        return None
    verified = FundedRule(
        status="verified_official", verified_on=date(2026, 10, 9), source="FTMO support"
    )
    return FundedRules(
        name="ftmo-funded-test",
        rules={
            "daily_loss_limit_pct": FundedRule(value=5.0, must_verify=False),
            "max_loss_limit_pct": FundedRule(value=10.0, must_verify=False),
            "max_loss_kind": FundedRule(value="static", must_verify=False),
            "ea_automated_trading": verified,
            "news_trading_window": verified if state == "verified" else FundedRule(),
        },
    )


def _settings(*, funded: bool, demo: bool, override: str) -> Settings | None:
    """The configuration for one cell, or ``None`` when ``Settings`` itself refuses it."""
    values: dict[str, Any] = {
        "demo_allowed_accounts": DEMO_LOGIN,
        "demo_allowed_servers": DEMO_SERVER,
        "funded_allowed_accounts": FUNDED_LOGIN,
        "funded_allowed_servers": FUNDED_SERVER,
        "funded_validated_risk_pct": 0.5,
    }
    if funded:
        values |= {"enable_funded_trading": True, "funded_magic": 9, "funded_initial_capital": 1e5}
    if demo:
        values |= {
            "enable_demo_trading": True,
            "demo_dry_run": False,
            "demo_magic": 7,
            "demo_initial_capital": 1e5,
        }
    if override != "off":
        values["funded_allow_unvalidated"] = True
    if override == "on+strategy":
        values["funded_strategy_id"] = STRATEGY
    try:
        return Settings(_env_file=None, **values)
    except ValidationError:
        return None


def _plan(settings: Settings, cell: tuple[Any, ...], rules_state: str) -> RunPlan | None:
    login, server, confirm, tier, validated = cell
    try:
        return build_run_plan(
            settings,
            AccountIdentity(login, server, trade_mode_demo=True),
            rules=_rules(rules_state),
            tier=TIERS[tier],
            validated=validated,
            confirm=confirm,
        )
    except (ModeError, FundedRulesNotVerifiedError):
        return None


INNER = list(
    itertools.product(
        (DEMO_LOGIN, FUNDED_LOGIN, OTHER_LOGIN),
        (DEMO_SERVER, FUNDED_SERVER),
        (None, "DEMO", "FUNDED"),
        (0, 1, 2, 3),
        (False, True),
    )
)


@pytest.mark.parametrize("override", ["off", "on", "on+strategy"])
@pytest.mark.parametrize("rules_state", ["verified", "pending", "missing"])
@pytest.mark.parametrize(
    ("funded_flag", "demo_flag"), [(False, False), (True, False), (False, True), (True, True)]
)
def test_the_matrix(funded_flag: bool, demo_flag: bool, rules_state: str, override: str) -> None:
    settings = _settings(funded=funded_flag, demo=demo_flag, override=override)
    if settings is None:
        # Settings refuses: both modes at once, or an override outside funded / without a strategy.
        assert (
            (funded_flag and demo_flag)
            or override == "on"
            or (override != "off" and not funded_flag)
        )
        return
    for cell in INNER:
        login, server, confirm, tier, validated = cell
        plan = _plan(settings, cell, rules_state)
        if plan is None:
            continue
        # funded risk: anything not VALIDATED is capped at 0.25%, whatever tier or settings say
        if plan.mode is RunMode.FUNDED and plan.evidence_label != "VALIDATED":
            assert plan.risk_pct <= UNVALIDATED_RISK_CAP_PCT
        # dry-run never reaches a broker, never on a funded login
        if plan.mode is RunMode.DRY_RUN:
            assert not plan.send_orders
            assert not plan.shadow
            assert plan.bridge_dry_run
            assert login != FUNDED_LOGIN
            assert plan.override is None
        if plan.mode is RunMode.DEMO:
            assert (demo_flag, funded_flag, login, server, confirm) == (
                True, False, DEMO_LOGIN, DEMO_SERVER, "DEMO",
            )  # fmt: skip
            assert plan.require_demo
            assert plan.override is None
        if plan.mode is RunMode.FUNDED:
            assert (funded_flag, demo_flag, login, server, confirm, rules_state) == (
                True, False, FUNDED_LOGIN, FUNDED_SERVER, "FUNDED", "verified",
            )  # fmt: skip
            assert plan.require_demo is False
            assert plan.rollout_tier == tier
            assert tier <= 2 or validated
            if plan.send_orders:
                assert tier >= 1
                assert not plan.shadow
            else:
                assert tier == 0
                assert plan.shadow
            if plan.override is not None:
                assert override == "on+strategy"
                assert not validated
                assert plan.override.strategy_id == STRATEGY
                assert plan.evidence_label == "UNVALIDATED"
            elif not validated:
                assert plan.evidence_label == "NONE"


def test_a_sending_funded_plan_exists_only_when_every_condition_holds() -> None:
    sending: set[tuple[Any, ...]] = set()
    for funded_flag, demo_flag, override, rules_state in itertools.product(
        (False, True),
        (False, True),
        ("off", "on", "on+strategy"),
        ("verified", "pending", "missing"),
    ):
        settings = _settings(funded=funded_flag, demo=demo_flag, override=override)
        if settings is None:
            continue
        for cell in INNER:
            plan = _plan(settings, cell, rules_state)
            if plan is not None and plan.mode is RunMode.FUNDED and plan.send_orders:
                login, server, confirm, tier, _validated = cell
                sending.add((funded_flag, demo_flag, rules_state, login, server, confirm, tier))
    assert sending == {
        (True, False, "verified", FUNDED_LOGIN, FUNDED_SERVER, "FUNDED", tier) for tier in (1, 2, 3)
    }


# -- single rules -----------------------------------------------------------------------------


def _funded(**over: Any) -> Settings:
    values: dict[str, Any] = {
        "enable_funded_trading": True,
        "funded_allowed_accounts": FUNDED_LOGIN,
        "funded_allowed_servers": FUNDED_SERVER,
        "funded_magic": 9,
        "funded_initial_capital": 100_000.0,
        "demo_allowed_accounts": DEMO_LOGIN,
    }
    values.update(over)
    return Settings(_env_file=None, **values)


def _funded_plan(settings: Settings, tier: int | TierConstraints, *, validated: bool) -> RunPlan:
    return build_run_plan(
        settings,
        AccountIdentity(FUNDED_LOGIN, FUNDED_SERVER, trade_mode_demo=False),
        rules=_rules("verified"),
        tier=TIERS[tier] if isinstance(tier, int) else tier,
        validated=validated,
        confirm="FUNDED",
    )


def test_tier_zero_is_shadow_only() -> None:
    plan = _funded_plan(_funded(), 0, validated=False)
    assert plan.send_orders is False
    assert plan.shadow is True
    assert plan.uses_executor is True
    assert plan.bridge_dry_run is False  # intents reach the executor, which only order_checks them
    assert plan.rollout_tier_name == "shadow"


def test_tier_one_caps_the_lot_and_tier_two_risks_a_quarter_percent() -> None:
    one = _funded_plan(_funded(), 1, validated=False)
    assert one.send_orders is True
    assert one.lot_cap == 0.01
    assert one.risk_pct <= 0.25
    two = _funded_plan(_funded(), 2, validated=False)
    assert two.lot_cap is None
    assert two.risk_pct == 0.25


def test_tier_three_is_refused_without_validated_evidence() -> None:
    with pytest.raises(PlanError, match="VALIDATED"):
        _funded_plan(_funded(funded_validated_risk_pct=0.5), 3, validated=False)


def test_tier_three_needs_the_monte_carlo_risk_and_then_uses_it() -> None:
    with pytest.raises(PlanError, match="FUNDED_VALIDATED_RISK_PCT"):
        _funded_plan(_funded(), 3, validated=True)
    plan = _funded_plan(_funded(funded_validated_risk_pct=0.4), 3, validated=True)
    assert plan.risk_pct == 0.4
    assert plan.evidence_label == "VALIDATED"
    assert plan.override is None


def test_a_funded_plan_needs_a_tier() -> None:
    with pytest.raises(PlanError, match="rollout tier"):
        build_run_plan(
            _funded(),
            AccountIdentity(FUNDED_LOGIN, FUNDED_SERVER, trade_mode_demo=True),
            rules=_rules("verified"),
            tier=None,
            validated=False,
            confirm="FUNDED",
        )


def test_the_unvalidated_cap_holds_even_against_a_bypassed_settings_object_and_a_bad_tier() -> None:
    # model_construct skips validation: a deliberate bypass of the 0.25 field ceiling
    rogue = Settings.model_construct(
        **(_funded().model_dump() | {"funded_risk_pct": 1.5, "funded_allow_unvalidated": True,
                                     "funded_strategy_id": STRATEGY})
    )  # fmt: skip
    greedy_tier = TierConstraints(2, "quarter-percent", True, None, 2.0)
    plan = _funded_plan(rogue, greedy_tier, validated=False)
    assert plan.evidence_label == "UNVALIDATED"
    assert plan.risk_pct == UNVALIDATED_RISK_CAP_PCT
    shadow = _funded_plan(rogue, TierConstraints(0, "shadow", False, None, None), validated=False)
    assert shadow.risk_pct == UNVALIDATED_RISK_CAP_PCT


def test_the_override_needs_the_flag_and_the_strategy_and_is_dropped_for_a_validated_strategy() -> (
    None
):
    off = _funded_plan(_funded(funded_strategy_id=STRATEGY), 2, validated=False)
    assert off.override is None
    assert off.evidence_label == "NONE"
    on = _funded_plan(
        _funded(funded_allow_unvalidated=True, funded_strategy_id=STRATEGY), 2, validated=False
    )
    assert on.override is not None
    assert on.override.enabled
    assert on.override.strategy_id == STRATEGY
    assert on.strategy_id == STRATEGY
    assert on.evidence_label == "UNVALIDATED"
    validated = _funded_plan(
        _funded(funded_allow_unvalidated=True, funded_strategy_id=STRATEGY), 2, validated=True
    )
    assert validated.override is None
    assert validated.evidence_label == "VALIDATED"


def test_funded_uses_its_own_files_magic_capital_whitelist_and_rules_profile() -> None:
    plan = _funded_plan(_funded(funded_max_lots=0.5), 1, validated=False)
    assert plan.magic == 9
    assert plan.initial_capital == 100_000.0
    assert plan.allowed_accounts == (FUNDED_LOGIN,)
    assert plan.state_path == Path("data/execution/funded_state.sqlite")
    assert plan.journal_path == Path("data/execution/funded_journal.jsonl")
    assert plan.prop_profile_source.replace("\\", "/") == "configs/prop/ftmo_funded.yaml"
    assert plan.max_lots == 0.5
    assert plan.status_mode == "funded"


def test_dry_run_and_demo_plans() -> None:
    dry = build_run_plan(
        Settings(_env_file=None),
        AccountIdentity(OTHER_LOGIN, "Any", trade_mode_demo=True),
        rules=None,
        tier=None,
        validated=False,
        confirm=None,
    )
    assert dry.mode is RunMode.DRY_RUN
    assert dry.status_mode == "dry-run"
    assert (dry.send_orders, dry.shadow, dry.uses_executor) == (False, False, False)
    assert dry.allowed_accounts == (OTHER_LOGIN,)
    assert dry.require_demo is True
    assert dry.state_path == Path("data/execution/state.sqlite")
    demo = build_run_plan(
        Settings(
            _env_file=None,
            enable_demo_trading=True,
            demo_dry_run=False,
            demo_allowed_accounts=DEMO_LOGIN,
            demo_magic=7,
            demo_initial_capital=50_000.0,
        ),
        AccountIdentity(DEMO_LOGIN, "Any", trade_mode_demo=True),
        rules=None,
        tier=None,
        validated=False,
        confirm="DEMO",
    )
    assert demo.mode is RunMode.DEMO
    assert demo.send_orders is True
    assert demo.lot_cap is None
    assert demo.magic == 7
    assert demo.initial_capital == 50_000.0
    assert demo.risk_pct == 0.5
    assert demo.evidence_label == "NONE"
