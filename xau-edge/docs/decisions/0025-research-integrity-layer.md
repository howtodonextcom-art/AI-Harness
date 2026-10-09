# ADR-0025: Research integrity layer

Status: accepted (2026-10-09). Extends ADR-0024 (research console) and ADR-0014 (evaluation protocol).
Benchmark: `docs/research/platform-benchmark.md`.

**Decision.** Add a pure, dependency-light package `xau_edge.integrity` and an Edge Program V2 runner
(`xau_edge.research_v2`) so that "we found evidence" can be told apart from "we found a convincing
backtest":

* **Evidence classes** (`DESCRIPTIVE .. EXECUTION`) and one function, `can_display(label, proof)`, that
  decides whether a label such as VALIDATED or CONFIRMATORY PASS may be shown. A missing proof (CI, K,
  effective N, dataset hashes, freeze record, verified hash chain, broker evidence) refuses the label
  with a reason.
* **Experiment identity and manifest**: canonical JSON hash of (programme, hypothesis, variant,
  config hash, dataset hashes, feature/label/cost versions, code commit, runner version, evidence
  class); immutable run manifest whose file name is its content hash. No incomplete identity is valid.
* **Prospective ledger**: append-only, hash-chained, with ordering rules (sealed before the earliest
  possible resolution, no outcome data in a signal, no time inversion, no duplicates). The UI may say
  SEALED BEFORE OUTCOME only when `verify` returns VALID.
* **Dependence-aware statistics**: effective N (cluster and serial design effects), 1/2/5-day block and
  stationary bootstrap sensitivity (DEPENDENCE_SENSITIVE), power engine V2 with planted-edge
  simulation, forward readiness from effective N, calendar exposure and regime coverage (the number 100
  survives only as a labelled legacy reference).
* **Diagnostics that cannot confer evidence**: placebo engine, edge attribution (timing, direction,
  drift), intrabar ambiguity (INTRABAR_SENSITIVE), era and structural-break report (ERA_DEPENDENT),
  empirical cost distributions with tail EV, robustness-gate calibration by planted strategies,
  Deflated Sharpe, PBO and a Reality Check, and a hash-chained research degrees-of-freedom ledger.
* **Causal event state machine** (BREACH, PENDING, ACCEPTED, REJECTED, UNRESOLVED) with
  `information_available_at <= decision_time < earliest_entry_time`, plus truncation and
  future-garbage property tests (Hypothesis).
* **Research-to-live parity**: a streaming detector for H07/H08 equal to the batch detector bar for
  bar; a mismatch is a blocker. A deterministic replay digest fingerprints a decision sequence.
* **Source-of-truth contract** (`docs/architecture/research-source-of-truth.md`): each UI field has
  one authoritative artefact and one parser; a field without provenance is a defect.

**Governance.** Batch A (H07-H10) was pre-registered in Markdown and a machine-readable sidecar, with
four variants dropped by the pre-declared underpowered-by-design rule (K = 20), and committed before
any outcome was computed. The runner refuses a dirty tree, an uncommitted or invalid registration and
any window other than Development-2. Test-H and the holdout cannot be reached from it.

**Rejected.** MLflow, DVC, Qlib, LEAN, NautilusTrader and W&B as dependencies (ideas adopted, software
not); pickle artefacts; a tracking server; any browser-triggered experiment.

**Consequences.** More files to keep consistent (tests pin the registration to the runner's variant
list). Stage 1 results are permanent records, including failures. A negative result is a valid outcome.
