"""Parse the Markdown ledger of an edge programme (``ledger.md``) into typed rows and K figures.

The ledger is written by the research code and is append-only; the console only reads it. A row that
does not match the expected shape is skipped and counted in ``malformed`` (never silently trusted),
and a ledger with no readable table is reported as unknown by the callers.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

_ROW = re.compile(
    r"^\|\s*(?P<n>\d+)\s*\|\s*(?P<time>[^|]+?)\s*\|\s*(?P<variant>[^|]+?)\s*\|"
    r"\s*(?P<period>[^|]+?)\s*\|\s*(?P<scenario>[^|]+?)\s*\|\s*(?P<note>.*?)\s*\|"
    r"\s*`?(?P<registry>[0-9a-f]{8,})`?\s*\|\s*$"
)
_TRADES = re.compile(r"(\d+)\s*lệnh")
_BASE = re.compile(r"mean net R\s*([+-]?\d+\.\d+)")
_PESSIMISTIC = re.compile(r"bi quan\s*([+-]?\d+\.\d+)")
_VERDICT = re.compile(r"\b(PASS|FAIL)\b")
_K = re.compile(r"K\s*=\s*\d+\s*\+\s*\d+\s*=\s*(\d+)")
_CAP = re.compile(r"(?:trần K cap|K cap)\s*=\s*(\d+)")
_ALPHA = re.compile(r"alpha\s*=\s*(?:0\.05\s*/\s*\d+\s*=\s*)?(0\.\d+)")
_TIME = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})")


@dataclass(frozen=True)
class LedgerRun:
    """One row of the run table."""

    number: int
    time: str | None
    variant: str
    hypothesis: str
    period: str
    scenario: str
    trades: int | None
    mean_net_r_base: float | None
    mean_net_r_pessimistic: float | None
    verdict: str | None
    registry_id: str
    note: str

    def when(self) -> datetime | None:
        """The run time as an aware UTC datetime, if the row carries one."""
        match = _TIME.search(self.time or "")
        if not match:
            return None
        return datetime.fromisoformat(f"{match.group(1)}T{match.group(2)}").replace(tzinfo=UTC)

    def as_dict(self) -> dict[str, Any]:
        """JSON-safe form."""
        return asdict(self)


@dataclass(frozen=True)
class LedgerParse:
    """Everything read from one ledger file."""

    runs: list[LedgerRun]
    k: int | None
    k_cap: int | None
    alpha: float | None
    malformed: int


def _float(pattern: re.Pattern[str], text: str) -> float | None:
    match = pattern.search(text)
    return float(match.group(1)) if match else None


def parse_ledger(text: str) -> LedgerParse:
    """Rows of the run table plus K, the cap and alpha when the text states them."""
    runs: list[LedgerRun] = []
    malformed = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("|---") or "Registry id" in stripped:
            continue
        match = _ROW.match(stripped)
        if match is None:
            if re.match(r"^\|\s*\d+\s*\|", stripped):
                malformed += 1
            continue
        note = match["note"]
        trades = _TRADES.search(note)
        verdict = _VERDICT.findall(note)
        variant = match["variant"].strip()
        runs.append(
            LedgerRun(
                number=int(match["n"]),
                time=match["time"].strip(),
                variant=variant,
                hypothesis=variant.split("-")[0],
                period=match["period"].strip(),
                scenario=match["scenario"].strip(),
                trades=int(trades.group(1)) if trades else None,
                mean_net_r_base=_float(_BASE, note),
                mean_net_r_pessimistic=_float(_PESSIMISTIC, note),
                verdict=verdict[-1] if verdict else None,
                registry_id=match["registry"],
                note=note,
            )
        )
    k_match, cap_match, alpha_match = _K.search(text), _CAP.search(text), _ALPHA.search(text)
    return LedgerParse(
        runs=runs,
        k=int(k_match.group(1)) if k_match else None,
        k_cap=int(cap_match.group(1)) if cap_match else None,
        alpha=float(alpha_match.group(1)) if alpha_match else None,
        malformed=malformed,
    )
