# ADR-0014: Outcome conventions, baselines and the evaluation protocol

Status: accepted (2026-10-08)

**Outcomes (`xau_edge.outcomes`).** Everything is measured from the CLOSE of the anchor bar over the
next `h` bars and normalised by the anchor's ATR (comparable across volatility regimes). Direction
is UP when the move is >= +0.5 ATR, DOWN when <= -0.5 ATR, else NEUTRAL (inclusive boundaries,
configurable). Barrier trades use a stop of 1.5 ATR and a target of 3.0 ATR (R = 2); if one bar
reaches both, the stop is assumed first. Unresolved trades are marked to market at the horizon.
Results are gross: spread, commission, slippage and swap belong to the backtest (Sprint 8).

**Baselines (`xau_edge.strategies`).** They emit signals only (direction, ATR, exit distances,
maximum hold); fills, costs and exits are the backtest's job. Parameters are fixed a priori and not
tuned on the evaluation periods:

* A: H1 structure trend, M15 RSI(14) pullback (<= 45 long, >= 55 short), M5 BOS/CHoCH in the
  trend direction, cooldown 12 M5 bars.
* B: EMA 9 > 20 > 50 stack (mirrored for short) with RSI(14) in 50-70 (30-50 short), first bar only.
* C: analogue direction (k = 20, window 30) when `p_up - p_down` >= 0.2 with at least 15 analogues.

**Cross-timeframe rule.** A slower timeframe is attached to a faster one only through
`align_to`: the latest slower bar whose `available_at` is not after the faster bar's
`available_at`. Joining on open timestamps would leak the unfinished slower bar.

**Evaluation protocol.** Periods, the analogue-study pass rule, edge criteria and the checkpoint
rule were written to `docs/evals/edge-criteria.md` before any result. The test period is behind an
explicit flag. Every run goes to the experiment registry, whose variant count feeds the
multiple-testing adjustment. The statistic reported for the analogue study has two parts, total and
timing, because gold drifts and a constant lean would otherwise look like skill.

**Consequences.** A negative result (see the Sprint 7 report) is a normal, recorded outcome, and
post-hoc ideas born from a failed run (for example "fade the analogues") count as new variants and
must clear the same bars on data they were not found on.
