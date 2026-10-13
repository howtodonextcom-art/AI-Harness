"""Deterministic, restartable replay of the candidate lifecycle (Gate B2 decision on F6).

The lifecycle memory of C1 keeps the planned stop FIXED at the bar the setup formed. A run is therefore a
function of the whole sequence of bars since the start of the run, not of the last few. Two consequences:

* a run is ONE continuous replay over the run window (no month boundary resets anything);
* a restart must resume from a persisted checkpoint and then produce exactly what the continuous run would.
  If the checkpoint cannot be restored (missing, corrupt, other spec / data / code, other bar history) the
  engine starts COLD: C1 decisions are WAIT until the setup has been off for ``memory_bars + 1`` bars, after
  which the state equals the continuous run's again. It never acts on a state that may differ.

A checkpoint carries the spec hash, the code version, the clean-store manifest hash, the variants, the bar
index, the last bar and a hash chain over every bar processed so far, and a hash of itself.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from xau_edge_v2.core.candidate import (
    CAND_VERSION,
    CandidateConfig,
    Memory,
    Observation,
    StepInfo,
    candidate_step,
)
from xau_edge_v2.core.decision import Decision, DecisionContext
from xau_edge_v2.core.market_state import MarketState

SCHEMA = 1
GENESIS = hashlib.sha256(b"xau-edge-v2 candidate replay").hexdigest()


def chain(digest: str, open_us: int) -> str:
    return hashlib.sha256(
        bytes.fromhex(digest) + int(open_us).to_bytes(8, "big", signed=True)
    ).hexdigest()


def digest_of(opens: Sequence[int] | np.ndarray) -> str:
    d = GENESIS
    for t in opens:
        d = chain(d, int(t))
    return d


@dataclass(frozen=True)
class Checkpoint:
    spec_sha256: str
    code_version: str
    store_manifest_sha256: str
    variants: tuple[str, ...]
    bar_index: int
    last_bar_open_us: int
    bars_digest: str
    origin_us: int
    """The first bar this lineage of the engine processed (the run start, or the bar of a cold start)."""
    memories: dict[str, dict[str, Any]]

    def payload(self) -> dict[str, Any]:
        d = asdict(self)
        d["variants"] = list(self.variants)
        d["schema"] = SCHEMA
        return d


def _seal(payload: dict[str, Any]) -> dict[str, Any]:
    body = {k: v for k, v in payload.items() if k != "payload_sha256"}
    text = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return {**body, "payload_sha256": hashlib.sha256(text.encode()).hexdigest()}


def save_checkpoint(path: Path, cp: Checkpoint) -> None:
    """Atomic write: temp file, fsync, replace; the previous checkpoint is kept as ``<name>.prev``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    data = json.dumps(_seal(cp.payload()), sort_keys=True, indent=1)
    with tmp.open("w", encoding="utf-8") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    if path.exists():
        os.replace(path, path.with_suffix(path.suffix + ".prev"))
    os.replace(tmp, path)


