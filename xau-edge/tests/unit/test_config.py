from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from xau_edge.config import Settings

pytestmark = pytest.mark.unit


def test_defaults_are_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XAU_EDGE_ENABLE_LIVE_TRADING", raising=False)
    s = Settings(_env_file=None)
    assert s.enable_live_trading is False
    assert s.data_dir == Path("data")


def test_live_trading_cannot_be_enabled_in_this_release(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XAU_EDGE_ENABLE_LIVE_TRADING", "true")
    with pytest.raises(ValidationError, match="not implemented"):
        Settings(_env_file=None)


def test_live_trading_cannot_be_enabled_by_argument() -> None:
    with pytest.raises(ValidationError, match="not implemented"):
        Settings(enable_live_trading=True, _env_file=None)


def test_env_overrides_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XAU_EDGE_DATA_DIR", str(tmp_path))
    assert Settings(_env_file=None).data_dir == tmp_path
