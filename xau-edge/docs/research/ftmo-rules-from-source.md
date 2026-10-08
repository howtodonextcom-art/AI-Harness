# FTMO rules as encoded in `Z:\Coding\2600629-FTMO` (ChallengeReady), read 2026-10-08

Written for the project owner. **These are the rules according to another project's source code,
not FTMO's current official terms.** ChallengeReady is an independent educational simulator ("not
affiliated with FTMO"); its authors fetched ftmo.com pages in July and September 2026 and encoded
what they found. Treat everything below as a well-sourced secondary reading. Re-verify against
ftmo.com before relying on it, especially anything marked "unverified".

Read-only review. No code was run, nothing in that folder was changed, and no `.env*` file or log
was opened (the folder holds `.env.local`, `.env.example` and `firestore-debug.log`; none were read).

## 1. Summary

1. For the **2-Step** challenge the source gives a precise, internally consistent loss model, and it
   matches our `configs/prop/ftmo_2step.yaml` on every number: 5% daily, 10% static maximum loss,
   targets 10% and 5%, 4 trading days, unlimited time, all measured on **equity**.
2. The source proves two subtleties our bot only approximates: the daily floor is measured from the
   **balance at 00:00 Prague time** (not from when the bot first looked), and **equality with the
   floor counts as a breach**.
3. On **bots and EAs the source gives no permission and no prohibition.** It lists "EA / Automated
   Trading" as content-only and unverified. The only related facts are a paraphrase of FTMO's
   forbidden practices (below), which constrain a bot but do not ban one.
4. I found **four gaps in XAU EDGE** against these rules (section 5), one of them real: the
   day-start balance.
5. The question "may a bot trade an FTMO account?" is **not answerable from this source**. The
   official terms must be checked (section 6).

## 2. Source map

| Path | What it holds | Used |
|---|---|---|
| `src/domain/rules/ruleRegistry.ts` | the 7 executable 2-Step rules with value, formula, excerpt | yes |
| `src/domain/rules/ruleSources.ts`, `ruleConfidenceGate.ts`, `ruleTypes.ts` | provenance, verification gate | yes |
| `src/domain/risk/formulas.ts`, `rollover.ts`, `tradingDays.ts` | the formulas | yes |
| `src/domain/prep/ruleScenarios.ts`, `eligibility.ts` | worked examples; eligibility self-check | skimmed |
| `specs/03_RULE_ENGINE_SPEC.md` (1853 lines), `04_RISK_ENGINE_SPEC.md` | rule and risk specification, content-only rules | read the relevant sections |
| `docs/release/OFFICIAL_GUIDE_FACTS_V55.md` | live-fetched facts: forbidden practices, reward, refund, KYC | yes |
| `docs/orchestration/CANONICAL_DECISIONS.md` | resolved conventions (signed swap, equality) | skimmed |
| `docs/release/MT4_MT5_INTEGRATION_SPIKE.md`, constitution 13.3 | why broker/EA integration is out of scope there | yes |
| `CLAUDE.md` (745 KB), `prompts/`, `reports/`, `e2e*`, `functions/`, `firestore.rules`, UI pages | agent notes, product work | searched for rule keywords: nothing relevant |
| `.env*`, `firestore-debug.log`, `node_modules`, `dist`, PDFs in `refer/` | secrets, build output, trading primers | **not read** |

## 3. Rules table (2-Step Challenge, "FTMO-style")

Confidence: **High** = the source cites an exact quote from the official page and re-fetched it twice.

