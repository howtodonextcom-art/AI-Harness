"""The bot and rollout scripts: honest docstrings, no forcing options, a thin composition root.

The scripts are only imported here (never run): nothing connects to a terminal.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS = Path(__file__).parents[2] / "scripts"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"script_{name}", SCRIPTS / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_bot_docstring_says_it_can_send_orders_and_documents_every_exit_code() -> None:
    doc = _load("demo_trader").__doc__ or ""
    assert "NEVER submits an order" not in doc
    assert "CAN SEND ORDERS" in doc
    assert "--confirm-mode FUNDED" in doc
    for code in ("0 ", "2 ", "3 ", "4 ", "5 ", "6 ", "7 "):
        assert f"\n    {code}" in doc


def test_the_bot_mode_comes_from_configuration_and_confirmation_is_restricted() -> None:
    parser = _load("demo_trader").build_parser()
    assert parser.parse_args([]).confirm_mode is None
    assert parser.parse_args(["--confirm-mode", "FUNDED"]).confirm_mode == "FUNDED"
    with pytest.raises(SystemExit):
        parser.parse_args(["--confirm-mode", "LIVE"])
    options = {a.dest for a in parser._actions}
    assert not options & {"mode", "live", "funded", "lots", "risk", "direction"}


def test_the_bot_script_never_calls_order_send_and_builds_through_bot_app() -> None:
    tree = ast.parse((SCRIPTS / "demo_trader.py").read_text(encoding="utf-8"))
    attributes = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "order_send" not in attributes
    for required in (
        "BotApp",
        "CountingMt5",
        "build_run_plan",
        "assert_live_trading_disabled",
        "setup_service_logging",
        "acquire_lock",
        "EntryGuard",
        "PropFacts",
        "banner",
    ):
        assert required in names, required


def test_the_rollout_cli_has_status_and_confirmed_promote_only() -> None:
    parser = _load("rollout").build_parser()
    assert parser.parse_args(["status"]).command == "status"
    assert parser.parse_args(["promote"]).confirm is False
    assert parser.parse_args(["promote", "--confirm"]).confirm is True
    for forbidden in (["promote", "--force"], ["promote", "--tier", "3"], ["demote"], ["set", "2"]):
        with pytest.raises(SystemExit):
            parser.parse_args(forbidden)
