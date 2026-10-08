from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from xau_edge.market_data.broker_clock import BrokerClock
from xau_edge.market_data.profiles import BrokerProfile

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[3]
FTMO = ROOT / "configs" / "brokers" / "ftmo_demo.yaml"


def test_ftmo_demo_profile_loads_with_empirically_derived_values() -> None:
    profile = BrokerProfile.from_yaml(FTMO)
    assert profile.name == "ftmo-demo"
    assert profile.clock == BrokerClock.parse("NY+7")
    cal = profile.validation.calendar
    assert cal.timezone == "America/New_York"
    assert (cal.weekend_close_minute, cal.weekend_open_minute) == (16 * 60 + 50, 18 * 60 + 5)
    assert (cal.daily_break_start_minute, cal.daily_break_end_minute) == (16 * 60 + 50, 18 * 60 + 5)
    assert profile.validation.max_spread_points == 200
    # Longest legitimate closure measured: Christmas, 1,550 open minutes (25.8 h).
    assert profile.validation.max_closure_minutes == 28 * 60
    assert profile.instrument.symbol == "XAUUSD"
    assert profile.instrument.digits == 2


def test_unknown_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "p.yaml"
    path.write_text("name: x\nclock: UTC\nsurprise: 1\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        BrokerProfile.from_yaml(path)


def test_invalid_values_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "p.yaml"
    path.write_text(
        "name: x\nclock: UTC\nvalidation:\n  calendar:\n    weekend_close_minute: 5000\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        BrokerProfile.from_yaml(path)


def test_minimal_profile_uses_defaults(tmp_path: Path) -> None:
    path = tmp_path / "p.yaml"
    path.write_text("name: minimal\nclock: Europe/Athens\n", encoding="utf-8")
    profile = BrokerProfile.from_yaml(path)
    assert profile.clock.iana == "Europe/Athens"
    assert profile.instrument.symbol == "XAUUSD"
    assert profile.validation.max_missing_fraction == pytest.approx(0.01)


def test_non_mapping_yaml_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "p.yaml"
    path.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        BrokerProfile.from_yaml(path)
