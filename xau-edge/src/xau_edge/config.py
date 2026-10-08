"""Application settings. Live trading is hard-disabled in this release."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Self

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide settings, read from ``XAU_EDGE_*`` environment variables or ``.env``.

    Instances are immutable and re-validated on every copy, so the live-trading guard holds
    after construction too (assignment and ``model_copy(update=...)`` are both refused). It
    stops accidental or careless enabling; code that deliberately bypasses pydantic
    (``model_construct``, ``object.__setattr__``) is out of scope, so any future execution entry
    point must re-check the flag itself rather than trust this object.
    """

    model_config = SettingsConfigDict(
        env_prefix="XAU_EDGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        validate_assignment=True,
    )

    enable_live_trading: bool = False
    data_dir: Path = Path("data")
    log_level: str = "INFO"

    @field_validator("enable_live_trading")
    @classmethod
    def _live_trading_disabled(cls, value: bool) -> bool:
        if value:
            msg = (
                "Live trading is not implemented in this release; "
                "XAU_EDGE_ENABLE_LIVE_TRADING must remain false"
            )
            raise ValueError(msg)
        return value

    def model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False) -> Self:
        """Copy with ``update`` applied *and validated* (pydantic's default skips validation)."""
        unknown = set(update or {}) - set(type(self).model_fields)
        if unknown:
            msg = f"unknown setting(s) in update: {sorted(unknown)}"
            raise ValueError(msg)
        data = self.model_dump()
        data.update(update or {})
        return type(self)(_env_file=None, **data)
