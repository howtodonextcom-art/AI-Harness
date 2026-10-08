"""Edge Program runner: one registered variant on one Edge-Program period, judged and recorded.

Frozen rules (``docs/evals/edge-criteria.md`` appendix, ``docs/research/edge-program/ledger.md``):

* Periods Dev-H 2011-01-01..2018-12-31, Val-H 2019-01-01..2021-12-31, Test-H 2022-01-01..
  2025-04-30 (end-exclusive bounds below). Nothing at or after 2025-05-01 may be touched: the
  holdout (2026-05-01..2026-10-07) is locked and 2025-05..2026-04 (old Dev/Val) is unused.
* Costs: ``spread_used = max(recorded, 30)`` points per bar, slippage 3 points per fill (base) or
  6 points (pessimistic), commission 0, swap from the current ``CostModel``.
* Verdict: the seven criteria of ``evaluation.edge.evaluate_edge`` with ``variants = 21``, 20,000
  day-block bootstrap resamples, seed 7; a stage PASS additionally needs the pessimistic mean net
  R > 0 on the same period.
* Test-H runs exactly once per variant that passed both Dev-H and Val-H (guards below).

Invalid data is reported, never repaired (ADR-0005): the research files are read exactly as
stored (exactly one raw file per timeframe, so no merge/de-duplication happens), their validator
issues (MISSING_BARS errors, WEEKEND_BARS, ...) are written into every result, and the bars are
used as they are. Missing bars are not filled: an indicator window spans the gap (ADR-0011) and a
signal whose next H1 bar is more than 30 minutes away is skipped by the engine as ``ENTRY_GAP``
(counted in the result). Weekend bars stay in the series. Only structurally unusable data
(unsorted or duplicate timestamps, inconsistent OHLC, missing spread) makes the run refuse.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Literal

import polars as pl

from xau_edge.backtest.costs import CostModel
from xau_edge.backtest.engine import BacktestConfig, BacktestResult, prop_breaches, run_backtest
from xau_edge.backtest.metrics import Metrics, compute_metrics
from xau_edge.domain.bars import coerce_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.evaluation.edge import EdgeVerdict, evaluate_edge
from xau_edge.experiments.registry import ExperimentRecord, ExperimentRegistry
from xau_edge.features.sessions import session_features
from xau_edge.market_data.store import RawStore
from xau_edge.market_data.validators import validate_bars
from xau_edge.market_data.validators.models import ValidationConfig, ValidationReport
from xau_edge.risk.engine import RiskLimits
from xau_edge.risk.prop_rules import PropProfile
from xau_edge.strategies.edge_program import (
    PROGRAM,
    SignalContext,
    Variant,
    edge_context,
    variant_signals,
)

FAMILY: Final = PROGRAM
SYMBOL: Final = "XAUUSD"
VARIANTS_K: Final = 21
N_RESAMPLES: Final = 20_000
SEED: Final = 7
INITIAL_CAPITAL: Final = 100_000.0
SPREAD_FLOOR_POINTS: Final = 30.0
BASE_SLIPPAGE_POINTS: Final = 3.0
PESSIMISTIC_SLIPPAGE_POINTS: Final = 6.0
HOLDOUT_CUTOFF: Final = datetime(2025, 5, 1, tzinfo=UTC)
DATA_TIMEFRAMES: Final = (Timeframe.H1, Timeframe.H4)
EDGE_PERIODS: Final[Mapping[str, tuple[datetime, datetime]]] = MappingProxyType(
    {
        "dev": (datetime(2011, 1, 1, tzinfo=UTC), datetime(2019, 1, 1, tzinfo=UTC)),
        "val": (datetime(2019, 1, 1, tzinfo=UTC), datetime(2022, 1, 1, tzinfo=UTC)),
        "test": (datetime(2022, 1, 1, tzinfo=UTC), datetime(2025, 5, 1, tzinfo=UTC)),
    }
)
PRE_TEST_PERIODS: Final = ("dev", "val")

Scenario = Literal["base", "pessimistic"]
NOTES: Final = (
    "edge program research run: H1 execution, no news calendar; spread max(recorded, 30) pts; "
    "slippage 3 pts (base) / 6 pts (pessimistic); commission 0 (unverified); swap per CostModel"
)


class HoldoutError(PermissionError):
    """A request touched data at or after 2025-05-01 (locked holdout / unused old splits)."""


class SingleTestRunError(PermissionError):
    """The single Test-H run is not (or no longer) allowed for a variant."""


class DatasetMismatchError(ValueError):
    """The research files do not match ``data-manifest.json``."""


# ---------------------------------------------------------------------------------------------
# guards


def check_before_holdout(start: datetime, end: datetime) -> None:
    """Refuse any window that starts at or ends after the 2025-05-01 cut-off (end-exclusive)."""
    if start.tzinfo is None or end.tzinfo is None:
        msg = "period bounds must be timezone-aware"
        raise ValueError(msg)
    if start >= end:
        msg = f"empty period {start.isoformat()} .. {end.isoformat()}"
        raise ValueError(msg)
    if start >= HOLDOUT_CUTOFF or end > HOLDOUT_CUTOFF:
        msg = (
            f"refused: {start.isoformat()} .. {end.isoformat()} reaches the locked data at or "
            f"after {HOLDOUT_CUTOFF.date().isoformat()}"
        )
        raise HoldoutError(msg)


def check_bars_before_holdout(bars: pl.DataFrame, label: str) -> None:
    """Refuse a frame holding any bar that opens at or after the cut-off."""
    if bars.height == 0:
        return
    last = bars["timestamp"].max()
    if not isinstance(last, datetime) or last >= HOLDOUT_CUTOFF:
        msg = f"refused: {label} contains bars at or after {HOLDOUT_CUTOFF.date().isoformat()}"
        raise HoldoutError(msg)


def edge_period(name: str) -> tuple[datetime, datetime]:
    """End-exclusive bounds of ``dev``, ``val`` or ``test`` (always before the cut-off)."""
    if name not in EDGE_PERIODS:
        msg = f"unknown period {name!r}; choose from {list(EDGE_PERIODS)}"
        raise ValueError(msg)
    bounds = EDGE_PERIODS[name]
    check_before_holdout(*bounds)
    return bounds


def _records(registry: ExperimentRegistry, variant_id: str, period: str) -> list[ExperimentRecord]:
    return [
        r
        for r in registry.list(FAMILY)
        if r.params.get("variant") == variant_id and r.period == period
    ]


def has_stage_pass(
    registry: ExperimentRegistry,
    variant_id: str,
    period: str,
    *,
    dataset_ids: Mapping[str, str] | None = None,
) -> bool:
    """True if the LATEST completed record of the variant on ``period`` is a stage PASS."""
    done = [
        r
        for r in _records(registry, variant_id, period)
        if r.metrics.get("status") == "completed"
        and (dataset_ids is None or r.dataset_ids == dict(dataset_ids))
    ]
    return bool(done) and done[-1].metrics.get("stage_pass") is True


def check_test_allowed(
    registry: ExperimentRegistry,
    variant_id: str,
    *,
    confirmed: bool,
    dataset_ids: Mapping[str, str],
) -> None:
    """Refuse Test-H unless confirmed, never run before, and passed on Dev-H and Val-H."""
    if not confirmed:
        msg = "Test-H is single-use: pass --confirm-single-test-run for a finished candidate only"
        raise SingleTestRunError(msg)
    if _records(registry, variant_id, "test"):
        msg = f"{variant_id} already has a Test-H record (started or completed); no re-runs"
        raise SingleTestRunError(msg)
    missing = [
        p
        for p in PRE_TEST_PERIODS
        if not has_stage_pass(registry, variant_id, p, dataset_ids=dataset_ids)
    ]
    if missing:
        msg = f"{variant_id} has no recorded stage PASS on {', '.join(missing)}; Test-H refused"
        raise SingleTestRunError(msg)


# ---------------------------------------------------------------------------------------------
# costs


def apply_cost_rule(bars: pl.DataFrame) -> pl.DataFrame:
    """Execution columns with ``spread = max(recorded, 30)`` points as Float64.

    A missing spread is refused rather than replaced: the rule is defined on a recorded value.
    """
    nulls = bars["spread"].null_count()
    if nulls:
        msg = f"{nulls} bar(s) have no recorded spread; refusing to invent one"
        raise ValueError(msg)
    return bars.select(
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        pl.max_horizontal(pl.col("spread").cast(pl.Float64), pl.lit(SPREAD_FLOOR_POINTS)).alias(
            "spread"
        ),
    )


def cost_model(scenario: Scenario) -> CostModel:
    """The frozen cost model of a scenario (only slippage differs)."""
    slippage = BASE_SLIPPAGE_POINTS if scenario == "base" else PESSIMISTIC_SLIPPAGE_POINTS
    return CostModel(slippage_points=slippage)


def cost_assumptions() -> dict[str, Any]:
    """What every result states about costs."""
    base = cost_model("base")
    return {
        "spread_rule": f"max(recorded, {SPREAD_FLOOR_POINTS:g}) points",
        "slippage_points": {
            "base": BASE_SLIPPAGE_POINTS,
            "pessimistic": PESSIMISTIC_SLIPPAGE_POINTS,
        },
        "commission_per_lot_per_side": base.commission_per_lot_per_side,
        "swap_points": {"long": base.swap_long_points, "short": base.swap_short_points},
    }


# ---------------------------------------------------------------------------------------------
# data


@dataclass(frozen=True)
class ResearchData:
    """The verified H1 and H4 research datasets with their ids and validator issues."""

    h1: pl.DataFrame
    h4: pl.DataFrame
    dataset_ids: dict[str, str]
    sha256: dict[str, str]
    validation: dict[str, list[dict[str, Any]]]


def issue_list(report: ValidationReport) -> list[dict[str, Any]]:
    """Validator issues as JSON-safe dicts (code, severity, count, message)."""
    return [
        {
            "code": i.code.value,
            "severity": i.severity.value,
            "count": i.count,
            "message": i.message,
        }
        for i in report.issues
    ]


def manifest_dataset_ids(manifest_path: Path | str) -> dict[str, str]:
    """``{timeframe: dataset_id}`` registered in the manifest for H1 and H4."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for tf in DATA_TIMEFRAMES:
        entry = manifest.get(tf.value) or {}
        if "dataset_id" not in entry or "sha256" not in entry:
            msg = f"manifest has no dataset_id/sha256 for {tf.value}"
            raise DatasetMismatchError(msg)
        out[tf.value] = str(entry["dataset_id"])
    return out


