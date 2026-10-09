"""Stage 1 event study: per-variant statistics, Holm screening, attribution, placebo, dependence.

Unit = event. Overlapping outcomes are handled by day-block resampling (blocks of one trading
day). Stage 1 is SCREENING: it can reject a mechanism early and cannot confer evidence (roadmap 12).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Any

import numpy as np
from numpy.typing import NDArray

from xau_edge.integrity.attribution import attribute
from xau_edge.integrity.dependence import dependence_report, dependence_sensitivity
from xau_edge.integrity.intrabar import intrabar_report
from xau_edge.integrity.placebo import run_placebo
from xau_edge.integrity.power2 import cluster_t_stat, power_report
from xau_edge.integrity.structure_breaks import era_report
from xau_edge.research_v2.barrier import Outcomes
from xau_edge.research_v2.events import EventSet
from xau_edge.research_v2.frame import H1Frame

SEED = 7
N_RESAMPLES = 20_000
HOLM_FAMILY_ALPHA = 0.10
MIN_CLUSTERS_FOR_P = 30
_NORMAL = NormalDist()
CLOCK_ERA_BOUNDARY_YEAR = 2021


def day_block_ci(
    values: NDArray[np.float64],
    days: NDArray[np.int64],
    *,
    resamples: int = N_RESAMPLES,
    seed: int = SEED,
    chunk: int = 1000,
) -> tuple[float, float]:
    """95% percentile interval of the mean, resampling whole trading days."""
    _, inverse = np.unique(days, return_inverse=True)
    n_days = int(inverse.max()) + 1
    sums = np.bincount(inverse, weights=values, minlength=n_days)
    counts = np.bincount(inverse, minlength=n_days).astype(np.float64)
    rng = np.random.default_rng(seed)
    means = np.empty(resamples)
    for start in range(0, resamples, chunk):
        size = min(chunk, resamples - start)
        pick = rng.integers(0, n_days, size=(size, n_days))
        means[start : start + size] = sums[pick].sum(axis=1) / counts[pick].sum(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


def one_sided_p(values: NDArray[np.float64], days: NDArray[np.int64]) -> float:
    """p-value of mean > 0 from the day-cluster robust t (normal approximation)."""
    if len(np.unique(days)) < MIN_CLUSTERS_FOR_P:
        return 1.0  # too few independent days for a normal approximation: never a rejection
    t = cluster_t_stat(values, days)
    return float(1 - _NORMAL.cdf(t))


def holm(p_values: dict[str, float], family_alpha: float) -> dict[str, bool]:
    """Holm-Bonferroni step-down: which hypotheses are rejected at the family-wise level."""
    order = sorted(p_values, key=lambda k: p_values[k])
    m = len(order)
    rejected = dict.fromkeys(order, False)
    for rank, name in enumerate(order):
        if p_values[name] <= family_alpha / (m - rank):
            rejected[name] = True
        else:
            break
    return rejected


@dataclass(frozen=True)
class VariantStudy:
    """Everything Stage 1 learned about one variant (JSON-ready in ``summary``)."""

    name: str
    n_events: int
    p_value: float
    mean_net_base: float
    mean_net_pess: float
    summary: dict[str, Any]


def _clean(value: float | None) -> float | None:
    return None if value is None or not math.isfinite(value) else float(value)


def study_variant(
    f: H1Frame,
    events: EventSet,
    longs: Outcomes,
    shorts: Outcomes,
    *,
    k: int,
    sd_assumed: float = 1.3,
    placebo_draws: int = 1000,
    resamples: int = N_RESAMPLES,
) -> VariantStudy:
    """Statistics of one variant on the frame's analysis window."""
    keep = [
        i
        for i, (d, s) in enumerate(zip(events.decision, events.direction, strict=True))
        if (longs if s > 0 else shorts).valid[d]
    ]
    d = events.decision[keep]
    s = events.direction[keep]
    out = {
        "gross": np.where(s > 0, longs.gross_mid[d], shorts.gross_mid[d]),
        "base": np.where(s > 0, longs.net_base[d], shorts.net_base[d]),
        "pess": np.where(s > 0, longs.net_pess[d], shorts.net_pess[d]),
        "opt": np.where(s > 0, longs.optimistic_gross[d], shorts.optimistic_gross[d]),
        "amb": np.where(s > 0, longs.ambiguous[d], shorts.ambiguous[d]),
        "label": np.where(s > 0, longs.label[d], shorts.label[d]),
        "mfe": np.where(s > 0, longs.mfe[d], shorts.mfe[d]),
        "mae": np.where(s > 0, longs.mae[d], shorts.mae[d]),
    }
    n = int(d.size)
    summary: dict[str, Any] = {
        "name": events.name,
        "n_events_raw": events.n,
        "n_events": n,
        "dropped_without_outcome": events.n - n,
        "excluded_clock_unsafe": events.excluded_unsafe,
        "evidence_class": "SCREENING",
    }
    if n < 30:
        summary["status"] = "TOO_FEW_EVENTS"
        return VariantStudy(events.name, n, 1.0, float("nan"), float("nan"), summary)
    days = f.day[d + 1]
    years = f.year[d]
    base, pess, gross = out["base"], out["pess"], out["gross"]
    lo, hi = day_block_ci(base, days, resamples=resamples)
    dep = dependence_report(base, days)
    sens = dependence_sensitivity(base, days, seed=SEED, include_stationary=False)
    power = power_report(raw_n=n, effective_n=dep.effective_n, k=k, sd=sd_assumed)
    p_value = one_sided_p(base, days)
    eras = era_report(base, ["pre-2021" if y < CLOCK_ERA_BOUNDARY_YEAR else "2021+" for y in years])
    summary |= {
        "mean_gross_mid_r": float(gross.mean()),
        "mean_net_base_r": float(base.mean()),
        "mean_net_pess_r": float(pess.mean()),
        "ci95_net_base": [lo, hi],
        "p_value_one_sided": p_value,
        "hit_target": float(np.mean(out["label"] == 1)),
        "hit_stop": float(np.mean(out["label"] == -1)),
        "timeout": float(np.mean(out["label"] == 0)),
        "mean_mfe_r": float(np.nanmean(out["mfe"])),
        "mean_mae_r": float(np.nanmean(out["mae"])),
        "by_year": {
            int(y): {
                "n": int((years == y).sum()),
                "mean_net_base_r": float(base[years == y].mean()),
            }
            for y in np.unique(years)
        },
        "dependence": {
            "raw_n": dep.raw_n,
            "unique_days": dep.unique_days,
            "unique_weeks": dep.unique_weeks,
            "effective_n": dep.effective_n,
            "icc": dep.icc,
            "lag1_autocorr": dep.lag1_autocorr,
            "sensitivity": sens.status,
            "ci_lower_by_block": {k_: v[0] for k_, v in sens.by_block.items()},
        },
        "power": {
            "k": k,
            "mde_raw": power.mde_raw,
            "mde_effective": power.mde_effective,
            "adequately_powered": power.adequately_powered,
            "required_effective_n": power.required_effective_n_for_target,
        },
        "era": {
            "status": eras.status,
            "reason": eras.reason,
            "eras": [e.__dict__ for e in eras.eras],
        },
        "intrabar": intrabar_report(
            np.minimum(out["gross"], out["opt"]), out["opt"], out["amb"].astype(bool)
        ).__dict__,
    }
    summary["attribution"] = _attribution(f, events, longs, shorts, keep, days, summary)
    summary["placebo"] = _placebo(f, longs, shorts, d, base, placebo_draws)
    return VariantStudy(events.name, n, p_value, float(base.mean()), float(pess.mean()), summary)


