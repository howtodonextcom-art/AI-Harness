"""Where the control plane and the bot meet on disk (all under ``<data_dir>/execution``)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

LOCK_FILE = "demo_trader.lock"
STOP_FILE = "stop_requested.json"
RUNTIME_MODE_FILE = "runtime_mode.json"
PROCESS_FILE = "bot_process.json"
TOKEN_FILE = "control_token"  # noqa: S105 - a file name, not a secret
LIMITS_FILE = "control_limits.json"


@dataclass(frozen=True)
class ControlPaths:
    """File locations derived from the data directory."""

    data_dir: Path

    @property
    def exec_dir(self) -> Path:
        """``<data_dir>/execution``."""
        return self.data_dir / "execution"

    @property
    def lock(self) -> Path:
        """The bot's single-instance lock (shared with ``scripts/demo_trader.py``)."""
        return self.exec_dir / LOCK_FILE

    @property
    def stop_sentinel(self) -> Path:
        """Soft-stop request the bot checks between cycles."""
        return self.exec_dir / STOP_FILE

    @property
    def runtime_mode(self) -> Path:
        """DRY_RUN or DEMO, chosen from the web (bounded by ``.env``)."""
        return self.exec_dir / RUNTIME_MODE_FILE

    @property
    def process(self) -> Path:
        """PID of a bot the API started as a subprocess."""
        return self.exec_dir / PROCESS_FILE

    @property
    def token(self) -> Path:
        """Per-start control token, readable by the current user only."""
        return self.exec_dir / TOKEN_FILE

    @property
    def limits(self) -> Path:
        """Rate-limit history of smoke and flatten."""
        return self.exec_dir / LIMITS_FILE

    @property
    def status(self) -> Path:
        """``status.json`` written by the bot every cycle."""
        return self.exec_dir / "status.json"

    @property
    def heartbeat(self) -> Path:
        """``heartbeat.json`` written by the bot."""
        return self.exec_dir / "heartbeat.json"

    @property
    def cycles(self) -> Path:
        """The demo cycle journal."""
        return self.exec_dir / "cycles.jsonl"

    @property
    def bot_log(self) -> Path:
        """stdout/stderr of a bot started by the API."""
        return self.data_dir / "logs" / "bot_web.log"
