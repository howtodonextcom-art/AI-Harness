"""The two research branches are separate, each frozen; the spec constants equal the code's."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from xau_edge_v2.core import risk
from xau_edge_v2.core.intelligence import families as fam
from xau_edge_v2.core.intelligence import volatility as vol
from xau_edge_v2.research import multifamily as mf

DOCS = Path(__file__).resolve().parents[2] / "docs" / "research"


def canon(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_the_multifamily_spec_matches_its_recorded_hash() -> None:
    spec = DOCS / "multifamily_0.1.0.spec.json"
    assert (DOCS / "multifamily_0.1.0.sha256").read_text(encoding="utf-8").strip() == canon(spec)


def test_the_spec_constants_are_the_codes_constants() -> None:
    c = json.loads((DOCS / "multifamily_0.1.0.spec.json").read_text(encoding="utf-8"))["constants"]
    assert c["BOX_BARS"] == vol.BOX_BARS
    assert c["BOX_MAX_HEIGHT_ATR"] == vol.BOX_MAX_HEIGHT_ATR
    assert c["BOX_MAX_MEAN_RANGE_ATR"] == vol.BOX_MAX_MEAN_RANGE_ATR
    assert c["BODY_SHARE"] == fam.BODY_SHARE and c["CONFIRM_WINDOW"] == fam.CONFIRM_WINDOW
    assert c["RANGE_LOOKBACK"] == fam.RANGE_LOOKBACK and c["RANGE_TOUCH_ATR"] == fam.RANGE_TOUCH_ATR
    for name in (
        "SLIPPAGE_POINTS",
        "COST_R_MAX",
        "MIN_CLEAR_ATR",
        "EPISODE_BARS",
        "EXPIRY_BARS",
        "MAX_HOLD_BARS",
    ):
        assert c[name] == getattr(mf, name), name
    assert c["MIN_NET_RR"] == risk.MIN_NET_RR and c["R_MULTIPLE"] == risk.R_MULTIPLE
    assert c["MAX_STOP_ATR"] == risk.MAX_STOP_ATR
    assert list(
        json.loads((DOCS / "multifamily_0.1.0.spec.json").read_text(encoding="utf-8"))[
            "order_contract"
        ]["gate_order"]
    ) == list(mf.GATES)


def test_the_branches_are_independent_and_protected() -> None:
    core = json.loads((DOCS / "cand_v2_spec.json").read_text(encoding="utf-8"))
    multi = json.loads((DOCS / "multifamily_0.1.0.spec.json").read_text(encoding="utf-8"))
    assert core["branch_id"] == "CAND_V2_CORE_1.1.0" and core["status"] == "FROZEN"
    assert multi["branch_id"] == "MULTIFAMILY_RESEARCH_0.1.0"
    assert "never merged" in multi["independence"] and multi["authority"].startswith("NONE")
    assert multi["research_budget"]["variants_allowed"] == 0
    for window in ("VALIDATION'", "CONFIRM_C", "TEST_H", "HOLDOUT"):
        assert multi["windows"][window].startswith("LOCKED")
    assert multi["outcomes"].startswith("NOT OPENED")
