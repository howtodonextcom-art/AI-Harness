# ADR-0024: Research console (read-only views plus one down-only write)

Status: accepted (2026-10-09). Adds to ADR-0023 (local web control plane); implements the web slices
of `docs/PROFITABILITY_ROADMAP.md` (section 24.3 allows web work only if it serves the research).

**Decision.**

* New GET-only routes `/research/*` and `/lifecycle/*` (`api/research.py`) read files that already
  exist: the ledger, the experiment result files, the data manifest, the logs of the bot, the
  configuration. They go through `ResearchRoot`, which allows only fixed folders and never `.env*`,
  databases, keys or the control token, rejects `..`, absolute and backslash paths, symlinks that
  leave the repository and files above 4 MB. Answers carry no absolute path.
* **Fail closed.** A missing or corrupt source is `status: "unknown"` ("KHÔNG RÕ"), never an implicit
  OK. Locks (Test-H, holdout) read "NGUYÊN VẸN" only when the experiment registry was read
  completely and shows no use. Robustness gates that never ran read "CHƯA CHẠY".
* **The console runs nothing.** No route and no button runs a backtest, an event study, Test-H or the
  holdout, enables funded trading or sends an order. Experiments are run by CLI code that records
  every run in the ledger (K) and checks the freeze record.
* **One write, down only.** `POST /control/lifecycle/demote` (under the ADR-0023 guard: token, Host,
  Origin, JSON, Idempotency-Key, rate limit) moves a strategy to WATCH, DEGRADED or DISABLED, needs
  the typed word `DEMOTE` and a reason, only from PAPER, DEMO, VALIDATED, FUNDED, WATCH or DEGRADED,
  and only to a lower state. It cannot promote, cannot touch REJECTED, RESEARCH or RETIRED strategies
  and cannot create one. Events go to the append-only `data/execution/lifecycle.jsonl` and to the
  execution journal (`source=web`). The route table test lists this route explicitly.
* Edge-decay thresholds are fixed in `configs/research/decay.yaml`; the console only suggests a state.

**Not decided here.** Experiment execution from the browser, promotion from the browser, editing the
ledger or the funded rules from the browser: all refused by design.
