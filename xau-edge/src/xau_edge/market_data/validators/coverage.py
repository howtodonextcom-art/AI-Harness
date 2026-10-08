"""Check that a downloaded dataset actually covers the requested period.

Providers can truncate history silently. The MT5 terminal, for example, serves at most its
configured "max bars in chart" and drops the OLDEST bars without raising an error. Row-level
validators cannot see a missing prefix, so coverage is checked against the request.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import polars as pl

from xau_edge.market_data.validators.models import IssueCode, Severity, ValidationIssue

DEFAULT_TOLERANCE = timedelta(days=4)
"""Long enough to absorb a weekend plus a holiday at either edge of the requested range."""


def check_coverage(
    df: pl.DataFrame,
    start: datetime,
    end: datetime,
    *,
    tolerance: timedelta = DEFAULT_TOLERANCE,
) -> ValidationIssue | None:
    """Return an ERROR issue if the data starts or ends materially inside ``[start, end)``."""
    if df.height == 0:
        return ValidationIssue(
            code=IssueCode.INCOMPLETE_COVERAGE,
            severity=Severity.ERROR,
            count=0,
            message=f"no bars returned for {start.isoformat()} .. {end.isoformat()}",
        )
    first = df["timestamp"].min()
    last = df["timestamp"].max()
    assert isinstance(first, datetime)  # noqa: S101 - frame is non-empty
    assert isinstance(last, datetime)  # noqa: S101
    problems: list[str] = []
    sample: list[datetime] = []
    late_start = first - start
    if late_start > tolerance:
        problems.append(
            f"data starts {late_start.days}d after the requested start "
            f"({first.isoformat()} vs {start.isoformat()}); the provider may have truncated history"
        )
        sample.append(first)
    early_end = end - last
    if early_end > tolerance:
        problems.append(
            f"data ends {early_end.days}d before the requested end "
            f"({last.isoformat()} vs {end.isoformat()})"
        )
        sample.append(last)
    if not problems:
        return None
    return ValidationIssue(
        code=IssueCode.INCOMPLETE_COVERAGE,
        severity=Severity.ERROR,
        count=len(problems),
        message="; ".join(problems),
        sample=tuple(sample),
    )
