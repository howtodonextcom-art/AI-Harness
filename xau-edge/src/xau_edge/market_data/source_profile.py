"""Which MT5 terminal feeds the desk, and the guards that keep two feeds from mixing.

The research programme, the cost calibration and ``data/market`` are FTMO. A second feed (the
generic MetaQuotes-Demo terminal) is allowed only as an isolated source: its own terminal, its
own bar store and its own paper-desk store, labelled on every payload. It is selected by
``XAU_EDGE_MARKET_SOURCE`` (``ftmo`` is the default). Two protections, neither of which can be
switched off by configuration:

* the connected account's server must carry the profile's marker (a MetaQuotes terminal can never
  write into the FTMO store, and the reverse);
* a store remembers the source that first wrote it (``source.json``) and refuses any other.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from xau_edge.market_data.atomic import atomic_write_text

ENV_VAR = "XAU_EDGE_MARKET_SOURCE"
ROOT = Path(__file__).resolve().parents[3]
MARKER_FILE = "source.json"


class SourceMismatchError(RuntimeError):
    """The connected terminal or the store belongs to a different market source."""


@dataclass(frozen=True)
class SourceProfile:
    id: str
    label: str
    server_marker: str
    terminal_path: str
    market_root: Path
    trade_root: Path
    is_research_baseline: bool

    def payload(self, server: str | None = None) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "server": server,
            "research_baseline": self.is_research_baseline,
        }


PROFILES: dict[str, SourceProfile] = {
    "ftmo": SourceProfile(
        id="ftmo",
        label="FTMO-Demo",
        server_marker="ftmo",
        terminal_path=r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe",
        market_root=ROOT / "data" / "market",
        trade_root=ROOT / "data" / "trade",
        is_research_baseline=True,
    ),
    "metaquotes": SourceProfile(
        id="metaquotes",
        label="MetaQuotes-Demo",
        server_marker="metaquotes",
        terminal_path=r"C:\Program Files\MetaTrader 5\terminal64.exe",
        market_root=ROOT / "data" / "market-metaquotes",
        trade_root=ROOT / "data" / "trade-metaquotes",
        is_research_baseline=False,
    ),
}


def active_profile(env: Mapping[str, str] | None = None) -> SourceProfile:
    name = (env if env is not None else os.environ).get(ENV_VAR, "ftmo").strip().lower() or "ftmo"
    try:
        return PROFILES[name]
    except KeyError:
        msg = f"{ENV_VAR}={name!r} is not one of {sorted(PROFILES)}"
        raise SourceMismatchError(msg) from None


def check_server(profile: SourceProfile, server: str | None) -> None:
    """Refuse a terminal whose account server does not belong to ``profile``."""
    if server is None or profile.server_marker not in server.lower():
        msg = (
            f"market source '{profile.id}' needs a '{profile.server_marker}' server, "
            f"the terminal reports {server!r}: nothing is written"
        )
        raise SourceMismatchError(msg)


def claim_store(root: Path, profile: SourceProfile) -> None:
    """The first source to write a store owns it; any other source is refused."""
    marker = root / MARKER_FILE
    if marker.exists():
        try:
            owner = json.loads(marker.read_text(encoding="utf-8")).get("id")
        except (OSError, ValueError):
            owner = None
        if owner != profile.id:
            msg = f"{root} belongs to market source {owner!r}, not {profile.id!r}: refusing to mix"
            raise SourceMismatchError(msg)
        return
    root.mkdir(parents=True, exist_ok=True)
    atomic_write_text(marker, json.dumps({"id": profile.id, "label": profile.label}))