def load_checkpoint(path: Path) -> tuple[Checkpoint | None, str]:
    """(checkpoint, reason). ``None`` with the reason when it cannot be trusted."""
    if not path.exists():
        return None, "no checkpoint"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if _seal(raw)["payload_sha256"] != raw.get("payload_sha256"):
            return None, "checkpoint hash mismatch (corrupted)"
        if raw.get("schema") != SCHEMA:
            return None, f"unknown checkpoint schema {raw.get('schema')}"
        return (
            Checkpoint(
                spec_sha256=raw["spec_sha256"],
                code_version=raw["code_version"],
                store_manifest_sha256=raw["store_manifest_sha256"],
                variants=tuple(raw["variants"]),
                bar_index=int(raw["bar_index"]),
                last_bar_open_us=int(raw["last_bar_open_us"]),
                bars_digest=raw["bars_digest"],
                origin_us=int(raw["origin_us"]),
                memories={k: dict(v) for k, v in raw["memories"].items()},
            ),
            "ok",
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return None, f"unreadable checkpoint: {exc}"


def _mem_dict(m: Memory) -> dict[str, Any]:
    return asdict(m)


class Replay:
    """The lifecycle of every variant over one continuous run."""

    def __init__(
        self,
        variants: Mapping[str, CandidateConfig],
        *,
        spec_sha256: str,
        store_manifest_sha256: str,
    ) -> None:
        self.variants = dict(variants)
        self.spec_sha256 = spec_sha256
        self.store_manifest_sha256 = store_manifest_sha256
        self.memories: dict[str, Memory] = {v: Memory() for v in self.variants}
        self.bar_index = 0
        self.last_bar_open_us = -1
        self.digest = GENESIS
        self.origin_us = -1
        self.status = "FRESH"

    # ---- start / restart -------------------------------------------------------------------
    @classmethod
    def restore(
        cls,
        path: Path,
        variants: Mapping[str, CandidateConfig],
        *,
        spec_sha256: str,
        store_manifest_sha256: str,
        run_opens: np.ndarray,
    ) -> Replay:
        """Resume from ``path`` when it is trustworthy, else start COLD at the first unprocessed bar.

        ``run_opens`` are the open times of ALL bars of the run in order; the checkpoint must agree with
        that very history (hash chain), else the restart cannot be proven equal to a continuous run.
        """
        eng = cls(variants, spec_sha256=spec_sha256, store_manifest_sha256=store_manifest_sha256)
        cp, why = load_checkpoint(path)
        reason = why
        if cp is not None:
            idx = int(np.searchsorted(run_opens, cp.last_bar_open_us))
            idx0 = int(np.searchsorted(run_opens, cp.origin_us))
            if cp.spec_sha256 != spec_sha256:
                reason = "checkpoint written under another spec"
            elif cp.code_version != CAND_VERSION:
                reason = "checkpoint written by another code version"
            elif cp.store_manifest_sha256 != store_manifest_sha256:
                reason = "checkpoint written on another data store"
            elif cp.variants != tuple(sorted(variants)):
                reason = "checkpoint holds other variants"
            elif (
                idx >= len(run_opens)
                or int(run_opens[idx]) != cp.last_bar_open_us
                or idx0 >= len(run_opens)
                or int(run_opens[idx0]) != cp.origin_us
                or cp.bar_index != idx - idx0 + 1
            ):
                reason = "checkpoint bar is not in this run's history"
            elif digest_of(run_opens[idx0 : idx + 1]) != cp.bars_digest:
                reason = "checkpoint bar history differs from this run's"
            else:
                eng.memories = {v: Memory(**cp.memories[v]) for v in variants}
                eng.bar_index = cp.bar_index
                eng.last_bar_open_us = cp.last_bar_open_us
                eng.digest = cp.bars_digest
                eng.origin_us = cp.origin_us
                eng.status = "RESTORED"
                return eng
        # cold: bars already processed are unknown to this engine; continue the index from the data
        eng.status = f"COLD: {reason}"
        eng.memories = {v: Memory.cold_start() for v in variants}
        return eng

    def resume_index(self, run_opens: np.ndarray) -> int:
        """Index in ``run_opens`` of the first bar this engine has not processed."""
        return (
            0
            if self.last_bar_open_us < 0
            else int(np.searchsorted(run_opens, self.last_bar_open_us, side="right"))
        )

    # ---- stepping --------------------------------------------------------------------------
    def _advance(self, open_us: int) -> None:
        if self.origin_us < 0:
            self.origin_us = int(open_us)
        self.bar_index += 1
        self.last_bar_open_us = int(open_us)
        self.digest = chain(self.digest, int(open_us))

    def skip(self, open_us: int) -> None:
        """A bar without usable data: the lifecycle is cleared (as in a continuous run), the bar still counts."""
        self.memories = {
            v: (Memory.cold_start() if m.cold else Memory()) for v, m in self.memories.items()
        }
        self._advance(open_us)

    def step(
        self, open_us: int, state: MarketState, ctx: DecisionContext, obs: Observation
    ) -> dict[str, tuple[Decision, StepInfo]]:
        out: dict[str, tuple[Decision, StepInfo]] = {}
        for name, cfg in self.variants.items():
            d, self.memories[name], info = candidate_step(
                self.memories[name], state, ctx, cfg, obs, self.bar_index
            )
            out[name] = (d, info)
        self._advance(open_us)
        return out

    # ---- persistence -----------------------------------------------------------------------
    def checkpoint(self) -> Checkpoint:
        return Checkpoint(
            spec_sha256=self.spec_sha256,
            code_version=CAND_VERSION,
            store_manifest_sha256=self.store_manifest_sha256,
            variants=tuple(sorted(self.variants)),
            bar_index=self.bar_index,
            last_bar_open_us=self.last_bar_open_us,
            bars_digest=self.digest,
            origin_us=self.origin_us,
            memories={v: _mem_dict(self.memories[v]) for v in sorted(self.variants)},
        )
