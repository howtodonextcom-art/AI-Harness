from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from xau_edge.integrity.prospective import (
    GENESIS,
    INVALID,
    UNKNOWN,
    VALID,
    LedgerError,
    ProspectiveLedger,
    verify,
)


def signal(n: int, created: str = "2026-10-09T10:00:00+00:00", **over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "record_id": f"s{n}",
        "kind": "SIGNAL",
        "created_at": created,
        "decision_available_at": "2026-10-09T09:45:00+00:00",
        "earliest_resolution_at": "2026-10-09T11:00:00+00:00",
        "strategy_id": "H07-a",
        "strategy_version": "1",
        "config_hash": "a" * 16,
        "dataset_hash": "b" * 16,
        "feature_version": "f1",
        "code_commit": "c" * 40,
        "market_regime": "range",
        "decision": "SELL",
        "direction": -1,
        "entry_reference": 2400.5,
        "sl": 2405.0,
        "tp": 2390.0,
        "predicted_probabilities": {"tp": 0.4, "sl": 0.5, "timeout": 0.1},
        "expected_r": 0.1,
        "evidence_status": "UNVALIDATED",
    }
    body.update(over)
    return body


def outcome(n: int, ref: int, observed: str = "2026-10-09T12:00:00+00:00") -> dict[str, Any]:
    return {
        "record_id": f"o{n}",
        "kind": "OUTCOME",
        "created_at": observed,
        "signal_id": f"s{ref}",
        "observed_at": observed,
        "net_r": -1.0,
    }


def test_a_missing_file_is_unknown_not_valid(tmp_path: Path) -> None:
    assert verify(tmp_path / "none.jsonl").status == UNKNOWN


def test_an_empty_file_has_no_evidence_and_is_not_sealed(tmp_path: Path) -> None:
    path = tmp_path / "l.jsonl"
    path.write_text("", encoding="utf-8")
    result = verify(path)
    assert result.status == VALID
    assert result.signals == 0
    assert not result.sealed_before_outcome


def test_a_clean_chain_verifies(tmp_path: Path) -> None:
    ledger = ProspectiveLedger(tmp_path / "l.jsonl")
    first = ledger.append(signal(1))
    assert first["previous_record_hash"] == GENESIS
    second = ledger.append(signal(2, "2026-10-09T10:15:00+00:00"))
    assert second["previous_record_hash"] == first["record_hash"]
    ledger.append(outcome(1, 1))
    result = verify(tmp_path / "l.jsonl")
    assert (result.status, result.signals, result.outcomes) == (VALID, 2, 1)
    assert result.sealed_before_outcome


def test_modifying_a_historical_record_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "l.jsonl"
    ledger = ProspectiveLedger(path)
    ledger.append(signal(1))
    ledger.append(signal(2, "2026-10-09T10:15:00+00:00"))
    path.write_text(
        path.read_text(encoding="utf-8").replace('"SELL"', '"BUY"', 1), encoding="utf-8"
    )
    result = verify(path)
    assert result.status == INVALID
    assert any("modified" in p for p in result.problems)
    with pytest.raises(LedgerError):
        ledger.append(signal(3, "2026-10-09T10:30:00+00:00"))


def test_deleting_a_middle_record_breaks_the_chain(tmp_path: Path) -> None:
    path = tmp_path / "l.jsonl"
    ledger = ProspectiveLedger(path)
    for n, t in enumerate(("10:00", "10:15", "10:30"), start=1):
        ledger.append(signal(n, f"2026-10-09T{t}:00+00:00"))
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(lines[0] + "\n" + lines[2] + "\n", encoding="utf-8")
    assert any("broken chain" in p for p in verify(path).problems)


def test_a_duplicate_record_id_is_refused(tmp_path: Path) -> None:
    ledger = ProspectiveLedger(tmp_path / "l.jsonl")
    ledger.append(signal(1))
    with pytest.raises(LedgerError, match="duplicate"):
        ledger.append(signal(1, "2026-10-09T10:15:00+00:00"))
    assert verify(tmp_path / "l.jsonl").status == VALID


def test_time_inversion_is_refused(tmp_path: Path) -> None:
    ledger = ProspectiveLedger(tmp_path / "l.jsonl")
    ledger.append(signal(1))
    with pytest.raises(LedgerError, match="time inversion"):
        ledger.append(signal(2, "2026-10-09T09:50:00+00:00"))


def test_a_signal_sealed_after_the_outcome_could_exist_is_refused(tmp_path: Path) -> None:
    ledger = ProspectiveLedger(tmp_path / "l.jsonl")
    with pytest.raises(LedgerError, match="earliest possible outcome"):
        ledger.append(signal(1, "2026-10-09T11:00:00+00:00"))


def test_a_signal_sealed_before_its_decision_was_available_is_refused(tmp_path: Path) -> None:
    ledger = ProspectiveLedger(tmp_path / "l.jsonl")
    with pytest.raises(LedgerError, match="before its own decision"):
        ledger.append(signal(1, "2026-10-09T09:00:00+00:00"))


def test_outcome_data_inside_a_signal_is_contamination(tmp_path: Path) -> None:
    ledger = ProspectiveLedger(tmp_path / "l.jsonl")
    with pytest.raises(LedgerError, match="outcome data"):
        ledger.append(signal(1, realised_pnl=3.0))


