from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from tests.unit.research_v2.helpers import frame, hand_bars, random_walk
from xau_edge.research_v2.barrier import Outcomes, compute_outcomes
from xau_edge.research_v2.events import (
    EventSet,
    h4_trend,
    prior_day_levels,
    sweep_events,
    volatility_events,
)
from xau_edge.research_v2.frame import H1Frame, build_frame, uncertified_years
from xau_edge.research_v2.study import day_block_ci, holm, one_sided_p, screen, study_variant

# ATR after the 2.0-range warm-up is 2.0, so a = 2: target +4, stop -2 from the entry open.


def outcomes_for(
    rows: Sequence[tuple[float, float, float, float]],
) -> tuple[H1Frame, Outcomes, Outcomes]:
    f = frame(hand_bars(rows))
    longs, shorts = compute_outcomes(f)
    return f, longs, shorts


def test_target_is_two_r_and_net_is_below_gross() -> None:
    # decision bar 20 (the first hand row); entry at the open of bar 21; target 2000+4
    f, longs, _ = outcomes_for(
        [(2000, 2001, 1999, 2000), (2000, 2005, 1999.5, 2004), (2004, 2005, 2003, 2004)]
    )
    d = 20
    assert longs.valid[d]
    assert longs.gross_mid[d] == pytest.approx(2.0)
    assert longs.label[d] == 1
    assert longs.net_base[d] < longs.gross_mid[d]
    assert longs.net_pess[d] < longs.net_base[d]
    assert f.atr[d] == pytest.approx(2.0)


def test_stop_is_minus_one_r() -> None:
    _, longs, _ = outcomes_for(
        [(2000, 2001, 1999, 2000), (2000, 2000.5, 1997.5, 1998), (1998, 1999, 1997, 1998)]
    )
    assert longs.gross_mid[20] == pytest.approx(-1.0)
    assert longs.label[20] == -1


def test_both_barriers_in_one_bar_is_a_stop_and_is_ambiguous() -> None:
    _, longs, _ = outcomes_for(
        [(2000, 2001, 1999, 2000), (2000, 2006, 1996, 2000), (2000, 2001, 1999, 2000)]
    )
    assert longs.ambiguous[20]
    assert longs.gross_mid[20] == pytest.approx(-1.0)
    assert longs.optimistic_gross[20] == pytest.approx(2.0)


def test_a_gap_through_the_stop_fills_at_the_open_not_the_stop() -> None:
    _, longs, _ = outcomes_for(
        [
            (2000, 2001, 1999, 2000),
            (2000, 2000.5, 1999.5, 2000),
            (1995, 1996, 1994, 1995),  # opens 5 below entry: stop (1998) is gapped through
            (1995, 1996, 1994, 1995),
        ]
    )
    assert longs.gross_mid[20] == pytest.approx(-2.5)


def test_the_short_side_mirrors_the_long_side() -> None:
    _, longs, shorts = outcomes_for(
        [(2000, 2001, 1999, 2000), (2000, 2005, 1999.5, 2004), (2004, 2005, 2003, 2004)]
    )
    assert shorts.gross_mid[20] == pytest.approx(-1.0)
    assert longs.gross_mid[20] > 0 > shorts.gross_mid[20]


def test_timeout_exits_at_the_close_of_the_last_bar() -> None:
    rows = [(2000, 2001, 1999, 2000)] + [(2000, 2001, 1999, 2000.5)] * 30
    _, longs, _ = outcomes_for(rows)
    assert longs.label[20] == 0
    assert longs.bars_held[20] == 24
    assert longs.gross_mid[20] == pytest.approx(0.25)


def test_the_last_bar_has_no_entry() -> None:
    _, longs, _ = outcomes_for([(2000, 2001, 1999, 2000)])
    assert not longs.valid[20]


# -- events --------------------------------------------------------------------------------


def test_prior_day_levels_use_only_completed_days() -> None:
    f = frame(random_walk(weeks=3, seed=3))
    hi, lo, _ = prior_day_levels(f)
    keys = np.unique(f.day)
    first_day = f.day == keys[0]
    assert np.isnan(hi[first_day]).all()
    second = np.flatnonzero(f.day == keys[1])
    first = np.flatnonzero(first_day)
    assert hi[second[0]] == pytest.approx(f.h[first].max())
    assert lo[second[0]] == pytest.approx(f.low[first].min())


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
@pytest.mark.parametrize(
    ("level_set", "mode"), [("PD", "reject"), ("PD", "accept"), ("ASIA", "reject")]
)
def test_sweep_events_are_prefix_stable(seed: int, level_set: str, mode: str) -> None:
    """Truncating the future cannot change events decided before the cut (no repaint)."""
    df = random_walk(weeks=8, seed=seed, vol=3.0)
    full = sweep_events(frame(df), level_set, mode, 0.25)
    cut = df.height * 2 // 3
    head = sweep_events(frame(df.head(cut)), level_set, mode, 0.25)
    expected = [
        (int(d), int(s)) for d, s in zip(full.decision, full.direction, strict=True) if d < cut
    ]
    got = [(int(d), int(s)) for d, s in zip(head.decision, head.direction, strict=True)]
    assert got == expected


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_future_garbage_cannot_change_past_events(seed: int) -> None:
    df = random_walk(weeks=8, seed=seed, vol=3.0)
    cut = df.height * 2 // 3
    rng = np.random.default_rng(99)
    junk = df.with_columns(
        [
            pl.when(pl.int_range(pl.len()) >= cut)
            .then(pl.col(c) + rng.normal(0, 50))
            .otherwise(pl.col(c))
            .alias(c)
            for c in ("open", "close")
        ]
    ).with_columns(
        [
            pl.when(pl.int_range(pl.len()) >= cut)
            .then(pl.col("high") + 80)
            .otherwise(pl.col("high"))
            .alias("high"),
            pl.when(pl.int_range(pl.len()) >= cut)
            .then(pl.col("low") - 80)
            .otherwise(pl.col("low"))
            .alias("low"),
        ]
    )
    a = sweep_events(frame(df), "PD", "reject", 0.0)
    b = sweep_events(frame(junk), "PD", "reject", 0.0)

    def before(e: EventSet) -> list[tuple[int, int]]:
        pairs = zip(e.decision, e.direction, strict=True)
        return [(int(d), int(x)) for d, x in pairs if d < cut - 3]

    assert before(a) == before(b)


