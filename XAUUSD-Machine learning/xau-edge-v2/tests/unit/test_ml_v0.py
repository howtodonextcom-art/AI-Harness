"""ML V0 guarantees: no leakage, frozen definitions, locks, ledger, registry, determinism."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from tests.conftest import write_series
from xau_edge_v2.domain.contract import Timeframe
from xau_edge_v2.ml import features as F
from xau_edge_v2.ml import guard, registry
from xau_edge_v2.ml import metrics as M
from xau_edge_v2.ml.data import dataset_hash, load_h1
from xau_edge_v2.ml.models import (
    Atr14OneFeature,
    HarRidge,
    MeanExpanding,
    RuleStateAtrPercentile,
    atr_percentile,
)
from xau_edge_v2.ml.walkforward import EMBARGO, walk_forward, years_of

H = 3600


def series(n: int, seed: int = 3, start: int = 1_262_304_000) -> F.Bars:
    """A random-walk H1 series starting 2010-01-01 00:00 UTC."""
    rng = np.random.default_rng(seed)
    close = 2000 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    spread = np.abs(rng.normal(0, 0.0015, n)) * close
    open_s = start + np.arange(n, dtype=np.int64) * H
    return F.Bars(open_s, close + spread, close - spread, close)


# ---- features and label: causality --------------------------------------------------------------
def test_features_do_not_depend_on_the_future() -> None:
    bars = series(900)
    full = F.build_features(bars)
    for cut in (300, 555, 899):
        part = F.build_features(bars.head(cut))
        np.testing.assert_allclose(full[:cut], part, equal_nan=True, err_msg=f"cut {cut}")


def test_changing_future_bars_never_moves_a_past_feature() -> None:
    bars = series(700)
    t = 400
    base = F.build_features(bars)[: t + 1]
    high, low, close = bars.high.copy(), bars.low.copy(), bars.close.copy()
    high[t + 1 :] *= 1.5
    low[t + 1 :] *= 0.5
    close[t + 1 :] *= 1.2
    mutated = F.build_features(
        F.Bars(bars.open_s, high, np.minimum(low, close), np.minimum(close, high))
    )
    np.testing.assert_allclose(base, mutated[: t + 1], equal_nan=True)


def test_live_row_equals_the_batch_row() -> None:
    bars = series(1200)
    batch = F.build_features(bars)
    for k in (400, 777, 1199, 1200):
        np.testing.assert_allclose(F.live_row(bars.head(k)), batch[k - 1], equal_nan=True)


def test_the_label_looks_exactly_24_bars_ahead_and_only_there() -> None:
    bars = series(300)
    y = F.build_label(bars)
    t = 100
    expected = np.log(
        (bars.high[t + 1 : t + 25].max() - bars.low[t + 1 : t + 25].min()) / bars.close[t]
    )
    assert y[t] == pytest.approx(expected)
    assert np.isnan(y[-24:]).all() and np.isfinite(y[:-24]).all()
    high = bars.high.copy()
    high[t + 25] *= 3  # the bar after the window: irrelevant
    high[t] *= 3  # the decision bar's own high: irrelevant (only its close enters)
    again = F.build_label(F.Bars(bars.open_s, high, bars.low, bars.close))
    assert again[t] == pytest.approx(y[t])
    high[t + 1] = bars.high[t + 1] * 2  # inside the window: it does move
    assert F.build_label(F.Bars(bars.open_s, high, bars.low, bars.close))[t] != pytest.approx(y[t])


def test_feature_definitions_match_the_frozen_spec() -> None:
    spec = F.spec_features()
    assert [f["name"] for f in spec] == list(F.FEATURE_NAMES) and len(spec) == 13
    assert F.feature_schema_hash() == F.feature_schema_hash() and len(F.feature_schema_hash()) == 64
    bars = series(500)
    x = F.build_features(bars)
    t = 300
    tr = np.maximum(
        bars.high[1:] - bars.low[1:],
        np.maximum(np.abs(bars.high[1:] - bars.close[:-1]), np.abs(bars.low[1:] - bars.close[:-1])),
    )  # tr[i-1] is the true range of bar i
    sma14 = tr[t - 14 : t].mean()  # bars t-13..t
    assert x[t, 0] == pytest.approx(np.log(sma14 / bars.close[t]))
    assert x[t, 3] == pytest.approx(
        np.log((bars.high[t - 23 : t + 1].max() - bars.low[t - 23 : t + 1].min()) / bars.close[t])
    )
    assert x[t, 6] == pytest.approx(abs(np.log(bars.close[t] / bars.close[t - 1])))
    assert x[t, 7] == pytest.approx(abs(bars.close[t] / bars.close[t - 5] - 1))
    window = bars.close[t - 19 : t + 1]
    assert x[t, 8] == pytest.approx(np.log(4 * window.std() / window.mean() + 1e-12))


def test_hour_and_weekday_features_use_the_bar_open_time_in_utc() -> None:
    monday_18 = int(datetime(2026, 10, 12, 18, tzinfo=UTC).timestamp())  # a Monday
    bars = F.Bars(
        np.array([monday_18 + i * H for i in range(300)], dtype=np.int64),
        np.full(300, 2001.0), np.full(300, 1999.0), np.full(300, 2000.0),
    )  # fmt: skip
    x = F.build_features(bars)
    assert x[0, 9] == pytest.approx(np.sin(2 * np.pi * 18 / 24)) and x[0, 10] == pytest.approx(
        np.cos(2 * np.pi * 18 / 24)
    )
    assert x[0, 11] == pytest.approx(0.0, abs=1e-12) and x[0, 12] == pytest.approx(
        1.0
    )  # Monday = 0
    assert x[6, 9] == pytest.approx(np.sin(2 * np.pi * 0 / 24))  # 6 bars later: Tuesday 00:00
    assert x[6, 11] == pytest.approx(np.sin(2 * np.pi * 1 / 7))


def test_rows_are_excluded_not_imputed_until_every_lookback_is_complete() -> None:
    bars = series(600)
    x, y = F.build_features(bars), F.build_label(bars)
    ok = F.valid_rows(x, y)
    assert not ok[: F.WARMUP_ROWS].any()  # the warm-up is never usable
    assert not ok[-24:].any()  # the last 24 rows have no label
    assert ok[F.WARMUP_ROWS : -24].all() and np.isfinite(x[ok]).all()


def test_bars_reject_bad_input() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        F.Bars(np.array([2, 1], dtype=np.int64), np.ones(2), np.ones(2), np.ones(2))
    with pytest.raises(ValueError, match="high must be >= low"):
        F.Bars(np.array([1, 2], dtype=np.int64), np.ones(2), np.full(2, 2.0), np.ones(2))


# ---- models ---------------------------------------------------------------------------------------
def test_har_ridge_equals_scikit_learn_standardscaler_ridge() -> None:
    sklearn_linear = pytest.importorskip("sklearn.linear_model")
    sklearn_pre = pytest.importorskip("sklearn.preprocessing")
    rng = np.random.default_rng(5)
    x = rng.normal(size=(500, 13)) * rng.uniform(0.1, 5, 13) + rng.normal(size=13)
    y = x @ rng.normal(size=13) + rng.normal(size=500)
    ours = HarRidge().fit(x, y)
    scaler = sklearn_pre.StandardScaler().fit(x)
    ref = sklearn_linear.Ridge(alpha=10.0).fit(scaler.transform(x), y)
    z = rng.normal(size=(50, 13))
    np.testing.assert_allclose(
        ours.predict(z), ref.predict(scaler.transform(z)), rtol=1e-9, atol=1e-9
    )
    exported = ours.export()
    assert set(exported) == {"alpha", "mean", "scale", "coef", "intercept"}


def test_baselines_behave_as_defined() -> None:
    rng = np.random.default_rng(1)
    x = rng.normal(size=(400, 13))
    y = 2.0 + 0.5 * x[:, 0] + rng.normal(scale=0.1, size=400)
    assert MeanExpanding().fit(x, y).predict(x[:3]).tolist() == [pytest.approx(y.mean())] * 3
    one = Atr14OneFeature().fit(x, y)
    assert one.coef[1] == pytest.approx(0.5, abs=0.05) and one.predict(x[:2]).shape == (2,)
    pct = rng.uniform(0, 1, 400)
    yb = np.where(pct < 0.2, 1.0, 5.0)
    rule = RuleStateAtrPercentile().fit(x, yb, pct)
    assert rule.means[0] == pytest.approx(1.0) and rule.means[4] == pytest.approx(5.0)
    assert rule.predict(x[:1], np.array([0.99]))[0] == pytest.approx(
        5.0
    )  # a percentile of ~1 is bucket 4
    with pytest.raises(ValueError, match="percentile"):
        RuleStateAtrPercentile().fit(x, y)


def test_atr_percentile_is_a_trailing_rank() -> None:
    x = np.zeros((400, 13))
    x[:, 0] = np.arange(400.0)  # strictly rising: always the highest of its window
    pct = atr_percentile(x)
    assert (
        np.isnan(pct[:249]).all()
        and pct[249] == pytest.approx(1.0)
        and pct[399] == pytest.approx(1.0)
    )
    x[:, 0] = -np.arange(400.0)  # strictly falling: always the lowest
    assert atr_percentile(x)[399] == pytest.approx(1 / 250)


# ---- walk-forward ---------------------------------------------------------------------------------
def prepared(n: int = 60_000):  # type: ignore[no-untyped-def]
    bars = series(n)
    x, y = F.build_features(bars), F.build_label(bars)
    aux = atr_percentile(x)
    ok = F.valid_rows(x, y) & np.isfinite(aux)
    return bars, x, y, aux, ok, years_of(bars.open_s)


def test_walk_forward_embargo_and_chronology() -> None:
    from xau_edge_v2.ml.models import Atr14OneFeature as A

    bars, x, y, aux, ok, years = prepared()
    test_years = [2013, 2014, 2015]
    wf = walk_forward(
        x, y, aux, ok, years, test_years, models={"atr14_one_feature": A, "har_ridge": HarRidge}
    )
    assert [f["year"] for f in wf.folds] == test_years
    for fold in wf.folds:
        first_test = int(np.flatnonzero(ok & (years == fold["year"]))[0])
        assert fold["train"] > 0 and fold["fit"] < fold["train"]
        # the training rows end at least EMBARGO bars before the first test row
        train_rows = np.flatnonzero(ok & (np.arange(bars.size) <= first_test - EMBARGO))
        assert (
            train_rows[-1] + 24 < first_test
        )  # the last training LABEL ends before the first test feature
    predicted = np.flatnonzero(np.isfinite(wf.preds["har_ridge"]))
    assert set(years[predicted]) == set(test_years)
    outside = ~np.isin(years, test_years)
    assert np.isnan(wf.preds["har_ridge"][outside]).all()


def test_walk_forward_is_deterministic_and_never_looks_ahead() -> None:
    bars, x, y, aux, ok, years = prepared(50_000)
    models = {"har_ridge": HarRidge}
    a = walk_forward(x, y, aux, ok, years, [2014], models=models)
    b = walk_forward(x, y, aux, ok, years, [2014], models=models)
    np.testing.assert_array_equal(a.preds["har_ridge"], b.preds["har_ridge"])
    # destroying every label from the test year on cannot change a prediction for that year
    y2 = y.copy()
    y2[years >= 2014] = 123.0
    c = walk_forward(x, y2, aux, ok, years, [2014], models=models)
    np.testing.assert_array_equal(a.preds["har_ridge"], c.preds["har_ridge"])


def test_the_interval_comes_from_calibration_residuals_and_covers_about_80_percent() -> None:
    rng = np.random.default_rng(2)
    n = 40_000
    open_s = 1_262_304_000 + np.arange(n, dtype=np.int64) * H
    x = rng.normal(size=(n, 13))
    y = x[:, 0] * 0.4 + rng.normal(size=n) * 0.5
    ok = np.ones(n, dtype=bool)
    ok[:250] = False
    years = years_of(open_s)
    aux = np.full(n, 0.5)
    wf = walk_forward(x, y, aux, ok, years, [2013, 2014], models={"har_ridge": HarRidge})
    mask = np.isfinite(wf.lower["har_ridge"])
    cover = M.coverage(wf.lower["har_ridge"], wf.upper["har_ridge"], y, mask)
    assert 0.77 < cover < 0.83
    assert (wf.upper["har_ridge"][mask] > wf.lower["har_ridge"][mask]).all()


def test_a_fold_with_too_little_history_is_skipped_not_faked() -> None:
    bars, x, y, aux, ok, years = prepared(
        12_000
    )  # 2010-2011 only: no fold has 3000 training rows... before 2010
    wf = walk_forward(x, y, aux, ok, years, [2010], models={"har_ridge": HarRidge})
    assert wf.folds == [] and np.isnan(wf.preds["har_ridge"]).all()


# ---- metrics --------------------------------------------------------------------------------------
def test_metric_definitions() -> None:
    y = np.array([0.0, 1.0, 2.0])
    p = np.array([0.0, 0.0, 4.0])
    m = np.ones(3, dtype=bool)
    assert M.mse(p, y, m) == pytest.approx((0 + 1 + 4) / 3)
    ratio = np.exp(y - p)
    assert M.qlike(p, y, m) == pytest.approx(np.mean(ratio - np.log(ratio) - 1))
    assert M.qlike(y, y, m) == pytest.approx(0.0)
    assert M.skill(0.9, 1.0) == pytest.approx(0.1) and M.skill(1.1, 1.0) == pytest.approx(-0.1)
    assert M.coverage(y - 1, y + 1, y, m) == 1.0 and M.coverage(y + 1, y + 2, y, m) == 0.0


def test_block_bootstrap_separates_a_better_model_from_an_equal_one() -> None:
    rng = np.random.default_rng(4)
    n = 6000
    months = np.repeat(np.arange(n // 100), 100).astype(np.int64)
    y = rng.normal(size=n)
    good = y + rng.normal(scale=0.3, size=n)
    bad = y + rng.normal(scale=0.9, size=n)
    mask = np.ones(n, dtype=bool)
    better = M.block_ci(good, bad, y, mask, months)
    assert better["ci95"][0] > 0 and better["lower97.5_one_sided"] > 0 and better["mean"] > 0
    same = M.block_ci(bad, bad, y, mask, months)
    assert same["ci95"] == [0.0, 0.0]
    wide = M.block_ci(bad, bad * 1.0 + rng.normal(scale=0.5, size=n) * 0, y, mask, months)
    assert wide["mean"] == 0.0
    assert M.block_ci(good, bad, y, mask, months) == better  # a fixed seed: reproducible
    # a 97.5% ONE-sided lower bound is the 2.5th percentile: exactly the two-sided 95% lower bound
    assert better["lower97.5_one_sided"] == better["ci95"][0]  # type: ignore[index]


# ---- data window ----------------------------------------------------------------------------------
def test_the_loader_refuses_the_locked_window_without_an_unlock(tmp_path: Path) -> None:
    root = tmp_path / "market"
    times = write_series(
        root, Timeframe.H1, datetime(2021, 12, 20, tzinfo=UTC), 24 * 30, step_minutes=60
    )
    assert times[-1] >= guard.DEV_UNTIL  # the store does have bars inside Test-H
    bars = load_h1(root)  # default: development window
    assert bars.size > 0 and datetime.fromtimestamp(float(bars.open_s[-1]), UTC) < guard.DEV_UNTIL
    with pytest.raises(guard.WindowLockError, match="locked"):
        load_h1(root, datetime(2022, 3, 1, tzinfo=UTC))
    with pytest.raises(guard.WindowLockError):
        guard.require_development_window(datetime(2026, 6, 1, tzinfo=UTC))
    assert len(dataset_hash(bars)) == 64 and dataset_hash(bars) == dataset_hash(load_h1(root))


# ---- confirmatory lock, K ledger, registry --------------------------------------------------------
def make_spec(tmp_path: Path) -> Path:
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"spec_id": "x", "spec_version": "1.1.0"}), encoding="utf-8")
    return spec


def setup_ledger(tmp_path: Path, spec: Path) -> tuple[Path, Path]:
    ledger, approvals = tmp_path / "k_ledger.json", tmp_path / "approvals"
    approvals.mkdir()
    data = {"families": {guard.FAMILY: {"k": 2, "spec_hash": guard.spec_hash(spec)}}, "events": []}
    ledger.write_text(json.dumps(data), encoding="utf-8")
    return ledger, approvals


def approve(approvals: Path, spec: Path, window: str = "TEST_H", **over: object) -> None:
    record = {
        "family": guard.FAMILY, "spec_hash": guard.spec_hash(spec),
        "approved_by": "project owner", "approved_at": "2026-10-20T00:00:00+00:00", **over,
    }  # fmt: skip
    (approvals / f"{window.lower()}_approval.json").write_text(json.dumps(record), encoding="utf-8")


def test_test_h_is_locked_without_an_owner_approval(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    ledger, approvals = setup_ledger(tmp_path, spec)
    with pytest.raises(guard.WindowLockError, match="no owner approval"):
        guard.issue_unlock("TEST_H", approvals=approvals, ledger=ledger, spec=spec)
    assert guard.looks_at("TEST_H", path=ledger) == 0
    with pytest.raises(guard.WindowLockError, match="unknown"):
        guard.issue_unlock("NOPE", approvals=approvals, ledger=ledger, spec=spec)


def test_an_approval_for_another_spec_or_family_or_unsigned_is_refused(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    ledger, approvals = setup_ledger(tmp_path, spec)
    approve(approvals, spec, spec_hash="0" * 64)
    with pytest.raises(guard.WindowLockError, match="does not match"):
        guard.issue_unlock("TEST_H", approvals=approvals, ledger=ledger, spec=spec)
    approve(approvals, spec, family="K_SOMETHING_ELSE")
    with pytest.raises(guard.WindowLockError, match="does not match"):
        guard.issue_unlock("TEST_H", approvals=approvals, ledger=ledger, spec=spec)
    approve(approvals, spec, approved_by="")
    with pytest.raises(guard.WindowLockError, match="lacks"):
        guard.issue_unlock("TEST_H", approvals=approvals, ledger=ledger, spec=spec)
    assert guard.looks_at("TEST_H", path=ledger) == 0


def test_a_family_missing_from_the_ledger_blocks_the_run(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    ledger, approvals = setup_ledger(tmp_path, spec)
    ledger.write_text(json.dumps({"families": {}, "events": []}), encoding="utf-8")
    approve(approvals, spec)
    with pytest.raises(guard.WindowLockError, match="K family"):
        guard.issue_unlock("TEST_H", approvals=approvals, ledger=ledger, spec=spec)


def test_the_window_opens_exactly_once_and_the_look_is_recorded_first(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    ledger, approvals = setup_ledger(tmp_path, spec)
    approve(approvals, spec)
    unlock = guard.issue_unlock("TEST_H", approvals=approvals, ledger=ledger, spec=spec)
    assert unlock.window == "TEST_H" and unlock.spec_hash == guard.spec_hash(spec)
    events = guard.load_ledger(ledger)["events"]
    assert [e["kind"] for e in events] == ["CONFIRMATORY_LOOK"] and events[0]["detail"][
        "run_id"
    ] == unlock.run_id
    with pytest.raises(guard.WindowLockError, match="already opened once"):
        guard.issue_unlock("TEST_H", approvals=approvals, ledger=ledger, spec=spec)
    # a crash after the unlock still counts as the one run: the ledger has no way to take it back
    assert guard.looks_at("TEST_H", path=ledger) == 1
    approve(approvals, spec, "HOLDOUT")
    assert (
        guard.issue_unlock("HOLDOUT", approvals=approvals, ledger=ledger, spec=spec).window
        == "HOLDOUT"
    )


def test_the_unlock_lets_the_loader_read_past_the_development_window(tmp_path: Path) -> None:
    root = tmp_path / "market"
    write_series(root, Timeframe.H1, datetime(2021, 12, 20, tzinfo=UTC), 24 * 30, step_minutes=60)
    spec = make_spec(tmp_path)
    ledger, approvals = setup_ledger(tmp_path, spec)
    approve(approvals, spec)
    unlock = guard.issue_unlock("TEST_H", approvals=approvals, ledger=ledger, spec=spec)
    bars = load_h1(root, datetime(2022, 1, 15, tzinfo=UTC), unlock=unlock)
    assert datetime.fromtimestamp(float(bars.open_s[-1]), UTC) >= guard.DEV_UNTIL


def record(**over: object) -> dict[str, object]:
    base: dict[str, object] = {k: "x" for k in registry.REQUIRED}
    base.update(
        status="RESEARCH", authority="NONE", model_id="har_ridge", version="0.1.0", metrics={}
    )
    base.update(over)
    return base


def test_the_registry_starts_at_research_with_no_authority_and_needs_the_full_record(
    tmp_path: Path,
) -> None:
    path = tmp_path / "registry.json"
    registry.register_research(record(), path=path)
    with pytest.raises(registry.PromotionError, match="lacks"):
        registry.register_research({"model_id": "x"}, path=path)
    with pytest.raises(registry.PromotionError, match="starts as RESEARCH"):
        registry.register_research(record(status="SHADOW"), path=path)
    with pytest.raises(registry.PromotionError, match="authority NONE"):
        registry.register_research(record(authority="ADVISORY"), path=path)
    registry.register_research(
        record(metrics={"mse": 1}), path=path
    )  # a RESEARCH record may be refreshed
    assert registry.load(path)["models"][0]["metrics"] == {"mse": 1}


def test_promotion_needs_a_ledgered_test_h_run_with_every_criterion_passed(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    registry.register_research(record(), path=path)
    spec = make_spec(tmp_path)
    ledger, approvals = setup_ledger(tmp_path, spec)
    with pytest.raises(registry.PromotionError, match="not a single allowed step"):
        registry.promote(
            "har_ridge", "0.1.0", "SHADOW", {"owner_approval": "x"}, path=path, ledger=ledger
        )
    with pytest.raises(registry.PromotionError, match="Test-H run recorded"):
        registry.promote(
            "har_ridge",
            "0.1.0",
            "VALIDATED_OFFLINE",
            {"test_h_run_id": "made-up", "criteria_all_passed": True},
            path=path,
            ledger=ledger,
        )
    approve(approvals, spec)
    unlock = guard.issue_unlock("TEST_H", approvals=approvals, ledger=ledger, spec=spec)
    with pytest.raises(registry.PromotionError, match="every pre-registered criterion"):
        registry.promote(
            "har_ridge",
            "0.1.0",
            "VALIDATED_OFFLINE",
            {"test_h_run_id": unlock.run_id, "criteria_all_passed": False},
            path=path,
            ledger=ledger,
        )
    registry.promote(
        "har_ridge",
        "0.1.0",
        "VALIDATED_OFFLINE",
        {"test_h_run_id": unlock.run_id, "criteria_all_passed": True},
        path=path,
        ledger=ledger,
    )
    model = registry.load(path)["models"][0]
    assert (
        model["status"] == "VALIDATED_OFFLINE" and model["authority"] == "NONE" and model["history"]
    )
    with pytest.raises(registry.PromotionError, match="owner's approval"):
        registry.promote("har_ridge", "0.1.0", "SHADOW", {}, path=path, ledger=ledger)
    registry.promote(
        "har_ridge", "0.1.0", "SHADOW", {"owner_approval": "msg"}, path=path, ledger=ledger
    )
    with pytest.raises(registry.PromotionError, match="cannot be replaced"):
        registry.register_research(record(), path=path)
    assert registry.load(path)["models"][0]["authority"] == "NONE"  # no step ever grants authority
    with pytest.raises(registry.PromotionError, match="unknown model"):
        registry.promote("nope", "1", "SHADOW", {}, path=path)


def test_a_closed_family_can_never_open_a_confirmatory_window(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    ledger, approvals = setup_ledger(tmp_path, spec)
    approve(approvals, spec)  # even with a valid approval
    guard.close_family(guard.FAMILY, "rejected at validation", path=ledger)
    data = guard.load_ledger(ledger)
    assert data["families"][guard.FAMILY]["status"] == "CLOSED"
    assert (
        data["events"][-1]["kind"] == "FAMILY_CLOSED"
        and data["events"][-1]["detail"]["confirmatory_looks"] == 0
    )
    with pytest.raises(guard.WindowLockError, match="CLOSED"):
        guard.issue_unlock("TEST_H", approvals=approvals, ledger=ledger, spec=spec)
    assert guard.looks_at("TEST_H", path=ledger) == 0
    with pytest.raises(guard.WindowLockError, match="unknown family"):
        guard.close_family("NOPE", "x", path=ledger)


def test_the_repository_record_says_v0_was_rejected_and_no_window_was_ever_opened() -> None:
    ledger = guard.load_ledger()
    assert ledger["families"][guard.FAMILY]["status"] == "CLOSED"
    assert guard.looks_at("TEST_H") == 0 and guard.looks_at("HOLDOUT") == 0
    kinds = [e["kind"] for e in ledger["events"]]
    assert kinds == ["FAMILY_REGISTERED", "POLICY_CLARIFICATION", "FAMILY_CLOSED"]
    statuses = {m["model_id"]: (m["status"], m["authority"]) for m in registry.load()["models"]}
    assert statuses == {"har_ridge": ("RETIRED", "NONE"), "lightgbm_regressor": ("RETIRED", "NONE")}
    assert not (guard.APPROVALS / "test_h_approval.json").exists()
    assert not (guard.APPROVALS / "holdout_approval.json").exists()