| Rule | Value | How it is measured | Source | Confidence |
|---|---|---|---|---|
| Maximum Daily Loss | 5% of initial capital (a fixed amount) | floor = balance at previous midnight CE(S)T minus 5% of initial; breached when **equity** is at or below it; equity = balance + open P/L ± swaps − commissions | `ruleRegistry.ts:78-92`, `formulas.ts:105-135`, spec 04 section 10 | High |
| Maximum Loss | 10% of initial capital | **static** floor = initial − 10%; breached when equity is at or below it | `ruleRegistry.ts:94-108`, `formulas.ts:149-170` | High (official quote in `ruleRegistry.ts:15-20`) |
| Profit Target, Challenge | +10% | balance reaches initial × 1.10 | `ruleRegistry.ts:110-122` | High |
| Profit Target, Verification | +5% | balance reaches initial × 1.05 | `ruleRegistry.ts:124-136` | High |
| Open-position requirement | 0 open positions | the target counts only when balance is at target **and** all positions are closed; floating profit never counts | `ruleRegistry.ts:167-181`, spec 03 section 10.16 | High |
| Minimum Trading Days | 4 per phase, not consecutive | a trading day is a unique Europe/Prague calendar date on which a trade was **opened**; holding across days adds nothing | `ruleRegistry.ts:138-151`, `tradingDays.ts:1-27` | High |
| Time limit | unlimited | never fail on elapsed time | `ruleRegistry.ts:153-165` | High |
| Daily reset | 00:00 Europe/Prague (CET/CEST, DST aware) | | `ruleRegistry.ts:40-43`, `rollover.ts` | High |
| Boundary | equality **is** a breach | `equity <= floor` | `formulas.ts:185`, `CANONICAL_DECISIONS.md:361` | High (a design decision of the source, consistent with "cannot drop below") |
| Fail order | daily loss, then max loss, then target/days | a phase cannot pass after an earlier breach | spec 03 section 12.3 | Medium (the source's own design) |
| 1-Step | 3% daily in our config; trailing 10% on highest end-of-day balance; Best Day rule | the source does **not** implement it: Best Day and 1-Step min days are "needs screenshot / secondary evidence" | spec 03 sections 11.1-11.2, 18.2 | Low in the source |
| Funded account | consistency rule | `CONFLICTED_SOURCE / ASK_SUPPORT`, explicitly not implemented | spec 03 section 11.3 | Low |
| Reward | 80% of profit (90% with Scaling or Premium); request from day 14 after the first trade; all positions and pending orders closed; review 1-2 business days | | `OFFICIAL_GUIDE_FACTS_V55.md` | Medium (fetched live, paraphrased) |
| Entry fee | may be refunded with the first reward (2-Step); not refunded (1-Step) | | same | Medium |
| Platforms | MT4, MT5, cTrader, TradingView | | same | Medium |

## 4. Trading restrictions the source records (paraphrased, not quoted)

`OFFICIAL_GUIDE_FACTS_V55.md` summarises FTMO's "Forbidden Trading Practices" page
(`https://ftmo.com/en/forbidden-trading-practices/`, fetched 2026-09-28) as ten items. The ten short
quotations were in a fetch log that was **not** saved; only the paraphrase survives:

1. exploiting price errors or latency;
2. opposite positions across accounts;
3. high-speed software, AI or tools that manipulate trading;
4. opening trades around major news;
5. opening trades close to the market close;
6. a hyperactive bot, stated as more than 2,000 requests per day;
7. hedging to get around the daily-loss rule;
8. giving a third party access to the account;
9. trading on someone else's account;
10. unusually large volumes compared with the other trades.

The specification files mark all of these content-only and verified-official in the abstract, but
they do not hold the exact wording, the definition of a "request", or the news window length.

## 5. Contradictions and uncertain points

* **No contradiction** between the 2-Step values in `ruleRegistry.ts`, `formulas.ts`, the specs and
  our `ftmo_2step.yaml`. The source's own check (`OFFICIAL_GUIDE_FACTS_V55.md`) found no conflict.
* The source says its first cited URL (`/en/ftmo-2-step/`) later returned 404 and was replaced by
  `/en/2-step-challenge/`; some documents still carry the old URL (7 mentions). Cosmetic.
* The 1-Step maximum loss is described in a quoted passage as a "different, dynamic daily-recalculated
  limit". Our 1-Step profile models it as trailing on the highest end-of-day balance. These agree in
  spirit; the exact formula is not in the source. Do not use the 1-Step profile for real decisions.
* Where the source is silent: leverage, inactivity limits, swap-free accounts, minimum lot rules,
  the exact news window, the exact definition of a "request", whether a Free Trial follows the same
  objectives. Do not assume anything about them.

## 6. Can a bot or EA trade? (the key question)

**Not answerable from this source.** Specifically:

* The source lists "EA / Automated Trading" among content-only items and gives it no status or value.
* It records, as forbidden, a hyperactive bot (more than 2,000 requests a day) and software that
  manipulates trading at high speed. That wording implies bots are not banned outright but are
  bounded. It is an inference from a paraphrase, not a rule.
* The source deliberately avoids any live-broker or EA integration for its own product.

What must be checked on ftmo.com before enabling order sending, ideally in writing from FTMO support:
automated trading and Expert Advisors in the Challenge, Verification and Funded phases, and on the
Free Trial; the exact meaning of a "request" and how they are counted; the news restriction window
and instruments; how close to the market close a new trade may open; whether AI-assisted decisions
are treated as "AI tools". Until then keep the bot on a plain demo account, as it is today.

## 7. Comparison with XAU EDGE

| Rule | XAU EDGE today | Status | Suggested change |
|---|---|---|---|
| 5% daily, 10% static, 10%/5% targets, 4 days, equity-based | `configs/prop/ftmo_2step.yaml`, `risk/prop_rules.py` | **Matches** | none |
| Daily floor from the balance at 00:00 Prague | `execution/state.py: account_baseline` takes the balance the bot sees on the **first call of the Prague day** | **Gap (real)**: if the bot starts or restarts mid-day after trades, the day-start balance is wrong and the floor is too loose or too tight | rebuild the midnight balance as current balance minus the net result of deals closed since 00:00 Prague, using the deal history the reader already queries; keep the stored value only as a fallback |
| Equality with the floor is a breach | `risk/engine.py:130` uses `equity < floor` | **Minor gap** | use `<=`, and compare the buffer checks the same way |
| Holding a losing position across Prague midnight (the source's rollover warning) | positions can live up to `max_hold_until` (about 5 h) and may cross midnight; no guard | **Gap** | refuse new orders when the position would still be open within the warning window before 00:00 Prague, or close before it |
| Profit target needs all positions closed | not modelled (the bot does not decide "passed") | n/a for orders | document; matters only if a pass detector is added |
| Minimum 4 trading days | not tracked | **Gap (informational)** | count unique Prague dates with an opened trade from the journal; show on the dashboard |
| News around major events | calendar loader exists; no calendar supplied, so all signals WAIT | **Aligned (fail-closed)** | the real FTMO window and instrument list are unverified; do not trade news until verified |
| Orders close to the market close | none | **Gap** | block new orders within a margin of the daily break (16:50 NY) and the weekend close, margin to be set after checking the rule |
| Hyperactive bot, more than 2,000 requests a day | about 10 to 25 terminal calls per 15-minute cycle (under 2,500 a day at most, probably fewer server-side) | **Unknown risk** | count calls per day in the journal, set a hard budget well under 2,000 trading-server requests, and confirm what counts as a request |
| Hedging, opposite positions | one bot position at a time; manual positions stop the bot | **Aligned** | none |
| Abnormal volume | sizing is risk-based and bounded by `demo_max_lots` | **Aligned** | none |
| Rule confidence gate (no pass/fail logic without a verified-official rule) | `verified_on` per profile, `*_restrictions: unverified` | **Partly** | adopt the source's idea: a per-rule status (verified official, secondary, unverified) and refuse to run order sending while an unverified rule is marked "must verify" |

## 8. For you to confirm

1. Whether you want the Prague-midnight baseline and the midnight-rollover and close-of-market guards
   implemented now (I recommend yes; they are fail-safe and small).
2. Who checks the FTMO terms on bots, news and "requests": I cannot, and the answer decides whether the
   demo bot may ever be pointed at a real challenge account.
3. Whether your demo account is a FTMO Free Trial or a plain broker demo, since the source cannot say
   whether the Free Trial follows the same objectives.
