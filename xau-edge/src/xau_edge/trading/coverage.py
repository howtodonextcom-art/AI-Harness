"""Decision-telemetry coverage: how many of the decisions that SHOULD exist were actually recorded.

Cadence, from the engine's own semantics (``TradeEngine.step`` / ``_recompute``): one decision row
is written per NEW closed M1 bar the engine observes while the market is open. It is not one row per
wall-clock minute: a closed market has no new bar, a bar missed by the collector has nothing to
decide on, and a freshly started engine records only the newest bar (it never back-fills the minutes
it was not running). So

    expected  = the closed M1 bars of the bar ledger inside the window (they exist only for open
                market minutes the collector delivered)
    recorded  = the distinct M1 bars named by decision rows

Rows written before ``m1_bar`` existed are mapped by their wall-clock minute (the engine decides
within seconds of the bar closing) and counted as ``approx_rows``.

Forward evidence is only as good as this coverage: below ``COVERAGE_OK_PCT`` the forward-acceptance
level is reported as INCOMPLETE, never as a plain F0.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

COVERAGE_OK_PCT = 95.0
"""Below this share of expected decisions recorded, forward evidence is INCOMPLETE."""

LATE_SECONDS = 90.0
"""A decision logged later than this after its bar closed is LATE (engine or collector lag)."""

_MINUTE = timedelta(minutes=1)


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _row_bar(row: dict[str, Any]) -> tuple[datetime, bool]:
    """(M1 bar open this row decided on, whether it is only approximated from the wall clock)."""
    if row.get("m1_bar"):
        return _parse(str(row["m1_bar"])), False
    at = _parse(str(row["at"]))
    return at.replace(second=0, microsecond=0) - _MINUTE, True


def _intervals(missing: list[datetime]) -> list[dict[str, Any]]:
    """Consecutive missing minutes merged into [from, to] runs (``to`` is the last missing bar)."""
    runs: list[dict[str, Any]] = []
    for bar in sorted(missing):
        if runs and bar - runs[-1]["_last"] == _MINUTE:
            runs[-1]["_last"] = bar
            runs[-1]["minutes"] += 1
        else:
            runs.append({"_first": bar, "_last": bar, "minutes": 1})
    return [
        {"from": r["_first"].isoformat(), "to": r["_last"].isoformat(), "minutes": r["minutes"]}
        for r in runs
    ]


def decision_coverage(
    expected_bars: list[datetime],
    rows: list[dict[str, Any]],
    *,
    window_from: datetime,
    window_to: datetime,
) -> dict[str, Any]:
    """Coverage of ``rows`` against the closed M1 bars the engine could have decided on."""
    expected = sorted({b for b in expected_bars if window_from <= b < window_to})
    expected_set = set(expected)
    seen: dict[datetime, int] = {}
    late = approx = outside = 0
    for row in rows:
        bar, approximate = _row_bar(row)
        if not window_from <= bar < window_to:
            continue
        if bar not in expected_set:
            outside += 1  # e.g. an engine restart while the market was closed
            continue
        seen[bar] = seen.get(bar, 0) + 1
        if approximate:
            approx += 1
        elif (_parse(str(row["at"])) - (bar + _MINUTE)).total_seconds() > LATE_SECONDS:
            late += 1
    missing = [b for b in expected if b not in seen]
    recorded = len(seen)
    pct = 100.0 if not expected else round(100.0 * recorded / len(expected), 2)
    return {
        "window": {"from": window_from.isoformat(), "to": window_to.isoformat()},
        "expected_m1_decisions": len(expected),
        "recorded_m1_decisions": recorded,
        "coverage_pct": pct,
        "missing": len(missing),
        "missing_intervals": _intervals(missing),
        "duplicate_rows": sum(n - 1 for n in seen.values() if n > 1),
        "late_rows": late,
        "approx_rows": approx,
        "outside_expected_rows": outside,
        "complete": bool(expected) and pct >= COVERAGE_OK_PCT,
        "threshold_pct": COVERAGE_OK_PCT,
    }


def apply_to_forward(forward: dict[str, Any], coverage: dict[str, Any] | None) -> dict[str, Any]:
    """Forward acceptance with its observation coverage: incomplete evidence says so explicitly."""
    if coverage is None or not forward.get("live"):
        return {**forward, "evidence_complete": None, "coverage_pct": None}
    incomplete = not coverage["complete"]
    text = forward["text"]
    if incomplete:
        text = (
            f"FORWARD EVIDENCE INCOMPLETE: only {coverage['coverage_pct']:.1f}% of the expected "
            f"decisions were recorded ({coverage['recorded_m1_decisions']} of "
            f"{coverage['expected_m1_decisions']}); {forward['text']}"
        )
    return {
        **forward,
        "text": text,
        "evidence_complete": not incomplete,
        "coverage_pct": coverage["coverage_pct"],
    }
