"""Research console views over a synthetic repository: sources, fail-closed answers, order."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.unit.research.helpers import (
    commit,
    make_repo,
    result_file,
    write,
)
from xau_edge.research.service import NO_EDGE_BANNER, ResearchService

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


def _service(root: Path) -> ResearchService:
    return ResearchService(root, clock=lambda: NOW)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return make_repo(tmp_path)


# -- W-R1 overview -----------------------------------------------------------------------------


def test_the_overview_states_the_verdict_k_and_the_no_edge_banner(repo: Path) -> None:
    view = _service(repo).overview()
    assert view["status"] == "ok"
    assert view["verdict"]["label"] == "(B) NO EDGE WITHIN BUDGET"
    assert view["v1"]["k"] == 21
    assert view["v1"]["k_cap"] == 21
    assert view["v1"]["hypotheses_used"] == 1
    assert view["v1"]["hypotheses_budget"] == 6
    assert view["v2"]["started"] is False
    assert view["v2"]["hypotheses_budget"] == 8
    assert view["v2"]["k_cap"] == 48
    assert view["banner"] == NO_EDGE_BANNER
    ids = [d["id"] for d in view["decisions"]]
    assert ids == ["D-1", "D-2"]
    assert all(d["state"] == "pending" for d in view["decisions"])


def test_a_decision_the_owner_recorded_is_shown_as_such(repo: Path) -> None:
    write(
        repo,
        "docs/research/edge-program-v2/STATE.json",
        json.dumps({"sprint": "P0", "decisions": {"D-1": "approved"}}),
    )
    view = _service(repo).overview()
    assert view["v2"]["started"] is True
    assert view["v2"]["sprint"] == "P0"
    states = {d["id"]: d["state"] for d in view["decisions"]}
    assert states == {"D-1": "approved", "D-2": "pending"}


def test_missing_sources_give_unknown_never_ok(tmp_path: Path) -> None:
    view = _service(tmp_path).overview()
    assert view["status"] == "unknown"
    assert view["verdict"]["status"] == "unknown"
    assert view["v1"]["status"] == "unknown"


def test_a_validated_strategy_removes_the_banner(repo: Path) -> None:
    write(
        repo,
        "data/execution/lifecycle.jsonl",
        json.dumps(
            {
                "strategy_id": "baseline_c",
                "from_state": "REJECTED",
                "to_state": "VALIDATED",
                "at": "t",
                "source": "cli",
                "reason": "r",
            }
        )
        + "\n",
    )
    view = _service(repo).overview()
    assert view["validated_strategies"] == ["baseline_c"]
    assert view["banner"] is None


def test_a_corrupt_lifecycle_store_never_shows_the_all_clear_banner_silently(repo: Path) -> None:
    write(repo, "data/execution/lifecycle.jsonl", "garbage\n")
    view = _service(repo).overview()
    assert view["banner"].startswith("KHÔNG RÕ")


def test_stop_conditions_are_reported_when_reached(repo: Path) -> None:
    text = (repo / "docs/research/edge-program/ledger.md").read_text(encoding="utf-8")
    write(
        repo,
        "docs/research/edge-program/ledger.md",
        text.replace("= 21.** alpha", "= 21.** alpha").replace("6 giả thuyết", "1 giả thuyết"),
    )
    view = _service(repo).overview()
    assert any("ngân sách" in s for s in view["stop_conditions_reached"])


# -- W-R2 ledger and power ---------------------------------------------------------------------


def test_the_ledger_view_filters_and_counts(repo: Path) -> None:
    svc = _service(repo)
    everything = svc.ledger()
    assert everything["total_runs"] == 4
    assert everything["verdicts"] == {"FAIL": 4}
    assert everything["k"] == 21
    val = svc.ledger(period="val-H")
    assert val["shown"] == 2
    assert svc.ledger(hypothesis="H09")["shown"] == 0


def test_the_v2_ledger_is_unknown_until_it_exists(repo: Path) -> None:
    view = _service(repo).ledger(programme="v2")
    assert view["status"] == "unknown"
    assert "chưa có" in view["reason"]


def test_the_power_view_flags_underpowered_designs(repo: Path) -> None:
    view = _service(repo).power(21, 100, 1.3)
    assert view["underpowered_by_design"] is True
    assert view["mde"] == pytest.approx(0.476, abs=0.001)
    assert view["trades_needed"]["0.1"] == pytest.approx(2269, abs=4)
    assert len(view["curve"]) == 6
    assert _service(repo).power(21, 3000, 1.3)["underpowered_by_design"] is False


# -- W-R3 hypotheses and the pre-registration order --------------------------------------------


def test_a_hypothesis_committed_before_its_first_run_is_registered_in_time(tmp_path: Path) -> None:
    make_repo(tmp_path, git=True)
    commit(tmp_path, "register", "2026-10-08T10:00:00+00:00")  # ledger rows say 14:50 UTC
    view = _service(tmp_path).hypotheses()
    h01 = next(h for h in view["hypotheses"] if h["id"] == "H01")
    assert h01["preregistration"]["state"] == "OK"
    assert h01["results"]["runs"] == 4
    assert h01["results"]["best_pessimistic_min"]["variant"] in {"H01-theta0.3", "H01-theta0.6"}
    assert view["violations"] == []
    assert {p["id"] for p in view["planned"]} == {f"H{i:02d}" for i in range(7, 15)}


def test_a_hypothesis_committed_after_its_first_run_is_a_violation(tmp_path: Path) -> None:
    make_repo(tmp_path, git=True)
    commit(tmp_path, "late", "2026-10-09T10:00:00+00:00")  # after the 14:50 UTC runs of 2026-10-08
    view = _service(tmp_path).hypotheses()
    h01 = next(h for h in view["hypotheses"] if h["id"] == "H01")
    assert h01["preregistration"]["state"] == "VIOLATION"
    assert "VI PHẠM ĐĂNG KÝ TRƯỚC" in h01["preregistration"]["detail"]
    assert view["violations"] == ["H01"]


def test_results_without_a_hypothesis_file_are_a_violation(tmp_path: Path) -> None:
    make_repo(tmp_path, git=True)
    (tmp_path / "docs/research/edge-program/hypotheses/H01.md").unlink()
    view = _service(tmp_path).hypotheses()
    assert view["hypotheses"] == []  # no file, no row; the ledger still has runs
    runs = _service(tmp_path).ledger()["runs"]
    assert {r["hypothesis"] for r in runs} == {"H01"}


def test_without_git_history_the_check_is_unknown_not_ok(tmp_path: Path) -> None:
    make_repo(tmp_path, git=False)  # no repository at all
    view = _service(tmp_path).hypotheses()
    h01 = next(h for h in view["hypotheses"] if h["id"] == "H01")
    assert h01["preregistration"]["state"] == "UNKNOWN"


def test_a_hypothesis_without_results_says_so(tmp_path: Path) -> None:
    make_repo(tmp_path, git=True)
    write(tmp_path, "docs/research/edge-program/ledger.md", "# empty ledger\n")
    commit(tmp_path, "x", "2026-10-08T10:00:00+00:00")
    h01 = _service(tmp_path).hypotheses()["hypotheses"][0]
    assert h01["preregistration"]["state"] == "NO_RESULTS"


# -- W-R4 candidates and gates -----------------------------------------------------------------


def _results(repo: Path, variant: str, dev: bool, val: bool) -> None:
    for name, ok in (("dev", dev), ("val", val)):
        write(
            repo,
            f"experiments/edge_program/{variant}_{name}_x.json",
            json.dumps(result_file(variant, name, passed=ok)),
        )


def test_a_variant_is_a_survivor_only_if_it_passes_both_periods(repo: Path) -> None:
    _results(repo, "H03-c1.0", True, False)
    _results(repo, "H04-L40", True, True)
    view = _service(repo).candidates()
    by_name = {v["variant"]: v for v in view["variants"]}
    assert by_name["H03-c1.0"]["survivor"] is False
    assert by_name["H04-L40"]["survivor"] is True
    assert view["survivors"] == ["H04-L40"]


def test_gates_that_never_ran_say_so_and_never_pass_silently(repo: Path) -> None:
    _results(repo, "H04-L40", True, True)
    gates = _service(repo).candidates()["variants"][0]["gates"]
    assert set(gates) == {
        "cost_stress",
        "parameter_stability",
        "temporal_stability",
        "broker_robustness",
    }
    assert all(g["state"] == "CHƯA CHẠY" for g in gates.values())
    write(
        repo,
        "experiments/edge_program_v2/robustness/H04-L40.json",
        json.dumps(
            {
                "cost_stress": {"passed": True},
                "parameter_stability": {"passed": False, "detail": "spike"},
            }
        ),
    )
    gates = _service(repo).candidates()["variants"][0]["gates"]
    assert gates["cost_stress"]["state"] == "PASS"
    assert gates["parameter_stability"]["state"] == "FAIL"
    assert gates["temporal_stability"]["state"] == "CHƯA CHẠY"


def test_the_candidate_detail_lists_the_seven_criteria_and_missing_columns(repo: Path) -> None:
    _results(repo, "H04-L40", True, True)
    detail = _service(repo).candidate("H04-L40")
    assert detail["status"] == "ok"
    assert detail["gross_mid_r"] is None
    assert "P1" in detail["gross_mid_note"]
    assert detail["equity_curve"] is None
    dev = detail["periods"]["dev"]
    assert dev["criteria_total"] == 2
    assert dev["mean_net_r_pessimistic"] == pytest.approx(0.03)
    assert _service(repo).candidate("H99-x")["status"] == "unknown"


def test_unreadable_result_files_are_skipped_not_trusted(repo: Path) -> None:
    write(repo, "experiments/edge_program/broken.json", "{oops")
    write(repo, "experiments/edge_program/list.json", "[1,2]")
    view = _service(repo).candidates()
    assert view["status"] == "unknown"
    assert view["variants"] == []


# -- W-R5 data, clock certificate, locks -------------------------------------------------------


def test_the_data_view_shows_validator_errors_and_uncertified_years(repo: Path) -> None:
    view = _service(repo).data()
    h1 = next(f for f in view["frames"] if f["timeframe"] == "H1")
    assert h1["validation_passed"] is False
    assert h1["errors"][0]["code"] == "MISSING_BARS"
    years = view["clock_certificate"]["years"]
    assert len(years) == 16
    assert not any(y["certified"] for y in years)
    assert 2013 in view["clock_certificate"]["session_hypotheses_blocked_years"]
    assert "bị chặn" in view["clock_certificate"]["message"]


def test_a_certified_year_is_unblocked_and_the_rest_stay_blocked(repo: Path) -> None:
    write(
        repo,
        "docs/research/edge-program-v2/clock-certificate.json",
        json.dumps({"years": {"2022": {"certified": True, "offset": "NY+7"}}}),
    )
    cert = _service(repo).data()["clock_certificate"]
    assert 2022 not in cert["session_hypotheses_blocked_years"]
    assert 2021 in cert["session_hypotheses_blocked_years"]
    assert next(y for y in cert["years"] if y["year"] == 2022)["offset"] == "NY+7"


def test_a_missing_manifest_is_unknown(tmp_path: Path) -> None:
    assert _service(tmp_path).data()["status"] == "unknown"


def _registry(repo: Path, name: str, family: str, period: str) -> None:
    write(
        repo,
        f"experiments/runs/{name}.json",
        json.dumps({"id": name, "family": family, "period": period}),
    )


def test_locks_are_pristine_only_when_the_registry_was_read_and_shows_no_use(repo: Path) -> None:
    _registry(repo, "a1", "backtest", "development")
    _registry(repo, "a2", "edge-program", "dev")
    view = _service(repo).locks()
    states = {lock["id"]: lock["state"] for lock in view["locks"]}
    assert view["status"] == "ok"
    assert states["testH"] == "NGUYÊN VẸN"
    assert states["holdout"] == "NGUYÊN VẸN"
    assert states["dev2"] == "ĐÃ DÙNG THIẾT KẾ"
    assert states["forward"] == "ĐANG TÍCH LŨY"


def test_a_test_record_marks_the_lock_as_used(repo: Path) -> None:
    _registry(repo, "t1", "edge-program", "test")
    _registry(repo, "t2", "model", "test")
    states = {lock["id"]: lock["state"] for lock in _service(repo).locks()["locks"]}
    assert states["testH"] == "ĐÃ DÙNG"
    assert states["holdout"] == "ĐÃ DÙNG"


def test_without_a_registry_the_locks_are_unknown_not_pristine(repo: Path) -> None:
    view = _service(repo).locks()
    states = {lock["id"]: lock["state"] for lock in view["locks"]}
    assert view["status"] == "unknown"
    assert states["testH"] == "KHÔNG RÕ"
    assert states["holdout"] == "KHÔNG RÕ"


def test_an_unreadable_registry_record_makes_the_locks_unknown(repo: Path) -> None:
    _registry(repo, "ok", "backtest", "development")
    write(repo, "experiments/runs/bad.json", "{oops")
    states = {lock["id"]: lock["state"] for lock in _service(repo).locks()["locks"]}
    assert states["testH"] == "KHÔNG RÕ"


# -- W-R6 lifecycle and forward ----------------------------------------------------------------


def test_the_strategy_table_is_seeded_from_the_results(repo: Path) -> None:
    _results(repo, "H04-L40", True, True)
    _results(repo, "H03-c1.0", True, False)
    view = _service(repo).strategies()
    states = {s["strategy_id"]: s["state"] for s in view["strategies"]}
    assert states["H04-L40"] == "RESEARCH"
    assert states["H03-c1.0"] == "REJECTED"
    assert states["baseline_c"] == "REJECTED"
    assert all(
        not s["web_demotable"] for s in view["strategies"] if s["state"] in {"REJECTED", "RESEARCH"}
    )
    assert "không nâng bậc" in view["web_rule"]


def test_forward_data_under_100_trades_is_not_a_conclusion(repo: Path) -> None:
    write(
        repo,
        "data/forward/s1/summary.json",
        json.dumps(
            {
                "n_trades": 40,
                "mean_r_expected": {"value": 0.1, "lo": 0.02, "hi": 0.2},
                "mean_r_realised": 0.05,
                "trades_net_r": [0.1] * 40,
            }
        ),
    )
    view = _service(repo).forward("s1")
    assert view["status"] == "ok"
    assert view["conclusion"] == "KHÔNG KẾT LUẬN"
    assert view["decay"] is None
    assert view["expected_vs_realised"]["mean_r_realised"] == 0.05


def test_forward_data_with_enough_trades_gets_a_decay_suggestion(repo: Path) -> None:
    write(
        repo,
        "data/forward/s1/summary.json",
        json.dumps(
            {
                "n_trades": 120,
                "mean_r_expected": {"value": 0.1, "lo": 0.02, "hi": 0.2},
                "validated_max_dd_r": 10,
                "cost_drift": 1.0,
                "trades_net_r": [0.1] * 60 + [-0.05] * 60,
            }
        ),
    )
    view = _service(repo).forward("s1")
    assert view["conclusion"] == "ĐỦ MẪU"
    assert view["decay"]["suggestion"] == "WATCH"


def test_no_forward_sample_is_stated_plainly(repo: Path) -> None:
    view = _service(repo).forward("nothing")
    assert view["status"] == "unknown"
    assert "KHÔNG CÓ MẪU FORWARD" in view["message"]
    assert _service(repo).forward("../x")["status"] == "unknown"


# -- W-R7 calibration and soak -----------------------------------------------------------------


def test_costs_are_assumptions_until_measured(repo: Path) -> None:
    view = _service(repo).calibration()
    assert view["status"] == "unknown"
    assert view["measured"] is None
    assert view["assumed"]["slippage_points"] == 3.0
    assert view["assumed"]["commission_per_lot_per_side"] == 0.0
    assert "GIẢ ĐỊNH" in view["message"]
    write(repo, "data/execution/calibration.json", json.dumps({"slippage_points_p50": 2.0}))
    measured = _service(repo).calibration()
    assert measured["status"] == "ok"
    assert measured["measured"]["slippage_points_p50"] == 2.0


def _cycles(repo: Path, times: list[datetime], *, duplicate: bool = False) -> None:
    rows = [{"decision_time": t.isoformat(), "skipped": False, "direction": "WAIT"} for t in times]
    if duplicate:
        rows.append(rows[0])
    write(repo, "data/execution/cycles.jsonl", "\n".join(json.dumps(r) for r in rows) + "\n")


def test_soak_uptime_counts_decided_bars_against_open_market_bars(repo: Path) -> None:
    start = datetime(2026, 3, 4, 8, 0, tzinfo=UTC)  # a Wednesday morning, market open
    full = [start + timedelta(minutes=15 * i) for i in range(16)]
    _cycles(repo, full)
    view = _service(repo).soak()
    assert view["status"] == "ok"
    assert view["decided_bars"] == 16
    assert view["expected_bars"] == 16
    assert view["uptime_m15"] == pytest.approx(1.0)
    assert view["duplicate_bars"] == 0
    missing = full[:5] + full[8:]
    _cycles(repo, missing)
    view = _service(repo).soak()
    assert view["expected_bars"] == 16
    assert view["uptime_m15"] == pytest.approx(13 / 16)
    assert view["funded_rules"]["status"] == "ok"
    assert len(view["funded_rules"]["pending"]) >= 12


def test_soak_does_not_count_closed_hours_against_uptime_and_flags_duplicates(repo: Path) -> None:
    # Friday 2026-03-06: the market closes at 17:00 New York (22:00 UTC); bars over the weekend
    # are not expected.
    a = datetime(2026, 3, 6, 21, 0, tzinfo=UTC)
    b = datetime(2026, 3, 9, 1, 0, tzinfo=UTC)
    _cycles(repo, [a, b], duplicate=True)
    view = _service(repo).soak()
    assert view["duplicate_bars"] == 1
    assert view["expected_bars"] < 200  # a weekend of 15-minute bars would be about 224
    assert view["uptime_m15"] is not None


def test_soak_without_cycles_is_unknown(repo: Path) -> None:
    assert _service(repo).soak()["status"] == "unknown"
    write(repo, "data/execution/cycles.jsonl", "oops\n")
    assert _service(repo).soak()["status"] == "unknown"
