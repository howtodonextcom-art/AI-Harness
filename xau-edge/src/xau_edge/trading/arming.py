"""Manual arming of automatic demo trading (trading core section 35).

States: DISARMED (nothing runs), DRY_RUN (decisions and intents only, never an order) and
DEMO_ARMED (orders may be sent to the DEMO account). The default is DISARMED. ``DEMO_ARMED`` needs
BOTH the explicit settings (demo trading enabled, dry-run off, account whitelist and magic number,
already enforced by ``Settings``) AND an unexpired arm marker written by an operator action. The
marker carries an expiry, so a restart long after the arming, or a forgotten arming, degrades to
DRY_RUN instead of silently continuing to trade. No code path arms by itself.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

from xau_edge.config import Settings

DEFAULT_ARM_HOURS = 8
MAX_ARM_HOURS = 24


class ArmState(StrEnum):
    DISARMED = "DISARMED"
    DRY_RUN = "DRY_RUN"
    DEMO_ARMED = "DEMO_ARMED"


@dataclass(frozen=True)
class ArmMarker:
    """An operator's explicit, time-limited arming."""

    armed_at: datetime
    armed_until: datetime
    operator: str


def write_marker(
    path: Path, operator: str, now: datetime, hours: float = DEFAULT_ARM_HOURS
) -> ArmMarker:
    """Arm for ``hours`` (capped); the operator name is recorded for the audit trail."""
    if not 0 < hours <= MAX_ARM_HOURS:
        msg = f"arming window must be within (0, {MAX_ARM_HOURS}] hours"
        raise ValueError(msg)
    marker = ArmMarker(now, now + timedelta(hours=hours), operator)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "armed_at": marker.armed_at.isoformat(),
                "armed_until": marker.armed_until.isoformat(),
                "operator": operator,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return marker


def clear_marker(path: Path) -> None:
    """Disarm immediately."""
    path.unlink(missing_ok=True)


def read_marker(path: Path) -> ArmMarker | None:
    """The marker, or None when absent or unreadable (never armed by a broken file)."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        armed_at = datetime.fromisoformat(raw["armed_at"])
        armed_until = datetime.fromisoformat(raw["armed_until"])
        operator = str(raw["operator"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if armed_at.tzinfo is None or armed_until.tzinfo is None or armed_until <= armed_at:
        return None
    return ArmMarker(armed_at.astimezone(UTC), armed_until.astimezone(UTC), operator)


def effective_state(settings: Settings, marker: ArmMarker | None, now: datetime) -> ArmState:
    """The state in force: the strictest of the settings and the arm marker."""
    if not settings.enable_demo_trading:
        return ArmState.DISARMED
    if settings.demo_dry_run:
        return ArmState.DRY_RUN
    if marker is None or not (marker.armed_at <= now < marker.armed_until):
        return ArmState.DRY_RUN
    return ArmState.DEMO_ARMED
