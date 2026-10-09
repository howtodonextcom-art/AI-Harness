"""Disk health for the market data directory: free space and days of headroom at the tick rate.

Market-data systems fail quietly when a disk fills, so health reports this BEFORE a write fails.
Thresholds are configurable; the daily growth is measured from the ledger itself (tick bytes per
stored day), not guessed.
"""

from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class DiskThresholds:
    warn_free_gb: float = 20.0
    critical_free_gb: float = 5.0
    warn_days: float = 60.0
    critical_days: float = 14.0


def _tree_bytes(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.is_dir() else 0


def disk_report(
    root: Path, symbol: str = "XAUUSD", thresholds: DiskThresholds | None = None
) -> dict[str, object]:
    """Free space, measured growth per day, estimated days left and a GOOD/WARN/CRITICAL level."""
    limit = thresholds or DiskThresholds()
    probe = root if root.exists() else root.parent
    usage = shutil.disk_usage(probe)
    free_gb = usage.free / 1e9
    ticks_dir = root / symbol / "ticks"
    day_files = list(ticks_dir.glob("*/*.parquet")) if ticks_dir.is_dir() else []
    tick_bytes = sum(p.stat().st_size for p in day_files)
    bytes_per_day = tick_bytes / len(day_files) if day_files else None
    # a calendar day carries ~5/7 of a stored trading day on average
    growth_per_calendar_day = None if bytes_per_day is None else bytes_per_day * 5 / 7
    days_left = None if not growth_per_calendar_day else usage.free / growth_per_calendar_day
    level = "GOOD"
    if free_gb < limit.warn_free_gb or (days_left is not None and days_left < limit.warn_days):
        level = "WARN"
    if free_gb < limit.critical_free_gb or (
        days_left is not None and days_left < limit.critical_days
    ):
        level = "CRITICAL"
    return {
        "level": level,
        "free_gb": round(free_gb, 2),
        "total_gb": round(usage.total / 1e9, 1),
        "market_data_gb": round(_tree_bytes(root) / 1e9, 3),
        "tick_gb": round(tick_bytes / 1e9, 3),
        "tick_days_stored": len(day_files),
        "tick_mb_per_stored_day": None if bytes_per_day is None else round(bytes_per_day / 1e6, 2),
        "estimated_days_remaining": None if days_left is None else round(days_left),
        "thresholds": asdict(limit),
    }