def load_research_data(
    root: Path | str,
    manifest_path: Path | str,
    *,
    validation: ValidationConfig | None = None,
    symbol: str = SYMBOL,
) -> ResearchData:
    """Load H1/H4 exactly as stored, refusing anything that disagrees with the manifest.

    Checks: exactly one raw file per timeframe, its content hash equals the manifest ``sha256``,
    the catalog-style ``dataset_id`` (hash of the file hashes) equals the manifest id, the row
    count matches, and no bar opens at or after the cut-off. The validator report is attached.
    """
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    expected = manifest_dataset_ids(manifest_path)
    store = RawStore(root)
    frames: dict[str, pl.DataFrame] = {}
    shas: dict[str, str] = {}
    issues: dict[str, list[dict[str, Any]]] = {}
    for tf in DATA_TIMEFRAMES:
        entry = manifest[tf.value]
        datasets = store.datasets(symbol, tf)
        hashes = sorted(d.sha256 for d in datasets)
        dataset_id = hashlib.sha256("|".join(hashes).encode()).hexdigest()[:16]
        if len(datasets) != 1 or hashes[0] != entry["sha256"] or dataset_id != expected[tf.value]:
            msg = (
                f"{tf.value}: stored files {hashes} (dataset_id {dataset_id}) do not match the "
                f"manifest (sha256 {entry['sha256']}, dataset_id {expected[tf.value]}); refusing"
            )
            raise DatasetMismatchError(msg)
        frame = coerce_bars(store.read_verified(datasets[0]))
        if "rows" in entry and frame.height != int(entry["rows"]):
            msg = f"{tf.value}: {frame.height} rows, manifest says {entry['rows']}"
            raise DatasetMismatchError(msg)
        check_bars_before_holdout(frame, f"{tf.value} research dataset")
        frames[tf.value] = frame
        shas[tf.value] = hashes[0]
        issues[tf.value] = issue_list(validate_bars(frame, tf, symbol=symbol, config=validation))
    return ResearchData(frames["H1"], frames["H4"], expected, shas, issues)


