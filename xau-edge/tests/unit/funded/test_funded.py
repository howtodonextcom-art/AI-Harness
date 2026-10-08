"""Funded-account policy: rules, identity, start-up authorisation matrix, rollout, override."""

from __future__ import annotations

import itertools
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from xau_edge.config import Settings
from xau_edge.execution.state import ExecutionState
from xau_edge.funded.identity import (
    AccountIdentity,
    ModeError,
    RunMode,
    banner,
    mask_login,
    requested_mode,
    resolve_mode,
)
from xau_edge.funded.rollout import (
    RolloutController,
    RolloutError,
    load_rollout,
)
from xau_edge.funded.rules import (
    FundedRule,
    FundedRules,
    FundedRulesNotVerifiedError,
    load_funded_rules,
)
from xau_edge.funded.startup import authorize_start

ROOT = Path(__file__).parents[3]
NOW = datetime(2026, 3, 4, 14, 0, tzinfo=UTC)


def _verified() -> FundedRule:
    return FundedRule(
        status="verified_official", must_verify=True, verified_on=date(2026, 10, 9), source="FTMO"
    )


def _rules(*, verified: bool) -> FundedRules:
    rule = _verified() if verified else FundedRule()
    return FundedRules(
        name="t",
        rules={
            "daily_loss_limit_pct": FundedRule(value=5.0, must_verify=False),
            "max_loss_limit_pct": FundedRule(value=10.0, must_verify=False),
            "max_loss_kind": FundedRule(value="static", must_verify=False),
            "ea_automated_trading": rule,
        },
    )


# -- rules ---------------------------------------------------------------------------------------


def test_the_shipped_funded_rules_are_all_pending_so_funded_is_locked() -> None:
    rules = load_funded_rules(ROOT / "configs" / "prop" / "ftmo_funded.yaml")
    pending = rules.pending()
    assert "ea_automated_trading" in pending
    assert "news_trading_window" in pending
    assert "request_definition_and_limit" in pending
    assert "market_close_margin" in pending
    with pytest.raises(FundedRulesNotVerifiedError, match="ea_automated_trading"):
        rules.require_verified()
    assert rules.to_prop_profile().daily_loss_limit_pct == 5.0


@pytest.mark.parametrize(
    "rule",
    [
        FundedRule(status="secondary", verified_on=date(2026, 1, 1), source="x"),
        FundedRule(status="verified_official", verified_on=None, source="x"),
        FundedRule(status="verified_official", verified_on=date(2026, 1, 1), source=""),
        FundedRule(status="verified_official", verified_on=date(2026, 1, 1), source=None),
        FundedRule(status="unverified"),
    ],
)
def test_a_must_verify_rule_needs_official_status_a_date_and_a_source(rule: FundedRule) -> None:
    rules = FundedRules(name="t", rules={"x": rule})
    assert rules.pending() == ["x"]


def test_a_verified_rule_and_a_not_required_rule_do_not_block() -> None:
    rules = FundedRules(
        name="t",
        rules={"a": _verified(), "b": FundedRule(status="unverified", must_verify=False)},
    )
    assert rules.pending() == []
    rules.require_verified()


# -- identity -------------------------------------------------------------------------------------


def test_the_account_number_is_masked_to_three_digits() -> None:
    assert mask_login("900123456") == "***456"
    assert mask_login("12") == "***"
    text = banner(RunMode.DEMO, AccountIdentity("900123456", "S1", True), "ftmo-2step")
    assert "900123456" not in text
    assert "***456" in text
    assert "MODE=DEMO" in text
    assert "trade_mode=DEMO" in text


def _settings(**over: Any) -> Settings:
    base: dict[str, Any] = {
        "demo_allowed_accounts": "111",
        "demo_allowed_servers": "Demo-Server",
    }
    base.update(over)
    return Settings(_env_file=None, **base)


def _funded_settings(**over: Any) -> Settings:
    base: dict[str, Any] = {
        "enable_funded_trading": True,
        "funded_allowed_accounts": "999",
        "funded_allowed_servers": "Funded-Server",
        "funded_magic": 9,
        "funded_initial_capital": 100_000.0,
        "demo_allowed_accounts": "111",
    }
    base.update(over)
    return Settings(_env_file=None, **base)


