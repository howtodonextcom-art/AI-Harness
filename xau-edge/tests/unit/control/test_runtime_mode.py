"""runtime_mode.json: only DRY_RUN or DEMO, bounded by .env, never FUNDED (ADR-0023)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from xau_edge.config import Settings
from xau_edge.control.runtime_mode import (
    RuntimeMode,
    RuntimeModeError,
    RuntimeModeRecord,
    apply_runtime_mode,
    describe_settings_error,
    effective_mode,
    env_ceiling,
    parse_runtime_mode,
    read_runtime_mode,
    write_runtime_mode,
)

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
DEMO_ENV: dict[str, Any] = {
    "enable_demo_trading": True,
    "demo_allowed_accounts": "12345678",
    "demo_magic": 777,
    "demo_initial_capital": 100_000.0,
}


def _settings(**over: Any) -> Settings:
    return Settings(_env_file=None, **over)


def _record(mode: RuntimeMode) -> RuntimeModeRecord:
    return RuntimeModeRecord(mode=mode, set_at=NOW)


@pytest.mark.parametrize(
    "bad", ["FUNDED", "LIVE", "demo", "dry_run", "DRY-RUN", "", " DEMO", None, 1, ["DEMO"]]
)
def test_the_validator_refuses_everything_but_dry_run_and_demo(bad: object) -> None:
    with pytest.raises(RuntimeModeError):
        parse_runtime_mode(bad)
    with pytest.raises(ValueError, match="DRY_RUN or DEMO"):
        RuntimeModeRecord.model_validate({"mode": bad, "set_at": NOW.isoformat()})


@pytest.mark.parametrize("good", ["DRY_RUN", "DEMO"])
def test_the_two_allowed_modes_round_trip(tmp_path: Path, good: str) -> None:
    path = tmp_path / "runtime_mode.json"
    write_runtime_mode(path, good, NOW)
    record = read_runtime_mode(path)
    assert record is not None
    assert record.mode.value == good
    assert record.source == "web"


@pytest.mark.parametrize("bad", ["FUNDED", "LIVE", "funded"])
def test_writing_funded_or_live_is_refused_and_leaves_no_file(tmp_path: Path, bad: str) -> None:
    path = tmp_path / "runtime_mode.json"
    with pytest.raises(RuntimeModeError):
        write_runtime_mode(path, bad, NOW)
    assert not path.exists()


@pytest.mark.parametrize(
    "content",
    [
        {"mode": "FUNDED", "set_at": NOW.isoformat()},
        {"mode": "LIVE", "set_at": NOW.isoformat()},
        {"mode": "DEMO", "set_at": NOW.isoformat(), "enable_funded_trading": True},
        {"mode": "DEMO"},
        "DEMO",
    ],
)
def test_a_hand_edited_file_with_anything_else_is_refused(tmp_path: Path, content: Any) -> None:
    path = tmp_path / "runtime_mode.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(RuntimeModeError):
        read_runtime_mode(path)


def test_no_file_means_env_decides(tmp_path: Path) -> None:
    assert read_runtime_mode(tmp_path / "missing.json") is None
    settings = _settings(**DEMO_ENV, demo_dry_run=False)
    assert apply_runtime_mode(settings, None) == (settings, None)
    assert effective_mode(settings, None) is RuntimeMode.DEMO


def test_demo_from_the_file_is_ignored_when_env_does_not_enable_demo_trading() -> None:
    settings = _settings()
    applied, note = apply_runtime_mode(settings, _record(RuntimeMode.DEMO))
    assert applied.demo_dry_run is True
    assert applied.enable_demo_trading is False
    assert note is not None
    assert "does not enable demo trading" in note
    assert effective_mode(settings, _record(RuntimeMode.DEMO)) is RuntimeMode.DRY_RUN
    assert env_ceiling(settings) is RuntimeMode.DRY_RUN


def test_the_file_chooses_within_the_dry_run_demo_pair() -> None:
    dry_env = _settings(**DEMO_ENV, demo_dry_run=True)
    demo, _ = apply_runtime_mode(dry_env, _record(RuntimeMode.DEMO))
    assert demo.demo_dry_run is False
    demo_env = _settings(**DEMO_ENV, demo_dry_run=False)
    dry, _ = apply_runtime_mode(demo_env, _record(RuntimeMode.DRY_RUN))
    assert dry.demo_dry_run is True


def test_demo_still_needs_every_env_guard() -> None:
    settings = _settings(enable_demo_trading=True, demo_allowed_accounts="12345678")
    with pytest.raises(ValueError, match="XAU_EDGE_DEMO_MAGIC") as info:
        apply_runtime_mode(settings, _record(RuntimeMode.DEMO))
    described = describe_settings_error(info.value)
    assert "XAU_EDGE_DEMO_MAGIC" in described
    assert "12345678" not in described


def test_funded_is_never_selected_or_changed_by_the_file() -> None:
    settings = _settings(
        enable_funded_trading=True,
        funded_allowed_accounts="999",
        funded_allowed_servers="FTMO-Server",
        funded_magic=1,
        funded_initial_capital=100_000.0,
    )
    for mode in RuntimeMode:
        applied, note = apply_runtime_mode(settings, _record(mode))
        assert applied is settings
        assert note is not None
        assert "FUNDED" in note
    assert {m.value for m in RuntimeMode} == {"DRY_RUN", "DEMO"}
