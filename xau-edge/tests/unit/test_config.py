from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from xau_edge.config import Settings

pytestmark = pytest.mark.unit


def test_defaults_are_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XAU_EDGE_ENABLE_LIVE_TRADING", raising=False)
    monkeypatch.delenv("XAU_EDGE_ENABLE_DEMO_TRADING", raising=False)
    monkeypatch.delenv("XAU_EDGE_DEMO_DRY_RUN", raising=False)
    s = Settings(_env_file=None)
    assert s.enable_live_trading is False
    assert s.enable_demo_trading is False
    assert s.demo_dry_run is True
    assert s.demo_allowed_symbols == "XAUUSD"
    assert s.data_dir == Path("data")


def test_live_trading_cannot_be_enabled_in_this_release(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XAU_EDGE_ENABLE_LIVE_TRADING", "true")
    with pytest.raises(ValidationError, match="not implemented"):
        Settings(_env_file=None)


def test_live_trading_cannot_be_enabled_by_argument() -> None:
    with pytest.raises(ValidationError, match="not implemented"):
        Settings(enable_live_trading=True, _env_file=None)


def test_live_trading_cannot_be_enabled_by_assignment() -> None:
    """ECC review F-02: the guard must hold after construction, not only in the constructor."""
    settings = Settings(_env_file=None)
    with pytest.raises(ValidationError):
        settings.enable_live_trading = True  # type: ignore[misc]
    assert settings.enable_live_trading is False


def test_live_trading_cannot_be_enabled_through_model_copy() -> None:
    settings = Settings(_env_file=None)
    with pytest.raises(ValidationError, match="not implemented"):
        settings.model_copy(update={"enable_live_trading": True})
    assert settings.model_copy(update={"log_level": "DEBUG"}).log_level == "DEBUG"


def test_demo_trading_defaults_to_dry_run_when_enabled() -> None:
    settings = Settings(enable_demo_trading=True, _env_file=None)
    assert settings.enable_demo_trading is True
    assert settings.demo_dry_run is True


def test_demo_order_mode_requires_whitelist_and_magic() -> None:
    with pytest.raises(ValidationError, match="DEMO_ALLOWED_ACCOUNTS"):
        Settings(enable_demo_trading=True, demo_dry_run=False, _env_file=None)

    with pytest.raises(ValidationError, match="DEMO_MAGIC"):
        Settings(
            enable_demo_trading=True,
            demo_dry_run=False,
            demo_allowed_accounts="123456",
            _env_file=None,
        )

    with pytest.raises(ValidationError, match="DEMO_INITIAL_CAPITAL"):
        Settings(
            enable_demo_trading=True,
            demo_dry_run=False,
            demo_allowed_accounts="123456",
            demo_magic=2601008,
            _env_file=None,
        )

    settings = Settings(
        enable_demo_trading=True,
        demo_dry_run=False,
        demo_allowed_accounts="123456",
        demo_magic=2601008,
        demo_initial_capital=100_000.0,
        _env_file=None,
    )
    assert settings.demo_magic == 2601008


def test_model_copy_rejects_unknown_keys_instead_of_ignoring_them() -> None:
    """Re-review: a typo in the key used to discard the update silently."""
    settings = Settings(_env_file=None)
    with pytest.raises(ValueError, match="unknown"):
        settings.model_copy(update={"enable_live_tradng": True})


def test_settings_are_immutable() -> None:
    settings = Settings(_env_file=None)
    with pytest.raises(ValidationError):
        settings.log_level = "DEBUG"  # type: ignore[misc]


def test_env_overrides_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XAU_EDGE_DATA_DIR", str(tmp_path))
    assert Settings(_env_file=None).data_dir == tmp_path


def test_smoke_mode_needs_demo_trading_and_the_explicit_guards() -> None:
    with pytest.raises(ValueError, match="SMOKE"):
        Settings(demo_smoke=True, _env_file=None)
    with pytest.raises(ValueError, match="explicit guard"):
        Settings(enable_demo_trading=True, demo_smoke=True, _env_file=None)
    ok = Settings(
        enable_demo_trading=True,
        demo_smoke=True,
        demo_allowed_accounts="123",
        demo_magic=7,
        demo_initial_capital=100_000.0,
        _env_file=None,
    )
    assert ok.demo_smoke is True
    assert Settings(_env_file=None).demo_smoke is False


def _funded(**over: object) -> Settings:
    base: dict[str, object] = {
        "enable_funded_trading": True,
        "funded_allowed_accounts": "900001",
        "funded_allowed_servers": "FTMO-Server",
        "funded_magic": 77,
        "funded_initial_capital": 100_000.0,
    }
    base.update(over)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


def test_funded_trading_is_off_by_default_and_live_stays_forbidden() -> None:
    settings = Settings(_env_file=None)
    assert settings.enable_funded_trading is False
    assert settings.funded_allow_unvalidated is False
    with pytest.raises(ValidationError, match="not implemented"):
        Settings(enable_live_trading=True, enable_funded_trading=True, _env_file=None)


@pytest.mark.parametrize(
    "missing",
    ["funded_allowed_accounts", "funded_allowed_servers", "funded_magic", "funded_initial_capital"],
)
def test_funded_trading_needs_every_explicit_setting(missing: str) -> None:
    with pytest.raises(ValidationError, match="funded execution requires"):
        _funded(**{missing: None if missing in {"funded_magic", "funded_initial_capital"} else ""})


def test_funded_and_demo_modes_exclude_each_other_and_share_no_account() -> None:
    with pytest.raises(ValidationError, match="exclude each other"):
        _funded(enable_demo_trading=True)
    with pytest.raises(ValidationError, match="must not share"):
        _funded(demo_allowed_accounts="900001")
    with pytest.raises(ValidationError, match="must not share"):
        Settings(demo_allowed_accounts="1,2,3", funded_allowed_accounts=" 3 ,4", _env_file=None)
    assert _funded().funded_magic == 77


def test_the_unvalidated_override_needs_funded_mode_and_a_named_strategy() -> None:
    with pytest.raises(ValidationError, match="specific"):
        _funded(funded_allow_unvalidated=True)
    with pytest.raises(ValidationError, match="specific"):
        Settings(funded_allow_unvalidated=True, funded_strategy_id="h03", _env_file=None)
    assert _funded(funded_allow_unvalidated=True, funded_strategy_id="h03").funded_strategy_id


def test_funded_mode_has_its_own_state_and_journal_files() -> None:
    settings = Settings(_env_file=None)
    assert settings.funded_state_path == Path("data/execution/funded_state.sqlite")
    assert settings.funded_journal_path == Path("data/execution/funded_journal.jsonl")
    assert settings.funded_state_path != settings.demo_state_path
    assert settings.funded_journal_path != settings.demo_journal_path
    moved = _funded(funded_state_path=Path("x/f.sqlite"), funded_journal_path=Path("x/f.jsonl"))
    assert moved.funded_state_path == Path("x/f.sqlite")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("funded_state_path", Path("data/execution/state.sqlite")),
        ("funded_journal_path", Path("data/execution/journal.jsonl")),
        ("funded_state_path", Path("data/execution/journal.jsonl")),
    ],
)
def test_funded_files_may_not_reuse_the_demo_files(field: str, value: Path) -> None:
    with pytest.raises(ValidationError, match="must differ"):
        Settings(_env_file=None, **{field: value})  # type: ignore[arg-type]


def test_the_override_risk_ceiling_cannot_be_raised_by_configuration() -> None:
    assert _funded().funded_risk_pct == 0.25
    with pytest.raises(ValidationError):
        _funded(funded_risk_pct=0.5)
    with pytest.raises(ValidationError):
        _funded(funded_risk_pct=0.0)