def test_the_requested_mode_follows_the_flags() -> None:
    assert requested_mode(Settings(_env_file=None)) is RunMode.DRY_RUN
    live_demo = _settings(
        enable_demo_trading=True, demo_dry_run=False, demo_magic=1, demo_initial_capital=1.0
    )
    assert requested_mode(live_demo) is RunMode.DEMO
    assert requested_mode(_funded_settings()) is RunMode.FUNDED


def test_dry_run_and_demo_refuse_a_funded_account() -> None:
    funded = AccountIdentity("999", "Funded-Server", True)
    s = _funded_settings(enable_funded_trading=False, funded_allow_unvalidated=False)
    with pytest.raises(ModeError, match="FUNDED-whitelisted"):
        resolve_mode(s, funded)
    demo = _settings(
        enable_demo_trading=True,
        demo_dry_run=False,
        demo_magic=1,
        demo_initial_capital=1.0,
        funded_allowed_accounts="999",
    )
    with pytest.raises(ModeError, match="FUNDED-whitelisted"):
        resolve_mode(demo, funded)


def test_funded_mode_refuses_a_demo_account_an_unknown_one_and_a_wrong_server() -> None:
    s = _funded_settings()
    with pytest.raises(ModeError, match="DEMO-whitelisted"):
        resolve_mode(s, AccountIdentity("111", "Funded-Server", True))
    with pytest.raises(ModeError, match="not on the funded whitelist"):
        resolve_mode(s, AccountIdentity("555", "Funded-Server", True))
    with pytest.raises(ModeError, match="server"):
        resolve_mode(s, AccountIdentity("999", "Other-Server", True))
    assert resolve_mode(s, AccountIdentity("999", "Funded-Server", False)) is RunMode.FUNDED


def test_trade_mode_is_not_used_to_identify_the_account() -> None:
    s = _funded_settings()
    for demo_flag in (True, False):
        assert resolve_mode(s, AccountIdentity("999", "Funded-Server", demo_flag)) is RunMode.FUNDED


# -- the authorisation matrix (T4.6) -------------------------------------------------------------


def test_funded_start_needs_every_condition_and_nothing_else_passes() -> None:
    combos = itertools.product(
        (True, False),  # funded flag
        ("999", "111", "555"),  # funded / demo / unknown login
        ("Funded-Server", "Other"),  # server
        (True, False),  # rules verified
        ("FUNDED", "DEMO", None),  # confirmation
    )
    passed: list[tuple[Any, ...]] = []
    for flag, login, server, verified, confirm in combos:
        settings = _funded_settings() if flag else Settings(_env_file=None)
        identity = AccountIdentity(login, server, True)
        try:
            mode = authorize_start(
                settings, identity, confirm=confirm, rules=_rules(verified=verified)
            )
        except (ModeError, FundedRulesNotVerifiedError):
            continue
        if mode is RunMode.FUNDED:
            passed.append((flag, login, server, verified, confirm))
    assert passed == [(True, "999", "Funded-Server", True, "FUNDED")]


def test_a_funded_start_without_a_rules_file_is_refused() -> None:
    with pytest.raises(ModeError, match="rules file"):
        authorize_start(
            _funded_settings(),
            AccountIdentity("999", "Funded-Server", True),
            confirm="FUNDED",
            rules=None,
        )


def test_demo_and_funded_whitelists_keep_demo_mode_demo_only() -> None:
    demo = _settings(
        enable_demo_trading=True, demo_dry_run=False, demo_magic=1, demo_initial_capital=1.0
    )
    ident = AccountIdentity("111", "Demo-Server", True)
    assert authorize_start(demo, ident, confirm="DEMO", rules=None) is RunMode.DEMO
    with pytest.raises(ModeError, match="--confirm-mode"):
        authorize_start(demo, ident, confirm=None, rules=None)
    with pytest.raises(ModeError, match="not on the demo whitelist"):
        authorize_start(
            demo, AccountIdentity("555", "Demo-Server", True), confirm="DEMO", rules=None
        )
    with pytest.raises(ModeError, match="server"):
        authorize_start(demo, AccountIdentity("111", "Elsewhere", True), confirm="DEMO", rules=None)
    # dry-run needs no confirmation and sends nothing
    assert (
        authorize_start(Settings(_env_file=None), ident, confirm=None, rules=None)
        is RunMode.DRY_RUN
    )


# -- rollout --------------------------------------------------------------------------------------