def period_inputs(
    h1: pl.DataFrame, h4: pl.DataFrame | None, period: tuple[datetime, datetime]
) -> tuple[SignalContext, pl.DataFrame]:
    """Signal context from every bar before the period end (warm-up from earlier data) and the
    period's H1 execution bars with the cost rule applied."""
    start, end = period
    check_before_holdout(start, end)
    ts = pl.col("timestamp")
    h1_hist = h1.filter(ts < end)
    h4_hist = None if h4 is None else h4.filter(ts < end)
    check_bars_before_holdout(h1_hist, "H1 input")
    if h4_hist is not None:
        check_bars_before_holdout(h4_hist, "H4 input")
    bars = apply_cost_rule(h1.filter((ts >= start) & (ts < end)))
    return edge_context(h1_hist, h4_hist), bars


def period_signals(
    variant: Variant, ctx: SignalContext, period: tuple[datetime, datetime]
) -> pl.DataFrame:
    """The variant's signals decided inside ``[start, end)``."""
    start, end = period
    sig = variant_signals(variant, ctx)
    return sig.filter((pl.col("decision_time") >= start) & (pl.col("decision_time") < end))


# ---------------------------------------------------------------------------------------------
# run


@dataclass(frozen=True)
class ScenarioRun:
    """One cost scenario of one variant-period run."""

    scenario: Scenario
    result: BacktestResult
    trades: pl.DataFrame
    metrics: Metrics
    verdict: EdgeVerdict | None
    """The seven criteria (base scenario only)."""
    mean_net_r: float | None