def _attribution(  # noqa: PLR0917
    f: H1Frame,
    events: EventSet,
    longs: Outcomes,
    shorts: Outcomes,
    keep: list[int],
    days: NDArray[np.int64],
    summary: dict[str, Any],
) -> dict[str, Any]:
    d = events.decision[keep]
    s = events.direction[keep].astype(np.float64)
    hours = np.unique(f.utc_hour[d])
    pool_mask = np.isin(f.utc_hour, hours) & longs.valid & shorts.valid & ~f.unsafe_day
    pool = (longs.net_base[pool_mask] + shorts.net_base[pool_mask]) / 2
    att = attribute(
        long_r=longs.net_base[d],
        short_r=shorts.net_base[d],
        direction=s,
        day_ids=days,
        matched_pool_mean_r=float(pool.mean()) if pool.size else None,
    )
    summary["attribution_pool_n"] = int(pool.size)
    return {
        "observed_mean_r": att.observed_mean_r,
        "direction_edge": att.direction_edge,
        "timing_edge": att.timing_edge,
        "drift_exposure": att.drift_exposure,
        "counterfactuals": [c.__dict__ for c in att.counterfactuals],
        "note": att.note,
    }


def _placebo(  # noqa: PLR0917
    f: H1Frame,
    longs: Outcomes,
    shorts: Outcomes,
    d: NDArray[np.int64],
    base: NDArray[np.float64],
    draws: int,
) -> dict[str, Any]:
    hours = np.unique(f.utc_hour[d])
    mask = np.isin(f.utc_hour, hours) & longs.valid & shorts.valid & ~f.unsafe_day
    pool_idx = np.flatnonzero(mask)
    if pool_idx.size < d.size * 2:
        return {"status": "POOL_TOO_SMALL"}
    ln, sn = longs.net_base[pool_idx], shorts.net_base[pool_idx]

    def draw(rng: np.random.Generator) -> float:
        pick = rng.choice(pool_idx.size, size=d.size, replace=False)
        sign = rng.integers(0, 2, size=d.size)
        return float(np.where(sign == 1, ln[pick], sn[pick]).mean())

    res = run_placebo(float(base.mean()), draw, n=draws, seed=SEED)
    return {
        "kind": "same-hour random timestamps, random direction",
        "real": res.real,
        "median": res.median,
        "p95": res.p95,
        "p99": res.p99,
        "empirical_percentile": res.empirical_percentile,
        "draws": res.n_placebo,
        "seed": res.seed,
    }


def screen(
    studies: list[VariantStudy],
    family_alpha: float = HOLM_FAMILY_ALPHA,
    family_size: int | None = None,
) -> dict[str, dict[str, Any]]:
    """Holm screening over the DECLARED family plus the pessimistic-cost condition.

    A variant with too few events counts as p = 1 inside the family, so it still occupies a slot:
    the family size is the number of declared variants, not the number that happened to qualify.
    """
    p = {s.name: (s.p_value if s.n_events >= 30 else 1.0) for s in studies}
    for i in range(max(0, (family_size or 0) - len(p))):
        p[f"__undeclared_slot_{i}"] = 1.0
    rejected = holm(p, family_alpha) if p else {}
    out: dict[str, dict[str, Any]] = {}
    for s in studies:
        holm_ok = rejected.get(s.name, False)
        pess_ok = math.isfinite(s.mean_net_pess) and s.mean_net_pess > 0
        out[s.name] = {
            "holm_family_alpha": family_alpha,
            "holm_rejects_null": holm_ok,
            "pessimistic_mean_positive": pess_ok,
            "stage1_survivor": bool(holm_ok and pess_ok),
        }
    return out
