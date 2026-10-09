"""Research console core: path guard, power arithmetic, ledger parser, lifecycle, decay."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tests.unit.research.helpers import LEDGER, make_repo, write
from xau_edge.research import power
from xau_edge.research.decay import DecayConfig, evaluate_decay, max_drawdown_r
from xau_edge.research.ledger import parse_ledger
from xau_edge.research.lifecycle import LifecycleError, LifecycleStore
from xau_edge.research.paths import ResearchRoot, SourceUnavailableError

# -- paths -------------------------------------------------------------------------------------


@pytest.fixture
def root(tmp_path: Path) -> ResearchRoot:
    make_repo(tmp_path)
    return ResearchRoot(tmp_path)


@pytest.mark.parametrize(
    "rel",
    [
        "../secret.txt",
        "docs/research/../../.env",
        "/etc/passwd",
        "C:/Windows/win.ini",
        "docs\\research\\x.md",
        "docs/research/~/x",
        "src/xau_edge/config.py",
        "",
        ".env",
        "data/execution/state.sqlite",
        "data/execution/control_token",
        "configs/.env.local",
        "docs/research/x.md\x00",
    ],
)
def test_unsafe_or_blocked_paths_are_refused(root: ResearchRoot, rel: str) -> None:
    with pytest.raises(SourceUnavailableError):
        root.read_text(rel)
    assert not root.exists(rel)


def test_an_allowed_file_is_read_and_a_missing_one_is_unavailable(root: ResearchRoot) -> None:
    assert "Ledger" in root.read_text("docs/research/edge-program/ledger.md")
    with pytest.raises(SourceUnavailableError, match="missing"):
        root.read_text("docs/research/edge-program/nope.md")
    write(root.root, "docs/research/bad.json", "{not json")
    with pytest.raises(SourceUnavailableError, match="invalid JSON"):
        root.read_json("docs/research/bad.json")


def test_oversized_and_blocked_files_are_not_listed_or_read(root: ResearchRoot) -> None:
    write(root.root, "data/execution/state.sqlite", "x")
    write(root.root, "data/execution/status.json", "{}")
    assert root.list("data/execution") == ["data/execution/status.json"]
    big = root.root / "docs/research/big.md"
    big.write_bytes(b"a" * 4_100_000)
    with pytest.raises(SourceUnavailableError, match="too large"):
        root.read_text("docs/research/big.md")


@pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
def test_a_symlink_that_escapes_the_repository_is_refused(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    make_repo(repo)
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    (repo / "docs/research/link.md").symlink_to(outside)
    with pytest.raises(SourceUnavailableError, match="escapes"):
        ResearchRoot(repo).read_text("docs/research/link.md")


# -- power -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("k", "n", "expected"),
    [
        (21, 100, 0.476),
        (21, 500, 0.213),
        (21, 3000, 0.087),
        (8, 1000, 0.137),
        (4, 200, 0.283),
        (1, 2000, 0.072),
    ],
)
def test_the_mde_matches_the_roadmap_table(k: int, n: int, expected: float) -> None:
    assert power.mde(k, n) == pytest.approx(expected, abs=0.001)


def test_trades_needed_matches_the_roadmap() -> None:
    assert power.trades_needed(21, 0.20) == pytest.approx(567, abs=2)
    assert power.trades_needed(21, 0.10) == pytest.approx(2269, abs=4)
    assert power.trades_needed(21, 0.05) == pytest.approx(9076, abs=8)
    assert power.trades_needed(8, 0.10) == pytest.approx(1884, abs=4)


def test_underpowered_by_design_follows_the_threshold() -> None:
    assert power.underpowered(21, 100)
    assert not power.underpowered(21, 3000)
    assert power.underpowered(21, 500)  # 0.213 > 0.20


@pytest.mark.parametrize("bad", [(0, 10), (5, 0), (5, -1)])
def test_power_rejects_nonsense_inputs(bad: tuple[int, int]) -> None:
    with pytest.raises(ValueError, match="must be"):
        power.mde(*bad)
    with pytest.raises(ValueError, match="effect"):
        power.trades_needed(5, 0.0)
    with pytest.raises(ValueError, match="must be"):
        power.mde(5, 10, sd=float("nan"))


# -- ledger ------------------------------------------------------------------------------------


def test_the_ledger_rows_and_k_are_parsed() -> None:
    parsed = parse_ledger(LEDGER)
    assert parsed.k == 21
    assert parsed.k_cap == 21
    assert parsed.alpha == pytest.approx(0.002381)
    assert [r.variant for r in parsed.runs] == [
        "H01-theta0.3", "H01-theta0.6", "H01-theta0.3", "H01-theta0.6",
    ]  # fmt: skip
    first = parsed.runs[0]
    assert first.hypothesis == "H01"
    assert first.trades == 2727
    assert first.mean_net_r_base == pytest.approx(-0.0812)
    assert first.mean_net_r_pessimistic == pytest.approx(-0.0933)
    assert first.verdict == "FAIL"
    when = first.when()
    assert when is not None
    assert when.tzinfo is not None


def test_a_malformed_row_is_counted_not_trusted() -> None:
    text = (
        LEDGER
        + "| 9 | garbage row without registry |\n| 10 | t | H02-b0 | dev-H | x | note | zz |\n"
    )
    parsed = parse_ledger(text)
    assert len(parsed.runs) == 4
    assert parsed.malformed == 2


def test_an_empty_or_unrelated_ledger_has_no_runs_and_no_k() -> None:
    parsed = parse_ledger("# nothing here\n")
    assert parsed.runs == []
    assert parsed.k is None


# -- lifecycle ---------------------------------------------------------------------------------


def _store(tmp_path: Path) -> LifecycleStore:
    seed = {
        "cand": "VALIDATED",
        "paper": "PAPER",
        "old": "REJECTED",
        "idea": "RESEARCH",
        "gone": "RETIRED",
    }
    return LifecycleStore(tmp_path / "lifecycle.jsonl", seed)


def test_a_demotion_is_recorded_and_changes_the_state(tmp_path: Path) -> None:
    store = _store(tmp_path)
    event = store.demote("cand", "WATCH", "rolling window below the bound", "web")
    assert (event.from_state, event.to_state) == ("VALIDATED", "WATCH")
    assert store.states()["cand"] == "WATCH"
    store.demote("cand", "DEGRADED", "second window", "web")
    store.demote("cand", "DISABLED", "drawdown", "web")
    assert [e.to_state for e in store.history("cand")] == ["WATCH", "DEGRADED", "DISABLED"]
    assert _store(tmp_path).states()["cand"] == "DISABLED"  # survives a restart


@pytest.mark.parametrize(
    ("strategy", "target", "message"),
    [
        ("cand", "VALIDATED", "may only set"),
        ("cand", "FUNDED", "may only set"),
        ("cand", "PAPER", "may only set"),
        ("cand", "RESEARCH", "may only set"),
        ("old", "WATCH", "cannot be changed"),
        ("idea", "DISABLED", "cannot be changed"),
        ("gone", "WATCH", "cannot be changed"),
        ("nobody", "WATCH", "unknown strategy"),
        ("../x", "WATCH", "invalid"),
    ],
)
def test_promotion_and_forbidden_changes_are_refused(
    tmp_path: Path, strategy: str, target: str, message: str
) -> None:
    store = _store(tmp_path)
    with pytest.raises(LifecycleError, match=message):
        store.demote(strategy, target, "reason", "web")
    assert not store.path.exists()  # nothing was written


def test_only_a_lower_state_is_allowed_never_sideways(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.demote("paper", "DEGRADED", "x", "web")
    with pytest.raises(LifecycleError, match="lower state"):
        store.demote("paper", "WATCH", "up again", "web")  # DEGRADED -> WATCH is a promotion
    with pytest.raises(LifecycleError, match="lower state"):
        store.demote("paper", "DEGRADED", "same", "web")


def test_a_reason_is_required_and_a_corrupt_store_fails_closed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(LifecycleError, match="reason"):
        store.demote("cand", "WATCH", "   ", "web")
    store.path.write_text("not json\n", encoding="utf-8")
    with pytest.raises(LifecycleError, match="unreadable"):
        store.states()
    with pytest.raises(LifecycleError, match="unreadable"):
        store.demote("cand", "WATCH", "x", "web")
    store.path.write_text(
        json.dumps(
            {
                "strategy_id": "cand",
                "from_state": "NOPE",
                "to_state": "WATCH",
                "at": "t",
                "source": "s",
                "reason": "r",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(LifecycleError):
        store.states()


# -- decay -------------------------------------------------------------------------------------

CFG = DecayConfig()


def _decay(trades: list[float], **over: float) -> str:
    args = {"ci_lower": 0.02, "validated_max_dd_r": 10.0, "cost_drift": 1.0}
    args.update(over)
    return evaluate_decay(trades, config=CFG, **args).suggestion


def test_decay_states_follow_the_fixed_rules() -> None:
    good = [0.1] * 60 + [0.1] * 60
    assert _decay(good) == "VALIDATED"
    one_bad = [0.1] * 60 + [-0.05] * 60  # newest window below the lower bound
    assert _decay(one_bad) == "WATCH"
    two_bad = [-0.05] * 60 + [-0.05] * 60
    assert _decay(two_bad) == "DEGRADED"
    assert _decay(good, cost_drift=1.6) == "DEGRADED"
    assert _decay([0.1] * 100 + [-1.0] * 20, validated_max_dd_r=5.0) == "DISABLED"


def test_decay_never_trusts_bad_numbers_and_measures_drawdown() -> None:
    assert _decay([0.1, float("nan")]) == "UNKNOWN"
    assert _decay([0.1] * 60, cost_drift=float("inf")) == "UNKNOWN"
    assert max_drawdown_r([1, -2, 1, -1, 3]) == pytest.approx(2.0)
    assert max_drawdown_r([]) == 0.0