@dataclass(frozen=True)
class VariantRun:
    """Everything produced by one variant on one period."""

    variant: Variant
    period_name: str
    period: tuple[datetime, datetime]
    signal_count: int
    base: ScenarioRun
    pessimistic: ScenarioRun
    prop_feasibility: dict[str, Any]
    n_resamples: int
    seed: int

    @property
    def stage_pass(self) -> bool:
        """Seven criteria on the base scenario AND pessimistic mean net R > 0."""
        assert self.base.verdict is not None  # noqa: S101 - base is always judged
        return stage_passed(self.base.verdict.passed, self.pessimistic.mean_net_r)


def stage_passed(base_passed: bool, pessimistic_mean_r: float | None) -> bool:
    """The frozen stage rule (ledger rule 2)."""
    return base_passed and pessimistic_mean_r is not None and pessimistic_mean_r > 0


def research_prop(prop: PropProfile) -> PropProfile:
    """The prop profile with its limits opened up, exactly as the baseline research runs do.

    A 5% / 10% buffer would stop every later trade and truncate the sample; feasibility under the
    real profile is measured afterwards from the equity curve.
    """
    return prop.model_copy(
        update={
            "daily_loss_limit_pct": 99.0,
            "max_loss_limit_pct": 99.0,
            "max_loss_kind": "static",
            "internal_buffer_pct_of_limit": 0.0,
        }
    )


def _with_sessions(trades: pl.DataFrame) -> pl.DataFrame:
    if trades.height:
        sessions = session_features(trades["entry_time"])["trading_session"]
        return trades.with_columns(sessions.alias("session"))
    return trades.with_columns(pl.lit(None, dtype=pl.String).alias("session"))


def run_scenario(
    scenario: Scenario,
    signals: pl.DataFrame,
    bars: pl.DataFrame,
    period: tuple[datetime, datetime],
    prop: PropProfile,
    *,
    judge: bool,
    n_resamples: int = N_RESAMPLES,
    seed: int = SEED,
    initial_capital: float = INITIAL_CAPITAL,
) -> ScenarioRun:
    """Backtest the signals on H1 bars under one cost scenario (and judge it if asked)."""
    config = BacktestConfig(
        signal_timeframe=Timeframe.H1,
        execution_timeframe=Timeframe.H1,
        initial_capital=initial_capital,
        costs=cost_model(scenario),
        require_news_calendar=False,
        limits=RiskLimits(daily_risk_budget_pct=100.0, consecutive_loss_limit=10_000),
    )
    result = run_backtest(signals, bars, config, research_prop(prop))
    trades = _with_sessions(result.trades)
    metrics = compute_metrics(trades, result.equity, initial_capital)
    verdict = None
    if judge:
        verdict = evaluate_edge(
            trades,
            result.equity,
            period=period,
            variants=VARIANTS_K,
            initial_capital=initial_capital,
            seed=seed,
            n_resamples=n_resamples,
        )
    mean = float(trades["net_r"].mean()) if trades.height else None  # type: ignore[arg-type]
    return ScenarioRun(scenario, result, trades, metrics, verdict, mean)


