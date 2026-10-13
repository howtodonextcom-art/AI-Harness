"""The server's session labels at DST-sensitive instants (pinned to the dashboard's own table).

``tests/fixtures/session_table.json`` is asserted by the dashboard's unit spec
(``apps/dashboard/e2e/unit/sessions.spec.ts``) against ``lib/sessions.ts``: if either side changes a
session rule, one of the two tests fails. The instants straddle the US (Mar 8 / Nov 1) and UK
(Mar 29 / Oct 25) clock changes.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from xau_edge.features.sessions import session_features

TABLE = json.loads(
    (Path(__file__).resolve().parents[2] / "fixtures" / "session_table.json").read_text(
        encoding="utf-8"
    )
)


def test_server_sessions_equal_the_pinned_table() -> None:
    stamps = [datetime.fromisoformat(k).replace(tzinfo=UTC) for k in TABLE]
    series = pl.Series("t", stamps, dtype=pl.Datetime("us", "UTC"))
    labels = session_features(series)["trading_session"].to_list()
    assert dict(zip(TABLE, labels, strict=True)) == TABLE
