# Checkpoint 1 (after Sprint 9): do the baselines show an edge after costs?

Date: 2026-10-08. Rule: `docs/evals/edge-criteria.md` (fixed before any result). Data: FTMO demo XAUUSD,
M5 execution with measured spread, slippage 3 points assumed, commission 0 (unverified), swap from the
terminal, no news calendar (none available), research limits open (see Sprint 9 report).

## Results (net of costs; criteria apply at alpha = 0.05 / 3 variants)

| Strategy | Period | Trades | Net | Profit factor | Avg R | Max DD | Verdict |
|---|---|---|---|---|---|---|---|
| A: H1 trend + M15 pullback + M5 break | Development | 135 | -8.95% | 0.80 | -0.135 | 12.3% | FAIL |
| | Validation | 63 | -3.16% | 0.85 | -0.099 | 7.0% | FAIL (also < 100 trades) |
| B: EMA stack + RSI | Development | 782 | +1.51% | 1.01 | +0.009 | 20.9% | FAIL |
| | Validation | 395 | -18.85% | 0.84 | -0.104 | 25.9% | FAIL |
| C: analogues only | Development | 799 | -35.25% | 0.81 | -0.105 | 44.1% | FAIL |
| | Validation | 413 | +4.76% | 1.04 | +0.027 | 15.4% | FAIL |

In every run the lower confidence bound of mean R is below zero (best case B Development: -0.105),
profit factor is below 1.2, and the R drawdown is far above 15 R. Test period: **never run, locked.**

## What this does and does not say

* It says: these three pre-specified, simple strategies show no statistically supportable edge on
  17 months of one broker's XAUUSD after realistic costs. The results flip sign between periods
  (B +1.5% then -18.9%; C -35% then +4.8%), the signature of noise, not of a stable effect.
* The pipeline can see an edge when one exists: a planted edge passes all seven criteria and the same
  market without it fails (`tests/statistical/test_pipeline_power.py`). An independent reviewer
  flipped every signal direction, hand-checked trades against raw bars, and compared gross and net:
  no bug explains the failures; costs of about 0.03-0.07 R per trade are applied once.
* It does not say that no edge exists anywhere in XAUUSD, only that none was found by these
  rules, on this sample, with these costs. Baseline A also produces too few trades (299 signals in
  17 months) for criterion 1 to be reachable on Validation.

## Decision (taken under the standing instruction to continue to completion; reversible)

The rule says: record "no statistically justified trade found with these baselines". Done here.
The rule also allows building the remaining components because their correct output in this
situation is **WAIT with reasons**. Therefore:

1. Sprint 10 builds the machine-learning benchmark and calibration with the same pre-registered
   splits and criteria. It is a test of whether anything beats the baselines, not an assumption that
   it will. No model is promoted unless it passes every criterion on Development and Validation.
2. Sprints 11-13 build the signal engine, API/dashboard and paper trading. The signal engine will
   output WAIT unless a calibrated edge estimate survives costs and risk checks; with the current
   evidence that means it will almost always say WAIT, which is the intended behaviour.
3. Nothing is described as profitable. The test period stays locked until a candidate passes both
   earlier periods.

The owner may stop here, or redirect effort (more data, tick data, other instruments, a news
calendar) instead of building more machinery on a null result.
