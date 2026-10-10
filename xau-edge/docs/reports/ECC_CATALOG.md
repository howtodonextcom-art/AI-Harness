# ECC_CATALOG — Danh mục đầy đủ Everything Claude Code và mức áp dụng cho XAU EDGE

Sinh tự động (chỉ đọc) từ `z:\Coding\Projects\AI-Harness\ECC` ngày 2026-10-11 — upstream `affaan-m/ECC` commit `4eb71d92` (VERSION 2.2.3; trước đó `c70874fa`/2.2.2). Mô tả lấy từ frontmatter `description` (cắt 160 ký tự). 🆕 = mục mới so với `c70874fa`.
Cột **Đọc sâu**: ✔ = đã mở và đọc nội dung file; trống = chỉ dựa vào frontmatter. **Trạng thái cài** so với `xau-edge/.claude/`.
Mức áp dụng dựa trên các vấn đề đang mở của XAU EDGE (dữ liệu/chart, guard FTMO, edge chiến lược, test/CI, tài liệu, funded readiness).

Tổng: 590 mục — skill: 302, agent: 71, command: 95, rule: 122.

| Nhóm | Số mục | Cao | Trung bình | Thấp | Không |
|---|---|---|---|---|---|
| 01 Orchestration & gates | 72 | 17 | 12 | 43 | 0 |
| 02 TDD / testing / E2E / eval | 26 | 10 | 9 | 7 | 0 |
| 03 Code review & quality | 42 | 13 | 23 | 6 | 0 |
| 04 Security | 8 | 2 | 4 | 2 | 0 |
| 05 Architecture / API / data / performance | 34 | 5 | 15 | 14 | 0 |
| 06 Frontend / design / UI | 33 | 0 | 26 | 7 | 0 |
| 07 Docs / ADR / knowledge | 16 | 3 | 7 | 6 | 0 |
| 08 DevOps / CI / deploy / git | 14 | 0 | 1 | 13 | 0 |
| 09 Memory / learning / session / context | 29 | 0 | 0 | 29 | 0 |
| 10 ECC meta / harness tooling | 34 | 0 | 1 | 33 | 0 |
| 90 Stack khác (không dùng) | 190 | 0 | 0 | 0 | 190 |
| 91 Business / content / marketing | 39 | 0 | 0 | 0 | 39 |
| 92 Domain khác (không liên quan trading XAU) | 53 | 0 | 0 | 0 | 53 |

## 01 Orchestration & gates

