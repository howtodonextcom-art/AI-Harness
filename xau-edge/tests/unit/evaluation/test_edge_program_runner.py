"""Edge Program runner on SYNTHETIC frames: guards, cost rule, manifest checks and recording."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import pytest

from xau_edge.backtest.engine import BacktestConfig, run_backtest
from xau_edge.domain.bars import BAR_SCHEMA
from xau_edge.domain.timeframe import Timeframe
from xau_edge.evaluation.edge import BASE_ALPHA
from xau_edge.evaluation.edge_program import (
    EDGE_PERIODS,
    FAMILY,
    HOLDOUT_CUTOFF,
    N_RESAMPLES,
    SEED,
    VARIANTS_K,
    DatasetMismatchError,
    HoldoutError,
    ResearchData,
    SingleTestRunError,
    apply_cost_rule,
    check_bars_before_holdout,
    check_before_holdout,
    check_test_allowed,
    cost_model,
    edge_period,
    execute,
    has_stage_pass,
    load_research_data,
    period_inputs,
    period_signals,
    stage_passed,
)
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.market_data.store import RawStore
from xau_edge.risk.engine import RiskLimits
from xau_edge.risk.prop_rules import load_prop_profile
from xau_edge.strategies.edge_program import VARIANTS, get_variant

PROP = load_prop_profile(Path(__file__).parents[3] / "configs" / "prop" / "ftmo_2step.yaml")
IDS = {"H1": "aaaaaaaaaaaaaaaa", "H4": "bbbbbbbbbbbbbbbb"}
H1 = Timeframe.H1
H4 = Timeframe.H4


def _walk(start: datetime, n: int, tf: Timeframe, seed: int, spread: int = 10) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    close = 2000.0 + np.cumsum(rng.normal(0.0, 1.0 + 0.8 * np.sin(np.arange(n) / 40.0)))
    opens = np.concatenate([[2000.0], close[:-1]])
    wick = np.abs(rng.normal(0.0, 0.5, n))
    return pl.DataFrame(
        {
            "timestamp": [start + i * timedelta(minutes=tf.minutes) for i in range(n)],
            "open": opens,
            "high": np.maximum(opens, close) + wick,
            "low": np.minimum(opens, close) - wick[::-1],
            "close": close,
            "tick_volume": np.full(n, 100),
            "spread": np.full(n, spread),
            "real_volume": [None] * n,
        },
        schema=BAR_SCHEMA,
    )


def _data(start: datetime, days: int) -> ResearchData:
    h1 = _walk(start, 24 * days, H1, 5)
    h4 = _walk(start + timedelta(hours=1), 6 * days, H4, 6)
    return ResearchData(h1, h4, dict(IDS), {"H1": "x", "H4": "y"}, {"H1": [], "H4": []})


def _record(
    registry: ExperimentRegistry,
    variant: str,
    period: str,
    *,
    stage_pass: bool,
    status: str = "completed",
    dataset_ids: dict[str, str] | None = None,
    note: str = "",
) -> None:
    registry.record(
        family=FAMILY,
        name=f"{variant}-{period}",
        dataset_ids=dataset_ids or dict(IDS),
        feature_ids={},
        params=get_variant(variant).params(),
        seeds={"bootstrap": 7},
        period=period,
        metrics={"status": status, "stage_pass": stage_pass},
        code_version="test",
        code_dirty=False,
        notes=note,
    )


# --- frozen constants and periods -----------------------------------------------------------


def test_frozen_statistical_constants() -> None:
    assert VARIANTS_K == 21
    assert N_RESAMPLES == 20_000
    assert SEED == 7
    assert datetime(2025, 5, 1, tzinfo=UTC) == HOLDOUT_CUTOFF


def test_edge_periods_match_the_appendix() -> None:
    assert edge_period("dev") == (
        datetime(2011, 1, 1, tzinfo=UTC),
        datetime(2019, 1, 1, tzinfo=UTC),
    )
    assert edge_period("val") == (
        datetime(2019, 1, 1, tzinfo=UTC),
        datetime(2022, 1, 1, tzinfo=UTC),
    )
    assert edge_period("test") == (
        datetime(2022, 1, 1, tzinfo=UTC),
        datetime(2025, 5, 1, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="dev"):
        edge_period("development")
    assert set(EDGE_PERIODS) == {"dev", "val", "test"}


# --- holdout guard --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (datetime(2025, 4, 1, tzinfo=UTC), datetime(2025, 5, 1, 1, tzinfo=UTC)),
        (datetime(2025, 5, 1, tzinfo=UTC), datetime(2025, 6, 1, tzinfo=UTC)),
        (datetime(2026, 5, 1, tzinfo=UTC), datetime(2026, 10, 8, tzinfo=UTC)),
    ],
)
def test_any_window_reaching_2025_05_01_is_refused(start: datetime, end: datetime) -> None:
    with pytest.raises(HoldoutError):
        check_before_holdout(start, end)


def test_bars_at_or_after_the_cutoff_are_refused() -> None:
    ok = _walk(datetime(2025, 4, 30, 20, tzinfo=UTC), 4, H1, 1)  # last bar opens 23:00
    check_bars_before_holdout(ok, "ok")
    with pytest.raises(HoldoutError):
        check_bars_before_holdout(_walk(datetime(2025, 4, 30, 20, tzinfo=UTC), 5, H1, 1), "late")


def test_run_variant_refuses_execution_bars_in_the_holdout() -> None:
    data = _data(datetime(2025, 4, 1, tzinfo=UTC), 40)
    with pytest.raises(HoldoutError):
        period_inputs(
            data.h1, data.h4, (datetime(2025, 4, 10, tzinfo=UTC), data.h1["timestamp"][-1])
        )


# --- cost rule ------------------------------------------------------------------------------


def test_spread_floor_of_thirty_points() -> None:
    bars = _walk(datetime(2011, 1, 3, tzinfo=UTC), 5, H1, 1).with_columns(
        pl.Series("spread", [0, 10, 30, 45, -5], dtype=pl.Int64)
    )
    out = apply_cost_rule(bars)
    assert out["spread"].to_list() == [30.0, 30.0, 30.0, 45.0, 30.0]
    assert out.schema["spread"] == pl.Float64
    assert out.columns == ["timestamp", "open", "high", "low", "close", "spread"]


def test_missing_spread_is_refused_not_invented() -> None:
    bars = _walk(datetime(2011, 1, 3, tzinfo=UTC), 3, H1, 1).with_columns(
        pl.Series("spread", [10, None, 10], dtype=pl.Int64)
    )
    with pytest.raises(ValueError, match="no recorded spread"):
        apply_cost_rule(bars)


def test_base_and_pessimistic_slippage() -> None:
    assert cost_model("base").slippage_points == 3.0
    assert cost_model("pessimistic").slippage_points == 6.0
    assert cost_model("base").commission_per_lot_per_side == 0.0
    assert cost_model("base").model_dump(exclude={"slippage_points"}) == cost_model(
        "pessimistic"
    ).model_dump(exclude={"slippage_points"})


@pytest.mark.parametrize(
    ("base", "pess", "expected"),
    [(True, 0.01, True), (True, 0.0, False), (True, None, False), (False, 0.5, False)],
)
def test_stage_pass_needs_seven_criteria_and_positive_pessimistic_mean(
    base: bool, pess: float | None, expected: bool
) -> None:
    assert stage_passed(base, pess) is expected


def test_engine_holds_in_h1_execution_bars() -> None:
    start = datetime(2011, 1, 3, tzinfo=UTC)
    bars = pl.DataFrame(
        {
            "timestamp": [start + timedelta(hours=i) for i in range(10)],
            "open": [2000.0] * 10,
            "high": [2000.1] * 10,
            "low": [1999.9] * 10,
            "close": [2000.0] * 10,
            "spread": [30.0] * 10,
        }
    )
    signals = pl.DataFrame(
        {
            "decision_time": [start + timedelta(hours=2)],
            "direction": [1],
            "atr": [1.0],
            "stop_atr": [1.5],
            "target_atr": [3.0],
            "max_hold_bars": [3],
        }
    )
    config = BacktestConfig(
        signal_timeframe=H1,
        execution_timeframe=H1,
        require_news_calendar=False,
        limits=RiskLimits(require_regime=False),
    )
    trades = run_backtest(signals, bars, config, PROP).trades
    assert trades["entry_time"][0] == start + timedelta(hours=2)
    assert trades["exit_time"][0] == start + timedelta(hours=4)
    assert trades["exit_reason"][0] == "TIME"


# --- test-period guards ---------------------------------------------------------------------


def test_test_run_needs_confirmation(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path)
    _record(registry, "H03-c0.9", "dev", stage_pass=True)
    _record(registry, "H03-c0.9", "val", stage_pass=True)
    with pytest.raises(SingleTestRunError, match="confirm-single-test-run"):
        check_test_allowed(registry, "H03-c0.9", confirmed=False, dataset_ids=IDS)
    check_test_allowed(registry, "H03-c0.9", confirmed=True, dataset_ids=IDS)


def test_test_run_needs_stage_pass_on_dev_and_val(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path)
    with pytest.raises(SingleTestRunError, match="dev, val"):
        check_test_allowed(registry, "H03-c0.9", confirmed=True, dataset_ids=IDS)
    _record(registry, "H03-c0.9", "dev", stage_pass=True)
    _record(registry, "H03-c0.9", "val", stage_pass=False)
    with pytest.raises(SingleTestRunError, match="val"):
        check_test_allowed(registry, "H03-c0.9", confirmed=True, dataset_ids=IDS)
    # a pass of ANOTHER variant does not unlock this one
    _record(registry, "H03-c0.8", "val", stage_pass=True)
    with pytest.raises(SingleTestRunError):
        check_test_allowed(registry, "H03-c0.9", confirmed=True, dataset_ids=IDS)


def test_the_latest_completed_record_decides(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path)
    _record(registry, "H01-theta0.3", "dev", stage_pass=True, note="first")
    assert has_stage_pass(registry, "H01-theta0.3", "dev")
    _record(registry, "H01-theta0.3", "dev", stage_pass=False, note="re-run after a code fix")
    assert not has_stage_pass(registry, "H01-theta0.3", "dev")


def test_passes_on_other_datasets_do_not_count(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path)
    other = {"H1": "cccccccccccccccc", "H4": "dddddddddddddddd"}
    _record(registry, "H03-c0.9", "dev", stage_pass=True, dataset_ids=other)
    _record(registry, "H03-c0.9", "val", stage_pass=True, dataset_ids=other)
    with pytest.raises(SingleTestRunError):
        check_test_allowed(registry, "H03-c0.9", confirmed=True, dataset_ids=IDS)


def test_test_run_is_refused_once_any_test_record_exists(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path)
    _record(registry, "H03-c0.9", "dev", stage_pass=True)
    _record(registry, "H03-c0.9", "val", stage_pass=True)
    _record(registry, "H03-c0.9", "test", stage_pass=False, status="started")
    with pytest.raises(SingleTestRunError, match="no re-runs"):
        check_test_allowed(registry, "H03-c0.9", confirmed=True, dataset_ids=IDS)


def test_execute_refuses_test_before_running_anything(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path / "runs")
    data = _data(datetime(2021, 12, 1, tzinfo=UTC), 30)
    with pytest.raises(SingleTestRunError):
        execute(
            [get_variant("H05-s1.5")], "test", data, PROP, registry, out_dir=tmp_path / "out",
            confirm_single_test_run=True, n_resamples=20, code_version="t", code_dirty=False,
        )  # fmt: skip
    assert registry.list(FAMILY) == []
    assert not (tmp_path / "out").exists()


def test_single_test_run_is_recorded_and_cannot_be_repeated(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path / "runs")
    _record(registry, "H05-s1.5", "dev", stage_pass=True)
    _record(registry, "H05-s1.5", "val", stage_pass=True)
    data = _data(datetime(2021, 12, 1, tzinfo=UTC), 45)
    kwargs: dict[str, Any] = {
        "confirm_single_test_run": True,
        "n_resamples": 20,
        "code_version": "t",
        "code_dirty": False,
    }
    done = execute(
        [get_variant("H05-s1.5")], "test", data, PROP, registry, out_dir=tmp_path / "o", **kwargs
    )
    assert len(done) == 1
    statuses = sorted(r.metrics["status"] for r in registry.list(FAMILY) if r.period == "test")
    assert statuses == ["completed", "started"]
    with pytest.raises(SingleTestRunError, match="no re-runs"):
        execute(
            [get_variant("H05-s1.5")],
            "test",
            data,
            PROP,
            registry,
            out_dir=tmp_path / "o",
            **kwargs,
        )


# --- warm-up and the end-to-end run ---------------------------------------------------------


def test_warm_up_comes_from_bars_before_the_period() -> None:
    start = datetime(2010, 12, 30, tzinfo=UTC)
    n = 24 * 5
    price = np.full(n, 2000.0)
    bars = pl.DataFrame(
        {
            "timestamp": [start + timedelta(hours=i) for i in range(n)],
            "open": price,
            "high": price + 0.1,
            "low": price - 0.1,
            "close": price,
            "tick_volume": np.full(n, 100),
            "spread": np.full(n, 10),
            "real_volume": [None] * n,
        },
        schema=BAR_SCHEMA,
    )
    big = pl.col("timestamp") == datetime(2011, 1, 1, 1, tzinfo=UTC)
    bars = bars.with_columns(
        pl.when(big).then(2001.0).otherwise(pl.col("close")).alias("close"),
        pl.when(big).then(2001.1).otherwise(pl.col("high")).alias("high"),
    )
    period = (datetime(2011, 1, 1, tzinfo=UTC), datetime(2011, 1, 3, tzinfo=UTC))
    ctx, exec_bars = period_inputs(bars, None, period)
    sig = period_signals(get_variant("H05-s1.5"), ctx, period)
    assert sig["decision_time"].to_list() == [datetime(2011, 1, 1, 2, tzinfo=UTC)]
    assert exec_bars["timestamp"].min() == period[0]
    assert exec_bars["timestamp"].max() == period[1] - timedelta(hours=1)
    assert (exec_bars["spread"] == 30.0).all()


def test_execute_dev_records_results_with_k21(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path / "runs")
    data = _data(datetime(2010, 12, 1, tzinfo=UTC), 75)
    variants = [get_variant("H01-theta0.3"), get_variant("H06-N20")]
    done = execute(
        variants, "dev", data, PROP, registry, out_dir=tmp_path / "out",
        trades_dir=tmp_path / "trades", n_resamples=50, code_version="abc123", code_dirty=True,
    )  # fmt: skip
    assert [d.run.variant.variant_id for d in done] == ["H01-theta0.3", "H06-N20"]
    for d in done:
        verdict = d.run.base.verdict
        assert verdict is not None
        assert verdict.variants == 21
        assert verdict.alpha == pytest.approx(BASE_ALPHA / 21)
        assert len(verdict.criteria) == 7
        trades = d.run.base.trades
        if trades.height:
            assert (trades["entry_time"] >= EDGE_PERIODS["dev"][0]).all()
        payload = json.loads(d.result_path.read_text(encoding="utf-8"))
        assert payload["variant"] == d.run.variant.variant_id
        assert payload["period"]["name"] == "dev"
        assert payload["variants_k"] == 21
        assert payload["n_resamples"] == 50
        assert payload["code_version"] == "abc123"
        assert payload["code_dirty"] is True
        assert payload["dataset_ids"] == IDS
        assert payload["costs"]["slippage_points"] == {"base": 3.0, "pessimistic": 6.0}
        assert set(payload["scenarios"]) == {"base", "pessimistic"}
        assert payload["stage_pass"] == d.run.stage_pass
        assert "period_h1" in payload["data_issues"]
        assert d.record.params["variant"] == d.run.variant.variant_id
        assert d.record.period == "dev"
        assert d.record.code_version == "abc123"
    assert len(list((tmp_path / "trades").glob("*.parquet"))) == 4
    assert registry.variant_count(FAMILY) == 2


def test_pessimistic_costs_never_beat_base_on_the_same_signals(tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path / "runs")
    data = _data(datetime(2010, 12, 1, tzinfo=UTC), 75)
    (done,) = execute(
        [get_variant("H05-s1.5")], "dev", data, PROP, registry, out_dir=tmp_path / "out",
        n_resamples=20, code_version="t", code_dirty=False,
    )  # fmt: skip
    base, pess = done.run.base.trades, done.run.pessimistic.trades
    assert base.height > 0
    assert base["entry_time"].to_list() == pess["entry_time"].to_list()
    assert float(pess["net_pnl"].sum()) < float(base["net_pnl"].sum())


# --- manifest verification ------------------------------------------------------------------


def _store(root: Path, h1: pl.DataFrame, h4: pl.DataFrame) -> dict[str, Any]:
    store = RawStore(root)
    manifest: dict[str, Any] = {}
    for tf, frame in ((H1, h1), (H4, h4)):
        ds = store.write(frame, symbol="XAUUSD", timeframe=tf, source="synthetic")
        manifest[tf.value] = {
            "rows": frame.height,
            "sha256": ds.sha256,
            "dataset_id": hashlib.sha256(ds.sha256.encode()).hexdigest()[:16],
        }
    return manifest


def _write_manifest(path: Path, manifest: dict[str, Any]) -> Path:
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_research_data_loads_when_it_matches_the_manifest(tmp_path: Path) -> None:
    h1 = _walk(datetime(2011, 1, 3, tzinfo=UTC), 48, H1, 1)
    h4 = _walk(datetime(2011, 1, 3, 1, tzinfo=UTC), 12, H4, 2)
    manifest = _store(tmp_path / "rh", h1, h4)
    data = load_research_data(tmp_path / "rh", _write_manifest(tmp_path / "m.json", manifest))
    assert data.dataset_ids == {tf: manifest[tf]["dataset_id"] for tf in ("H1", "H4")}
    assert data.h1.height == 48
    assert set(data.validation) == {"H1", "H4"}


def test_dataset_id_mismatch_is_refused(tmp_path: Path) -> None:
    h1 = _walk(datetime(2011, 1, 3, tzinfo=UTC), 48, H1, 1)
    h4 = _walk(datetime(2011, 1, 3, 1, tzinfo=UTC), 12, H4, 2)
    manifest = _store(tmp_path / "rh", h1, h4)
    manifest["H1"]["dataset_id"] = "0000000000000000"
    with pytest.raises(DatasetMismatchError):
        load_research_data(tmp_path / "rh", _write_manifest(tmp_path / "m.json", manifest))


def test_an_extra_raw_file_is_refused(tmp_path: Path) -> None:
    h1 = _walk(datetime(2011, 1, 3, tzinfo=UTC), 48, H1, 1)
    h4 = _walk(datetime(2011, 1, 3, 1, tzinfo=UTC), 12, H4, 2)
    manifest = _store(tmp_path / "rh", h1, h4)
    RawStore(tmp_path / "rh").write(
        _walk(datetime(2011, 2, 3, tzinfo=UTC), 10, H1, 3),
        symbol="XAUUSD",
        timeframe=H1,
        source="synthetic",
    )
    with pytest.raises(DatasetMismatchError):
        load_research_data(tmp_path / "rh", _write_manifest(tmp_path / "m.json", manifest))


def test_research_data_reaching_the_holdout_is_refused(tmp_path: Path) -> None:
    h1 = _walk(datetime(2025, 4, 30, 20, tzinfo=UTC), 8, H1, 1)
    h4 = _walk(datetime(2025, 4, 29, 1, tzinfo=UTC), 6, H4, 2)
    manifest = _store(tmp_path / "rh", h1, h4)
    with pytest.raises(HoldoutError):
        load_research_data(tmp_path / "rh", _write_manifest(tmp_path / "m.json", manifest))


def test_every_registered_variant_runs_on_synthetic_data() -> None:
    data = _data(datetime(2010, 12, 1, tzinfo=UTC), 60)
    period = (datetime(2011, 1, 1, tzinfo=UTC), datetime(2011, 1, 30, tzinfo=UTC))
    ctx, _ = period_inputs(data.h1, data.h4, period)
    for v in VARIANTS.values():
        sig = period_signals(v, ctx, period)
        assert sig.height == 0 or (sig["decision_time"] >= period[0]).all()
