"""Application settings. Live trading is hard-disabled in this release."""

from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide settings, read from ``XAU_EDGE_*`` environment variables or ``.env``."""

    model_config = SettingsConfigDict(
        env_prefix="XAU_EDGE_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
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
