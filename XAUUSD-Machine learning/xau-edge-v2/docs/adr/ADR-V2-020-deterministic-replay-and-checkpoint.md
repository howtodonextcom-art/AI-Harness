# ADR-V2-020: deterministic replay, checkpoint and cold start of the candidate lifecycle (F6)

Status: accepted by the owner (Gate B2, 2026-10-13), implemented at Gate B3.

## Context
C1 remembers a setup and its planned invalidation stop. The stop is computed where the setup formed, so a run is a function of the whole bar sequence since the start of the run, not of its last few bars. Month-chunked runs (and a restart that replays a few dozen bars) therefore gave different stops for setups armed longer than the replay.

## Decision
1. The planned stop stays FIXED at the bar where the setup formed. It is never refreshed.
2. A run is ONE continuous replay of its window (`research/replay.py`, `scripts/research/cand_replay.py`); month boundaries reset nothing. The month-parallel `cand_signals.py` is not restart-safe and now refuses C1 variants unless `--allow-chunked`.
3. After each month a checkpoint is written atomically (`.prev` kept): spec hash, code version, clean-store manifest hash, variants, bar index, last bar, a hash chain over every bar processed, the memories, and its own hash.
4. A restart restores the checkpoint only when every field and the bar history match. Then it produces exactly what the continuous run produces (tested on synthetic streams with armed runs of 120-160 bars and on real clean months).
5. If the checkpoint cannot be restored (missing, corrupt, other spec/code/data/variants/history) the engine starts COLD: C1 decisions are WAIT (`RESTORE_PENDING`) until the armed condition has been off for `memory_bars + 1` bars; from then on the state equals a continuous run's. Variants without C1 are never affected.
6. A bar without usable data clears the lifecycle (as in a continuous run) but still counts in the index and the hash chain.

## Consequences
Stage A for a window is a single sequential pass (about 90 s per month of M5 on one core, low priority); parallelism across months is given up for correctness. The cold start is deliberately conservative: it may WAIT where a continuous run would act, never the opposite.
