"""Settings. The mode can only be PAPER; there is no field that could enable orders."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = Path("Z:/Coding/Projects/AI-Harness/xau-edge/data/market")


def default_mirrors() -> list[Path]:
    """A second partition when there is one. NOTE: another partition of the same disk protects
    against deletion and corruption, not against the disk dying (see ``backup_offdevice_dir``)."""
    drive = Path("D:/")
    return [drive / "XAU-EDGE-V2-backups"] if drive.exists() and ROOT.drive.upper() != "D:" else []


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="XAU_V2_", extra="forbid", env_file=ROOT / ".env", env_file_encoding="utf-8"
    )

    mode: Literal["PAPER"] = "PAPER"
    host: str = "127.0.0.1"
    port: int = Field(default=8200, ge=1024, le=65535)
    data_root: Path = DEFAULT_DATA_ROOT
    """Shared market store (V1's). Read-only: V2 never writes there (ADR-V2-003)."""
    web_dist: Path = ROOT / "apps" / "web" / "dist"
    log_dir: Path = ROOT / "logs"
    paper_equity: float = Field(default=10_000.0, gt=0)
    """ASSUMED starting equity of the paper account (recorded once, never rewritten)."""
    paper_db: Path = ROOT / "data" / "paper.sqlite3"
    """V2's own durable state (positions, journal): the only file V2 writes."""
    auto_paper: bool = True
    """Open a PAPER position automatically for a valid BUY/SELL. It can never reach a broker."""
    engine_enabled: bool = True
    """Run the background loop that manages paper positions and (if auto) opens them."""
    paper_poll_seconds: float = Field(default=3.0, gt=0)
    backup_keep: int = Field(default=14, ge=1)
    """Daily online backups of the paper database kept (``<paper_db dir>/backups``)."""
    backup_mirrors: list[Path] = Field(default_factory=default_mirrors)
    """Extra copies of every daily backup, verified byte for byte (JSON list in the environment)."""
    backup_offdevice_dir: Path | None = None
    """A mirror that lives on ANOTHER DEVICE (external drive, NAS, a synced cloud folder). Until it
    is set, /health says plainly that no off-device copy exists."""
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None
    """Operational alerts only (service health). Never a signal, a price or a PnL."""
    alerts_enabled: bool = True
    alert_confirm_seconds: float = Field(default=120.0, ge=0)
    """A problem must last this long before it is reported (no alert on a blip)."""
    alert_renotify_seconds: float = Field(default=3600.0, gt=0)
    heartbeat_seconds: float = Field(default=5.0, gt=0)
    live_poll_seconds: float = Field(default=1.0, gt=0)
    """How often the socket looks for a new quote / forming bar to push."""
    state_poll_seconds: float = Field(default=3.0, gt=0)
    """How often the socket recomputes the decision to see whether it changed."""
    disk_warn_gb: float = 20.0
    disk_critical_gb: float = 5.0