def test_an_outcome_must_follow_its_signal_and_refer_to_a_known_one(tmp_path: Path) -> None:
    ledger = ProspectiveLedger(tmp_path / "l.jsonl")
    ledger.append(signal(1))
    with pytest.raises(LedgerError, match="unknown signal"):
        ledger.append(outcome(1, 9))
    early = outcome(2, 1, "2026-10-09T10:00:00+00:00")
    with pytest.raises(LedgerError, match="before its signal"):
        ledger.append(early)


def test_a_naive_timestamp_is_refused(tmp_path: Path) -> None:
    ledger = ProspectiveLedger(tmp_path / "l.jsonl")
    with pytest.raises(LedgerError, match="time zone"):
        ledger.append(signal(1, "2026-10-09T10:00:00"))


def test_garbage_lines_make_the_ledger_invalid(tmp_path: Path) -> None:
    path = tmp_path / "l.jsonl"
    path.write_text("not json\n", encoding="utf-8")
    assert verify(path).status == INVALID


@given(target=st.integers(min_value=0, max_value=2), data=st.data())
@settings(max_examples=40, deadline=None)
def test_any_single_character_change_is_detected(
    target: int, data: st.DataObject, tmp_path_factory: pytest.TempPathFactory
) -> None:
    path = tmp_path_factory.mktemp("prop") / "l.jsonl"
    ledger = ProspectiveLedger(path)
    for n, t in enumerate(("10:00", "10:15", "10:30"), start=1):
        ledger.append(signal(n, f"2026-10-09T{t}:00+00:00"))
    lines = path.read_text(encoding="utf-8").splitlines()
    original = lines[target]
    pos = data.draw(st.integers(min_value=0, max_value=len(original) - 1))
    replacement = "X" if original[pos] != "X" else "Y"
    lines[target] = original[:pos] + replacement + original[pos + 1 :]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert verify(path).status == INVALID


def test_a_live_ledger_refuses_a_backdated_signal(tmp_path: Path) -> None:
    from datetime import UTC, datetime, timedelta  # noqa: PLC0415

    now = datetime(2026, 10, 9, 10, 0, tzinfo=UTC)
    ledger = ProspectiveLedger(tmp_path / "l.jsonl", clock=lambda: now)
    with pytest.raises(LedgerError, match="backdated"):
        ledger.append(
            signal(
                1, "2020-01-01T10:00:00+00:00", decision_available_at="2019-12-31T00:00:00+00:00"
            )
        )
    ok = signal(2, (now + timedelta(seconds=30)).isoformat())
    assert ledger.append(ok)["record_id"] == "s2"


def test_tail_truncation_is_detected_through_the_head_anchor(tmp_path: Path) -> None:
    path = tmp_path / "l.jsonl"
    ledger = ProspectiveLedger(path)
    ledger.append(signal(1))
    ledger.append(signal(2, "2026-10-09T10:15:00+00:00"))
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(lines[0] + "\n", encoding="utf-8")  # drop the newest record
    result = verify(path)
    assert result.status == INVALID
    assert any("tail truncated" in p for p in result.problems)


def test_an_outcome_before_the_earliest_resolution_or_a_second_outcome_is_refused(
    tmp_path: Path,
) -> None:
    ledger = ProspectiveLedger(tmp_path / "l.jsonl")
    ledger.append(signal(1))
    with pytest.raises(LedgerError, match="earliest resolution"):
        ledger.append(outcome(1, 1, "2026-10-09T10:30:00+00:00"))
    ledger.append(outcome(2, 1, "2026-10-09T12:00:00+00:00"))
    with pytest.raises(LedgerError, match="second outcome"):
        ledger.append(outcome(3, 1, "2026-10-09T13:00:00+00:00"))
    with pytest.raises(LedgerError, match="unknown signal"):
        ledger.append(outcome(4, 2, "2026-10-09T14:00:00+00:00"))  # s2 does not exist


def test_a_missing_anchor_makes_a_non_empty_ledger_unknown_not_valid(tmp_path: Path) -> None:
    path = tmp_path / "l.jsonl"
    ledger = ProspectiveLedger(path)
    ledger.append(signal(1))
    ledger.append(signal(2, "2026-10-09T10:15:00+00:00"))
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(lines[0] + "\n", encoding="utf-8")  # truncate
    (tmp_path / "l.jsonl.head").unlink()  # and remove the anchor
    result = verify(path)
    assert result.status == UNKNOWN
    assert not result.sealed_before_outcome


def test_a_crash_between_the_append_and_the_anchor_does_not_brick_the_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "l.jsonl"
    ledger = ProspectiveLedger(path)
    ledger.append(signal(1))

    def boom(self: ProspectiveLedger, state: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(ProspectiveLedger, "_write_anchor", boom)
    with pytest.raises(OSError, match="disk full"):
        ledger.append(signal(2, "2026-10-09T10:15:00+00:00"))
    monkeypatch.undo()
    assert verify(path).status == VALID  # one record ahead of its anchor: tolerated
    ledger.append(signal(3, "2026-10-09T10:30:00+00:00"))
    assert verify(path).status == VALID
