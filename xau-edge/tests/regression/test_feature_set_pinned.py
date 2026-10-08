"""The default feature set on a fixed synthetic input must not change silently.

A deliberate change (new feature, different convention) needs a new ``FEATURE_SET_VERSION``,
an update of this hash, and a line in the sprint report.
"""

from __future__ import annotations

from tests.conftest import make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.features.feature_set import FEATURE_SET_VERSION, build_features
from xau_edge.market_data.store import dataframe_sha256

PINNED_VERSION = "1"
PINNED_HASH = "72e42332baba3cd1afb0a5b39014c7dbb1118b100604d30129483018c3c87844"


def test_default_feature_set_output_is_pinned() -> None:
    assert FEATURE_SET_VERSION == PINNED_VERSION
    frame = build_features(make_bars(300, Timeframe.M15), Timeframe.M15)
    assert dataframe_sha256(frame) == PINNED_HASH
