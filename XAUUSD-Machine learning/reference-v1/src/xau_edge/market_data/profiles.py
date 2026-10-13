"""Broker profiles: clock, market calendar, validation thresholds and instrument spec in YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from xau_edge.domain.instrument import XAUUSD, Instrument
from xau_edge.market_data.broker_clock import BrokerClock
from xau_edge.market_data.validators.models import ValidationConfig


def _parse_clock(value: Any) -> Any:
    return BrokerClock.parse(value) if isinstance(value, str) else value


class BrokerProfile(BaseModel):
    """Everything broker-specific that data handling depends on.

    Values must be derived from evidence (see ``docs/reports/mt5-verification.md``), never guessed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    clock: Annotated[BrokerClock, BeforeValidator(_parse_clock)]
    instrument: Instrument = XAUUSD
    validation: ValidationConfig = Field(default_factory=ValidationConfig)

    @classmethod
    def from_yaml(cls, path: Path | str) -> BrokerProfile:
        """Load and validate a profile; unknown keys and out-of-range values are rejected."""
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            msg = f"{path}: profile must be a YAML mapping"
            raise ValueError(msg)
        return cls.model_validate(raw)