def run_variant(
    variant: Variant,
    ctx: SignalContext,
    bars: pl.DataFrame,
    period_name: str,
    period: tuple[datetime, datetime],
    *,
    prop: PropProfile,
    n_resamples: int = N_RESAMPLES,
    seed: int = SEED,
    initial_capital: float = INITIAL_CAPITAL,
) -> VariantRun:
    """Signals, both cost scenarios, the seven criteria and the pessimistic condition."""
    check_before_holdout(*period)
    check_bars_before_holdout(bars, "execution bars")
    signals = period_signals(variant, ctx, period)
    kwargs: dict[str, Any] = {
        "n_resamples": n_resamples,
        "seed": seed,
        "initial_capital": initial_capital,
    }
    base = run_scenario("base", signals, bars, period, prop, judge=True, **kwargs)
    pess = run_scenario("pessimistic", signals, bars, period, prop, judge=False, **kwargs)
    breaches = prop_breaches(base.result.equity, prop, initial_capital=initial_capital)
    daily: list[date] = breaches["daily"]
    feasibility = {
        "profile": prop.name,
        "daily_floor_breach_days": len(daily),
        "first_breach_days": [d.isoformat() for d in daily[:5]],
        "max_loss_floor_hit": bool(breaches["max_loss"]),
    }
    return VariantRun(
        variant, period_name, period, signals.height, base, pess, feasibility, n_resamples, seed
    )


# ---------------------------------------------------------------------------------------------
# recording