def test_one_event_per_level_per_day() -> None:
    f = frame(random_walk(weeks=10, seed=5, vol=4.0))
    ev = sweep_events(f, "PD", "reject", 0.0)
    seen = set()
    for d, name in zip(ev.decision, ev.level, strict=True):
        key = (name, int(f.day[d]))
        assert key not in seen
        seen.add(key)
    assert ev.n > 0
    assert set(ev.direction.tolist()) <= {-1, 1}


def test_clock_unsafe_days_are_excluded_not_shifted() -> None:
    df = random_walk(year=2016, weeks=40, seed=2, vol=4.0)
    safe = sweep_events(build_frame(df, set()), "PD", "reject", 0.0)
    unsafe = sweep_events(build_frame(df, {2016}), "PD", "reject", 0.0)
    assert unsafe.n < safe.n
    assert unsafe.excluded_unsafe > 0
    assert set(map(int, unsafe.decision)) <= set(map(int, safe.decision))


def test_uncertified_years_without_a_certificate_means_every_year(tmp_path: Path) -> None:
    assert 2023 in uncertified_years(tmp_path / "missing.json")
    cert = tmp_path / "c.json"
    cert.write_text('{"years": {"2022": {"certified": true}, "2014": {"certified": false}}}')
    assert uncertified_years(cert) == {2014}


def test_h4_trend_uses_only_closed_h4_bars() -> None:
    df = random_walk(weeks=6, seed=6)
    f = frame(df)
    h4 = (
        df.group_by_dynamic("timestamp", every="4h")
        .agg(
            pl.col("close").last(),
            pl.col("high").max(),
            pl.col("low").min(),
            pl.col("open").first(),
        )
        .sort("timestamp")
    )
    t1 = h4_trend(f, h4, 5)
    cut = h4.height // 2
    t2 = h4_trend(
        f, h4.head(cut).vstack(h4.tail(h4.height - cut).with_columns(pl.col("close") + 500)), 5
    )
    boundary = int(h4["timestamp"][cut].timestamp() * 1_000_000) if False else None
    del boundary
    stamp = h4["timestamp"].dt.epoch("us").to_numpy()[cut]
    early = f.t + 3_600_000_000 < stamp  # decisions that close before H4 bar `cut` is even open
    assert np.array_equal(t1[early], t2[early])


def test_volatility_events_one_per_day_and_trend_sided() -> None:
    df = random_walk(weeks=30, seed=7, vol=2.0)
    f = frame(df)
    h4 = (
        df.group_by_dynamic("timestamp", every="4h")
        .agg(
            pl.col("close").last(),
            pl.col("high").max(),
            pl.col("low").min(),
            pl.col("open").first(),
        )
        .sort("timestamp")
    )
    ev = volatility_events(f, h4, 0.95, 20)
    days = [int(f.day[d]) for d in ev.decision]
    assert len(days) == len(set(days))
    assert set(ev.direction.tolist()) <= {-1, 1}


# -- study ---------------------------------------------------------------------------------


def test_day_block_ci_brackets_the_mean_and_is_deterministic() -> None:
    rng = np.random.default_rng(0)
    values = rng.normal(0.1, 1.0, 600)
    days = np.repeat(np.arange(200), 3)
    a = day_block_ci(values, days, resamples=400)
    assert a == day_block_ci(values, days, resamples=400)
    assert a[0] < values.mean() < a[1]


def test_holm_rejects_in_order_and_stops_at_the_first_failure() -> None:
    p = {"a": 0.001, "b": 0.02, "c": 0.06, "d": 0.5}
    assert holm(p, 0.10) == {"a": True, "b": True, "c": False, "d": False}
    assert not any(holm({"a": 0.2, "b": 0.3}, 0.10).values())


def test_a_planted_edge_is_a_stage_one_survivor_and_noise_is_not() -> None:
    rng = np.random.default_rng(1)
    days = np.repeat(np.arange(300), 2)
    noise = rng.normal(0, 1.0, 600)
    edge = rng.normal(0.35, 1.0, 600)
    assert one_sided_p(edge, days) < 0.001
    assert one_sided_p(noise, days) > 0.01


def test_study_variant_produces_a_complete_summary_on_synthetic_data() -> None:
    df = random_walk(weeks=60, seed=11, vol=3.0)
    f = frame(df)
    longs, shorts = compute_outcomes(f)
    ev = sweep_events(f, "PD", "reject", 0.0)
    assert ev.n >= 30
    study = study_variant(f, ev, longs, shorts, k=24, placebo_draws=100, resamples=300)
    s = study.summary
    for key in (
        "ci95_net_base",
        "dependence",
        "power",
        "era",
        "intrabar",
        "attribution",
        "placebo",
    ):
        assert key in s
    assert s["evidence_class"] == "SCREENING"
    assert s["mean_gross_mid_r"] > s["mean_net_base_r"] > s["mean_net_pess_r"]
    assert s["power"]["k"] == 24
    out = screen([study])
    assert set(out[study.name]) == {
        "holm_family_alpha",
        "holm_rejects_null",
        "pessimistic_mean_positive",
        "stage1_survivor",
    }
