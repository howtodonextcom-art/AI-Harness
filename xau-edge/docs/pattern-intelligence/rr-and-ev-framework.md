# Net R:R, break-even and expected value: the decision framework

Status: **design only**. Implemented in `src/xau_edge/decision_research/` with tests; **not connected** to the TradeEngine, TradingSignal, PaperDesk, any adapter or the UI. Nothing here activates a strategy.

## Rule 1: R:R is payoff geometry, not probability

* A 1:1 payoff does **not** mean 50%. A 2:1 payoff does **not** mean 66%. R:R says what win probability is *required* to break even; it never says what the probability *is*.
* Break-even win rate = 1 / (1 + R). Before costs: 1:1 needs 50%, 2:1 needs 33.3%, 3:1 needs 25%.
* Costs raise the requirement. The framework always uses **net** R:R: `net_rr = (reward - costs) / (risk + costs)` with costs = spread + slippage + commission + swap, in price units, the same convention as `trading/levels.py`. Example from the tests: a gross 2.0R with 0.5 spread, 0.2 slippage and 0.1 commission on a 1.0 risk is below 2.0 net; the gate uses the net figure.
* 1:1 is not "gambling" by itself: it needs a higher win probability to overcome costs. It is refused by default because no validated probability exists, not because of the ratio.

## Rule 2: minimum net R:R = 2.0, as a gate and not a promise

A candidate is entry-eligible only if net R:R is at least 2.0 (`Thresholds.min_net_rr` default). Below it the answer is WAIT with the reason "Net R:R hiện 1.4R, dưới ngưỡng 2R". **2R is necessary, not sufficient**: the other gates (data trusted, no blocker, pattern confirmed, room to target, preregistered thresholds, a publishable probability, probability above break-even plus margins, positive expected value) must all pass.

## What the shapes themselves offer (descriptive, at the moment of detection)

Gross R:R of the textbook levels on Development-2 H1 (entry at the trigger close, stop at the invalidation level, target at the measured move or EPA): double top/bottom median **0.72** (0 of 287 reach 1.5); head and shoulders median 1.46 (29% reach 1.5); Wolfe median 3.6 (90% reach 1.5, because the stop sits at the extreme). So the textbook double top fails the 2.0 gate by construction, and the Wolfe picture passes only by assuming an entry near an extreme that is unknowable in advance. This says nothing about what price does afterwards.

## Rule 3: 1R / 2R / 3R, educationally

| Net payoff | Break-even win rate (before costs) | Reading |
|---|---|---|
| 1R | 50% | needs the highest hit rate; costs matter most |
| 2R | 33.3% | lower hit rate needed, target is twice as far |
| 3R | 25% | lower still, but the target is harder to reach and may not fit the available room |

None is optimal without evidence. A lower win rate with a larger payoff can have the same or better expected value; that is why the UI must show net R:R, the break-even rate, an evidence-based probability and expected value together, never a single "confidence" number.

## Rule 4: structure-room gate

Even with a theoretical 2R, the setup is refused if the opposing structure leaves less free distance than the reward needs (`room_to_target < gross_reward`), or if the room is unknown. Unknown room is not free room.

## Rule 5: entry authorization state machine (`authorization.authorize`)

```
no pattern / possible / developing / near confirmation / invalidated  -> WAIT (the stage is the reason)
confirmed or actionable
  -> levels coherent?              no -> WAIT
  -> net R:R >= 2.0 ?              no -> WAIT "Net R:R hiện x, dưới ngưỡng 2R"
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
| Planned TP: defined before entry; a mechanical planning target | allowed as a plan only; a TP that cannot reach 2R with credible room means WAIT |
| Dynamic exit | UNVALIDATED, disabled |
| Emergency exit (risk/ops rule) | existing guards; unchanged |
| Partial take profit | **DISABLED** (changes the payoff distribution; needs separate outcome research) |
| Break-even move, trailing stop | **UNVALIDATED / DISABLED** |
| Time exit | a valid exit type only if preregistered with the horizon of the probability |

Valid future exits: TP, SL, a time exit, a formal invalidation, an emergency risk guard, a manual close. A vague "price looks weak" is not an exit.

## What is not here

No probability model, no calibration fit, no feature engineering, no ML, no outcome data was read. Model complexity order if a future programme is ever authorised: rule-based conditional statistics, then a Bayesian model, then calibrated logistic regression, then trees, and complex ML only if necessary.
