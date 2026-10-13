"""Forward evidence: what the engine saw and did, summarised without any claim.

Pure functions over the decision log, the paper positions and the list of closed M5 bars the store
holds in the observation window. The protocol (``docs/forward/FORWARD_EVIDENCE_PROTOCOL.md``) fixes
the minimums before any claim is allowed; until they are met (and an owner-approved hypothesis
exists) this module only describes. ``coverage`` matters most: a gap in the log means the engine
was not watching, and a forward sample with silent gaps is not a forward sample.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from xau_edge_v2.domain.contract import (
    ForwardFunnel,
    ForwardGap,
    ForwardProgress,
    ForwardSummary,
    ForwardTrades,
)

PROTOCOL = "docs/forward/FORWARD_EVIDENCE_PROTOCOL.md"
MIN_CLOSED_TRADES = 100
MIN_DAYS = 60
MIN_COVERAGE = 0.95
_US = 1_000_000
LEVEL_NAMES = ("NEUTRAL", "BIAS", "WATCH", "SETUP_ARMED", "TRIGGER", "PLAN_VALID", "READY")


def _dt(us: int) -> datetime:
    return datetime.fromtimestamp(us / _US, UTC)


def wilson(wins: int, n: int, z: float = 1.959964) -> tuple[float, float] | None:
    """Wilson score interval for a proportion (None for n = 0)."""
    if n == 0:
        return None
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def gaps(expected: list[int], logged: set[int], bar_us: int) -> list[ForwardGap]:
    """Runs of expected closed bars with no log row (merged into one gap per run)."""
    out: list[ForwardGap] = []
    run: list[int] = []
    for us in expected:
        if us in logged:
            if run:
                out.append(ForwardGap(start=_dt(run[0]), end=_dt(run[-1] + bar_us), bars=len(run)))
                run = []
        else:
            run.append(us)
    if run:
        out.append(ForwardGap(start=_dt(run[0]), end=_dt(run[-1] + bar_us), bars=len(run)))
    return out


def funnel(rows: list[dict[str, Any]]) -> ForwardFunnel:
    actions = Counter(r["action"] for r in rows)
    levels = Counter(LEVEL_NAMES[int(r["readiness_level"])] for r in rows)
    first: Counter[str] = Counter()
    for r in rows:
        refusals = json.loads(r["refusals"])
        if refusals:
            first[refusals[0]] += 1
    signals = [r for r in rows if r["action"] in ("BUY", "SELL")]
    return ForwardFunnel(
        by_action=dict(actions),
        by_readiness={name: levels.get(name, 0) for name in LEVEL_NAMES},
        first_refusal=dict(first.most_common()),
        signals=len(signals),
        distinct_setups=len({r["setup_id"] for r in signals if r["setup_id"]}),
    )


def trades_by_version(
    positions: Iterable[dict[str, Any]], version_of: dict[str, str]
) -> list[ForwardTrades]:
    closed = [p for p in positions if p["status"] == "CLOSED"]
    versions: dict[str, list[dict[str, Any]]] = {}
    for p in closed:
        versions.setdefault(version_of.get(p["decision_id"], "unknown"), []).append(p)
    out: list[ForwardTrades] = []
    for version, rows in sorted(versions.items()):
        nets = [float(r["pnl_usd"] or 0.0) + float(r["swap_usd"] or 0.0) for r in rows]
        rs = [n / r["risk_amount"] for n, r in zip(nets, rows, strict=True) if r["risk_amount"]]
        wins = sum(1 for n in nets if n > 0)
        out.append(
            ForwardTrades(
                strategy_version=version,
                closed=len(rows),
                wins=wins,
                losses=sum(1 for n in nets if n < 0),
                total_r=sum(rs),
                mean_r=(sum(rs) / len(rs)) if rs else None,
                win_rate=wins / len(rows),
                win_rate_ci95=wilson(wins, len(rows)),
            )
        )
    return out


def summarize(  # noqa: PLR0913 - the full set of observations
    decisions: list[dict[str, Any]],
    positions: list[dict[str, Any]],
    expected_bars: list[int],
    *,
    paper_return_pct: float | None,
    hold_prices: tuple[float, float] | None,
    bar_us: int = 300 * _US,
    owner_hypothesis: bool = False,
) -> ForwardSummary:
    if not decisions:
        return ForwardSummary(
            evidence="NO_OBSERVATIONS",
            protocol=PROTOCOL,
            started=None,
            last=None,
            logged_bars=0,
            expected_bars=0,
            funnel=None,
            gaps=(),
            trades=(),
            progress=ForwardProgress(
                closed_trades=0,
                min_closed_trades=MIN_CLOSED_TRADES,
                observed_days=0.0,
                min_days=MIN_DAYS,
                coverage=None,
                min_coverage=MIN_COVERAGE,
                trades_per_day=None,
                eta_days_to_min_trades=None,
                claim_allowed=False,
                reason="chưa có quan sát nào",
            ),
            buy_and_hold_pct=None,
            paper_return_pct=paper_return_pct,
            notes=("Chưa ghi nhận nến M5 nào.",),
        )
    first, last = int(decisions[0]["bar_open_us"]), int(decisions[-1]["bar_open_us"])
    window = [us for us in expected_bars if first <= us <= last]
    logged = {int(r["bar_open_us"]) for r in decisions}
    expected_n = max(len(window), len(logged))
    coverage = len(logged & set(window)) / expected_n if expected_n else None
    days = (last - first) / (86_400 * _US)
    version_of = {r["decision_id"]: r["strategy_version"] for r in decisions}
    # a position's decision_id is the id of the decision it opened from (not necessarily logged)
    for p in positions:
        version_of.setdefault(p["decision_id"], decisions[-1]["strategy_version"])
    by_version = trades_by_version(positions, version_of)
    closed = sum(t.closed for t in by_version)
    rate = closed / days if days > 0 else None
    versions = {r["strategy_version"] for r in decisions}
    reasons: list[str] = []
    if closed < MIN_CLOSED_TRADES:
        reasons.append(f"mới {closed}/{MIN_CLOSED_TRADES} lệnh đã đóng")
    if days < MIN_DAYS:
        reasons.append(f"mới {days:.1f}/{MIN_DAYS} ngày quan sát")
    if coverage is None or coverage < MIN_COVERAGE:
        cov_text = "chưa có" if coverage is None else f"{coverage * 100:.1f}%"
        reasons.append(f"độ phủ quan sát {cov_text} < {MIN_COVERAGE * 100:.0f}%")
    if len(versions) > 1:
        reasons.append("chiến lược đổi giữa chừng: đồng hồ quan sát phải đặt lại")
    if not owner_hypothesis:
        reasons.append("chưa có giả thuyết forward được chủ dự án duyệt (họ K riêng)")
    allowed = not reasons
    notes = [
        "Đây là MÔ TẢ quan sát, không phải bằng chứng. Nhãn bằng chứng của hệ thống vẫn là UNVALIDATED.",
    ]
    if closed and any(t.closed < 30 for t in by_version):
        notes.append("Mẫu lệnh quá nhỏ: tỉ lệ thắng và R trung bình có khoảng tin cậy rất rộng.")
    gap_list = gaps(window, logged, bar_us)
    return ForwardSummary(
        evidence="FORWARD_ACCUMULATING",
        protocol=PROTOCOL,
        started=_dt(first),
        last=_dt(last),
        logged_bars=len(logged),
        expected_bars=expected_n,
        funnel=funnel(decisions),
        gaps=tuple(gap_list[-20:]),
        trades=tuple(by_version),
        progress=ForwardProgress(
            closed_trades=closed,
            min_closed_trades=MIN_CLOSED_TRADES,
            observed_days=round(days, 3),
            min_days=MIN_DAYS,
            coverage=coverage,
            min_coverage=MIN_COVERAGE,
            trades_per_day=rate,
            eta_days_to_min_trades=(
                max(MIN_CLOSED_TRADES - closed, 0) / rate if rate and rate > 0 else None
            ),
            claim_allowed=allowed,
            reason="; ".join(reasons) if reasons else "đủ mọi mức tối thiểu của giao thức",
        ),
        buy_and_hold_pct=(
            None
            if hold_prices is None or hold_prices[0] <= 0
            else (hold_prices[1] / hold_prices[0] - 1) * 100
        ),
        paper_return_pct=paper_return_pct,
        notes=tuple(notes),
    )
