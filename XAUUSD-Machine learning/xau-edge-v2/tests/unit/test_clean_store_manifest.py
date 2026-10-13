"""The committed manifest of the clean store (docs/research/clean_store_manifest.json) and the gates around it."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from xau_edge_v2.research.clean_store import SCOPE, TFS, manifest_hash

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "research"
MANIFEST = json.loads((DOCS / "clean_store_manifest.json").read_text(encoding="utf-8"))


def test_the_manifest_hash_is_intact() -> None:
    assert manifest_hash(MANIFEST) == MANIFEST["manifest_sha256"]


def test_the_scope_never_reaches_a_locked_window() -> None:
    months = sorted(MANIFEST["months"])
    assert months[0] == "2005-06"
    assert (
        months[-1] == "2021-12"
    )  # Confirm-C (2025-05..), Test-H (2022-01..2025-04) and Holdout are never listed
    assert all(
        w in {"DEV'", "VALIDATION'", "QUARANTINE", "RESERVED"}
        for w in (m["window"] for m in MANIFEST["months"].values())
    )
    assert [(lo, hi, name) for lo, hi, name in SCOPE] == [
        (s["from"], s["to"], s["window"]) for s in MANIFEST["scope"]
    ]


def test_every_pass_month_has_hashed_files_for_every_timeframe_and_raw_inputs() -> None:
    for month, m in MANIFEST["months"].items():
        if m["status"] != "PASS":
            assert not m["files"], month
            assert m["reasons"], month  # a quarantine always says why
            continue
        assert set(m["files"]) == set(TFS), month
        assert all(len(f["sha256"]) == 64 and f["rows"] > 0 for f in m["files"].values()), month
        assert set(m["raw_sha256"]) == set(TFS), month
        checks = m["checks"]
        for key in ("sync_M1_M5", "sync_M5_M15", "sync_M5_M30", "sync_M5_H1", "sync_H1_H4"):
            assert checks[key]["share"] >= 0.995, (month, key)
        assert all(
            checks[f"residual_pseudo_{tf}"] == 0 for tf in ("M1", "M5", "M15", "M30", "H1")
        ), month


def test_the_owner_decisions_are_in_the_manifest() -> None:
    by = {}
    for month, m in MANIFEST["months"].items():
        by.setdefault((m["window"], m["status"]), []).append(month)
    assert len(by[("QUARANTINE", "QUARANTINED")]) == 8  # 2021-02..09 stay out
    assert by[("RESERVED", "PASS")] == ["2021-10", "2021-11", "2021-12"]
    assert ("VALIDATION'", "QUARANTINED") in by  # 2021-01: the source history changed on 2021-01-21
    assert MANIFEST["summary"]["dropped_m1"] == 2216


def test_months_with_nothing_to_clean_are_byte_equal_to_the_raw_month() -> None:
    untouched = [
        m
        for m in MANIFEST["months"].values()
        if m["status"] == "PASS" and m["checks"].get("identical_to_raw")
    ]
    assert len(untouched) >= 80  # 2005-06..2012-05 and the reserved months pass through unchanged


def test_the_dropped_bar_list_matches_its_hash_and_the_count() -> None:
    path = DOCS / "dropped_pseudo_bars.csv"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == MANIFEST["dropped_pseudo_bars_sha256"]
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert sum(r["timeframe"] == "M1" for r in rows) == MANIFEST["summary"]["dropped_m1"]
    assert min(r["timestamp_utc"] for r in rows if r["timeframe"] == "M1").startswith("2012-06-26")
    assert max(r["timestamp_utc"] for r in rows if r["timeframe"] == "M1").startswith("2021-01-20")


def test_the_refetch_provider_and_the_known_source_defects_are_recorded() -> None:
    assert "MetaQuotes-Demo" in MANIFEST["terminal_refetch_provenance"]["provider"]
    assert "pseudo" in json.dumps(MANIFEST["known_source_defects"]).lower()
    assert "2022-01-04" in json.dumps(MANIFEST["known_source_defects"])


def test_the_proposed_spec_is_not_a_frozen_spec() -> None:
    proposed = json.loads((DOCS / "cand_v2_spec_1.1.0.PROPOSED.json").read_text(encoding="utf-8"))
    assert proposed["status"] == "PROPOSED"
    assert not (DOCS / "cand_v2_spec_1.1.0.PROPOSED.sha256").exists()
    assert proposed["data"]["manifest_sha256_at_proposal"] == MANIFEST["manifest_sha256"]
    assert proposed["windows"]["TEST_H"]["state"].startswith("LOCKED")
    assert proposed["windows"]["QUARANTINE"]["range"] == "2021-02..2021-09"


def test_the_month_chunked_signal_script_refuses_without_the_explicit_flag() -> None:
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "research" / "cand_signals.py"), "--window", "DEV", "--months", "2011-03"],
        capture_output=True, text=True, cwd=ROOT, check=False, timeout=120,
    )  # fmt: skip
    assert r.returncode != 0
    assert "NOT restart-safe" in (r.stderr + r.stdout)
