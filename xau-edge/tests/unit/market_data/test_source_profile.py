"""A second market feed can exist only as an isolated, labelled source."""

from __future__ import annotations

from pathlib import Path

import pytest

from xau_edge.market_data.source_profile import (
    PROFILES,
    SourceMismatchError,
    active_profile,
    check_server,
    claim_store,
)


def test_default_is_ftmo_and_the_research_baseline() -> None:
    p = active_profile({})
    assert p.id == "ftmo" and p.is_research_baseline
    assert p.market_root.name == "market" and p.trade_root.name == "trade"


def test_metaquotes_has_its_own_stores_and_is_not_the_baseline() -> None:
    p = active_profile({"XAU_EDGE_MARKET_SOURCE": "MetaQuotes"})
    assert p.id == "metaquotes" and not p.is_research_baseline
    assert p.market_root != PROFILES["ftmo"].market_root
    assert p.trade_root != PROFILES["ftmo"].trade_root


def test_unknown_source_is_refused() -> None:
    with pytest.raises(SourceMismatchError):
        active_profile({"XAU_EDGE_MARKET_SOURCE": "other"})


def test_a_foreign_server_never_passes() -> None:
    check_server(PROFILES["ftmo"], "FTMO-Demo")
    check_server(PROFILES["metaquotes"], "MetaQuotes-Demo")
    for profile, server in [
        (PROFILES["ftmo"], "MetaQuotes-Demo"),
        (PROFILES["metaquotes"], "FTMO-Demo"),
    ]:
        with pytest.raises(SourceMismatchError):
            check_server(profile, server)
    with pytest.raises(SourceMismatchError):
        check_server(PROFILES["ftmo"], None)


def test_a_store_belongs_to_the_first_source_that_wrote_it(tmp_path: Path) -> None:
    claim_store(tmp_path, PROFILES["ftmo"])
    claim_store(tmp_path, PROFILES["ftmo"])  # the owner may come back
    with pytest.raises(SourceMismatchError):
        claim_store(tmp_path, PROFILES["metaquotes"])