| Tên | Loại | Mô tả (từ file) | Trạng thái cài | Phụ thuộc | Áp dụng XAU EDGE | Đọc sâu |
|---|---|---|---|---|---|---|
| `planner` | agent | Expert planning specialist for complex features and refactoring. Use PROACTIVELY when users request feature implementation, architectural changes, or complex re (`agents/planner.md`) | Đã cài |  | Cao |  |
| `checkpoint` | command | Create, verify, or list workflow checkpoints after running verification checks. (`commands/checkpoint.md`) | Đã cài |  | Cao |  |
| `orch-add-feature` | command | Orchestrate building a brand-new feature end to end — research, plan, TDD, review, gated commit. Wrapper that kicks off the orch-add-feature skill. (`commands/orch-add-feature.md`) | Đã cài |  | Cao |  |
| `orch-change-feature` | command | Orchestrate altering an existing, working feature to new desired behavior — update tests to the new spec, change impl, review, gated commit. Wrapper for the orc (`commands/orch-change-feature.md`) | Đã cài |  | Cao |  |
| `orch-fix-defect` | command | Orchestrate fixing a bug — reproduce it as a failing regression test, fix to green, review, gated commit. Wrapper for the orch-fix-defect skill. (`commands/orch-fix-defect.md`) | Đã cài |  | Cao | ✔ |
| `orch-refine-code` | command | Orchestrate a behavior-preserving refactor — confirm tests green, restructure without changing behavior, keep green, review, gated commit. Wrapper for the orch- (`commands/orch-refine-code.md`) | Đã cài |  | Cao |  |
| `orch-review` | command | Run the orch-review native Workflow over a diff (local changes or a GitHub PR) and report blocking vs advisory findings. Surface for the orch-review workflow. U (`commands/orch-review.md`) | Đã cài |  | Cao |  |
| `plan` | command | Restate requirements, assess risks, and create step-by-step implementation plan. WAIT for user CONFIRM before touching any code. Use for a single-model inline o (`commands/plan.md`) | Đã cài |  | Cao |  |
| `santa-loop` | command | Adversarial dual-review convergence loop — two independent model reviewers must both approve before code ships. Use for the CLI-driven version of this loop; wra (`commands/santa-loop.md`) | Đã cài | 2 model CLI | Cao |  |
| `council` | skill | Convene a four-voice council for ambiguous decisions, tradeoffs, and go/no-go calls. Use when multiple valid paths exist and you need structured disagreement be (`skills/council/SKILL.md`) | Đã cài |  | Cao | ✔ |
| `intent-driven-development` | skill | Turn ambiguous or high-impact product and engineering changes into scoped, verifiable acceptance criteria before or alongside implementation. Use when a user as (`skills/intent-driven-development/SKILL.md`) | Đã cài |  | Cao | ✔ |
| `orch-add-feature` | skill | Orchestrate building a brand-new feature end to end — research, plan, TDD implementation, review, and gated commit — by delegating each phase to the matching EC (`skills/orch-add-feature/SKILL.md`) | Đã cài |  | Cao |  |
| `orch-change-feature` | skill | Orchestrate altering an existing, working feature to new desired behavior — update its tests to the new spec, change the implementation to match, review, and ga (`skills/orch-change-feature/SKILL.md`) | Đã cài |  | Cao |  |
| `orch-fix-defect` | skill | Orchestrate fixing a bug — reproduce it as a failing regression test, fix to green, review, and gated commit — by delegating each phase to the matching ECC agen (`skills/orch-fix-defect/SKILL.md`) | Đã cài |  | Cao | ✔ |
| `orch-pipeline` | skill | Shared orchestration engine behind the orch-* skill family — the gated Research-Plan-TDD-Review-Commit pipeline, size classifier, agent and command map, and two (`skills/orch-pipeline/SKILL.md`) | Đã cài |  | Cao | ✔ |
| `orch-refine-code` | skill | Orchestrate a behavior-preserving refactor — confirm tests are green, restructure without changing behavior, keep tests green, review, and gated commit. Use whe (`skills/orch-refine-code/SKILL.md`) | Đã cài |  | Cao |  |
| `santa-method` | skill | Multi-agent adversarial verification: two independent reviewers with the same rubric must both pass before output ships, with a fix-and-re-review convergence lo (`skills/santa-method/SKILL.md`) | Đã cài |  | Cao | ✔ |
| `feature-dev` | command | Guided feature development with codebase understanding and architecture focus (`commands/feature-dev.md`) | Đã cài |  | Trung bình |  |
| `plan-canvas` | command | Open a plan or HTML artifact in the browser Plan Canvas for annotate-and-approve review. This is a thin slash-command entrypoint over the plan-canvas skill, whi (`commands/plan-canvas.md`) | Đã cài | server local ECC | Trung bình |  |
| `plan-prd` | command | Generate a lean, problem-first PRD and hand off to /plan for implementation planning. (`commands/plan-prd.md`) | Đã cài |  | Trung bình |  |
| `prp-implement` | command | Execute an implementation plan with rigorous validation loops (`commands/prp-implement.md`) | Đã cài |  | Trung bình |  |
| `prp-plan` | command | Create comprehensive feature implementation plan with codebase analysis and pattern extraction (`commands/prp-plan.md`) | Đã cài |  | Trung bình |  |
| `quality-gate` | command | Run the ECC formatter quality gate for a single file and report remediation steps. (`commands/quality-gate.md`) | Đã cài |  | Trung bình |  |
| `blueprint` | skill | Turn a one-line objective into a step-by-step construction plan for multi-session, multi-agent engineering projects: one-PR-sized steps with self-contained cont (`skills/blueprint/SKILL.md`) | Chỉ trong ECC |  | Trung bình |  |
| `loop-design-check` | skill | Design a goal-oriented agent loop or review one for failure modes: spinning, Goodhart-gaming the verifier, or running a wrong answer to completion. Covers machi (`skills/loop-design-check/SKILL.md`) | Đã cài |  | Trung bình |  |
| `plan-canvas` | skill | Open plans and HTML artifacts in a local browser canvas where the human annotates elements, chats, and approves or requests changes without leaving the page. Us (`skills/plan-canvas/SKILL.md`) | Đã cài | server local ECC | Trung bình |  |
| `product-capability` | skill | Translate PRD intent, roadmap asks, or product discussions into an implementation-ready capability plan that exposes constraints, invariants, interfaces, and un (`skills/product-capability/SKILL.md`) | Chỉ Codex tree |  | Trung bình |  |
| `product-lens` | skill | Validate the why before building through four product diagnostics — a YC-style product diagnostic that produces PRODUCT-BRIEF.md with a go/no-go recommendation, (`skills/product-lens/SKILL.md`) | Đã cài |  | Trung bình |  |
| `recursive-decision-ledger` | skill | Run repeated rollouts ("Prime Gauss" style recursive prompting) while keeping an append-only decision ledger of trials, marks, coherence checks, and promotion g (`skills/recursive-decision-ledger/SKILL.md`) | Chỉ trong ECC |  | Trung bình |  |
| `gan-evaluator` | agent | GAN Harness — Evaluator agent. Tests the live running application via Playwright, scores against rubric, and provides actionable feedback to the Generator. (`agents/gan-evaluator.md`) | Đã cài |  | Thấp |  |
| `gan-generator` | agent | GAN Harness — Generator agent. Implements features according to the spec, reads evaluator feedback, and iterates until quality threshold is met. (`agents/gan-generator.md`) | Đã cài |  | Thấp |  |
| `gan-planner` | agent | GAN Harness — Planner agent. Expands a one-line prompt into a full product specification with features, sprints, evaluation criteria, and design direction. (`agents/gan-planner.md`) | Đã cài |  | Thấp |  |
| `loop-operator` | agent | Operate autonomous agent loops, monitor progress, and intervene safely when loops stall. (`agents/loop-operator.md`) | Đã cài |  | Thấp |  |
| `epic-claim` | command | Claim an epic issue, stamp coordination state, and sync local ownership. (`commands/epic-claim.md`) | Đã cài |  | Thấp |  |
| `epic-publish` | command | Publish a validated epic update back to the issue and local cache. (`commands/epic-publish.md`) | Đã cài |  | Thấp |  |
| `epic-review` | command | Mark epic review requested, approved, or changes requested. (`commands/epic-review.md`) | Đã cài |  | Thấp |  |
| `epic-sync` | command | Sync epic issue bodies, labels, and local coordination snapshots from GitHub. (`commands/epic-sync.md`) | Đã cài |  | Thấp |  |
| `epic-unblock` | command | Sweep blocked epic issues and reopen anything whose dependencies are closed. (`commands/epic-unblock.md`) | Đã cài |  | Thấp |  |
| `epic-validate` | command | Validate epic readiness, dependencies, and coordination policy. (`commands/epic-validate.md`) | Đã cài |  | Thấp |  |
| `gan-build` | command | Run a generator/evaluator build loop for implementation tasks with bounded iterations and scoring. (`commands/gan-build.md`) | Đã cài |  | Thấp |  |
| `gan-design` | command | Run a generator/evaluator design loop for frontend or visual work with bounded iterations and scoring. (`commands/gan-design.md`) | Đã cài |  | Thấp |  |
| `loop-start` | command | Prepare a managed autonomous loop pattern with safety defaults and explicit stop conditions, then print the commands to launch and monitor it. Use to set up seq (`commands/loop-start.md`) | Đã cài |  | Thấp |  |
| `loop-status` | command | Inspect active loop state, progress, failure signals, and recommended intervention. (`commands/loop-status.md`) | Đã cài |  | Thấp |  |
| `multi-backend` | command | Run a backend-focused multi-model workflow for APIs, algorithms, data, and business logic. (`commands/multi-backend.md`) | Đã cài | ccg-workflow runtime ngoài | Thấp |  |
| `multi-execute` | command | Execute a multi-model implementation plan while preserving Claude as the only filesystem writer. (`commands/multi-execute.md`) | Đã cài | ccg-workflow runtime ngoài | Thấp |  |
| `multi-frontend` | command | Run a frontend-focused multi-model workflow for components, layouts, animation, and UI polish. (`commands/multi-frontend.md`) | Đã cài | ccg-workflow runtime ngoài | Thấp |  |
| `multi-plan` | command | Create a multi-model (Codex + Antigravity) implementation plan without modifying production code. Requires the external ccg-workflow runtime, not part of the ba (`commands/multi-plan.md`) | Đã cài | ccg-workflow runtime ngoài | Thấp |  |
| `multi-workflow` | command | Run a full multi-model development workflow with research, planning, execution, optimization, and review. (`commands/multi-workflow.md`) | Đã cài | ccg-workflow runtime ngoài | Thấp |  |
| `orch-build-mvp` | command | Orchestrate bootstrapping a working MVP from a design/spec doc — ingest, slice, scaffold, TDD, review, gated commit (reuses the GAN harness). Wrapper for the or (`commands/orch-build-mvp.md`) | Đã cài |  | Thấp |  |
| `prp-commit` | command | Quick commit with natural language file targeting — describe what to commit in plain English (`commands/prp-commit.md`) | Đã cài |  | Thấp |  |
| `prp-pr` | command | Alias of /pr for the PRP workflow series. Use when creating a pull request mid-PRP workflow; otherwise use /pr. (`commands/prp-pr.md`) | Đã cài |  | Thấp |  |
| `prp-prd` | command | Interactive PRD generator - problem-first, hypothesis-driven product spec with back-and-forth questioning (`commands/prp-prd.md`) | Đã cài |  | Thấp |  |
| `agentic-engineering` | skill | Operate as an agentic engineer using eval-first execution, decomposition, and cost-aware model routing. Use when planning or executing engineering work that age (`skills/agentic-engineering/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `ai-first-engineering` | skill | Engineering operating model for teams where AI agents generate a large share of implementation output. Use when setting team process, review gates, or ownership (`skills/ai-first-engineering/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `autonomous-agent-harness` | skill | Transform Claude Code into a fully autonomous agent system with persistent memory, scheduled operations, computer use, and task queuing. Replaces standalone age (`skills/autonomous-agent-harness/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `autonomous-loops` | skill | Patterns and architectures for autonomous Claude Code loops — from simple sequential pipelines to RFC-driven multi-agent DAG systems. Retained for compatibility (`skills/autonomous-loops/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `claude-devfleet` | skill | Orchestrate multi-agent coding tasks via Claude DevFleet — plan projects, dispatch parallel agents in isolated worktrees, monitor progress, and read structured  (`skills/claude-devfleet/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `continuous-agent-loop` | skill | Patterns for continuous autonomous agent loops with quality gates, evals, and recovery controls. Use when running an agent loop that must self-check, gate on ev (`skills/continuous-agent-loop/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `council-multi-model` | skill | Add one optional external Codex critique after the existing council has produced a decision draft. Use when an ambiguous, high-consequence decision would benefi (`skills/council-multi-model/SKILL.md`) | Đã cài | Codex CLI | Thấp |  |
| `delivery-gate` | skill | Stop hook that blocks Claude from finishing until quality checks pass. Detects rationalization patterns (surface text heuristics), stale learning logs (filesyst (`skills/delivery-gate/SKILL.md`) | Đã cài | Hook (đang tắt) | Thấp | ✔ |
| `dev-team` | skill | Simulate a collaborative dev team session where multiple role-based personas (PM, Architect, Developer, QA) respond to the same problem together in one session. (`skills/dev-team/SKILL.md`) | Đã cài |  | Thấp |  |
| `dmux-workflows` | skill | Multi-agent orchestration using dmux (tmux pane manager for AI agents). Patterns for parallel agent workflows across Claude Code, Codex, OpenCode, and other har (`skills/dmux-workflows/SKILL.md`) | Chỉ Codex tree |  | Thấp |  |
| `dynamic-workflow-mode` | skill | Design task-local harnesses, eval gates, and reusable skill extraction for Claude dynamic workflow mode and other adaptive agent harnesses. Use when building a  (`skills/dynamic-workflow-mode/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `gan-style-harness` | skill | GAN-inspired Generator-Evaluator agent harness for building high-quality applications autonomously. Based on Anthropic's March 2026 harness design paper. Use wh (`skills/gan-style-harness/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `gateguard` | skill | PreToolUse fact-forcing gate that denies the first Edit/Write/Bash (including MultiEdit) attempt until the agent presents concrete facts (importers, data schema (`skills/gateguard/SKILL.md`) | Đã cài | Hook (đang tắt) | Thấp | ✔ |
| `orch-build-mvp` | skill | Orchestrate bootstrapping a working MVP from a design or spec document — ingest the SDD/PRD, plan thin vertical slices, scaffold the first end-to-end slice, the (`skills/orch-build-mvp/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `parallel-execution-optimizer` | skill | Speed up a task by turning it into a dependency graph of parallel lanes with a lane matrix, batched reads and checks, write surfaces isolated by file, worktree, (`skills/parallel-execution-optimizer/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `plan-orchestrate` | skill | Read a plan document, decompose it into steps, classify each step, and emit the ready-to-paste ECC slash command for that step, carrying the step identifier and (`skills/plan-orchestrate/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `ralphinho-rfc-pipeline` | skill | Split an RFC into a multi-agent execution DAG — decompose into work units with dependencies and acceptance tests, run research, plan, implement, test, and revie (`skills/ralphinho-rfc-pipeline/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `safety-guard` | skill | Guard against destructive operations with three modes: Careful intercepts dangerous commands (rm -rf, git push --force, DROP TABLE) for confirmation, Freeze loc (`skills/safety-guard/SKILL.md`) | Đã cài | Hook (đang tắt) | Thấp | ✔ |
| `team-agent-orchestration` | skill | Run team-based orchestration for agent squads: work items with owners and scope, agent Kanban state, branch isolation, control pane visibility, and merge gates. (`skills/team-agent-orchestration/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `team-builder` | skill | Interactive picker that discovers available agent personas via the claude agents command and agents/ markdown globs, groups them into domains, has the user sele (`skills/team-builder/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |

## 02 TDD / testing / E2E / eval

| Tên | Loại | Mô tả (từ file) | Trạng thái cài | Phụ thuộc | Áp dụng XAU EDGE | Đọc sâu |
|---|---|---|---|---|---|---|
| `e2e-runner` | agent | End-to-end testing specialist using Vercel Agent Browser (preferred) with Playwright fallback. Use PROACTIVELY for generating, maintaining, and running E2E test (`agents/e2e-runner.md`) | Đã cài | Agent Browser/Playwright | Cao |  |
| `pr-test-analyzer` | agent | Review pull request test coverage quality and completeness, with emphasis on behavioral coverage and real bug prevention. (`agents/pr-test-analyzer.md`) | Đã cài |  | Cao | ✔ |
| `tdd-guide` | agent | Test-Driven Development specialist enforcing write-tests-first methodology. Use PROACTIVELY when writing new features, fixing bugs, or refactoring code. Ensures (`agents/tdd-guide.md`) | Đã cài |  | Cao |  |
| `test-coverage` | command | Analyze coverage, identify gaps, and generate missing tests toward the target threshold. (`commands/test-coverage.md`) | Đã cài |  | Cao |  |
| `e2e-testing` | skill | Playwright E2E testing patterns, Page Object Model, configuration, CI/CD integration, artifact management, and flaky test strategies. Use when writing Playwrigh (`skills/e2e-testing/SKILL.md`) | Đã cài |  | Cao | ✔ |
| `eval-harness` | skill | Eval-driven development (EDD) framework for AI coding sessions — define capability and regression evals before coding, grade with code-based, model-based, rule, (`skills/eval-harness/SKILL.md`) | Đã cài |  | Cao | ✔ |
| `production-audit` | skill | Local-evidence production readiness audit for shipped apps, pre-launch reviews, post-merge checks, and "what breaks in prod?" questions without sending repo dat (`skills/production-audit/SKILL.md`) | Đã cài |  | Cao | ✔ |
| `python-testing` | skill | Python testing strategies using pytest, TDD methodology, fixtures, mocking, parametrization, and coverage requirements. Use when writing pytest tests — fixtures (`skills/python-testing/SKILL.md`) | Đã cài |  | Cao | ✔ |
| `tdd-workflow` | skill | Test-driven development workflow: write a failing test first, watch it fail, implement the smallest change to green, then refactor with 80%+ coverage across uni (`skills/tdd-workflow/SKILL.md`) | Đã cài |  | Cao | ✔ |
| `verification-loop` | skill | Run a six-phase verification of a Claude Code session's work — build, type check, lint, tests with coverage, security grep, and diff review — then produce a PAS (`skills/verification-loop/SKILL.md`) | Đã cài |  | Cao | ✔ |
| `agent-evaluator` | agent | Evaluates agent output against 5-axis quality rubric (accuracy, completeness, clarity, actionability, conciseness). Use after any non-trivial task when the user (`agents/agent-evaluator.md`) | Đã cài |  | Trung bình |  |
| `react-test` | command | Enforce TDD workflow for React. Write React Testing Library tests first (behavior-focused, accessibility-first), then implement components. Detects Vitest or Je (`commands/react-test.md`) | Đã cài |  | Trung bình |  |
| `ai-regression-testing` | skill | Regression testing strategies for AI-assisted development. Sandbox-mode API testing without database dependencies, automated bug-check workflows, and patterns t (`skills/ai-regression-testing/SKILL.md`) | Đã cài |  | Trung bình | ✔ |
| `benchmark` | skill | Measure performance baselines and detect regressions across browser Core Web Vitals (LCP, INP, CLS, page weight), API endpoint latency percentiles, and build/te (`skills/benchmark/SKILL.md`) | Chỉ trong ECC |  | Trung bình |  |
| `benchmark-optimization-loop` | skill | Convert 'make it faster' requests into a bounded measured optimization loop — baseline first, generate one-hypothesis variants, benchmark each against a correct (`skills/benchmark-optimization-loop/SKILL.md`) | Chỉ trong ECC |  | Trung bình |  |
| `browser-qa` | skill | Run automated post-deploy UI verification with a browser automation MCP (claude-in-chrome, Playwright, or Puppeteer): console-error and Core Web Vitals smoke ch (`skills/browser-qa/SKILL.md`) | Đã cài | MCP browser (Playwright có sẵn) | Trung bình | ✔ |
| `click-path-audit` | skill | Trace every user-facing button/touchpoint through its full state change sequence to find bugs where functions individually work but cancel each other out, produ (`skills/click-path-audit/SKILL.md`) | Đã cài |  | Trung bình | ✔ |
| `react-testing` | skill | React component testing with React Testing Library, Vitest/Jest, MSW for network mocking, accessibility assertions with axe, and the decision boundary between c (`skills/react-testing/SKILL.md`) | Chỉ trong ECC |  | Trung bình |  |
| `windows-desktop-e2e` | skill | E2E testing for Windows native desktop apps (WPF, WinForms, Win32/MFC, Qt) using pywinauto and Windows UI Automation. Use when writing E2E tests for a Windows n (`skills/windows-desktop-e2e/SKILL.md`) | Đã cài |  | Trung bình | ✔ |
| `harness-optimizer` | agent | Improve local agent-harness configuration reliability and cost using eval-driven grading (pass@k/pass^k) derived from the eval-harness skill. (`agents/harness-optimizer.md`) | Đã cài |  | Thấp |  |
| `learn-eval` | command | Extract reusable patterns from the session, self-evaluate quality before saving, and determine the right save location (Global vs Project). (`commands/learn-eval.md`) | Đã cài |  | Thấp |  |
| `agent-eval` | skill | Head-to-head comparison of coding agents (Claude Code, Aider, Codex, etc.) on custom tasks with pass rate, cost, time, and consistency metrics. Use when choosin (`skills/agent-eval/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `agent-self-evaluation` | skill | Use after completing any non-trivial task. The agent self-rates its output on 5 axes — accuracy, completeness, clarity, actionability, conciseness — with concre (`skills/agent-self-evaluation/SKILL.md`) | Đã cài |  | Thấp |  |
| `canary-watch` | skill | Use this skill to monitor and verify a deployed URL after releases — checks HTTP endpoints, SSE streams, static assets, console errors, and performance regressi (`skills/canary-watch/SKILL.md`) | Chỉ trong ECC |  | Thấp | ✔ |
| `iterative-retrieval` | skill | Pattern for progressively refining context retrieval to solve the subagent context problem. Use when a subagent lacks the context it needs and retrieval must be (`skills/iterative-retrieval/SKILL.md`) | Đã cài |  | Thấp |  |
| `scientific-thinking-scholar-evaluation` | skill | Structured scholarly-work evaluation for papers, proposals, literature reviews, methods sections, evidence quality, citation support, and research-writing feedb (`skills/scientific-thinking-scholar-evaluation/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |

## 03 Code review & quality

| Tên | Loại | Mô tả (từ file) | Trạng thái cài | Phụ thuộc | Áp dụng XAU EDGE | Đọc sâu |
|---|---|---|---|---|---|---|
| `code-reviewer` | agent | Expert code review specialist. Proactively reviews code for quality, security, and maintainability. Use immediately after writing or modifying code. MUST BE USE (`agents/code-reviewer.md`) | Đã cài |  | Cao |  |
| `fastapi-reviewer` | agent | Reviews FastAPI applications for async correctness, dependency injection, Pydantic schemas, security, OpenAPI quality, testing, and production readiness. (`agents/fastapi-reviewer.md`) | Đã cài |  | Cao | ✔ |
| `mle-reviewer` | agent | Production machine-learning engineering reviewer for data contracts, feature pipelines, training reproducibility, offline/online evaluation, model serving, moni (`agents/mle-reviewer.md`) | Đã cài |  | Cao | ✔ |
| `python-reviewer` | agent | Expert Python code reviewer specializing in PEP 8 compliance, Pythonic idioms, type hints, security, and performance. Use for all Python code changes. MUST BE U (`agents/python-reviewer.md`) | Đã cài |  | Cao | ✔ |
| `react-reviewer` | agent | Expert React/JSX code reviewer specializing in hook correctness, render performance, server/client component boundaries, accessibility, and React-specific secur (`agents/react-reviewer.md`) | Đã cài |  | Cao | ✔ |
| `silent-failure-hunter` | agent | Review code for silent failures, swallowed errors, bad fallbacks, and missing error propagation. (`agents/silent-failure-hunter.md`) | Đã cài |  | Cao | ✔ |
| `typescript-reviewer` | agent | Expert TypeScript/JavaScript code reviewer specializing in type safety, async correctness, Node/web security, and idiomatic patterns. Use for all TypeScript and (`agents/typescript-reviewer.md`) | Đã cài |  | Cao | ✔ |
| `code-review` | command | Code review — local uncommitted changes or GitHub PR (pass PR number/URL for PR mode). Use for a step-by-step PRP-style checklist review; for a multi-agent pass (`commands/code-review.md`) | Đã cài |  | Cao |  |
| `fastapi-review` | command | Review a FastAPI application for architecture, async correctness, dependency injection, Pydantic schemas, security, performance, and testability. (`commands/fastapi-review.md`) | Đã cài |  | Cao |  |
| `python-review` | command | Comprehensive Python code review for PEP 8 compliance, type hints, security, and Pythonic idioms. Invokes the python-reviewer agent. (`commands/python-review.md`) | Đã cài |  | Cao |  |
| `react-review` | command | Comprehensive React/JSX code review for hook correctness, render performance, server/client component boundaries, accessibility, and React-specific security. In (`commands/react-review.md`) | Đã cài |  | Cao |  |
| `review-pr` | command | Comprehensive PR review using specialized agents (code-reviewer, comment-analyzer, pr-test-analyzer, silent-failure-hunter, type-design-analyzer, code-simplifie (`commands/review-pr.md`) | Đã cài |  | Cao |  |
| `error-handling` | skill | Patterns for robust error handling across TypeScript, Python, and Go. Covers typed errors, error boundaries, retries, circuit breakers, and user-facing error me (`skills/error-handling/SKILL.md`) | Đã cài |  | Cao |  |
| `build-error-resolver` | agent | Build and TypeScript error resolution specialist. Use PROACTIVELY when build fails or type errors occur. Fixes build/type errors only with minimal diffs, no arc (`agents/build-error-resolver.md`) | Đã cài |  | Trung bình |  |
| `code-explorer` | agent | Deeply analyzes existing codebase features by tracing execution paths, mapping architecture layers, and documenting dependencies to inform new development. (`agents/code-explorer.md`) | Đã cài |  | Trung bình |  |
| `code-simplifier` | agent | Simplifies and refines code for clarity, consistency, and maintainability while preserving behavior. Focus on recently modified code unless instructed otherwise (`agents/code-simplifier.md`) | Đã cài |  | Trung bình |  |
| `comment-analyzer` | agent | Analyze code comments for accuracy, completeness, maintainability, and comment rot risk. (`agents/comment-analyzer.md`) | Đã cài |  | Trung bình |  |
| `commit-reviewer` 🆕 | agent | Reviews a staged diff and drafts a Conventional Commits-compliant message matching the repository's actual history norms. Use before committing, or when asked t (`agents/commit-reviewer.md`) | Chỉ trong ECC |  | Trung bình |  |
| `refactor-cleaner` | agent | Dead code cleanup and consolidation specialist. Use PROACTIVELY for removing unused code, duplicates, and refactoring. Runs analysis tools (knip, depcheck, ts-p (`agents/refactor-cleaner.md`) | Đã cài |  | Trung bình |  |
| `spec-miner` | agent | Extracts behavioral specs from existing codebases for OpenSpec. Produces flat Requirement and Invariant blocks with structured metadata (entities, enforced, id, (`agents/spec-miner.md`) | Đã cài |  | Trung bình |  |
| `type-design-analyzer` | agent | Analyze type design for encapsulation, invariant expression, usefulness, and enforcement. (`agents/type-design-analyzer.md`) | Đã cài |  | Trung bình |  |
| `build-fix` | command | Detect the project build system and incrementally fix build/type errors with minimal safe changes. (`commands/build-fix.md`) | Đã cài |  | Trung bình |  |
| `refactor-clean` | command | Safely identify and remove dead code with verification after each change. (`commands/refactor-clean.md`) | Đã cài |  | Trung bình |  |
| `common/agents.md` | rule | ECC agents ship with the `ecc@ecc` plugin, not in `~/.claude/agents/`. (`rules/common/agents.md`) | Đã cài |  | Trung bình |  |
| `common/code-review.md` | rule | Code review ensures quality, security, and maintainability before code is merged. This rule defines when and how to conduct code reviews. (`rules/common/code-review.md`) | Đã cài |  | Trung bình |  |
| `common/coding-style.md` | rule | ALWAYS create new objects, NEVER mutate existing ones: (`rules/common/coding-style.md`) | Đã cài |  | Trung bình |  |
| `common/development-workflow.md` | rule | > This file extends [common/git-workflow.md](./git-workflow.md) with the full feature development process that happens before git operations. (`rules/common/development-workflow.md`) | Đã cài |  | Trung bình |  |
| `common/git-workflow.md` | rule | ``` (`rules/common/git-workflow.md`) | Đã cài |  | Trung bình |  |
| `common/hooks.md` | rule | - **PreToolUse**: Before tool execution (validation, parameter modification) (`rules/common/hooks.md`) | Đã cài |  | Trung bình |  |
| `common/patterns.md` | rule | When implementing new functionality: (`rules/common/patterns.md`) | Đã cài |  | Trung bình |  |
| `common/performance.md` | rule | **Haiku** (90% of Sonnet capability, 3x cost savings): (`rules/common/performance.md`) | Đã cài |  | Trung bình |  |
| `common/security.md` | rule | Before ANY commit: (`rules/common/security.md`) | Đã cài |  | Trung bình |  |
| `common/testing.md` | rule | Test Types (ALL required): (`rules/common/testing.md`) | Đã cài |  | Trung bình |  |
| `conventional-commit-review` 🆕 | skill | Reviews staged changes and drafts a Conventional Commits-compliant commit message with the right type, scope, and length. Use before committing, or when the use (`skills/conventional-commit-review/SKILL.md`) | Chỉ trong ECC |  | Trung bình |  |
| `inherit-legacy-style` | skill | Prevent AI style drift on legacy projects by scanning the codebase for implicit conventions, resolving conflicts with the operator one at a time, and writing an (`skills/inherit-legacy-style/SKILL.md`) | Đã cài |  | Trung bình |  |
| `mcp-dependency-review` 🆕 | skill | Statically review MCP configuration for mutable package references before approval or CI, without executing discovered MCP servers. Use when reviewing .mcp.json (`skills/mcp-dependency-review/SKILL.md`) | Chỉ trong ECC |  | Trung bình | ✔ |
| `database-reviewer` | agent | PostgreSQL database specialist for query optimization, schema design, security, and performance. Use PROACTIVELY when writing SQL, creating migrations, designin (`agents/database-reviewer.md`) | Đã cài |  | Thấp | ✔ |
| `rag-pipeline-reviewer` | agent | Reviews RAG (Retrieval-Augmented Generation) pipelines for retrieval quality, chunking strategy, embedding choices, and evaluation coverage. Invoke when the use (`agents/rag-pipeline-reviewer.md`) | Đã cài |  | Thấp |  |
| `codehealth-mcp` | skill | Real-time structural Code Health via CodeScene MCP — review before edits, verify score deltas after changes, gate commits and PRs. Use when reviewing code quali (`skills/codehealth-mcp/SKILL.md`) | Đã cài | MCP CodeScene | Thấp |  |
| `coding-standards` | skill | Baseline cross-project coding conventions for naming, readability, immutability, and code-quality review. Use detailed frontend or backend skills for framework- (`skills/coding-standards/SKILL.md`) | Chỉ Codex tree |  | Thấp |  |
| `plankton-code-quality` | skill | Write-time code quality enforcement using Plankton — auto-formatting, linting, and Claude-powered fixes on every file edit via hooks. Use when setting up write- (`skills/plankton-code-quality/SKILL.md`) | Đã cài | Hook + Plankton | Thấp | ✔ |
| `scientific-thinking-literature-review` | skill | Systematic literature-review workflow for academic, biomedical, technical, and scientific topics, including search planning, source screening, synthesis, citati (`skills/scientific-thinking-literature-review/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |

## 04 Security

| Tên | Loại | Mô tả (từ file) | Trạng thái cài | Phụ thuộc | Áp dụng XAU EDGE | Đọc sâu |
|---|---|---|---|---|---|---|
| `security-reviewer` | agent | Security vulnerability detection and remediation specialist. Use PROACTIVELY after writing code that handles user input, authentication, API endpoints, or sensi (`agents/security-reviewer.md`) | Đã cài |  | Cao |  |
| `prediction-market-risk-review` | skill | Review prediction-market, basket, oracle, and trading-agent workflows for compliance, safety, data-quality, privacy, and execution risk. Use before any workflow (`skills/prediction-market-risk-review/SKILL.md`) | Chỉ trong ECC |  | Cao | ✔ |
| `security-scan` | command | Run AgentShield against agent, hook, MCP, permission, and secret surfaces. This is the slash-command entrypoint for that audit; prefer the security-scan skill f (`commands/security-scan.md`) | Đã cài | AgentShield (npx) | Trung bình |  |
| `llm-trading-agent-security` | skill | Security patterns for autonomous trading agents with wallet or transaction authority. Covers prompt injection, spend limits, pre-send simulation, circuit breake (`skills/llm-trading-agent-security/SKILL.md`) | Đã cài |  | Trung bình | ✔ |
| `security-review` | skill | Use this skill when adding authentication, handling user input, working with secrets, creating API endpoints, or implementing payment/sensitive features. Provid (`skills/security-review/SKILL.md`) | Đã cài |  | Trung bình |  |
| `security-scan` | skill | Scan your Claude Code configuration (.claude/ directory) for security vulnerabilities, misconfigurations, and injection risks using AgentShield. Checks CLAUDE.m (`skills/security-scan/SKILL.md`) | Đã cài | AgentShield (npx) | Trung bình |  |
| `agent-security-hardening` 🆕 | skill | Security hardening guidance for AI agent frameworks that process untrusted content, invoke tools, write workspace files, manage runtime identifiers, or handle c (`skills/agent-security-hardening/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `security-bounty-hunter` | skill | Hunt for exploitable, bounty-worthy security issues in repositories. Focuses on remotely reachable vulnerabilities that qualify for real reports instead of nois (`skills/security-bounty-hunter/SKILL.md`) | Đã cài |  | Thấp |  |

## 05 Architecture / API / data / performance

| Tên | Loại | Mô tả (từ file) | Trạng thái cài | Phụ thuộc | Áp dụng XAU EDGE | Đọc sâu |
|---|---|---|---|---|---|---|
| `architect` | agent | Software architecture specialist for system design, scalability, and technical decision-making. Use PROACTIVELY when planning new features, refactoring large sy (`agents/architect.md`) | Đã cài |  | Cao | ✔ |
| `code-architect` | agent | Designs feature architectures by analyzing existing codebase patterns and conventions, then providing implementation blueprints with concrete files, interfaces, (`agents/code-architect.md`) | Đã cài |  | Cao | ✔ |
| `architecture-decision-records` | skill | Capture architectural decisions as numbered ADR markdown files in docs/adr/ with context, alternatives considered, consequences, and an index README. Use when t (`skills/architecture-decision-records/SKILL.md`) | Đã cài |  | Cao | ✔ |
| `latency-critical-systems` | skill | Optimize and verify latency-sensitive systems — realtime dashboards, market data feeds, streaming agents, execution gateways, queues, and caches — by tracking p (`skills/latency-critical-systems/SKILL.md`) | Chỉ trong ECC |  | Cao | ✔ |
| `python-patterns` | skill | Pythonic idioms, PEP 8 standards, type hints, and best practices for building robust, efficient, and maintainable Python applications. Use when writing or revie (`skills/python-patterns/SKILL.md`) | Đã cài |  | Cao |  |
| `performance-optimizer` | agent | Performance analysis and optimization specialist. Use PROACTIVELY for identifying bottlenecks, optimizing slow code, reducing bundle sizes, and improving runtim (`agents/performance-optimizer.md`) | Đã cài |  | Trung bình | ✔ |
| `python/coding-style.md` | rule | paths: (`rules/python/coding-style.md`) | Đã cài |  | Trung bình |  |
| `python/fastapi.md` | rule | paths: (`rules/python/fastapi.md`) | Đã cài |  | Trung bình |  |
| `python/hooks.md` | rule | paths: (`rules/python/hooks.md`) | Đã cài |  | Trung bình |  |
| `python/patterns.md` | rule | paths: (`rules/python/patterns.md`) | Đã cài |  | Trung bình |  |
| `python/security.md` | rule | paths: (`rules/python/security.md`) | Đã cài |  | Trung bình |  |
| `python/testing.md` | rule | paths: (`rules/python/testing.md`) | Đã cài |  | Trung bình |  |
| `api-design` | skill | REST API design patterns including resource naming, status codes, pagination, filtering, error responses, versioning, and rate limiting for production APIs. Use (`skills/api-design/SKILL.md`) | Chỉ Codex tree |  | Trung bình |  |
| `content-hash-cache-pattern` | skill | Cache expensive file processing results using SHA-256 content hashes — path-independent, auto-invalidating, with service layer separation. Use when repeated fil (`skills/content-hash-cache-pattern/SKILL.md`) | Chỉ trong ECC |  | Trung bình |  |
| `contract-first` | skill | Coordinate frontend/backend or service-to-service work through one authoritative machine-checkable contract (OpenAPI, AsyncAPI, Protocol Buffers, or JSON Schema (`skills/contract-first/SKILL.md`) | Chỉ trong ECC |  | Trung bình | ✔ |
| `data-throughput-accelerator` | skill | Diagnose and accelerate large data movement — ingestion, backfill, export, ETL, warehouse loading, manifest catch-up, and table synchronization — by isolating t (`skills/data-throughput-accelerator/SKILL.md`) | Chỉ trong ECC |  | Trung bình | ✔ |
| `fastapi-patterns` | skill | FastAPI best practices covering project structure, Pydantic v2 schemas, dependency injection, async handlers, authentication, authorization, transactional servi (`skills/fastapi-patterns/SKILL.md`) | Chỉ trong ECC |  | Trung bình |  |
| `hexagonal-architecture` | skill | Design, implement, and refactor Ports & Adapters systems with clear domain boundaries, dependency inversion, and testable use-case orchestration across TypeScri (`skills/hexagonal-architecture/SKILL.md`) | Chỉ trong ECC |  | Trung bình |  |
| `mle-workflow` | skill | Production machine-learning engineering workflow for data contracts, reproducible training, model evaluation, deployment, monitoring, and rollback. Use when bui (`skills/mle-workflow/SKILL.md`) | Chỉ Codex tree |  | Trung bình |  |
| `react-performance` | skill | React and Next.js performance optimization patterns adapted from Vercel Engineering's React Best Practices (https://github.com/vercel-labs/agent-skills). Organi (`skills/react-performance/SKILL.md`) | Chỉ trong ECC |  | Trung bình |  |
| `a11y-architect` | agent | Accessibility Architect specializing in WCAG 2.2 compliance for Web and Native platforms. Use PROACTIVELY when designing UI components, establishing design syst (`agents/a11y-architect.md`) | Đã cài |  | Thấp |  |
| `agent-architecture-audit` | skill | Full-stack diagnostic for agent and LLM applications. Audits the 12-layer agent stack for wrapper regression, memory pollution, tool discipline failures, hidden (`skills/agent-architecture-audit/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `api-connector-builder` | skill | Build a new API connector or provider by matching the target repo's existing integration pattern exactly. Use when adding one more integration without inventing (`skills/api-connector-builder/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `backend-patterns` | skill | Backend architecture patterns, API design, database optimization, and server-side best practices for Node.js, Express, and Next.js API routes. Use when building (`skills/backend-patterns/SKILL.md`) | Chỉ Codex tree |  | Thấp |  |
| `clickhouse-io` | skill | ClickHouse database patterns, query optimization, analytics, and data engineering best practices for high-performance analytical workloads. Use when writing Cli (`skills/clickhouse-io/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `database-migrations` | skill | Safe, reversible database migration patterns: forward-only production changes, expand-contract zero-downtime renames, concurrent indexes, batched backfills, and (`skills/database-migrations/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `ml-adoption-playbook` | skill | End-to-end methodology for AI agents and software engineers to add machine learning algorithms to existing non-ML codebases. Covers problem framing, data readin (`skills/ml-adoption-playbook/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `mysql-patterns` | skill | MySQL and MariaDB schema, query, indexing, transaction, replication, and connection-pool patterns for production backends. Use when designing MySQL or MariaDB s (`skills/mysql-patterns/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `postgres-patterns` | skill | PostgreSQL database patterns for query optimization, schema design, indexing, and security. Based on Supabase best practices. Use when designing PostgreSQL sche (`skills/postgres-patterns/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `prisma-patterns` | skill | Prisma ORM patterns for TypeScript backends — schema design, query optimization, transactions, pagination, and critical traps like updateMany returning count no (`skills/prisma-patterns/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `pytorch-patterns` | skill | PyTorch deep learning patterns and best practices for building robust, efficient, and reproducible training pipelines, model architectures, and data loading. Us (`skills/pytorch-patterns/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `recsys-pipeline-architect` | skill | Design composable recommendation, ranking, and feed pipelines using the six-stage Source→Hydrator→Filter→Scorer→Selector→SideEffect framework popularized by xAI (`skills/recsys-pipeline-architect/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `redis-patterns` | skill | Redis data structure patterns, caching strategies, distributed locks, rate limiting, pub/sub, and connection management for production applications. Use when ad (`skills/redis-patterns/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `regex-vs-llm-structured-text` | skill | Decision framework for parsing structured text (quizzes, forms, invoices, receipts, tables) with a hybrid regex-first pipeline — regex extraction handles 95%+ c (`skills/regex-vs-llm-structured-text/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |

## 06 Frontend / design / UI

| Tên | Loại | Mô tả (từ file) | Trạng thái cài | Phụ thuộc | Áp dụng XAU EDGE | Đọc sâu |
|---|---|---|---|---|---|---|
| `react-build-resolver` | agent | Diagnose and fix React build failures across Vite, webpack, Next.js, CRA, Parcel, esbuild, and Bun. Handles JSX/TSX compile errors, hydration mismatches, server (`agents/react-build-resolver.md`) | Đã cài |  | Trung bình |  |
| `react-build` | command | Fix React build failures (Vite, webpack, Next.js, CRA, Parcel, esbuild, Bun) incrementally — JSX/TSX compile errors, hydration mismatches, server/client compone (`commands/react-build.md`) | Đã cài |  | Trung bình |  |
| `react/coding-style.md` | rule | paths: (`rules/react/coding-style.md`) | Đã cài |  | Trung bình |  |
| `react/hooks.md` | rule | paths: (`rules/react/hooks.md`) | Đã cài |  | Trung bình |  |
| `react/patterns.md` | rule | paths: (`rules/react/patterns.md`) | Đã cài |  | Trung bình |  |
| `react/security.md` | rule | paths: (`rules/react/security.md`) | Đã cài |  | Trung bình |  |
| `react/testing.md` | rule | paths: (`rules/react/testing.md`) | Đã cài |  | Trung bình |  |
| `typescript/coding-style.md` | rule | paths: (`rules/typescript/coding-style.md`) | Đã cài |  | Trung bình |  |
| `typescript/hooks.md` | rule | paths: (`rules/typescript/hooks.md`) | Đã cài |  | Trung bình |  |
| `typescript/patterns.md` | rule | paths: (`rules/typescript/patterns.md`) | Đã cài |  | Trung bình |  |
| `typescript/security.md` | rule | paths: (`rules/typescript/security.md`) | Đã cài |  | Trung bình |  |
| `typescript/testing.md` | rule | paths: (`rules/typescript/testing.md`) | Đã cài |  | Trung bình |  |
| `web/coding-style.md` | rule | paths: (`rules/web/coding-style.md`) | Đã cài |  | Trung bình |  |
| `web/design-quality.md` | rule | paths: (`rules/web/design-quality.md`) | Đã cài |  | Trung bình |  |
| `web/hooks.md` | rule | paths: (`rules/web/hooks.md`) | Đã cài |  | Trung bình |  |
| `web/patterns.md` | rule | paths: (`rules/web/patterns.md`) | Đã cài |  | Trung bình |  |
| `web/performance.md` | rule | paths: (`rules/web/performance.md`) | Đã cài |  | Trung bình |  |
| `web/security.md` | rule | paths: (`rules/web/security.md`) | Đã cài |  | Trung bình |  |
| `web/testing.md` | rule | paths: (`rules/web/testing.md`) | Đã cài |  | Trung bình |  |
| `design-system` | skill | Generate a design system from an existing codebase or audit one for visual consistency: extract tokens (colors, typography, spacing, shadows) into design-tokens (`skills/design-system/SKILL.md`) | Chỉ trong ECC |  | Trung bình |  |
| `frontend-a11y` | skill | Accessibility patterns for React and Next.js — semantic HTML, ARIA attributes, form labeling, keyboard navigation, focus management, and screen reader support.  (`skills/frontend-a11y/SKILL.md`) | Chỉ trong ECC |  | Trung bình |  |
| `frontend-design-direction` | skill | Set an ECC-specific frontend design direction for production UI work. Use when building or improving websites, dashboards, applications, components, landing pag (`skills/frontend-design-direction/SKILL.md`) | Chỉ trong ECC |  | Trung bình |  |
| `frontend-patterns` | skill | Frontend development patterns for React, Next.js, state management, performance optimization, and UI best practices. Use when building or reviewing React or Nex (`skills/frontend-patterns/SKILL.md`) | Chỉ Codex tree |  | Trung bình |  |
| `make-interfaces-feel-better` | skill | Apply concrete design-engineering details that make interfaces feel polished. Use when reviewing or improving UI spacing, typography, borders, shadows, motion,  (`skills/make-interfaces-feel-better/SKILL.md`) | Chỉ trong ECC |  | Trung bình |  |
| `nextjs-turbopack` | skill | Next.js 16+ and Turbopack guidance — incremental Rust bundling, file-system caching, faster dev startup and HMR, Turbopack vs webpack tradeoffs, and the middlew (`skills/nextjs-turbopack/SKILL.md`) | Chỉ Codex tree |  | Trung bình |  |
| `react-patterns` | skill | React 18/19 patterns including hooks discipline, server/client component boundaries, Suspense + error boundaries, form actions, data fetching, state management  (`skills/react-patterns/SKILL.md`) | Chỉ trong ECC |  | Trung bình |  |
| `accessibility` | skill | Design, implement, and audit accessible UI to WCAG 2.2 Level AA across Web, iOS, and Android — semantic ARIA roles and labels, accessibility traits and hints, f (`skills/accessibility/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `bun-runtime` | skill | Bun as runtime, package manager, bundler, and test runner. When to choose Bun vs Node, migration notes, and Vercel support. (`skills/bun-runtime/SKILL.md`) | Chỉ Codex tree |  | Thấp |  |
| `i18n-sync` | skill | Translate and synchronize application JSON locale files using source-key usage, project terminology, and focused validation. Use when adding keys or languages,  (`skills/i18n-sync/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `motion-advanced` | skill | Advanced motion patterns for React / Next.js — drag & drop, gestures, text animations, SVG path drawing, custom hooks, imperative sequences (useAnimate), loader (`skills/motion-advanced/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `motion-foundations` | skill | Motion tokens, spring presets, performance rules, device adaptation, accessibility enforcement, and SSR safety for React / Next.js using motion/react. Foundatio (`skills/motion-foundations/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `motion-patterns` | skill | Production-ready animation patterns for React / Next.js — button, modal, toast, stagger, page transitions, exit animations, scroll, and layout — built on motion (`skills/motion-patterns/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `vite-patterns` | skill | Vite build tool patterns including config, plugins, HMR, env variables, proxy setup, SSR, library mode, dependency pre-bundling, and build optimization. Activat (`skills/vite-patterns/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |

## 07 Docs / ADR / knowledge

| Tên | Loại | Mô tả (từ file) | Trạng thái cài | Phụ thuộc | Áp dụng XAU EDGE | Đọc sâu |
|---|---|---|---|---|---|---|
| `update-docs` | command | Sync documentation from source-of-truth files such as scripts, schemas, routes, and exports. (`commands/update-docs.md`) | Đã cài |  | Cao | ✔ |
| `living-docs-governance` | skill | Keep a long-lived project's documentation from rotting by assigning existing project docs clear constitution, map, status, and history roles, then wiring the ac (`skills/living-docs-governance/SKILL.md`) | Đã cài |  | Cao | ✔ |
| `search-first` | skill | Research-before-coding workflow: search npm/PyPI, MCP servers, skills, and GitHub for existing tools before writing custom code, then adopt, extend, or build. L (`skills/search-first/SKILL.md`) | Đã cài |  | Cao |  |
| `doc-updater` | agent | Documentation and codemap specialist. Use PROACTIVELY for updating codemaps and documentation. Generates docs/CODEMAPS/*, updates READMEs and guides. Backs the  (`agents/doc-updater.md`) | Đã cài |  | Trung bình |  |
| `docs-lookup` | agent | When the user asks how to use a library, framework, or API or needs up-to-date code examples, use Context7 MCP to fetch current documentation and return answers (`agents/docs-lookup.md`) | Đã cài | MCP Context7 | Trung bình |  |
| `update-codemaps` | command | Scan project structure and generate token-lean architecture codemaps. (`commands/update-codemaps.md`) | Đã cài |  | Trung bình |  |
| `code-tour` | skill | Create CodeTour `.tour` files — persona-targeted, step-by-step walkthroughs with real file and line anchors. Use for onboarding tours, architecture walkthroughs (`skills/code-tour/SKILL.md`) | Đã cài |  | Trung bình |  |
| `codebase-onboarding` | skill | Analyze an unfamiliar codebase and generate a structured onboarding guide with architecture map, key entry points, conventions, and a starter CLAUDE.md. Use whe (`skills/codebase-onboarding/SKILL.md`) | Đã cài |  | Trung bình |  |
| `docs-governance` 🆕 | skill | Route broad documentation-governance requests to existing ECC skills and run an opt-in, read-only audit of mapped documentation roles, links, ADR indexes, and e (`skills/docs-governance/SKILL.md`) | Chỉ trong ECC |  | Trung bình | ✔ |
| `documentation-lookup` | skill | Use up-to-date library and framework docs via Context7 MCP instead of training data. Activates for setup questions, API references, code examples, or when the u (`skills/documentation-lookup/SKILL.md`) | Chỉ Codex tree | MCP Context7 | Trung bình |  |
| `deep-research` | skill | Produce cited research reports from multiple web sources using firecrawl and exa MCP tools — plan sub-questions, search and deep-read sources, then synthesize f (`skills/deep-research/SKILL.md`) | Chỉ Codex tree | MCP firecrawl/exa | Thấp | ✔ |
| `docker-patterns` | skill | Docker and Docker Compose patterns for local development, hardened CLI installer harnesses, container security, networking, volumes, and multi-service orchestra (`skills/docker-patterns/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `exa-search` | skill | Neural search via Exa MCP for web, code, and company research. Use when the user needs web search, code examples, company intel, people lookup, or AI-powered de (`skills/exa-search/SKILL.md`) | Chỉ Codex tree | MCP exa | Thấp |  |
| `knowledge-ops` | skill | Knowledge base management, ingestion, sync, and retrieval across multiple storage layers (local files, MCP memory, vector stores, Git repos). Use when the user  (`skills/knowledge-ops/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `market-research` | skill | Conduct market research, competitive analysis, investor due diligence, and industry intelligence with source attribution and decision-oriented summaries. Use wh (`skills/market-research/SKILL.md`) | Chỉ Codex tree |  | Thấp |  |
| `research-ops` | skill | Evidence-first current-state research workflow for ECC. Use when the user wants fresh facts, comparisons, enrichment, or a recommendation built from current pub (`skills/research-ops/SKILL.md`) | Chỉ trong ECC |  | Thấp | ✔ |

## 08 DevOps / CI / deploy / git

| Tên | Loại | Mô tả (từ file) | Trạng thái cài | Phụ thuộc | Áp dụng XAU EDGE | Đọc sâu |
|---|---|---|---|---|---|---|
| `git-workflow` | skill | Git workflow patterns including branching strategies, commit conventions, keeping history clean and readable, tidying local commits before merging, merge vs reb (`skills/git-workflow/SKILL.md`) | Đã cài |  | Trung bình |  |
| `pm2` | command | Analyze a project and generate PM2 service commands for detected frontend, backend, or database services. (`commands/pm2.md`) | Đã cài |  | Thấp |  |
| `pr` | command | Create a GitHub PR from current branch with unpushed commits — discovers templates, analyzes changes, pushes (`commands/pr.md`) | Đã cài |  | Thấp |  |
| `setup-pm` | command | Configure your preferred package manager (npm/pnpm/yarn/bun) (`commands/setup-pm.md`) | Đã cài |  | Thấp |  |
| `dashboard-builder` | skill | Build monitoring dashboards that answer real operator questions for Grafana, SigNoz, and similar platforms. Use when turning metrics into a working dashboard in (`skills/dashboard-builder/SKILL.md`) | Chỉ trong ECC |  | Thấp | ✔ |
| `deployment-patterns` | skill | Deployment workflows, CI/CD pipeline patterns, Docker containerization, health checks, rollback strategies, and production readiness checklists for web applicat (`skills/deployment-patterns/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `enterprise-agent-ops` | skill | Operational controls for long-lived or cloud-hosted agent systems — runtime lifecycle (start, pause, stop, restart), observability (logs, metrics, traces), leas (`skills/enterprise-agent-ops/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `flox-environments` | skill | Create reproducible, cross-platform (macOS/Linux) development environments with Flox, a declarative Nix-based environment manager. Use when setting up project t (`skills/flox-environments/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `generating-python-installer` | skill | Commercial-grade Python installer expert for Windows: Nuitka extreme compilation, dist slimming, DLL footprint analysis, and Inno Setup packaging to ship the sm (`skills/generating-python-installer/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `github-ops` | skill | GitHub repository operations, automation, and management. Issue triage, PR management, CI/CD operations, release management, and security monitoring using the g (`skills/github-ops/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `kubernetes-patterns` | skill | Kubernetes workload patterns, resource management, RBAC, probes, autoscaling, ConfigMap/Secret handling, and kubectl debugging for production-grade deployments. (`skills/kubernetes-patterns/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `project-flow-ops` | skill | Operate execution flow across GitHub and Linear by triaging issues and pull requests, linking active work, and keeping GitHub public-facing while Linear remains (`skills/project-flow-ops/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `terminal-ops` | skill | Evidence-first repo execution workflow for ECC. Use when the user wants a command run, a repo checked, a CI failure debugged, or a narrow fix pushed with exact  (`skills/terminal-ops/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `uncloud` | skill | Use when managing an Uncloud cluster — deploying services, configuring Caddy ingress, adding static proxy routes for non-cluster devices, publishing ports, scal (`skills/uncloud/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |

## 09 Memory / learning / session / context

| Tên | Loại | Mô tả (từ file) | Trạng thái cài | Phụ thuộc | Áp dụng XAU EDGE | Đọc sâu |
|---|---|---|---|---|---|---|
| `aside` | command | Answer a quick side question without interrupting or losing context from the current task. Resume work automatically after answering. (`commands/aside.md`) | Đã cài |  | Thấp |  |
| `cost-report` | command | Generate a local Claude Code cost report from the ECC cost-tracker metrics log. Use for a terminal summary or CSV export of tracked spend; the cost-tracking ski (`commands/cost-report.md`) | Đã cài | cost-tracker hook log | Thấp |  |
| `evolve` | command | Analyze instincts and suggest or generate evolved structures (`commands/evolve.md`) | Đã cài |  | Thấp |  |
| `instinct-export` | command | Export instincts from project/global scope to a file (`commands/instinct-export.md`) | Đã cài |  | Thấp |  |
| `instinct-import` | command | Import instincts from file or URL into project/global scope (`commands/instinct-import.md`) | Đã cài |  | Thấp |  |
| `instinct-status` | command | Show learned instincts (project + global) with confidence (`commands/instinct-status.md`) | Đã cài |  | Thấp |  |
| `learn` | command | Extract reusable patterns from the current session and save them as candidate skills or guidance. Use to review a session on demand and persist an approved skil (`commands/learn.md`) | Đã cài |  | Thấp |  |
| `model-route` | command | Recommend the best model tier for the current task based on complexity, risk, and budget. (`commands/model-route.md`) | Đã cài |  | Thấp |  |
| `projects` | command | List known projects and their instinct statistics (`commands/projects.md`) | Đã cài |  | Thấp |  |
| `promote` | command | Promote project-scoped instincts to global scope (`commands/promote.md`) | Đã cài |  | Thấp |  |
| `prune` | command | Delete pending instincts older than 30 days that were never promoted. Thin CLI wrapper for continuous-learning-v2's instinct-cli.py prune command; use to clean  (`commands/prune.md`) | Đã cài |  | Thấp |  |
| `resume-session` | command | Load the most recent session file from ~/.claude/session-data/ and resume work with full context from where the last session ended. (`commands/resume-session.md`) | Đã cài |  | Thấp |  |
| `save-session` | command | Save current session state to a dated file in ~/.claude/session-data/ so work can be resumed in a future session with full context. (`commands/save-session.md`) | Đã cài |  | Thấp |  |
| `sessions` | command | Manage Claude Code session history, aliases, and session metadata. (`commands/sessions.md`) | Đã cài |  | Thấp |  |
| `token-card` 🆕 | command | Render a token-usage stat card from local agent session logs and commit it to the repo. Invokes the token-card skill. (`commands/token-card.md`) | Chỉ trong ECC |  | Thấp |  |
| `agent-introspection-debugging` | skill | Structured self-debugging workflow for AI agent failures using capture, diagnosis, contained recovery, and introspection reports. Use when an agent run fails an (`skills/agent-introspection-debugging/SKILL.md`) | Đã cài |  | Thấp |  |
| `ck` | skill | Persistent per-project memory for Claude Code (Context Keeper) driven by deterministic Node.js /ck commands: init, save, resume, info, list, forget, and v1-to-v (`skills/ck/SKILL.md`) | Đã cài | Node ck scripts | Thấp |  |
| `context-budget` | skill | Audits Claude Code context window consumption across agents, skills, MCP servers, and rules. Identifies bloat, redundant components, and produces prioritized to (`skills/context-budget/SKILL.md`) | Đã cài |  | Thấp |  |
| `continuous-learning` | skill | [DEPRECATED - use continuous-learning-v2] Legacy v1 stop-hook skill extractor. v2 is a strict superset with instinct-based, project-scoped, hook-reliable learni (`skills/continuous-learning/SKILL.md`) | Đã cài | Hook (đang tắt) | Thấp |  |
| `continuous-learning-v2` | skill | Instinct-based learning system that observes sessions via hooks, creates atomic instincts with confidence scoring, and evolves them into skills/commands/agents. (`skills/continuous-learning-v2/SKILL.md`) | Đã cài | Hook (đang tắt) | Thấp |  |
| `cost-aware-llm-pipeline` | skill | Cost optimization patterns for LLM API usage — model routing by task complexity, budget tracking, retry logic, and prompt caching. Use when LLM spend needs to c (`skills/cost-aware-llm-pipeline/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `cost-tracking` | skill | Track and report Claude Code token usage, spending, and budgets from the local ECC cost-tracker metrics log. Use when the user asks about costs, spending, usage (`skills/cost-tracking/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `ecc-tools-cost-audit` | skill | Evidence-first ECC Tools burn and billing audit workflow. Use when investigating runaway PR creation, quota bypass, premium-model leakage, duplicate jobs, or Gi (`skills/ecc-tools-cost-audit/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `growth-log` | skill | Write growth log entries that extract reusable patterns from completed work — root cause, transferable rule, and a recognizable signal — instead of diary-style  (`skills/growth-log/SKILL.md`) | Đã cài |  | Thấp |  |
| `prompt-caching-strategy` 🆕 | skill | Optimize LLM prompt caching hit rate to reduce API costs and improve latency. Analyzes prompt structure, identifies cacheable vs non-cacheable content, and reco (`skills/prompt-caching-strategy/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `strategic-compact` | skill | Suggests manual context compaction at logical intervals to preserve context through task phases rather than arbitrary auto-compaction. Use when a session is app (`skills/strategic-compact/SKILL.md`) | Đã cài |  | Thấp |  |
| `token-budget-advisor` | skill | Offer a choice of response depth (25%/50%/75%/100%) with token estimates before answering, then answer at that level. Use when the user asks to control response (`skills/token-budget-advisor/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `token-card` 🆕 | skill | Render a token-usage stat card from local Claude Code, Codex, Gemini CLI, and OpenCode session logs and commit it into the repository as a file. Use when someon (`skills/token-card/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `unified-memory` | skill | Share durable, inspectable context and handoffs between Claude, Codex, Hermes, Cursor, OpenCode, and other agents through the local ECC Memory Vault. Use when a (`skills/unified-memory/SKILL.md`) | Đã cài | ECC Memory Vault | Thấp |  |

## 10 ECC meta / harness tooling

| Tên | Loại | Mô tả (từ file) | Trạng thái cài | Phụ thuộc | Áp dụng XAU EDGE | Đọc sâu |
|---|---|---|---|---|---|---|
| `harness-audit` | command | Run a deterministic repository harness audit and return a prioritized scorecard. Use for a deterministic overall repo-readiness scorecard; for a security-specif (`commands/harness-audit.md`) | Đã cài |  | Trung bình |  |
| `conversation-analyzer` | agent | Use this agent when analyzing conversation transcripts to find behaviors worth preventing with hooks. Triggered by /hookify without arguments. (`agents/conversation-analyzer.md`) | Đã cài |  | Thấp |  |
| `auto-update` | command | Pull the latest ECC repo changes and reinstall the current managed targets. (`commands/auto-update.md`) | Đã cài |  | Thấp |  |
| `ecc-guide` | command | Navigate ECC's current agents, skills, commands, hooks, install profiles, and docs from the live repository surface. This is the slash-command entrypoint for th (`commands/ecc-guide.md`) | Đã cài |  | Thấp |  |
| `hookify` | command | Create hooks to prevent unwanted behaviors from conversation analysis or explicit instructions. Use to generate a new hook rule file from conversation analysis  (`commands/hookify.md`) | Đã cài | Hook | Thấp |  |
| `hookify-configure` | command | Enable or disable hookify rules interactively (`commands/hookify-configure.md`) | Đã cài |  | Thấp |  |
| `hookify-help` | command | Get help with the hookify system (`commands/hookify-help.md`) | Đã cài |  | Thấp |  |
| `hookify-list` | command | List all configured hookify rules (`commands/hookify-list.md`) | Đã cài |  | Thấp |  |
| `project-init` | command | Detect a project's stack and produce a dry-run ECC onboarding plan using the repository's install manifests and stack mappings. Use to onboard ECC into a target (`commands/project-init.md`) | Đã cài |  | Thấp |  |
| `skill-create` | command | Analyze local git history to extract coding patterns and generate SKILL.md files. Local version of the Skill Creator GitHub App. Use to generate new skills from (`commands/skill-create.md`) | Đã cài |  | Thấp |  |
| `skill-health` | command | Show skill portfolio health dashboard with charts and analytics. Use for the quantitative usage/success-rate dashboard; for a qualitative compliance or quality  (`commands/skill-health.md`) | Đã cài |  | Thấp |  |
| `agent-harness-construction` | skill | Design and optimize AI agent action spaces, tool definitions, and observation formatting for higher completion rates. Use when defining or revising an agent's t (`skills/agent-harness-construction/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `agent-sort` | skill | Build an evidence-backed ECC install plan for a specific repo by sorting skills, commands, rules, hooks, and extras into DAILY vs LIBRARY buckets using parallel (`skills/agent-sort/SKILL.md`) | Đã cài |  | Thấp |  |
| `agentic-os` | skill | Build persistent multi-agent operating systems on Claude Code. Covers kernel architecture, specialist agents, slash commands, file-based memory, scheduled autom (`skills/agentic-os/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `automation-audit-ops` | skill | Evidence-first automation inventory and overlap audit workflow for ECC. Use when the user wants to know which jobs, hooks, connectors, MCP servers, or wrappers  (`skills/automation-audit-ops/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `config-gc` | skill | Garbage collection for your Claude Code configuration. Periodically scans ~/.claude (skills, memory, hooks, permissions, MCP servers, caches) for redundant, sta (`skills/config-gc/SKILL.md`) | Đã cài |  | Thấp |  |
| `configure-ecc` | skill | Run the conversational ECC setup wizard inside the current harness: inventory the install, collect scope (user/project/local) and hook mode (off/minimal/standar (`skills/configure-ecc/SKILL.md`) | Đã cài |  | Thấp |  |
| `counterparty-channel-discipline` | skill | Per-channel strict prompts, mention gating, silent observation, and a communication autonomy policy for agents that sit in shared channels with external counter (`skills/counterparty-channel-discipline/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `ecc-guide` | skill | Answer questions about ECC by reading the live repo surface — agents, skills, commands, hooks, rules, install profiles, and docs — instead of memory. Use when t (`skills/ecc-guide/SKILL.md`) | Đã cài |  | Thấp |  |
| `ecc-recipes` | skill | Map a described workflow to the right ECC command group with run-order and stop condition, or browse all command-group recipe families read live from the comman (`skills/ecc-recipes/SKILL.md`) | Đã cài |  | Thấp |  |
| `hermes-imports` | skill | Convert local Hermes operator workflows into sanitized ECC skills and release-pack artifacts. Use when preparing a Hermes workflow for public ECC reuse without  (`skills/hermes-imports/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `hookify-rules` | skill | Create and configure hookify rules — markdown files with YAML frontmatter that match bash, file, prompt, or stop events by regex or conditions and show warn/blo (`skills/hookify-rules/SKILL.md`) | Đã cài | Hook | Thấp |  |
| `mcp-server-patterns` | skill | Build MCP servers with Node/TypeScript SDK — tools, resources, prompts, Zod validation, stdio vs Streamable HTTP. Use Context7 or official MCP docs for latest A (`skills/mcp-server-patterns/SKILL.md`) | Chỉ Codex tree |  | Thấp |  |
| `nanoclaw-repl` | skill | Operate and extend NanoClaw, ECC's zero-dependency session-aware REPL, with persistent markdown-backed sessions and slash commands for model switching, skill lo (`skills/nanoclaw-repl/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `nasiko-control-plane` | skill | Manage the experimental Nasiko CLI lifecycle through ECC — read-only status checks, consent-gated install of the pinned qualified version with dry-run preview,  (`skills/nasiko-control-plane/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `openclaw-persona-forge` | skill | 为 OpenClaw AI Agent 锻造完整的龙虾灵魂方案。根据用户偏好或随机抽卡， 输出身份定位、灵魂描述(SOUL.md)、角色化底线规则、名字和头像生图提示词。 如当前环境提供已审核的生图 skill，可自动生成统一风格头像图片。 当用户需要创建、设计或定制 OpenClaw 龙虾灵魂时使用。 不适用于：微调 (`skills/openclaw-persona-forge/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `operator-approval-loop` | skill | Operator approval contract with internal filing notices for agent-drafted outbound messages, hashed drafts, epoch-keyed decisions, durable delivery claims and r (`skills/operator-approval-loop/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `prompt-optimizer` | skill | Analyze draft prompts, detect intent and missing context, match ECC commands, skills, and agents, and output a ready-to-paste optimized prompt with diagnosis an (`skills/prompt-optimizer/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |
| `repo-scan` | skill | Bootstrap pointer that installs the external repo-scan skill from a pinned, reviewable commit. Use when repo-scan must be installed before running its cross-sta (`skills/repo-scan/SKILL.md`) | Đã cài | cài skill ngoài | Thấp |  |
| `rules-distill` | skill | Scan skills to extract cross-cutting principles and distill them into rules — append, revise, or create new rule files. Use when the same principle keeps recurr (`skills/rules-distill/SKILL.md`) | Đã cài |  | Thấp |  |
| `skill-comply` | skill | Visualize whether skills, rules, and agent definitions are actually followed — auto-generates scenarios at 3 prompt strictness levels, runs agents, classifies b (`skills/skill-comply/SKILL.md`) | Đã cài |  | Thấp |  |
| `skill-scout` | skill | Search existing local, marketplace, GitHub, and web skill sources before creating a new skill. Use when the user wants to create, build, fork, or find a skill f (`skills/skill-scout/SKILL.md`) | Đã cài |  | Thấp |  |
| `skill-stocktake` | skill | Use when auditing Claude skills and commands for quality. Supports Quick Scan (changed skills only) and Full Stocktake modes with sequential subagent batch eval (`skills/skill-stocktake/SKILL.md`) | Đã cài |  | Thấp |  |
| `workspace-surface-audit` | skill | Audit the active repo, MCP servers, plugins, connectors, env surfaces, and harness setup, then recommend the highest-value ECC-native skills, hooks, agents, and (`skills/workspace-surface-audit/SKILL.md`) | Chỉ trong ECC |  | Thấp |  |

## 90 Stack khác (không dùng)

| Tên | Loại | Mô tả (từ file) | Trạng thái cài | Phụ thuộc | Áp dụng XAU EDGE | Đọc sâu |
|---|---|---|---|---|---|---|
| `bengali-reviewer` 🆕 | agent | Reviews code handling Bengali (Bangla) text for Unicode correctness, proper normalization, script-aware processing, and internationalization best practices. Use (`agents/bengali-reviewer.md`) | Chỉ trong ECC |  | Không |  |
| `cpp-build-resolver` | agent | C++ build, CMake, and compilation error resolution specialist. Fixes build errors, linker issues, and template errors with minimal changes. Use when C++ builds  (`agents/cpp-build-resolver.md`) | Đã cài |  | Không |  |
| `cpp-reviewer` | agent | Expert C++ code reviewer specializing in memory safety, modern C++ idioms, concurrency, and performance. Use for all C++ code changes. MUST BE USED for C++ proj (`agents/cpp-reviewer.md`) | Đã cài |  | Không |  |
| `csharp-reviewer` | agent | Expert C# code reviewer specializing in .NET conventions, async patterns, security, nullable reference types, and performance. Use for all C# code changes. MUST (`agents/csharp-reviewer.md`) | Đã cài |  | Không |  |
| `dart-build-resolver` | agent | Dart/Flutter build, analysis, and dependency error resolution specialist. Fixes `dart analyze` errors, Flutter compilation failures, pub dependency conflicts, a (`agents/dart-build-resolver.md`) | Đã cài |  | Không |  |
| `django-build-resolver` | agent | Django/Python build, migration, and dependency error resolution specialist. Fixes pip/Poetry errors, migration conflicts, import errors, Django configuration is (`agents/django-build-resolver.md`) | Đã cài |  | Không |  |
| `django-reviewer` | agent | Expert Django code reviewer specializing in ORM correctness, DRF patterns, migration safety, security misconfigurations, and production-grade Django practices.  (`agents/django-reviewer.md`) | Đã cài |  | Không |  |
| `flutter-reviewer` | agent | Flutter and Dart code reviewer. Reviews Flutter code for widget best practices, state management patterns, Dart idioms, performance pitfalls, accessibility, and (`agents/flutter-reviewer.md`) | Đã cài |  | Không |  |
| `fsharp-reviewer` | agent | Expert F# code reviewer specializing in functional idioms, type safety, pattern matching, computation expressions, and performance. Use for all F# code changes. (`agents/fsharp-reviewer.md`) | Đã cài |  | Không |  |
| `go-build-resolver` | agent | Go build, vet, and compilation error resolution specialist. Fixes build errors, go vet issues, and linter warnings with minimal changes. Use when Go builds fail (`agents/go-build-resolver.md`) | Đã cài |  | Không |  |
| `go-reviewer` | agent | Expert Go code reviewer specializing in idiomatic Go, concurrency patterns, error handling, and performance. Use for all Go code changes. MUST BE USED for Go pr (`agents/go-reviewer.md`) | Đã cài |  | Không |  |
| `harmonyos-app-resolver` | agent | HarmonyOS application development expert specializing in ArkTS and ArkUI. Reviews code for V2 state management compliance, Navigation routing patterns, API usag (`agents/harmonyos-app-resolver.md`) | Đã cài |  | Không |  |
| `java-build-resolver` | agent | Java/Maven/Gradle build, compilation, and dependency error resolution specialist. Automatically detects Spring Boot or Quarkus and applies framework-specific fi (`agents/java-build-resolver.md`) | Đã cài |  | Không |  |
| `java-reviewer` | agent | Expert Java code reviewer for Spring Boot and Quarkus projects. Automatically detects the framework and applies the appropriate review rules. Covers layered arc (`agents/java-reviewer.md`) | Đã cài |  | Không |  |
| `kotlin-build-resolver` | agent | Kotlin/Gradle build, compilation, and dependency error resolution specialist. Fixes build errors, Kotlin compiler errors, and Gradle issues with minimal changes (`agents/kotlin-build-resolver.md`) | Đã cài |  | Không |  |
| `kotlin-reviewer` | agent | Kotlin and Android/KMP code reviewer. Reviews Kotlin code for idiomatic patterns, coroutine safety, Compose best practices, clean architecture violations, and c (`agents/kotlin-reviewer.md`) | Đã cài |  | Không |  |
| `php-reviewer` | agent | Expert PHP code reviewer specializing in PSR-12 compliance, PHP type system, Eloquent ORM patterns, security, and performance. Use for all PHP code changes. MUS (`agents/php-reviewer.md`) | Đã cài |  | Không |  |
| `pytorch-build-resolver` | agent | PyTorch runtime, CUDA, and training error resolution specialist. Fixes tensor shape mismatches, device errors, gradient issues, DataLoader problems, and mixed p (`agents/pytorch-build-resolver.md`) | Đã cài |  | Không |  |
| `ruby-reviewer` 🆕 | agent | Expert Ruby and Rails code reviewer specializing in idiomatic Ruby, Active Record query safety, Rails security defaults, and RSpec/Minitest quality. Use for all (`agents/ruby-reviewer.md`) | Chỉ trong ECC |  | Không |  |
| `rust-build-resolver` | agent | Rust build, compilation, and dependency error resolution specialist. Fixes cargo build errors, borrow checker issues, and Cargo.toml problems with minimal chang (`agents/rust-build-resolver.md`) | Đã cài |  | Không |  |
| `rust-reviewer` | agent | Expert Rust code reviewer specializing in ownership, lifetimes, error handling, unsafe usage, and idiomatic patterns. Use for all Rust code changes. MUST BE USE (`agents/rust-reviewer.md`) | Đã cài |  | Không |  |
| `swift-build-resolver` | agent | Swift/Xcode build, compilation, and dependency error resolution specialist. Fixes swift build errors, Xcode build failures, SPM dependency issues, and code sign (`agents/swift-build-resolver.md`) | Đã cài |  | Không |  |
| `swift-reviewer` | agent | Expert Swift code reviewer specializing in protocol-oriented design, value semantics, ARC memory management, Swift Concurrency, and idiomatic patterns. Use for  (`agents/swift-reviewer.md`) | Đã cài |  | Không |  |
| `vue-reviewer` | agent | Expert Vue.js code reviewer specializing in Composition API correctness, reactivity pitfalls, component architecture, template security, and Vue-specific perfor (`agents/vue-reviewer.md`) | Đã cài |  | Không |  |
| `cpp-build` | command | Fix C++ build errors, CMake issues, and linker problems incrementally. Invokes the cpp-build-resolver agent for minimal, surgical fixes. (`commands/cpp-build.md`) | Đã cài |  | Không |  |
| `cpp-review` | command | Comprehensive C++ code review for memory safety, modern C++ idioms, concurrency, and security. Invokes the cpp-reviewer agent. (`commands/cpp-review.md`) | Đã cài |  | Không |  |
| `cpp-test` | command | Enforce TDD workflow for C++. Write GoogleTest tests first, then implement. Verify coverage with gcov/lcov. (`commands/cpp-test.md`) | Đã cài |  | Không |  |
| `epic-decompose` | command | Break an epic into task children without creating task branches. (`commands/epic-decompose.md`) | Đã cài |  | Không |  |
| `flutter-build` | command | Fix Dart analyzer errors and Flutter build failures incrementally. Invokes the dart-build-resolver agent for minimal, surgical fixes. (`commands/flutter-build.md`) | Đã cài |  | Không |  |
| `flutter-review` | command | Review Flutter/Dart code for idiomatic patterns, widget best practices, state management, performance, accessibility, and security. Invokes the flutter-reviewer (`commands/flutter-review.md`) | Đã cài |  | Không |  |
| `flutter-test` | command | Run Flutter/Dart tests, report failures, and incrementally fix test issues. Covers unit, widget, golden, and integration tests. (`commands/flutter-test.md`) | Đã cài |  | Không |  |
| `go-build` | command | Fix Go build errors, go vet warnings, and linter issues incrementally. Invokes the go-build-resolver agent for minimal, surgical fixes. (`commands/go-build.md`) | Đã cài |  | Không |  |
| `go-review` | command | Comprehensive Go code review for idiomatic patterns, concurrency safety, error handling, and security. Invokes the go-reviewer agent. (`commands/go-review.md`) | Đã cài |  | Không |  |
| `go-test` | command | Enforce TDD workflow for Go. Write table-driven tests first, then implement. Verify 80%+ coverage with go test -cover. (`commands/go-test.md`) | Đã cài |  | Không |  |
| `gradle-build` | command | Fix Gradle build errors for Android and KMP projects (`commands/gradle-build.md`) | Đã cài |  | Không |  |
| `kotlin-build` | command | Fix Kotlin/Gradle build errors, compiler warnings, and dependency issues incrementally. Invokes the kotlin-build-resolver agent for minimal, surgical fixes. (`commands/kotlin-build.md`) | Đã cài |  | Không |  |
| `kotlin-review` | command | Comprehensive Kotlin code review for idiomatic patterns, null safety, coroutine safety, and security. Invokes the kotlin-reviewer agent. (`commands/kotlin-review.md`) | Đã cài |  | Không |  |
| `kotlin-test` | command | Enforce TDD workflow for Kotlin. Write Kotest tests first, then implement. Verify 80%+ coverage with Kover. (`commands/kotlin-test.md`) | Đã cài |  | Không |  |
| `rust-build` | command | Fix Rust build errors, borrow checker issues, and dependency problems incrementally. Invokes the rust-build-resolver agent for minimal, surgical fixes. (`commands/rust-build.md`) | Đã cài |  | Không |  |
| `rust-review` | command | Comprehensive Rust code review for ownership, lifetimes, error handling, unsafe usage, and idiomatic patterns. Invokes the rust-reviewer agent. (`commands/rust-review.md`) | Đã cài |  | Không |  |
| `rust-test` | command | Enforce TDD workflow for Rust. Write tests first, then implement. Verify 80%+ coverage with cargo-llvm-cov. (`commands/rust-test.md`) | Đã cài |  | Không |  |
| `vue-review` | command | Comprehensive Vue.js code review for Composition API correctness, reactivity, composable patterns, template security, accessibility, and Vue-specific performanc (`commands/vue-review.md`) | Đã cài |  | Không |  |
| `README.md` | rule | Rules are organized into a **common** layer plus **language-specific** directories: (`rules/README.md`) | Đã cài |  | Không |  |
| `angular/coding-style.md` | rule | paths: (`rules/angular/coding-style.md`) | Đã cài |  | Không |  |
| `angular/hooks.md` | rule | paths: (`rules/angular/hooks.md`) | Đã cài |  | Không |  |
| `angular/patterns.md` | rule | paths: (`rules/angular/patterns.md`) | Đã cài |  | Không |  |
| `angular/security.md` | rule | paths: (`rules/angular/security.md`) | Đã cài |  | Không |  |
| `angular/testing.md` | rule | paths: (`rules/angular/testing.md`) | Đã cài |  | Không |  |
| `arkts/coding-style.md` | rule | paths: (`rules/arkts/coding-style.md`) | Đã cài |  | Không |  |
| `arkts/hooks.md` | rule | paths: (`rules/arkts/hooks.md`) | Đã cài |  | Không |  |
| `arkts/patterns.md` | rule | paths: (`rules/arkts/patterns.md`) | Đã cài |  | Không |  |
| `arkts/security.md` | rule | paths: (`rules/arkts/security.md`) | Đã cài |  | Không |  |
| `arkts/testing.md` | rule | paths: (`rules/arkts/testing.md`) | Đã cài |  | Không |  |
| `cpp/coding-style.md` | rule | paths: (`rules/cpp/coding-style.md`) | Đã cài |  | Không |  |
| `cpp/hooks.md` | rule | paths: (`rules/cpp/hooks.md`) | Đã cài |  | Không |  |
| `cpp/patterns.md` | rule | paths: (`rules/cpp/patterns.md`) | Đã cài |  | Không |  |
| `cpp/security.md` | rule | paths: (`rules/cpp/security.md`) | Đã cài |  | Không |  |
| `cpp/testing.md` | rule | paths: (`rules/cpp/testing.md`) | Đã cài |  | Không |  |
| `csharp/coding-style.md` | rule | paths: (`rules/csharp/coding-style.md`) | Đã cài |  | Không |  |
| `csharp/hooks.md` | rule | paths: (`rules/csharp/hooks.md`) | Đã cài |  | Không |  |
| `csharp/patterns.md` | rule | paths: (`rules/csharp/patterns.md`) | Đã cài |  | Không |  |
| `csharp/security.md` | rule | paths: (`rules/csharp/security.md`) | Đã cài |  | Không |  |
| `csharp/testing.md` | rule | paths: (`rules/csharp/testing.md`) | Đã cài |  | Không |  |
| `dart/coding-style.md` | rule | paths: (`rules/dart/coding-style.md`) | Đã cài |  | Không |  |
| `dart/hooks.md` | rule | paths: (`rules/dart/hooks.md`) | Đã cài |  | Không |  |
| `dart/patterns.md` | rule | paths: (`rules/dart/patterns.md`) | Đã cài |  | Không |  |
| `dart/security.md` | rule | paths: (`rules/dart/security.md`) | Đã cài |  | Không |  |
| `dart/testing.md` | rule | paths: (`rules/dart/testing.md`) | Đã cài |  | Không |  |
| `fsharp/coding-style.md` | rule | paths: (`rules/fsharp/coding-style.md`) | Đã cài |  | Không |  |
| `fsharp/hooks.md` | rule | paths: (`rules/fsharp/hooks.md`) | Đã cài |  | Không |  |
| `fsharp/patterns.md` | rule | paths: (`rules/fsharp/patterns.md`) | Đã cài |  | Không |  |
| `fsharp/security.md` | rule | paths: (`rules/fsharp/security.md`) | Đã cài |  | Không |  |
| `fsharp/testing.md` | rule | paths: (`rules/fsharp/testing.md`) | Đã cài |  | Không |  |
| `golang/coding-style.md` | rule | paths: (`rules/golang/coding-style.md`) | Đã cài |  | Không |  |
| `golang/hooks.md` | rule | paths: (`rules/golang/hooks.md`) | Đã cài |  | Không |  |
| `golang/patterns.md` | rule | paths: (`rules/golang/patterns.md`) | Đã cài |  | Không |  |
| `golang/security.md` | rule | paths: (`rules/golang/security.md`) | Đã cài |  | Không |  |
| `golang/testing.md` | rule | paths: (`rules/golang/testing.md`) | Đã cài |  | Không |  |
| `java/coding-style.md` | rule | paths: (`rules/java/coding-style.md`) | Đã cài |  | Không |  |
| `java/hooks.md` | rule | paths: (`rules/java/hooks.md`) | Đã cài |  | Không |  |
| `java/patterns.md` | rule | paths: (`rules/java/patterns.md`) | Đã cài |  | Không |  |
| `java/security.md` | rule | paths: (`rules/java/security.md`) | Đã cài |  | Không |  |
| `java/testing.md` | rule | paths: (`rules/java/testing.md`) | Đã cài |  | Không |  |
| `kotlin/coding-style.md` | rule | paths: (`rules/kotlin/coding-style.md`) | Đã cài |  | Không |  |
| `kotlin/hooks.md` | rule | paths: (`rules/kotlin/hooks.md`) | Đã cài |  | Không |  |
| `kotlin/patterns.md` | rule | paths: (`rules/kotlin/patterns.md`) | Đã cài |  | Không |  |
| `kotlin/security.md` | rule | paths: (`rules/kotlin/security.md`) | Đã cài |  | Không |  |
| `kotlin/testing.md` | rule | paths: (`rules/kotlin/testing.md`) | Đã cài |  | Không |  |
| `nuxt/coding-style.md` | rule | paths: (`rules/nuxt/coding-style.md`) | Đã cài |  | Không |  |
| `nuxt/hooks.md` | rule | paths: (`rules/nuxt/hooks.md`) | Đã cài |  | Không |  |
| `nuxt/patterns.md` | rule | paths: (`rules/nuxt/patterns.md`) | Đã cài |  | Không |  |
| `nuxt/security.md` | rule | paths: (`rules/nuxt/security.md`) | Đã cài |  | Không |  |
| `nuxt/testing.md` | rule | paths: (`rules/nuxt/testing.md`) | Đã cài |  | Không |  |
| `perl/coding-style.md` | rule | paths: (`rules/perl/coding-style.md`) | Đã cài |  | Không |  |
| `perl/hooks.md` | rule | paths: (`rules/perl/hooks.md`) | Đã cài |  | Không |  |
| `perl/patterns.md` | rule | paths: (`rules/perl/patterns.md`) | Đã cài |  | Không |  |
| `perl/security.md` | rule | paths: (`rules/perl/security.md`) | Đã cài |  | Không |  |
| `perl/testing.md` | rule | paths: (`rules/perl/testing.md`) | Đã cài |  | Không |  |
| `php/coding-style.md` | rule | paths: (`rules/php/coding-style.md`) | Đã cài |  | Không |  |
| `php/hooks.md` | rule | paths: (`rules/php/hooks.md`) | Đã cài |  | Không |  |
| `php/patterns.md` | rule | paths: (`rules/php/patterns.md`) | Đã cài |  | Không |  |
| `php/security.md` | rule | paths: (`rules/php/security.md`) | Đã cài |  | Không |  |
| `php/testing.md` | rule | paths: (`rules/php/testing.md`) | Đã cài |  | Không |  |
| `react-native/accessibility.md` | rule | paths: (`rules/react-native/accessibility.md`) | Đã cài |  | Không |  |
| `react-native/coding-style.md` | rule | paths: (`rules/react-native/coding-style.md`) | Đã cài |  | Không |  |
| `react-native/hooks.md` | rule | paths: (`rules/react-native/hooks.md`) | Đã cài |  | Không |  |
| `react-native/patterns.md` | rule | paths: (`rules/react-native/patterns.md`) | Đã cài |  | Không |  |
| `react-native/performance.md` | rule | paths: (`rules/react-native/performance.md`) | Đã cài |  | Không |  |
| `react-native/production-readiness.md` | rule | paths: (`rules/react-native/production-readiness.md`) | Đã cài |  | Không |  |
| `react-native/security.md` | rule | paths: (`rules/react-native/security.md`) | Đã cài |  | Không |  |
| `react-native/testing.md` | rule | paths: (`rules/react-native/testing.md`) | Đã cài |  | Không |  |
| `ruby/coding-style.md` | rule | paths: (`rules/ruby/coding-style.md`) | Đã cài |  | Không |  |
| `ruby/hooks.md` | rule | paths: (`rules/ruby/hooks.md`) | Đã cài |  | Không |  |
| `ruby/patterns.md` | rule | paths: (`rules/ruby/patterns.md`) | Đã cài |  | Không |  |
| `ruby/security.md` | rule | paths: (`rules/ruby/security.md`) | Đã cài |  | Không |  |
| `ruby/testing.md` | rule | paths: (`rules/ruby/testing.md`) | Đã cài |  | Không |  |
| `rust/coding-style.md` | rule | paths: (`rules/rust/coding-style.md`) | Đã cài |  | Không |  |
| `rust/hooks.md` | rule | paths: (`rules/rust/hooks.md`) | Đã cài |  | Không |  |
| `rust/patterns.md` | rule | paths: (`rules/rust/patterns.md`) | Đã cài |  | Không |  |
| `rust/security.md` | rule | paths: (`rules/rust/security.md`) | Đã cài |  | Không |  |
| `rust/testing.md` | rule | paths: (`rules/rust/testing.md`) | Đã cài |  | Không |  |
| `swift/coding-style.md` | rule | paths: (`rules/swift/coding-style.md`) | Đã cài |  | Không |  |
| `swift/hooks.md` | rule | paths: (`rules/swift/hooks.md`) | Đã cài |  | Không |  |
| `swift/patterns.md` | rule | paths: (`rules/swift/patterns.md`) | Đã cài |  | Không |  |
| `swift/security.md` | rule | paths: (`rules/swift/security.md`) | Đã cài |  | Không |  |
| `swift/testing.md` | rule | paths: (`rules/swift/testing.md`) | Đã cài |  | Không |  |
| `vue/coding-style.md` | rule | paths: (`rules/vue/coding-style.md`) | Đã cài |  | Không |  |
| `vue/hooks.md` | rule | paths: (`rules/vue/hooks.md`) | Đã cài |  | Không |  |
| `vue/patterns.md` | rule | paths: (`rules/vue/patterns.md`) | Đã cài |  | Không |  |
| `vue/security.md` | rule | paths: (`rules/vue/security.md`) | Đã cài |  | Không |  |
| `vue/testing.md` | rule | paths: (`rules/vue/testing.md`) | Đã cài |  | Không |  |
| `android-clean-architecture` | skill | Clean Architecture patterns for Android and Kotlin Multiplatform projects — module structure, dependency rules, UseCases, Repositories, and data layer patterns. (`skills/android-clean-architecture/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `angular-developer` | skill | Generates Angular code and provides architectural guidance. Trigger when creating projects, components, or services, or for best practices on reactivity (signal (`skills/angular-developer/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `bengali-nlp` 🆕 | skill | Bengali (Bangla) text processing patterns including Unicode normalization, script detection, tokenization, conjunct handling, and Bangla-specific NLP best pract (`skills/bengali-nlp/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `cisco-ios-patterns` | skill | Cisco IOS and IOS-XE review patterns for show commands, config hierarchy, wildcard masks, ACL placement, interface hygiene, and safe change-window verification. (`skills/cisco-ios-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `compose-multiplatform-patterns` | skill | Compose Multiplatform and Jetpack Compose patterns for KMP projects — state management, navigation, theming, performance, and platform-specific UI. Use when bui (`skills/compose-multiplatform-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `cpp-coding-standards` | skill | C++ coding standards based on the C++ Core Guidelines (isocpp.github.io). Use when writing, reviewing, or refactoring C++ code to enforce modern, safe, and idio (`skills/cpp-coding-standards/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `cpp-testing` | skill | Use only when writing/updating/fixing C++ tests, configuring GoogleTest/CTest, diagnosing failing or flaky tests, or adding coverage/sanitizers. (`skills/cpp-testing/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `csharp-testing` | skill | C# and .NET testing patterns with xUnit, FluentAssertions, mocking, integration tests, and test organization best practices. Use when writing or reviewing xUnit (`skills/csharp-testing/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `dart-flutter-patterns` | skill | Production-ready Dart and Flutter patterns covering null safety, immutable state with Freezed, async composition, widget architecture, state management (BLoC, R (`skills/dart-flutter-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `django-celery` | skill | Django + Celery async task patterns — configuration, task design, beat scheduling, retries, canvas workflows, monitoring, and testing. Use when adding backgroun (`skills/django-celery/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `django-patterns` | skill | Django architecture patterns, REST API design with DRF, ORM best practices, caching, signals, middleware, and production-grade Django apps. Use when building or (`skills/django-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `django-security` | skill | Django security best practices, authentication, authorization, CSRF protection, SQL injection prevention, XSS prevention, and secure deployment configurations.  (`skills/django-security/SKILL.md`) | Đã cài |  | Không |  |
| `django-tdd` | skill | Django testing strategies with pytest-django, TDD methodology, factory_boy, mocking, coverage, and testing Django REST Framework APIs. Use when writing Django o (`skills/django-tdd/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `django-verification` | skill | Run the full Django verification loop — environment check, mypy/ruff/black linting, migration safety, pytest with coverage targets, pip-audit and bandit securit (`skills/django-verification/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `dotnet-patterns` | skill | Idiomatic C# and .NET patterns, conventions, dependency injection, async/await, and best practices for building robust, maintainable .NET applications. Use when (`skills/dotnet-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `flutter-dart-code-review` | skill | Library-agnostic Flutter/Dart code review checklist covering widget best practices, state management patterns (BLoC, Riverpod, Provider, GetX, MobX, Signals), D (`skills/flutter-dart-code-review/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `foundation-models-on-device` | skill | Apple FoundationModels framework for on-device LLM — text generation, guided generation with @Generable, tool calling, and snapshot streaming in iOS 26+. Use wh (`skills/foundation-models-on-device/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `fsharp-testing` | skill | F# testing patterns with xUnit, FsUnit, Unquote, FsCheck property-based testing, integration tests, and test organization best practices. Use when writing F# te (`skills/fsharp-testing/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `golang-patterns` | skill | Idiomatic Go patterns, best practices, and conventions for building robust, efficient, and maintainable Go applications. Use when writing or reviewing Go code a (`skills/golang-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `golang-testing` | skill | Go testing patterns including table-driven tests, subtests, benchmarks, fuzzing, and test coverage. Follows TDD methodology with idiomatic Go practices. Use whe (`skills/golang-testing/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `ios-icon-gen` | skill | Generate iOS app icons as PNG imagesets for Xcode asset catalogs from SF Symbols (5000+ Apple-native) or Iconify API (275k+ open source icons from 200+ collecti (`skills/ios-icon-gen/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `java-coding-standards` | skill | Java coding standards for Spring Boot and Quarkus services: naming, immutability, Optional usage, streams, exceptions, generics, CDI, reactive patterns, and pro (`skills/java-coding-standards/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `jpa-patterns` | skill | JPA/Hibernate patterns for entity design, relationships, query optimization, transactions, auditing, indexing, pagination, and pooling in Spring Boot. Use when  (`skills/jpa-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `kotlin-coroutines-flows` | skill | Kotlin Coroutines and Flow patterns for Android and KMP — structured concurrency, Flow operators, StateFlow, error handling, and testing. Use when writing corou (`skills/kotlin-coroutines-flows/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `kotlin-exposed-patterns` | skill | JetBrains Exposed ORM patterns including DSL queries, DAO pattern, transactions, HikariCP connection pooling, Flyway migrations, and repository pattern. Use whe (`skills/kotlin-exposed-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `kotlin-ktor-patterns` | skill | Ktor server patterns including routing DSL, plugins, authentication, Koin DI, kotlinx.serialization, WebSockets, and testApplication testing. Use when building  (`skills/kotlin-ktor-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `kotlin-patterns` | skill | Idiomatic Kotlin patterns, best practices, and conventions for building robust, efficient, and maintainable Kotlin applications with coroutines, null safety, an (`skills/kotlin-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `kotlin-testing` | skill | Kotlin testing patterns with Kotest, MockK, coroutine testing, property-based testing, and Kover coverage. Follows TDD methodology with idiomatic Kotlin practic (`skills/kotlin-testing/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `laravel-patterns` | skill | Laravel architecture patterns, routing/controllers, Eloquent ORM, service layers, queues, events, caching, and API resources for production apps. Use when build (`skills/laravel-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `laravel-plugin-discovery` | skill | Discover and evaluate Laravel packages via LaraPlugins.io MCP. Use when the user wants to find plugins, check package health, or assess Laravel/PHP compatibilit (`skills/laravel-plugin-discovery/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `laravel-security` | skill | Laravel security best practices — authentication, authorization, Eloquent safety, CSRF, XSS prevention, API security, and secure deployment configurations. Use  (`skills/laravel-security/SKILL.md`) | Đã cài |  | Không |  |
| `laravel-tdd` | skill | Laravel testing strategies with PHPUnit, Pest, model factories, HTTP tests, Sanctum authentication testing, mocking, and coverage. Use when writing Laravel test (`skills/laravel-tdd/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `laravel-verification` | skill | Verification loop for Laravel projects: env checks, linting, static analysis, tests with coverage, security scans, and deployment readiness. Use when verifying  (`skills/laravel-verification/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `liquid-glass-design` | skill | iOS 26 Liquid Glass design system — dynamic glass material with blur, reflection, and interactive morphing for SwiftUI, UIKit, and WidgetKit. Use when building  (`skills/liquid-glass-design/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `mybatis-patterns` 🆕 | skill | MyBatis and MyBatis-Spring patterns for mapper design, XML and annotation SQL, result mapping, dynamic SQL safety, transactions, batching, pagination, and query (`skills/mybatis-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `nestjs-patterns` | skill | NestJS architecture patterns for modules, controllers, providers, DTO validation, guards, interceptors, config, and production-grade TypeScript backends. Use wh (`skills/nestjs-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `nuxt4-patterns` | skill | Nuxt 4 app patterns for hydration safety, performance, route rules, lazy loading, and SSR-safe data fetching with useFetch and useAsyncData. Use when building o (`skills/nuxt4-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `perl-patterns` | skill | Modern Perl 5.36+ idioms, best practices, and conventions for building robust, maintainable Perl applications. Use when writing or reviewing modern Perl 5.36+ c (`skills/perl-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `perl-security` | skill | Comprehensive Perl security covering taint mode, input validation, safe process execution, DBI parameterized queries, web security (XSS/SQLi/CSRF), and perlcrit (`skills/perl-security/SKILL.md`) | Đã cài |  | Không |  |
| `perl-testing` | skill | Perl testing patterns using Test2::V0, Test::More, prove runner, mocking, coverage with Devel::Cover, and TDD methodology. Use when writing Perl tests with Test (`skills/perl-testing/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `quarkus-patterns` | skill | Quarkus 3.x LTS architecture patterns with Camel for messaging, RESTful API design, CDI services, data access with Panache, and async processing. Use for Java Q (`skills/quarkus-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `quarkus-security` | skill | Quarkus security implementation patterns: JWT and OIDC authentication, @RolesAllowed RBAC and SecurityIdentity checks, Bean Validation and custom validators, pa (`skills/quarkus-security/SKILL.md`) | Đã cài |  | Không |  |
| `quarkus-tdd` | skill | Test-driven development for Quarkus 3.x LTS using JUnit 5, Mockito, REST Assured, Camel testing, and JaCoCo. Use when adding features, fixing bugs, or refactori (`skills/quarkus-tdd/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `quarkus-verification` | skill | Verification loop for Quarkus projects: build, static analysis (Checkstyle, PMD, SpotBugs), tests with JaCoCo coverage, OWASP dependency and container security  (`skills/quarkus-verification/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `rails-patterns` | skill | Ruby on Rails framework patterns for Rails 7.1+ and 8.x apps. Covers the directory contract, skinny controllers with service objects, form objects, query object (`skills/rails-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `react-native-patterns` | skill | React Native and Expo app patterns — Expo Router navigation, state separation (server/client/route/form), TanStack Query data fetching with Zod, performant list (`skills/react-native-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `rust-patterns` | skill | Idiomatic Rust patterns, ownership, error handling, traits, concurrency, and best practices for building safe, performant applications. Use when writing or revi (`skills/rust-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `rust-testing` | skill | Rust testing patterns including unit tests, integration tests, async testing, property-based testing, mocking, and coverage. Follows TDD methodology. Use when w (`skills/rust-testing/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `springboot-patterns` | skill | Spring Boot architecture patterns, REST API design, layered services, data access, caching, async processing, and logging. Use for Java Spring Boot backend work (`skills/springboot-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `springboot-security` | skill | Spring Security best practices for authn/authz, validation, CSRF, secrets, headers, rate limiting, and dependency security in Java Spring Boot services. Use whe (`skills/springboot-security/SKILL.md`) | Đã cài |  | Không |  |
| `springboot-tdd` | skill | Test-driven development for Spring Boot using JUnit 5, Mockito, MockMvc, Testcontainers, and JaCoCo. Use when adding features, fixing bugs, or refactoring. (`skills/springboot-tdd/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `springboot-verification` | skill | Run the full Spring Boot verification loop — Maven or Gradle build, SpotBugs, PMD, and Checkstyle static analysis, unit and Testcontainers integration tests wit (`skills/springboot-verification/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `swift-actor-persistence` | skill | Thread-safe data persistence in Swift using actors — in-memory cache with file-backed storage, eliminating data races by design. Use when persisting data in Swi (`skills/swift-actor-persistence/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `swift-concurrency-6-2` | skill | Swift 6.2 Approachable Concurrency — single-threaded by default, @concurrent for explicit background offloading, isolated conformances for main actor types. Use (`skills/swift-concurrency-6-2/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `swift-protocol-di-testing` | skill | Protocol-based dependency injection for testable Swift code — mock file system, network, and external APIs using focused protocols and Swift Testing. Use when S (`skills/swift-protocol-di-testing/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `swiftui-patterns` | skill | SwiftUI architecture patterns, state management with @Observable, view composition, navigation, performance optimization, and modern iOS/macOS UI best practices (`skills/swiftui-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `tinystruct-patterns` | skill | Expert guidance for developing with the tinystruct Java framework. Use when working on the tinystruct codebase or any project built on tinystruct — including ge (`skills/tinystruct-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `ui-to-vue` | skill | Use when the user has UI screenshots or design exports that need batch conversion into Vue 3 components, especially with Vant, Element Plus, or Ant Design Vue. (`skills/ui-to-vue/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `vue-patterns` | skill | Vue.js 3 Composition API patterns, component architecture, reactivity best practices, Pinia state management, Vue Router navigation, and Nuxt SSR patterns. Acti (`skills/vue-patterns/SKILL.md`) | Chỉ trong ECC |  | Không |  |

## 91 Business / content / marketing

| Tên | Loại | Mô tả (từ file) | Trạng thái cài | Phụ thuộc | Áp dụng XAU EDGE | Đọc sâu |
|---|---|---|---|---|---|---|
| `chief-of-staff` | agent | Personal communication chief of staff that triages email, Slack, LINE, and Messenger. Classifies messages into 4 tiers (skip/info_only/meeting_info/action_requi (`agents/chief-of-staff.md`) | Đã cài |  | Không |  |
| `marketing-agent` | agent | Marketing strategist and copywriter for campaign planning, audience research, positioning, copy creation, and content review. Covers landing pages, email sequen (`agents/marketing-agent.md`) | Đã cài |  | Không |  |
| `opensource-forker` | agent | Fork any project for open-sourcing. Copies files, strips secrets and credentials (20+ patterns), replaces internal references with placeholders, generates .env. (`agents/opensource-forker.md`) | Đã cài |  | Không |  |
| `opensource-packager` | agent | Generate complete open-source packaging for a sanitized project. Produces CLAUDE.md, setup.sh, README.md, LICENSE, CONTRIBUTING.md, and GitHub issue templates.  (`agents/opensource-packager.md`) | Đã cài |  | Không |  |
| `opensource-sanitizer` | agent | Verify an open-source fork is fully sanitized before release. Scans for leaked secrets, PII, internal references, and dangerous files using 20+ regex patterns.  (`agents/opensource-sanitizer.md`) | Đã cài |  | Không |  |
| `seo-specialist` | agent | SEO specialist for technical SEO audits, on-page optimization, structured data, Core Web Vitals, and content/keyword mapping. Use for site audits, meta tag revi (`agents/seo-specialist.md`) | Đã cài |  | Không |  |
| `jira` | command | Retrieve a Jira ticket, analyze requirements, update status, or add comments. Uses the jira-integration skill and MCP or REST API. (`commands/jira.md`) | Đã cài | Jira API | Không |  |
| `marketing-campaign` | command | Plan and execute a full marketing campaign. Accepts a product brief and returns positioning, landing page copy, email sequence, social posts, ad variants, video (`commands/marketing-campaign.md`) | Đã cài |  | Không |  |
| `article-writing` | skill | Write articles, guides, blog posts, tutorials, newsletter issues, and other long-form content in a distinctive voice derived from supplied examples or brand gui (`skills/article-writing/SKILL.md`) | Chỉ Codex tree |  | Không |  |
| `benchmark-methodology` | skill | Score a scoped competitor set into comparable profile cards: nine weighted dimensions (positioning, voice, visual craft, offer packaging, evidence, enterprise-r (`skills/benchmark-methodology/SKILL.md`) | Chỉ Codex tree |  | Không | ✔ |
| `brand-discovery` | skill | Run a structured, resumable multi-session brand identity interview across 8 modules (purpose, positioning, audience, personality, voice, narrative, founder tens (`skills/brand-discovery/SKILL.md`) | Chỉ Codex tree |  | Không |  |
| `brand-voice` | skill | Build a source-derived writing style profile from real posts, essays, launch notes, docs, or site copy, then reuse that profile across content, outreach, and so (`skills/brand-voice/SKILL.md`) | Chỉ Codex tree |  | Không |  |
| `competitive-platform-analysis` | skill | Use when scoping a competitive landscape — identifying, categorising, and score-filtering a competitor set before any benchmarking begins. Decides who counts as (`skills/competitive-platform-analysis/SKILL.md`) | Chỉ Codex tree |  | Không |  |
| `competitive-report-structure` | skill | Assemble scored competitor profile cards (from benchmark-methodology) into a decision-grade competitive report with landscape map, competitor tiers, benchmarkin (`skills/competitive-report-structure/SKILL.md`) | Chỉ Codex tree |  | Không |  |
| `connections-optimizer` | skill | Reorganize the user's X and LinkedIn network with review-first pruning, add/follow recommendations, and channel-specific warm outreach drafted in the user's rea (`skills/connections-optimizer/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `content-engine` | skill | Create platform-native content systems for X, LinkedIn, TikTok, YouTube, newsletters, and repurposed multi-platform campaigns. Use when the user wants social po (`skills/content-engine/SKILL.md`) | Chỉ Codex tree |  | Không |  |
| `crosspost` | skill | Multi-platform content distribution across X, LinkedIn, Threads, and Bluesky. Adapts content per platform using content-engine patterns. Never posts identical c (`skills/crosspost/SKILL.md`) | Chỉ Codex tree |  | Không |  |
| `customer-billing-ops` | skill | Operate customer billing workflows such as subscriptions, refunds, churn triage, billing-portal recovery, and plan analysis using connected billing tools like S (`skills/customer-billing-ops/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `email-ops` | skill | Evidence-first mailbox triage, drafting, send verification, and sent-mail-safe follow-up workflow for ECC. Use when the user wants to organize email, draft or s (`skills/email-ops/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `esign-field-placement` | skill | Deterministic method for placing signature, date, and text fields in a web e-signature composer through a browser automation session, using a fixed signature pa (`skills/esign-field-placement/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `finance-billing-ops` | skill | Evidence-first revenue, pricing, refunds, team-billing, and billing-model truth workflow for ECC. Use when the user wants a sales snapshot, pricing comparison,  (`skills/finance-billing-ops/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `frontend-slides` | skill | Create stunning, animation-rich HTML presentations from scratch or by converting PowerPoint files. Use when the user wants to build a presentation, convert a PP (`skills/frontend-slides/SKILL.md`) | Chỉ Codex tree |  | Không |  |
| `google-workspace-ops` | skill | Operate across Google Drive, Docs, Sheets, and Slides as one workflow surface for plans, trackers, decks, and shared documents. Use when the user needs to find, (`skills/google-workspace-ops/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `investor-materials` | skill | Create and update pitch decks, one-pagers, investor memos, accelerator applications, financial models, and fundraising materials. Use when the user needs invest (`skills/investor-materials/SKILL.md`) | Chỉ Codex tree |  | Không |  |
| `investor-outreach` | skill | Draft cold emails, warm intro blurbs, follow-ups, update emails, and investor communications for fundraising. Use when the user wants outreach to angels, VCs, s (`skills/investor-outreach/SKILL.md`) | Chỉ Codex tree |  | Không |  |
| `jira-integration` | skill | Use this skill when retrieving Jira tickets, analyzing requirements, updating ticket status, adding comments, or transitioning issues. Provides Jira API pattern (`skills/jira-integration/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `lead-intelligence` | skill | AI-native lead intelligence and outreach pipeline. Replaces Apollo, Clay, and ZoomInfo with agent-powered signal scoring, mutual ranking, warm path discovery, s (`skills/lead-intelligence/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `mailtrap-email-integration` | skill | Guides agents through integrating transactional email sending via Mailtrap's Email API, including sandbox testing, domain verification, and API authentication.  (`skills/mailtrap-email-integration/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `marketing-campaign` | skill | End-to-end marketing campaign planning and execution. Covers audience research, positioning, campaign angle definition, landing page copy, email sequences, soci (`skills/marketing-campaign/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `master-agreement-generator` | skill | Generate review drafts of counterparty master agreements from one template plus a JSON spec, with role-selected clauses and a Schedule A workflow limited to the (`skills/master-agreement-generator/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `messages-ops` | skill | Evidence-first live messaging workflow for ECC. Use when the user wants to read texts or DMs, recover a recent one-time code, inspect a thread before replying,  (`skills/messages-ops/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `nutrient-document-processing` | skill | Process, convert, OCR, extract, redact, sign, and fill documents using the Nutrient DWS API. Works with PDFs, DOCX, XLSX, PPTX, HTML, and images. Use when conve (`skills/nutrient-document-processing/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `opensource-pipeline` | skill | Open-source pipeline: fork, sanitize, and package private projects for safe public release. Chains 3 agents (forker, sanitizer, packager). Triggers: '/opensourc (`skills/opensource-pipeline/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `seo` | skill | Audit, plan, and implement SEO improvements across technical SEO, on-page optimization, structured data, Core Web Vitals, and content strategy. Use when the use (`skills/seo/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `social-graph-ranker` | skill | Weighted social-graph ranking for warm intro discovery, bridge scoring, and network gap analysis across X and LinkedIn. Use when the user wants the reusable gra (`skills/social-graph-ranker/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `social-publisher` | skill | Agent-driven scheduling and publishing of social media posts across 13 platforms via SocialClaw. Use when the user wants to publish to X, LinkedIn, Instagram, F (`skills/social-publisher/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `unified-notifications-ops` | skill | Operate notifications as one ECC-native workflow across GitHub, Linear, desktop alerts, hooks, and connected communication surfaces. Use when the real problem i (`skills/unified-notifications-ops/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `visa-doc-translate` | skill | Translate visa document images (bank deposit, employment, income, and retirement certificates; HEIC, PNG, or JPG) into English via OCR and produce a bilingual P (`skills/visa-doc-translate/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `x-api` | skill | X/Twitter API integration for posting tweets, threads, reading timelines, search, and analytics. Covers OAuth auth patterns, rate limits, and platform-native co (`skills/x-api/SKILL.md`) | Chỉ Codex tree |  | Không |  |

## 92 Domain khác (không liên quan trading XAU)

| Tên | Loại | Mô tả (từ file) | Trạng thái cài | Phụ thuộc | Áp dụng XAU EDGE | Đọc sâu |
|---|---|---|---|---|---|---|
| `healthcare-reviewer` | agent | Reviews healthcare application code for clinical safety, CDSS accuracy, PHI compliance, and medical data integrity. Specialized for EMR/EHR, clinical decision s (`agents/healthcare-reviewer.md`) | Đã cài |  | Không |  |
| `homelab-architect` | agent | Designs home and small-lab network plans from hardware inventory, goals, and operator experience level, with safe staged changes and rollback guidance. (`agents/homelab-architect.md`) | Đã cài |  | Không |  |
| `network-architect` | agent | Designs enterprise or multi-site network architecture from requirements, using existing network skills for focused routing, validation, automation, and troubles (`agents/network-architect.md`) | Đã cài |  | Không |  |
| `network-config-reviewer` | agent | Reviews router and switch configurations for security, correctness, stale references, risky change-window commands, and missing operational guardrails. (`agents/network-config-reviewer.md`) | Đã cài |  | Không |  |
| `network-troubleshooter` | agent | Diagnoses network connectivity, routing, DNS, interface, and policy symptoms with a read-only OSI-layer workflow and evidence-backed root cause summary. (`agents/network-troubleshooter.md`) | Đã cài |  | Không |  |
| `agent-payment-x402` | skill | Add x402 payment execution to AI agents with per-task budgets, spending controls, and non-custodial wallets. Supports Base through agentwallet-sdk, X Layer thro (`skills/agent-payment-x402/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `blender-motion-state-inspection` | skill | Use this skill when inspecting Blender characters, rigs, poses, animation retargeting, ground contact, facing direction, or model-vs-motion alignment where scre (`skills/blender-motion-state-inspection/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `carrier-relationship-management` | skill | Manage truckload, LTL, and intermodal carrier portfolios: sourcing and FMCSA vetting, freight rate and fuel-surcharge negotiation, RFPs and routing guides, carr (`skills/carrier-relationship-management/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `customs-trade-compliance` | skill | Codified customs and trade compliance expertise — HS/HTS tariff classification with GRI rules, commercial invoices and entry documentation, Incoterms 2020, FTA  (`skills/customs-trade-compliance/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `data-scraper-agent` | skill | Build a fully automated AI-powered data collection agent for any public source — job boards, prices, news, GitHub, sports, anything. Runs on a schedule, enriche (`skills/data-scraper-agent/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `defi-amm-security` | skill | Security checklist for Solidity AMM contracts, liquidity pools, and swap flows. Covers reentrancy, CEI ordering, donation or inflation attacks, oracle manipulat (`skills/defi-amm-security/SKILL.md`) | Đã cài |  | Không |  |
| `energy-procurement` | skill | Procure electricity and natural gas for commercial and industrial facilities: tariff and rate-schedule optimization, demand-charge mitigation, supplier RFPs, fi (`skills/energy-procurement/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `evm-token-decimals` | skill | Prevent silent decimal mismatch bugs across EVM chains. Covers runtime decimal lookup, chain-aware caching, bridged-token precision drift, and safe normalizatio (`skills/evm-token-decimals/SKILL.md`) | Đã cài |  | Không |  |
| `fal-ai-media` | skill | Unified media generation via fal.ai MCP — image, video, and audio. Covers text-to-image (Nano Banana), text/image-to-video (Seedance, Kling, Veo 3), text-to-spe (`skills/fal-ai-media/SKILL.md`) | Chỉ Codex tree |  | Không |  |
| `healthcare-cdss-patterns` | skill | Clinical Decision Support System (CDSS) development patterns. Drug interaction checking, dose validation, clinical scoring (NEWS2, qSOFA), alert severity classi (`skills/healthcare-cdss-patterns/SKILL.md`) | Đã cài |  | Không |  |
| `healthcare-emr-patterns` | skill | EMR/EHR development patterns for healthcare applications. Clinical safety, encounter workflows, prescription generation, clinical decision support integration,  (`skills/healthcare-emr-patterns/SKILL.md`) | Đã cài |  | Không |  |
| `healthcare-eval-harness` | skill | Patient safety evaluation harness for healthcare application deployments. Automated test suites for CDSS accuracy, PHI exposure, clinical workflow integrity, an (`skills/healthcare-eval-harness/SKILL.md`) | Đã cài |  | Không |  |
| `healthcare-phi-compliance` | skill | Protected Health Information (PHI) and PII compliance patterns for healthcare applications: data classification, row-level access control, tamper-proof audit tr (`skills/healthcare-phi-compliance/SKILL.md`) | Đã cài |  | Không |  |
| `hipaa-compliance` | skill | HIPAA-specific entrypoint for healthcare privacy and security work. Use when a task is explicitly framed around HIPAA, PHI handling, covered entities, BAAs, bre (`skills/hipaa-compliance/SKILL.md`) | Đã cài |  | Không |  |
| `homelab-network-readiness` | skill | Readiness checklist for homelab VLAN segmentation, local DNS filtering (Pi-hole, AdGuard Home), and WireGuard-style remote access. Use when planning or reviewin (`skills/homelab-network-readiness/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `homelab-network-setup` | skill | Practical home and homelab network planning for gateways, switches, access points, IP ranges, DHCP reservations, DNS, cabling, and common beginner mistakes. Use (`skills/homelab-network-setup/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `homelab-pihole-dns` | skill | Pi-hole installation, blocklist management, DNS-over-HTTPS setup, DHCP integration, local DNS records, and troubleshooting broken DNS resolution on a home netwo (`skills/homelab-pihole-dns/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `homelab-vlan-segmentation` | skill | Segmenting home networks into VLANs for IoT, guest, trusted, and server traffic using UniFi, pfSense/OPNsense, and MikroTik — including switch trunk config, fir (`skills/homelab-vlan-segmentation/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `homelab-wireguard-vpn` | skill | WireGuard VPN server setup, peer configuration, key generation, split tunneling vs full tunnel routing, and remote access to a home network from mobile and lapt (`skills/homelab-wireguard-vpn/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `inventory-demand-planning` | skill | Codified demand planning expertise for multi-location retailers: demand forecasting method selection, ABC/XYZ segmentation, safety stock and reorder-point optim (`skills/inventory-demand-planning/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `ito-baskets` | skill | Read-only Itô basket and prediction-market data skill. Index the live basket catalog, compare a basket against user-supplied research or a watchlist, build a so (`skills/ito-baskets/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `ito-compute` | skill | Query live GPU inventory, submit an authenticated Itô fixed-rate RFQ, inspect RFQ or procurement status, revoke device credentials, and run explicitly gated nod (`skills/ito-compute/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `ito-inference` | skill | Inspect the availability of model serving on a completed Itô compute booking and, when the canonical backend becomes available, hand off an explicitly confirmed (`skills/ito-inference/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `ito-training` | skill | Inspect the availability of ML training on a completed Itô compute booking and, when the canonical backend becomes available, hand off an explicitly confirmed t (`skills/ito-training/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `logistics-exception-management` | skill | Codified freight-exception handling expertise for shipment delays, damages, losses, shortages, and carrier disputes, with escalation protocols, carrier-specific (`skills/logistics-exception-management/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `manim-video` | skill | Build reusable Manim explainers for technical concepts, graphs, system diagrams, and product walkthroughs, then hand off to the wider ECC video stack if needed. (`skills/manim-video/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `netmiko-ssh-automation` | skill | Safe Python Netmiko patterns for read-only collection, bounded batch SSH, TextFSM parsing, guarded config changes, timeouts, and network automation error handli (`skills/netmiko-ssh-automation/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `network-bgp-diagnostics` | skill | Diagnostics-only BGP troubleshooting patterns for neighbor state, route exchange, prefix policy, AS path inspection, and safe evidence collection. Use when a BG (`skills/network-bgp-diagnostics/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `network-config-validation` | skill | Pre-deployment checks for router and switch configuration, including dangerous commands, duplicate addresses, subnet overlaps, stale references, management-plan (`skills/network-config-validation/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `network-interface-health` | skill | Diagnose interface errors, drops, CRCs, duplex mismatches, flapping, speed negotiation issues, and counter trends on routers, switches, and Linux hosts. Use whe (`skills/network-interface-health/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `nodejs-keccak256` | skill | Prevent Ethereum hashing bugs in JavaScript and TypeScript. Node's sha3-256 is NIST SHA3, not Ethereum Keccak-256, and silently breaks selectors, signatures, st (`skills/nodejs-keccak256/SKILL.md`) | Đã cài |  | Không |  |
| `osint-investigation` 🆕 | skill | Sparse-clue OSINT investigation methodology for extracting overlooked leads, connecting fragmented evidence, and testing explanations across sources. Use for mu (`skills/osint-investigation/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `prediction-market-oracle-research` | skill | Research prediction markets as data sources or oracle signals for products, agents, dashboards, and corporate decision intelligence. Use for source-grounded ana (`skills/prediction-market-oracle-research/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `production-scheduling` | skill | Codified expertise for production scheduling, job sequencing, line balancing, changeover optimization, and bottleneck resolution in discrete and batch manufactu (`skills/production-scheduling/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `quality-nonconformance` | skill | Quality control and non-conformance management for regulated manufacturing (FDA 21 CFR 820, IATF 16949, AS9100): NCR lifecycle and disposition, 5-Why/Ishikawa/f (`skills/quality-nonconformance/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `remotion-video-creation` | skill | Best practices for Remotion - Video creation in React. 29 domain-specific rules covering 3D, animations, audio, captions, charts, transitions, and more. Use whe (`skills/remotion-video-creation/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `returns-reverse-logistics` | skill | Codified expertise for returns authorization, receipt and inspection, disposition decisions, refund processing, fraud detection, and warranty claims management. (`skills/returns-reverse-logistics/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `scientific-db-pubmed-database` | skill | Direct PubMed and NCBI E-utilities search workflows for biomedical literature, MeSH queries, PMID lookup, citation retrieval, and API-backed literature monitori (`skills/scientific-db-pubmed-database/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `scientific-db-uspto-database` | skill | USPTO patent and trademark data workflow for official record lookup, PatentSearch queries, TSDR checks, assignment data, and reproducible IP research logs. Use  (`skills/scientific-db-uspto-database/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `scientific-pkg-gget` | skill | gget CLI and Python workflow for quick genomic database queries, sequence lookup, BLAST-style searches, enrichment checks, and reproducible bioinformatics evide (`skills/scientific-pkg-gget/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `taste` | skill | Creative-direction layer for music videos and short-form edits in the angelcore / cloud-trance / hyperpop family — a named-genre aesthetic vocabulary, mood + co (`skills/taste/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `taste-application` | skill | Generate new video against a distilled style pack and cut it into a finished piece - plan takes from the reference's cut rhythm, generate on fal, grade with the (`skills/taste-application/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `taste-distillation` | skill | Measure a set of reference videos into a reusable style pack - colour grade as a 3D LUT, cut rhythm as a shot-length distribution, hero stills, screen-blend ove (`skills/taste-distillation/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `tasteforge-video` | skill | Use for file-driven multimodal image, video, and 3D-asset discovery; taste interviews; distill or apply workflows; style-pack validation; editable EDL/FCPXML ex (`skills/tasteforge-video/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `terminal-opener` | skill | Open an executable and its argument array in a visible terminal window through a reusable, shell-free launch plan with dry-run, JSON, capability detection, deta (`skills/terminal-opener/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `ui-demo` | skill | Record polished UI demo videos using Playwright. Use when the user asks to create a demo, walkthrough, screen recording, or tutorial video of a web application. (`skills/ui-demo/SKILL.md`) | Chỉ trong ECC |  | Không |  |
| `video-editing` | skill | AI-assisted video editing workflows for cutting, structuring, and augmenting real footage. Covers the full pipeline from raw capture through FFmpeg, Remotion, E (`skills/video-editing/SKILL.md`) | Chỉ Codex tree |  | Không |  |
| `videodb` | skill | Ingest, index, search, edit, and monitor video and audio with the VideoDB Python SDK — upload from files, URLs, or RTSP feeds, build spoken and scene indexes wi (`skills/videodb/SKILL.md`) | Chỉ trong ECC |  | Không |  |

## Các lớp khác của ECC (không phải skill/agent/command/rule)

- **hooks/** (6): `README.md`, `codex-hooks.json`, `hermes`, `hooks.json`, `hooks.metadata.json`, `memory-persistence`
- **scripts/** (63): `auto-update.js`, `build-opencode.js`, `build-pi-core.js`, `catalog.js`, `ci`, `claw.js`, `codemaps`, `codex`, `codex-git-hooks`, `consult.js`, `control-pane.js`, `coordination-inventory.js`, `dashboard-web.js`, `dev`, `discord`, `discussion-audit.js`, `doctor.js`, `ecc.js`, `eval-harness.js`, `feedback.js`, `gan-harness.sh`, `gemini-adapt-agents.js`, `github-coordination.js`, `harness-adapter-compliance.js`, `harness-audit.js`, `hooks`, `install-apply.js`, `install-guided.js`, `install-plan.js`, `ito.js`, `lib`, `list-installed.js`, `loop-status.js`, `mcp-inventory.js`, `memory-mcp.mjs`, `memory.js`, `nasiko.js`, `observability-readiness.js`, `operator-readiness-dashboard.js`, `orchestrate-codex-worker.sh`, `orchestrate-worktrees.js`, `orchestration-status.js`, `plan-canvas.js`, `platform-audit.js`, `preview-pack-smoke.js`, `profile.js`, `proximity-tick.js`, `release-approval-gate.js`, `release-video-suite.js`, `release.sh`, `repair.js`, `session-inspect.js`, `sessions-cli.js`, `setup-package-manager.js`, `setup.js`, `skill-create-output.js`, `skills-health.js`, `status.js`, `sync-ecc-to-codex.sh`, `uninstall.js`, `welcome.js`, `work-items.js`, `worktree-lifecycle.js`
- **schemas/** (16): `capsule-envelope.schema.json`, `context-carrier.schema.json`, `context-pack-registry.schema.json`, `context-profile.schema.json`, `ecc-install-config.schema.json`, `hooks-metadata.schema.json`, `hooks.schema.json`, `install-components.schema.json`, `install-modules.schema.json`, `install-profiles.schema.json`, `install-state.schema.json`, `memory.schema.json`, `package-manager.schema.json`, `plugin.schema.json`, `provenance.schema.json`, `state-store.schema.json`
- **manifests/** (7): `context-packs`, `context-profiles`, `install-assets`, `install-components.json`, `install-modules.json`, `install-profiles.json`, `pi-core.json`
- **mcp-configs/** (1): `mcp-servers.json`
- **contexts/** (3): `dev.md`, `research.md`, `review.md`
- **workflows/** (2): `README.md`, `orch-review.workflow.js`
- **examples/** (16): `CLAUDE.md`, `coordination-inventory`, `django-api-CLAUDE.md`, `eval-harness`, `evaluator-rag-prototype`, `gan-harness`, `go-microservice-CLAUDE.md`, `harmonyos-app-CLAUDE.md`, `hud-status-contract.json`, `laravel-api-CLAUDE.md`, `rails-app-CLAUDE.md`, `rust-api-CLAUDE.md`, `saas-nextjs-CLAUDE.md`, `statusline.json`, `unified-memory`, `user-CLAUDE.md`
- **ecc2/** (5): `Cargo.lock`, `Cargo.toml`, `README.md`, `rust-toolchain.toml`, `src`
- **docs/** (55): `ANTIGRAVITY-GUIDE.md`, `ATLAS-CLOUD-GUIDE.md`, `CODEX-NAVIGATION-GUIDE.md`, `COMMAND-AGENT-MAP.md`, `COMMAND-REGISTRY.json`, `ECC-2.0-GA-ROADMAP.md`, `ECC-2.0-REFERENCE-ARCHITECTURE.md`, `ECC-PRO-SECURITY-ROADMAP.md`, `HERMES-HOOKS.md`, `HERMES-OPENCLAW-MIGRATION.md`, `HERMES-SETUP.md`, `ITO-DESK.md`, `JOYCODE-GUIDE.md`, `LANE-RULES.md`, `MANUAL-ADAPTATION-GUIDE.md`, `MCP-CONNECTOR-POLICY.md`, `MIGRATION-1X-TO-2.0.md`, `PLAN-PRD-PATTERN.md`, `QWEN-GUIDE.md`, `ROADMAP.md`, `SELECTIVE-INSTALL-ARCHITECTURE.md`, `SKILL-DEVELOPMENT-GUIDE.md`, `SKILL-PLACEMENT-POLICY.md`, `TROUBLESHOOTING.md`, `architecture`, `bn`, `business`, `capability-surface-selection.md`, `continuous-learning-v2-spec.md`, `control-plane`, `de-DE`, `design`, `drafts`, `es`, `examples`, `fixes`, `hook-bug-workarounds.md`, `ja-JP`, `ko-KR`, `legacy-artifact-inventory.md`, `pl`, `pt-BR`, `releases`, `ru`, `security`, `skill-adaptation-policy.md`, `stale-pr-salvage-ledger.md`, `th`, `token-optimization.md`, `tr`, `uk-UA`, `ur`, `vi-VN`, `zh-CN`, `zh-TW`
- **config/** (2): `github-native-coordination.json`, `project-stack-mappings.json`
- **plugins/** (2): `README.md`, `ecc`
- **integrations/** (1): `aura`
- **scaffolds/** (1): `cursor`
