"""Pinned content hashes: a silent change in hashing or in the synthetic generator fails here."""

from __future__ import annotations

from tests.conftest import make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.store import dataframe_sha256

PINNED = {
    Timeframe.M5: "22daea4fb890034e9e873310b4738f1d730bdbb912dc48f9bcfa400cc0e9e52e",
    Timeframe.H1: "d0e8a03f3f8edf4a13f4b5aee9d98ed83cdaf825c0fdb309da7a3d21402e2c82",
}


def test_synthetic_dataset_hashes_are_pinned() -> None:
    for timeframe, expected in PINNED.items():
        assert dataframe_sha256(make_bars(50, timeframe)) == expected


def test_dataframe_hash_is_stable_across_runs() -> None:
    first = dataframe_sha256(make_bars(50, Timeframe.M5))
    second = dataframe_sha256(make_bars(50, Timeframe.M5))
    assert first == second
    assert first != dataframe_sha256(make_bars(51, Timeframe.M5))