def _controller(tmp_path: Path, *, validated: bool = False) -> RolloutController:
    config = load_rollout(ROOT / "configs" / "execution" / "rollout.yaml")
    return RolloutController(ExecutionState(tmp_path / "s.sqlite"), config, validated=validated)


def test_the_shipped_rollout_has_four_tiers_with_the_agreed_limits() -> None:
    config = load_rollout(ROOT / "configs" / "execution" / "rollout.yaml")
    assert [t.name for t in config.tiers] == [
        "shadow",
        "minimum-lot",
        "quarter-percent",
        "validated-sizing",
    ]
    assert config.tier(0).send_orders is False
    assert config.tier(1).lot_cap == 0.01
    assert config.tier(2).risk_pct == 0.25
    assert config.tier(3).requires_validated is True
    assert config.tier(0).exit.min_trading_days == 5
    assert config.tier(1).exit.min_orders == 10
    assert config.tier(1).exit.max_rejected_or_unknown == 0
    assert config.tier(2).exit.min_weeks == 4


def test_a_fresh_state_starts_in_the_shadow_tier(tmp_path: Path) -> None:
    c = _controller(tmp_path)
    assert c.stored_tier() == 0
    constraints = c.constraints()
    assert constraints.name == "shadow"
    assert constraints.send_orders is False


def test_shadow_promotion_needs_five_shadow_trading_days(tmp_path: Path) -> None:
    c = _controller(tmp_path)
    decision = c.evaluate_promotion(NOW)
    assert not decision.eligible
    assert "5 more trading day(s) needed" in decision.unmet
    with pytest.raises(RolloutError, match="refused"):
        c.promote(NOW)
    for i in range(5):
        c.record_shadow_day(f"2026-03-0{i + 1}")
    assert c.evaluate_promotion(NOW).eligible
    c.promote(NOW)
    assert c.stored_tier() == 1
    assert c.constraints().lot_cap == 0.01


def test_minimum_lot_tier_needs_ten_clean_orders(tmp_path: Path) -> None:
    c = _controller(tmp_path)
    c.state.set_meta("rollout_tier", "1")
    c.state.set_meta("rollout_tier_started_at", (NOW - timedelta(days=1)).isoformat())
    assert any("filled order" in u for u in c.evaluate_promotion(NOW).unmet)
    for i in range(10):
        c.state.begin_submission(f"i{i}", f"h{i}")
        c.state.finish_submission(f"i{i}", "FILLED", ticket=str(i))
    now = datetime.now(UTC)
    assert c.evaluate_promotion(now).eligible
    c.state.begin_submission("bad", "hb")
    c.state.finish_submission("bad", "REJECTED", retcode=10006)
    decision = c.evaluate_promotion(now)
    assert not decision.eligible
    assert any("rejected/unknown" in u for u in decision.unmet)


def test_quarter_percent_tier_needs_four_weeks(tmp_path: Path) -> None:
    c = _controller(tmp_path, validated=True)
    c.state.set_meta("rollout_tier", "2")
    c.state.set_meta("rollout_tier_started_at", (NOW - timedelta(weeks=3)).isoformat())
    assert not c.evaluate_promotion(NOW).eligible
    c.state.set_meta("rollout_tier_started_at", (NOW - timedelta(weeks=5)).isoformat())
    assert c.evaluate_promotion(NOW).eligible
    c.promote(NOW)
    assert c.constraints().name == "validated-sizing"


def test_an_unvalidated_strategy_is_capped_at_tier_two_whatever_is_stored(tmp_path: Path) -> None:
    c = _controller(tmp_path, validated=False)
    c.state.set_meta("rollout_tier", "3")  # even a tampered state cannot lift the cap
    assert c.stored_tier() == 3
    assert c.effective_tier() == 2
    assert c.constraints().name == "quarter-percent"
    c.state.set_meta("rollout_tier", "2")
    c.state.set_meta("rollout_tier_started_at", (NOW - timedelta(weeks=9)).isoformat())
    decision = c.evaluate_promotion(NOW)
    assert not decision.eligible
    assert any("VALIDATED" in u or "UNVALIDATED" in u for u in decision.unmet)
    with pytest.raises(RolloutError):
        c.promote(NOW)


def test_the_highest_tier_has_nowhere_to_go(tmp_path: Path) -> None:
    c = _controller(tmp_path, validated=True)
    c.state.set_meta("rollout_tier", "3")
    assert c.evaluate_promotion(NOW).target is None
    with pytest.raises(RolloutError):
        c.promote(NOW)