def _json_safe(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _json_object(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(k): _json_safe(v) for k, v in value.items()}


def _skipped(result: BacktestResult) -> dict[str, int]:
    if result.skipped.height == 0:
        return {}
    counts = result.skipped.group_by("reason").len().sort("reason")
    return {str(r): int(n) for r, n in counts.iter_rows()}


def _scenario_summary(s: ScenarioRun) -> dict[str, Any]:
    out: dict[str, Any] = {
        "trades": s.trades.height,
        "mean_net_r": s.mean_net_r,
        "metrics": asdict(s.metrics),
        "skipped_signals": _skipped(s.result),
        "slippage_points": cost_model(s.scenario).slippage_points,
    }
    if s.verdict is not None:
        out["verdict"] = s.verdict.as_dict()
    return out


def run_metrics(run: VariantRun, data_issues: Mapping[str, Any]) -> dict[str, Any]:
    """JSON-safe metrics block stored in the registry record."""
    return _json_object(
        {
            "status": "completed",
            "stage_pass": run.stage_pass,
            "variants_k": VARIANTS_K,
            "alpha": run.base.verdict.alpha if run.base.verdict else None,
            "n_resamples": run.n_resamples,
            "signals": run.signal_count,
            "scenarios": {
                "base": _scenario_summary(run.base),
                "pessimistic": _scenario_summary(run.pessimistic),
            },
            "prop_feasibility": run.prop_feasibility,
            "data_issues": dict(data_issues),
        }
    )


def record_run(
    registry: ExperimentRegistry,
    run: VariantRun,
    *,
    dataset_ids: Mapping[str, str],
    data_issues: Mapping[str, Any],
    code_version: str | None = None,
    code_dirty: bool | None = None,
) -> ExperimentRecord:
    """Write the run to the registry (git sha and dirty flag are detected when not given)."""
    return registry.record(
        family=FAMILY,
        name=f"{run.variant.variant_id}-{run.period_name}",
        dataset_ids=dict(dataset_ids),
        feature_ids={},
        params=run.variant.params(),
        seeds={"bootstrap": run.seed},
        period=run.period_name,
        metrics=run_metrics(run, data_issues),
        code_version=code_version,
        code_dirty=code_dirty,
        notes=NOTES,
    )


def mark_test_started(
    registry: ExperimentRegistry,
    variant: Variant,
    *,
    dataset_ids: Mapping[str, str],
    code_version: str | None = None,
    code_dirty: bool | None = None,
) -> ExperimentRecord:
    """Record the Test-H attempt BEFORE it runs, so a crash cannot open a second attempt."""
    return registry.record(
        family=FAMILY,
        name=f"{variant.variant_id}-test-started",
        dataset_ids=dict(dataset_ids),
        feature_ids={},
        params=variant.params(),
        seeds={"bootstrap": SEED},
        period="test",
        metrics={"status": "started", "started_at": datetime.now(UTC).isoformat()},
        code_version=code_version,
        code_dirty=code_dirty,
        notes=NOTES,
    )


def result_payload(
    run: VariantRun,
    record: ExperimentRecord,
    *,
    sha256: Mapping[str, str],
) -> dict[str, Any]:
    """The JSON result file: identity, assumptions, verdict, pessimistic condition, data issues."""
    start, end = run.period
    return _json_object(
        {
            "program": PROGRAM,
            "variant": run.variant.variant_id,
            "hypothesis": run.variant.hypothesis,
            "params": run.variant.params(),
            "period": {
                "name": run.period_name,
                "start": start,
                "end_exclusive": end,
            },
            "dataset_ids": record.dataset_ids,
            "dataset_sha256": dict(sha256),
            "code_version": record.code_version,
            "code_dirty": record.code_dirty,
            "registry_id": record.id,
            "recorded_at": record.created_at,
            "seed": run.seed,
            "costs": cost_assumptions(),
            "assumptions": NOTES,
            **record.metrics,
        }
    )


def write_result(payload: Mapping[str, Any], out_dir: Path | str) -> Path:
    """Write ``<variant>_<period>_<registry id>.json`` (never overwrites an earlier result)."""
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{payload['variant']}_{payload['period']['name']}_{payload['registry_id']}.json"
    path = directory / name
    path.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    return path


@dataclass(frozen=True)
class ExecutedRun:
    """A recorded run and where its files went."""

    run: VariantRun
    record: ExperimentRecord
    result_path: Path


def execute(
    variants: Sequence[Variant],
    period_name: str,
    data: ResearchData,
    prop: PropProfile,
    registry: ExperimentRegistry,
    *,
    out_dir: Path | str,
    confirm_single_test_run: bool = False,
    validation: ValidationConfig | None = None,
    trades_dir: Path | str | None = None,
    n_resamples: int = N_RESAMPLES,
    seed: int = SEED,
    code_version: str | None = None,
    code_dirty: bool | None = None,
) -> list[ExecutedRun]:
    """Guard, run, record and write results for ``variants`` on one Edge-Program period.

    For ``test`` every variant is checked BEFORE anything runs; one refusal refuses the batch.
    """
    period = edge_period(period_name)
    if period_name == "test":
        for v in variants:
            check_test_allowed(
                registry,
                v.variant_id,
                confirmed=confirm_single_test_run,
                dataset_ids=data.dataset_ids,
            )
    ctx, bars = period_inputs(data.h1, data.h4, period)
    window = data.h1.filter((pl.col("timestamp") >= period[0]) & (pl.col("timestamp") < period[1]))
    issues: dict[str, Any] = {
        "policy": "reported, never repaired (ADR-0005); bars used as stored",
        "dataset": data.validation,
        "period_h1": issue_list(validate_bars(window, Timeframe.H1, config=validation)),
    }
    done: list[ExecutedRun] = []
    for v in variants:
        if period_name == "test":
            mark_test_started(
                registry,
                v,
                dataset_ids=data.dataset_ids,
                code_version=code_version,
                code_dirty=code_dirty,
            )
        run = run_variant(
            v, ctx, bars, period_name, period, prop=prop, n_resamples=n_resamples, seed=seed
        )
        record = record_run(
            registry,
            run,
            dataset_ids=data.dataset_ids,
            data_issues=issues,
            code_version=code_version,
            code_dirty=code_dirty,
        )
        path = write_result(result_payload(run, record, sha256=data.sha256), out_dir)
        if trades_dir is not None:
            tdir = Path(trades_dir)
            tdir.mkdir(parents=True, exist_ok=True)
            for s in (run.base, run.pessimistic):
                s.trades.write_parquet(
                    tdir / f"trades_{v.variant_id}_{period_name}_{s.scenario}_{record.id}.parquet"
                )
        done.append(ExecutedRun(run, record, path))
    return done
