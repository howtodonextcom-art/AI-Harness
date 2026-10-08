"""Operations settings (Telegram credentials), read from ``XAU_EDGE_*`` variables or ``.env``.

Kept separate from ``xau_edge.config.Settings`` so the notifier can be wired without touching the
trading settings. The bot token is a ``SecretStr``: it never appears in ``repr`` or logs.
"""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpsSettings(BaseSettings):
    """Alerting configuration. Both Telegram values must be set for pushes to be sent."""

    model_config = SettingsConfigDict(
        env_prefix="XAU_EDGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None
    alert_min_interval_minutes: float = Field(default=15.0, ge=0)
    alert_critical_repeat_minutes: float = Field(default=30.0, ge=0)
    alert_max_per_hour: int = Field(default=30, ge=1)
    ntp_servers: str = "time.windows.com,pool.ntp.org,time.cloudflare.com"
    ntp_max_offset_seconds: float = Field(default=5.0, gt=0)
    log_file: str = "data/logs/xau_edge.log"

    @property
    def telegram_configured(self) -> bool:
        """True when both the bot token and the chat id are present."""
        token = self.telegram_bot_token
        has_token = token is not None and bool(token.get_secret_value().strip())
        return has_token and bool((self.telegram_chat_id or "").strip())
