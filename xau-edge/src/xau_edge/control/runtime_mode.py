"""The DRY-RUN/DEMO choice made from the web, stored in ``runtime_mode.json`` (ADR-0023).

Rules:

* the file holds exactly ``DRY_RUN`` or ``DEMO``; anything else (``FUNDED``, ``LIVE``, lower case,
  a typo, extra keys) is refused by the validator, and the bot refuses to start on such a file;
* the file only chooses between the dry-run and demo pair. ``.env`` stays the upper bound: without
  ``XAU_EDGE_ENABLE_DEMO_TRADING=true`` a DEMO file is ignored and the bot runs DRY-RUN;
* FUNDED is never read from this file: when ``.env`` enables funded trading the file is ignored.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from xau_edge.config import Settings


class RuntimeMode(StrEnum):
    """The only two modes the web may choose."""

    DRY_RUN = "DRY_RUN"
    DEMO = "DEMO"


ALLOWED_RUNTIME_MODES = frozenset(m.value for m in RuntimeMode)


class RuntimeModeError(ValueError):
    """The runtime mode value or file is not acceptable."""


def parse_runtime_mode(value: object) -> RuntimeMode:
    """``DRY_RUN`` or ``DEMO`` exactly (case-sensitive); everything else raises."""
    if not isinstance(value, str) or value not in ALLOWED_RUNTIME_MODES:
        msg = "the runtime mode must be exactly DRY_RUN or DEMO"
        raise RuntimeModeError(msg)
    return RuntimeMode(value)


class RuntimeModeRecord(BaseModel):
    """The file contents."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: RuntimeMode
    set_at: datetime
    source: Literal["web", "cli"] = "web"

    @field_validator("mode", mode="before")
    @classmethod
    def _only_dry_run_or_demo(cls, value: object) -> RuntimeMode:
        return parse_runtime_mode(value)


def read_runtime_mode(path: Path) -> RuntimeModeRecord | None:
    """The stored choice, ``None`` when there is no file; a bad file raises ``RuntimeModeError``."""
    if not path.exists():
        return None
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
        return RuntimeModeRecord.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError, RuntimeModeError) as exc:
        msg = "runtime_mode.json is unreadable or holds a value other than DRY_RUN or DEMO"
        raise RuntimeModeError(msg) from exc


def write_runtime_mode(
    path: Path, mode: object, now: datetime, *, source: Literal["web", "cli"] = "web"
) -> RuntimeModeRecord:
    """Validate and atomically replace the file."""
    record = RuntimeModeRecord(mode=parse_runtime_mode(mode), set_at=now, source=source)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(record.model_dump_json(), encoding="utf-8")
    tmp.replace(path)
    return record


def env_ceiling(settings: Settings) -> RuntimeMode:
    """The highest mode ``.env`` allows the web to choose."""
    return RuntimeMode.DEMO if settings.enable_demo_trading else RuntimeMode.DRY_RUN


def env_default(settings: Settings) -> RuntimeMode:
    """The mode ``.env`` alone selects (used when there is no runtime file)."""
    if settings.enable_demo_trading and not settings.demo_dry_run:
        return RuntimeMode.DEMO
    return RuntimeMode.DRY_RUN


def effective_mode(settings: Settings, record: RuntimeModeRecord | None) -> RuntimeMode:
    """What the bot will run as (dry-run/demo pair only; never called for funded)."""
    if record is None:
        return env_default(settings)
    if record.mode is RuntimeMode.DEMO and not settings.enable_demo_trading:
        return RuntimeMode.DRY_RUN
    return record.mode


def apply_runtime_mode(
    settings: Settings, record: RuntimeModeRecord | None
) -> tuple[Settings, str | None]:
    """Settings with the web's choice applied, and a note for the operator when it was bounded.

    Raises ``ValueError`` (pydantic) when DEMO is chosen but ``.env`` lacks a demo guard setting.
    """
    if record is None:
        return settings, None
    if settings.enable_funded_trading:
        return (
            settings,
            "runtime_mode.json ignored: FUNDED is configured in .env, never from the web",
        )
    if not settings.enable_demo_trading:
        if record.mode is RuntimeMode.DEMO:
            return settings, "runtime_mode.json asks for DEMO but .env does not enable demo trading"
        return settings, None
    dry_run = record.mode is RuntimeMode.DRY_RUN
    if settings.demo_dry_run == dry_run:
        return settings, None
    return settings.model_copy(update={"demo_dry_run": dry_run}), None


def describe_settings_error(exc: Exception) -> str:
    """A settings validation error without the input values (they can hold account numbers)."""
    if isinstance(exc, ValidationError):
        parts = []
        for error in exc.errors(include_input=False, include_url=False):
            where = ".".join(str(p) for p in error.get("loc", ())) or "settings"
            parts.append(f"{where}: {error.get('msg', 'invalid')}")
        return "; ".join(parts)
    return type(exc).__name__
