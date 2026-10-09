"""Research degrees-of-freedom ledger and overfitting diagnostics (roadmap section 19).

K counts declared variants; it does not show how the idea was reached. This append-only,
hash-chained ledger records, per new hypothesis, what the researcher already knew and considered,
so adaptive research is visible. The diagnostics (Deflated Sharpe Ratio, Probability of Backtest
Overfitting, a stationary-bootstrap Reality Check) are DIAGNOSTIC and never a pass criterion; each
documents the assumption under which it is meaningful.
"""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path
from statistics import NormalDist

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

from xau_edge.integrity.canonical import canonical_json
from xau_edge.integrity.dependence import stationary_indices
from xau_edge.integrity.prospective import GENESIS, seal

_NORMAL = NormalDist()
_EULER = 0.5772156649015329


class DesignEntry(BaseModel):
    """What was known and considered when a hypothesis was designed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    hypothesis_id: str = Field(min_length=1)
    recorded_at: str
    idea_origin: str = Field(min_length=1)
    previous_experiments_known: list[str]
    datasets_results_already_seen: list[str]
    labels_considered: list[str]
    horizons_considered: list[str]
    filters_considered: list[str]
    parameters_considered: list[str]
    rejected_alternatives: list[str]
    ai_suggestions_consulted: list[str]


class DesignLedger:
    """Append-only hash-chained file of ``DesignEntry`` records."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _lines(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        return [json.loads(ln) for ln in self.path.read_text(encoding="utf-8").splitlines() if ln]

    def verify(self) -> bool:
        """True when every record's hash and chain link hold."""
        previous = GENESIS
        for record in self._lines():
            rest = {k: v for k, v in record.items() if k != "record_hash"}
            if rest.get("previous_record_hash") != previous:
                return False
            if (
                seal({k: v for k, v in rest.items() if k != "previous_record_hash"}, previous)
                != record
            ):
                return False
            previous = str(record["record_hash"])
        return True

    def append(self, entry: DesignEntry) -> dict[str, object]:
        """Add one entry. A hypothesis id may be recorded once; the chain must verify first."""
        if not self.verify():
            msg = "the design ledger does not verify; refusing to append"
            raise ValueError(msg)
        records = self._lines()
        if any(r.get("hypothesis_id") == entry.hypothesis_id for r in records):
            msg = f"{entry.hypothesis_id} is already recorded (the ledger is append-only)"
            raise ValueError(msg)
        head = str(records[-1]["record_hash"]) if records else GENESIS
        record = seal(entry.model_dump(mode="json"), head)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(record) + "\n")
        return record

    def entries(self) -> list[DesignEntry]:
        """All entries (without chain fields)."""
        keep = DesignEntry.model_fields
        return [DesignEntry(**{k: v for k, v in r.items() if k in keep}) for r in self._lines()]


# -- diagnostics ---------------------------------------------------------------------------


def expected_max_sharpe(n_trials: int, var_trial_sharpe: float) -> float:
    """Expected maximum of ``n_trials`` independent standard-normal-scaled Sharpe ratios.

    Assumption (Bailey and Lopez de Prado, 2014): trial Sharpe ratios are roughly normal and
    independent; correlated trials make this an overestimate, so the DSR is then conservative.
    """
    if n_trials < 1 or var_trial_sharpe < 0:
        msg = "n_trials >= 1 and a non-negative variance are required"
        raise ValueError(msg)
    if n_trials == 1:
        return 0.0
    sd = math.sqrt(var_trial_sharpe)
    return sd * (
        (1 - _EULER) * _NORMAL.inv_cdf(1 - 1 / n_trials)
        + _EULER * _NORMAL.inv_cdf(1 - 1 / (n_trials * math.e))
    )


def deflated_sharpe(
    sharpe: float,
    n_obs: int,
    *,
    skew: float,
    kurt: float,
    n_trials: int,
    var_trial_sharpe: float,
) -> float:
    """Probability the true Sharpe beats the best expected from ``n_trials`` luck-only trials.

    ``sharpe`` is per observation, ``kurt`` is non-excess kurtosis. Needs the number of trials the
    researcher really tried; the design ledger exists to make that number honest.
    """
    if n_obs < 3:
        msg = "at least 3 observations are required"
        raise ValueError(msg)
    benchmark = expected_max_sharpe(n_trials, var_trial_sharpe)
    denom = 1 - skew * sharpe + (kurt - 1) / 4 * sharpe**2
    if denom <= 0:
        return float("nan")
    z = (sharpe - benchmark) * math.sqrt(n_obs - 1) / math.sqrt(denom)
    return _NORMAL.cdf(z)


def probability_of_backtest_overfitting(
    returns: NDArray[np.float64], *, partitions: int = 8
) -> float:
    """CSCV estimate: how often the best in-sample trial ranks below median out of sample.

    ``returns`` is (time, trials). Meaningful when the trials are alternatives tried on the SAME
    period; with a single trial it is undefined (returns NaN).
    """
    t, m = returns.shape
    if m < 2 or partitions % 2 or t < partitions * 2:
        return float("nan")
    size = t // partitions
    parts = [returns[i * size : (i + 1) * size] for i in range(partitions)]
    below = 0
    total = 0
    for chosen in itertools.combinations(range(partitions), partitions // 2):
        rest = [i for i in range(partitions) if i not in chosen]
        in_s = np.vstack([parts[i] for i in chosen]).mean(axis=0)
        out_s = np.vstack([parts[i] for i in rest]).mean(axis=0)
        best = int(np.argmax(in_s))
        rank = float(np.mean(out_s <= out_s[best]))
        below += rank < 0.5
        total += 1
    return below / total


def reality_check_pvalue(
    excess: NDArray[np.float64], *, seed: int, draws: int = 1000, mean_block: float = 5.0
) -> float:
    """White's Reality Check p-value: is the best of the strategies better than chance?

    ``excess`` is (time, strategies) of returns above the benchmark (zero for R-multiples).
    Uses a stationary bootstrap; the null is that no strategy has positive mean.
    """
    t, m = excess.shape
    if t < 20 or m < 1:
        return float("nan")
    rng = np.random.default_rng(seed)
    centred = excess - excess.mean(axis=0)
    observed = math.sqrt(t) * float(excess.mean(axis=0).max())
    p = 1.0 / mean_block
    exceed = 0
    for _ in range(draws):
        idx = stationary_indices(rng, t, p)
        stat = math.sqrt(t) * float(centred[idx].mean(axis=0).max())
        exceed += stat >= observed
    return (exceed + 1) / (draws + 1)
