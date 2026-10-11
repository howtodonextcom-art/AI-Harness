# Edge Program V3 — preregistration template

Status: **TEMPLATE ONLY**. Do not populate with a speculative strategy. Do not run a V3
hypothesis until K governance stays on the V2 ledger (cap = 24 unless the ledger is
amended) and a new *mechanism* is named. Test-H and Holdout stay untouched.

Copy this file to a dated hypothesis note. Leave unused fields as `TBD`.

## Identity

- Mechanism:
- Hypothesis (one sentence, directional, falsifiable):
- Family / multiple-testing group:
- Author / date:

## Setup

- Symbol / session:
- Entry:
- Exit (SL / TP / time / invalidation):
- Parameters (closed list):
- Cost model:

## Sample and power

- Sample definition:
- Expected trades / power:
- Minimum detectable effect:
- Dev window:
- Val window:
- Test-H (protected — do not run until pre-registered pass on Dev+Val):
- Holdout (protected — last):

## Metrics and gates

- Primary metric:
- Secondary metrics:
- Pass / fail criteria (pre-registered):
- Multiple-testing policy (K from ledger, not from STATE.json):
- Evidence label if pass: still UNVALIDATED until Test-H + holdout protocol completes.

## Must not

- Slice a burned Dev sample until something is green.
- Touch Test-H or Holdout.
- Override `k_cap` from UI / STATE.json.
- Claim VALIDATED from replay or paper fills.
