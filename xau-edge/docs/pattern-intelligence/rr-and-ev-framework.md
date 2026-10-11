# Net R:R, break-even and expected value: the decision framework

Status: **design only**. Implemented in `src/xau_edge/decision_research/` with tests; **not connected** to the TradeEngine, TradingSignal, PaperDesk, any adapter or the UI. Nothing here activates a strategy.

## Rule 1: R:R is payoff geometry, not probability

* A 1:1 payoff does **not** mean 50%. A 2:1 payoff does **not** mean 66%. R:R says what win probability is *required* to break even; it never says what the probability *is*.
* Break-even win rate = 1 / (1 + R). Before costs: 1:1 needs 50%, 2:1 needs 33.3%, 3:1 needs 25%.
* Costs raise the requirement. The research framework uses **net** R:R: `net_rr = (reward - costs) / (risk + costs)` with costs = spread + slippage + commission + swap, in price units. All four inputs, their source, and verification status are explicit; an unverified model is a hard WAIT. This convention is research-only and does not imply the baseline prices those same costs.
* 1:1 is not "gambling" by itself: it needs a higher win probability to overcome costs. It is refused by default because no validated probability exists, not because of the ratio.

## Rule 2: current minimum entry-geometry policy = 1.5 net R:R

A research proposal cannot pass geometry below 1.50 net (`Thresholds.min_net_rr` default and minimum allowed). Below it the answer is WAIT, for example: "CHỜ: Net R:R hiện 1.40R, dưới ngưỡng 1.5R." This is an entry-geometry floor, not edge, win probability, profitability, or a sufficient reason to enter. Data trust, blockers, confirmed pattern, causal entry, structural stop and target, verified costs, structure room, risk guard, preregistered thresholds, publishable probability, probability above break-even plus margins, and positive expected value remain separate gates.

## What the shapes themselves offer (descriptive, at the moment of detection)

Updated descriptive geometry on Development-2 H1 (48,470 bars; fixed defaults; actionable-close reference, adversely tick-rounded; no outcomes): 143 double tops had median gross R:R 0.74 (2/143 at least 1.5); 144 double bottoms 0.77 (4/144); 3 head-and-shoulders 1.94 (3/3); 4 inverse H&S 1.23 (1/4); 71 Wolfe 3.64 (64/71). Across all types, opposing confirmed structure blocked 344/365 targets with a one-tick buffer. These are gross reference geometries, not executable fills. No NET R:R distribution or eligible count is claimed: the historical H1 extract has no next-open fill and complete verified all-in cost model.

## Rule 3: payoff geometry and theoretical break-even

| Net payoff geometry | Theoretical break-even before costs | Reading |
|---|---|---|
| 1R | 50% | needs the highest hit rate; costs matter most |
| 1.5R | 40% | current minimum geometry floor; not an optimal threshold |
| 2R | 33.3% | lower hit rate needed, target is twice as far |
| 3R | 25% | lower still, but the target is harder to reach and may not fit the available room |

These theoretical break-even rates are not predicted win probabilities; after costs the break-even rate is higher. None is optimal without evidence. The 1.5 floor controls payoff geometry only and implies neither edge nor profitability.

## Rule 4: structure-room gate

Even with theoretical 1.5R, the setup is refused unless opposing structure leaves at least one tick beyond the rounded reward distance, or if room is unknown. Unknown room is not free room.

## Rule 5: entry authorization state machine (`authorization.authorize`)

```
no pattern / possible / developing / near confirmation / invalidated  -> WAIT (the stage is the reason)
confirmed or actionable
  -> levels coherent?              no -> WAIT
  -> verified costs and tick rounding? no -> WAIT
  -> net R:R >= 1.5 ?              no -> WAIT "Net R:R hiện x, dưới ngưỡng 1.5R"
  -> room to target >= reward ?    no -> WAIT
  -> thresholds preregistered ?    no -> WAIT
  -> publishable probability ?     no -> WAIT (unavailable / insufficient sample / not calibrated / interval too wide)
  -> probability >= break-even + calibration margin + uncertainty margin ? no -> WAIT
  -> EV in R > preregistered threshold ? no -> WAIT
  -> BUY_CANDIDATE or SELL_CANDIDATE
both sides pass -> WAIT (conflict; never a vote)
```

Both sides are always evaluated and reported. SELL has exactly the standards of BUY. WAIT reasons are first-class and in Vietnamese for a human: for example "CHỜ: pattern đã xác nhận nhưng chưa đủ bằng chứng xác suất", "CHỜ: MUA và BÁN cùng đủ điều kiện, không chọn bừa". **Today every call ends in WAIT**: no probability exists and no thresholds are preregistered (tests assert this). `BUY_CANDIDATE` is a research-design output meaning "a future validated programme's gates would be satisfied", not an order or a recommendation.

## Rule 6: expected value

`EV (in R) = p * net_rr - (1 - p)`, with costs already inside `net_rr`; `p` must be a calibrated, out-of-sample probability of the specific trade within a stated horizon (see `probability-contract.md`). The decision requires EV above a preregistered positive threshold, and `p` above the break-even rate plus preregistered calibration and uncertainty margins. Break-even alone is not enough.

## Rule 7: take-profit, exits and trade management

External practice catalogued (not adopted): fixed R multiple; structure target (next level); liquidity target; measured move equal to the pattern height (reels 19, 22, 25); point 6 on the 1-4 line (Wolfe); Fibonacci projections (butterfly); several take-profit levels (reel 10, the only one); trailing; partial close; time exit.

| Item | Status |
|---|---|
| Planned TP: defined before entry; a mechanical planning target | allowed as a plan only; a TP that cannot reach 1.5 net R with credible room means WAIT |
| Dynamic exit | UNVALIDATED, disabled |
| Emergency exit (risk/ops rule) | existing guards; unchanged |
| Partial take profit | **DISABLED** (changes the payoff distribution; needs separate outcome research) |
| Break-even move, trailing stop | **UNVALIDATED / DISABLED** |
| Time exit | a valid exit type only if preregistered with the horizon of the probability |

Valid future exits: TP, SL, a time exit, a formal invalidation, an emergency risk guard, a manual close. A vague "price looks weak" is not an exit.

## What is not here

No probability model, no calibration fit, no feature engineering, no ML, no outcome data was read. Model complexity order if a future programme is ever authorised: rule-based conditional statistics, then a Bayesian model, then calibrated logistic regression, then trees, and complex ML only if necessary.
