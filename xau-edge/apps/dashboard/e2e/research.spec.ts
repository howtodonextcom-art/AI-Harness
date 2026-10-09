import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Research console e2e against the production build. The research API (port 8000) and the control
 * proxy are mocked in the browser with page.route; no Python API, no token file, no MT5 is involved.
 */

const NOW = new Date().toISOString();
const GATES_NOT_RUN = {
  cost_stress: { state: "CHƯA CHẠY" },
  parameter_stability: { state: "CHƯA CHẠY" },
  temporal_stability: { state: "CHƯA CHẠY" },
  broker_robustness: { state: "CHƯA CHẠY" },
};

const OVERVIEW = {
  status: "ok",
  generated_at: NOW,
  verdict: { status: "ok", label: "(B) NO EDGE WITHIN BUDGET", source: "docs/research/edge-program/final-verdict.md" },
  v1: {
    status: "ok",
    source: "docs/research/edge-program/ledger.md",
    runs: 36,
    malformed_rows: 0,
    k: 21,
    k_cap: 21,
    alpha: 0.002381,
    hypotheses_used: 6,
    hypotheses_budget: 6,
  },
  v2: { status: "ok", started: false, message: "chưa bắt đầu V2 (cần quyết định D-1 của chủ dự án)", k_cap: 48, hypotheses_budget: 8, source: "docs/research/edge-program-v2/STATE.json" },
  decisions: [
    { id: "D-1", text: "Approve Edge Program V2: budget (<= 8 hypotheses)", recommended: "Yes", state: "pending" },
    { id: "D-4", text: "Do not use the UNVALIDATED override for profit; at most for demo plumbing", recommended: "Yes", state: "pending" },
  ],
  stop_conditions_reached: ["V1: đã dùng hết ngân sách giả thuyết", "V1: K chạm trần"],
  validated_strategies: [],
  banner: "Không có edge được kiểm định.",
  sources: ["docs/research/edge-program/final-verdict.md", "docs/PROFITABILITY_ROADMAP.md"],
};

const LEDGER = {
  status: "ok",
  source: "docs/research/edge-program/ledger.md",
  programme: "v1",
  k: 21,
  k_cap: 21,
  alpha: 0.002381,
  malformed_rows: 0,
  total_runs: 3,
  shown: 3,
  verdicts: { FAIL: 3 },
  legacy_k: { baselines: 3, programme_1: 21 },
  runs: [
    { number: 1, time: "2026-10-08 14:50:34 UTC", variant: "H01-theta0.3", hypothesis: "H01", period: "dev-H", scenario: "base + bi quan", trades: 2727, mean_net_r_base: -0.0812, mean_net_r_pessimistic: -0.0933, verdict: "FAIL", registry_id: "1eb8c293cfe9074f", note: "" },
    { number: 2, time: "2026-10-08 14:50:38 UTC", variant: "H02-b0.0", hypothesis: "H02", period: "dev-H", scenario: "base + bi quan", trades: 1714, mean_net_r_base: -0.0595, mean_net_r_pessimistic: -0.0736, verdict: "FAIL", registry_id: "0c53b7e69ff4fce1", note: "" },
    { number: 3, time: "2026-10-08 14:51:00 UTC", variant: "H02-b0.0", hypothesis: "H02", period: "val-H", scenario: "base + bi quan", trades: 600, mean_net_r_base: -0.05, mean_net_r_pessimistic: -0.07, verdict: "FAIL", registry_id: "aa53b7e69ff4fce1", note: "" },
  ],
};

const HYPOTHESES = {
  status: "ok",
  source: "docs/research/edge-program/hypotheses, docs/research/edge-program/ledger.md",
  violations: ["H02"],
  planned: [{ id: "H11", name: "Overnight gap fade", batch: "B" }],
  hypotheses: [
    {
      id: "H01",
      programme: "V1",
      title: "H01: Động lượng ở giờ mở phiên",
      registered: "Đăng ký: 2026-10-08.",
      grid: "**Lưới.** `theta` in {0.3, 0.6, 0.9}.",
      path: "docs/research/edge-program/hypotheses/H01.md",
      results: { runs: 6, variants: 3, any_pass: false, best_pessimistic_min: { variant: "H01-theta0.3", value: -0.0933 } },
      preregistration: { state: "OK", detail: "đăng ký trước kết quả", registered_at: "2026-10-08T14:26:25+00:00", first_run_at: "2026-10-08T14:50:34+00:00" },
      registration: { status: "legacy", reason: "chương trình V1 không có sidecar" },
      registration_commit: { commit: "aaaaaaaa1111", time: "2026-10-08T14:26:25+00:00", unknown_reason: "" },
      first_result_commit: { commit: "bbbbbbbb2222", time: "2026-10-08T14:50:34+00:00" },
    },
    {
      id: "H02",
      programme: "V1",
      title: "H02: Phá vỡ biên độ Asia",
      registered: "Đăng ký: 2026-10-08.",
      grid: "**Lưới.** `b` in {0.0, 0.25}.",
      path: "docs/research/edge-program/hypotheses/H02.md",
      results: { runs: 4, variants: 2, any_pass: false, best_pessimistic_min: null },
      preregistration: { state: "VIOLATION", detail: "VI PHẠM ĐĂNG KÝ TRƯỚC: file giả thuyết được commit SAU lần chạy đầu tiên" },
      registration: { status: "legacy", reason: "chương trình V1 không có sidecar" },
      registration_commit: { commit: null, time: null, unknown_reason: "không có git" },
      first_result_commit: { commit: null, time: null },
    },
    {
      id: "H07",
      programme: "V2",
      title: "H07: Quét thanh khoản rồi đảo chiều",
      registered: "Đăng ký: 2026-10-09.",
      grid: "**Lưới.** `e` in {0, 0.25, 0.5}.",
      path: "docs/research/edge-program-v2/hypotheses/H07.md",
      results: { runs: 3, variants: 3, any_pass: false, best_pessimistic_min: null },
      preregistration: { state: "OK", detail: "đăng ký trước kết quả", registered_at: "2026-10-09T01:00:00+00:00", first_run_at: "2026-10-09T01:51:00+00:00" },
      registration: {
        status: "ok",
        source: "docs/research/edge-program-v2/hypotheses/H07.registration.json",
        evidence_class: "DESCRIPTIVE",
        expected_event_count: 2142,
        effective_event_count_estimate: 1900,
        expected_sd: 1.3,
        k_at_registration: 20,
        power_target: 0.8,
        mde_raw: 0.1025,
        mde_effective: 0.1088,
        underpowered_by_design: false,
        required_effective_n_for_target: 2250,
        parameter_grid: { entry: ["ASIA", "PD"], e: [0, 0.25, 0.5] },
        variant_ids: ["H07-ASIA-e0", "H07-ASIA-e0.25", "H07-PD-e0"],
        variant_count: 3,
        dropped_variants: ["H07-PD-e0.5"],
        economic_rationale: "Stop hunting quanh đỉnh/đáy phiên có thể để lại lệnh một chiều.",
        mechanism_status: "HYPOTHESIZED",
        observed_pattern: "Giá thường đảo chiều sau khi quét đỉnh phiên Á (mô tả).",
        hypothesized_explanation: "Lệnh dừng bị kích hoạt tạo thanh khoản cho bên đối ứng (CHƯA kiểm chứng).",
        falsification_condition: "Bác bỏ nếu mean net R CI95 chứa 0 trên Test-H với N hiệu dụng đủ.",
        problems: [],
      },
      registration_commit: { commit: "cccccccc3333", time: "2026-10-09T01:00:00+00:00", unknown_reason: "" },
      first_result_commit: { commit: "dddddddd4444", time: "2026-10-09T01:51:00+00:00" },
    },
    {
      id: "H08",
      programme: "V2",
      title: "H08: Biên độ phiên Á",
      registered: "Đăng ký: 2026-10-09.",
      grid: "**Lưới.** `e` in {0}.",
      path: "docs/research/edge-program-v2/hypotheses/H08.md",
      results: { runs: 0, variants: 0, any_pass: false, best_pessimistic_min: null },
      preregistration: { state: "NO_RESULTS", detail: "chưa có kết quả" },
      registration: { status: "unknown", reason: "không có đăng ký có cấu trúc hợp lệ" },
      registration_commit: { commit: null, time: null, unknown_reason: "không có git" },
      first_result_commit: { commit: null, time: null },
    },
  ],
};

const criterion = (passed: boolean, value: number | null, threshold: number) => ({ passed, value, threshold });
const PERIOD = {
  trades: 2727,
  mean_net_r_base: -0.08,
  mean_net_r_pessimistic: -0.09,
  stage_pass: false,
  criteria_passed: 1,
  criteria_total: 7,
  criteria: {
    min_trades: criterion(true, 2727, 100),
    ci_lower_above_zero: criterion(false, -0.13, 0),
    profit_factor: criterion(false, 0.79, 1.2),
    max_drawdown_r: criterion(false, 222.6, 15),
    positive_folds: criterion(false, 0, 3),
    robust_to_best_trades: criterion(false, -0.19, 0),
    no_concentration: criterion(false, null, 0.6),
  },
  metrics: { profit_factor: 0.79 },
  variants_k: 21,
  alpha: 0.00238,
  dataset_ids: { H1: "8e64dd6561015b72" },
  registry_id: "1eb8c293cfe9074f",
  recorded_at: NOW,
};
const BRIEF = { trades: 2727, mean_net_r_base: -0.08, mean_net_r_pessimistic: -0.09, stage_pass: false, criteria_passed: 1, criteria_total: 7 };

const CANDIDATES = {
  status: "ok",
  source: "experiments/edge_program, experiments/edge_program_v2",
  survivors: [],
  note: "Một biến thể chỉ là ứng viên khi qua cả hai giai đoạn; cổng robustness chưa chạy luôn hiện CHƯA CHẠY.",
  variants: [{ variant: "H01-theta0.3", hypothesis: "H01", periods: { dev: BRIEF, val: BRIEF }, survivor: false, gates: GATES_NOT_RUN }],
};

const CANDIDATE = {
  status: "ok",
  variant: "H01-theta0.3",
  hypothesis: "H01",
  periods: { dev: PERIOD, val: PERIOD },
  gates: GATES_NOT_RUN,
  gross_mid_r: null,
  gross_mid_note: "chưa có: cột gross-at-mid thuộc sprint P1 của roadmap",
  equity_curve: null,
  equity_note: "file kết quả không chứa đường vốn",
  sources: ["experiments/edge_program/H01-theta0.3-dev.json"],
};

const issue = (code: string, severity: string, count: number) => ({ code, severity, count });
const DATA = {
  status: "ok",
  source: "docs/research/edge-program/data-manifest.json",
  generated_at: "2026-10-01T14:10:52+00:00",
  frames: [
    { timeframe: "M15", rows: 66720, first: "2022-07-04T22:00:00+00:00", last: "2025-04-30T23:45:00+00:00", dataset_id: "f1480a7251ffce51", validation_passed: true, errors: [], warnings: [issue("MISSING_BARS", "WARNING", 1)] },
    { timeframe: "H1", rows: 91655, first: "2010-01-24T23:00:00+00:00", last: "2025-04-30T23:00:00+00:00", dataset_id: "8e64dd6561015b72", validation_passed: false, errors: [issue("MISSING_BARS", "ERROR", 1003)], warnings: [] },
  ],
  clock_certificate: {
    source: "docs/research/edge-program-v2/clock-certificate.json",
    present: true,
    years: [
      { year: 2010, certified: true, state: "CHỨNG NHẬN", offset: 2 },
      { year: 2011, certified: false, state: "CHƯA CHỨNG NHẬN", offset: null },
    ],
    session_hypotheses_blocked_years: [2011],
    message: "H09 và mọi giả thuyết theo phiên bị chặn ở các năm chưa chứng nhận",
  },
};

const LOCKS = {
  status: "ok",
  source: "experiments/runs",
  registry_records: 71,
  unreadable_records: 0,
  freeze_records: [],
  locks: [
    { id: "dev2", outcome_state: null, name: "Development-2", from: "2011-01-01", to: "2018-12-31", use: "thiết kế, Stage 1", burned: true, state: "ĐÃ DÙNG THIẾT KẾ" },
    { id: "val2", outcome_state: null, name: "Validation-2", from: "2019-01-01", to: "2021-12-31", use: "Stage 1/2", burned: true, state: "ĐÃ DÙNG THIẾT KẾ" },
    { id: "testH", outcome_state: "LOCKED", name: "Test-H", from: "2022-01-01", to: "2025-04-30", use: "xác nhận", burned: false, state: "NGUYÊN VẸN" },
    { id: "holdout", outcome_state: "UNKNOWN", name: "Holdout", from: "2026-05-01", to: "2026-10-07", use: "cuối cùng", burned: false, state: "KHÔNG RÕ" },
    { id: "forward", outcome_state: null, name: "Forward", from: "2026-10-09", to: null, use: "paper rồi demo", burned: false, state: "ĐANG TÍCH LŨY" },
  ],
};

const STRATEGIES = {
  status: "ok",
  source: "data/execution/lifecycle.jsonl",
  states: ["RESEARCH", "REJECTED", "PAPER", "DEMO", "VALIDATED", "FUNDED", "WATCH", "DEGRADED", "DISABLED", "RETIRED"],
  web_rule: "Từ web chỉ được HẠ xuống WATCH, DEGRADED hoặc DISABLED; không nâng bậc.",
  strategies: [
    { strategy_id: "H01-theta0.3", state: "REJECTED", history: [], web_demotable: false },
    { strategy_id: "DEMO-STRAT", state: "DEMO", history: [], web_demotable: true },
  ],
};

const FORWARD = {
  status: "ok",
  source: "data/forward/DEMO-STRAT/summary.json",
  strategy_id: "DEMO-STRAT",
  n_trades: 100,
  legacy_reference_trades: 100,
  legacy_reference_note: "100 lệnh chỉ là mốc tham chiếu cũ, không đủ để kết luận",
  conclusion: "INCONCLUSIVE",
  readiness: {
    conclusion: "INCONCLUSIVE",
    raw_n: 100,
    effective_n: 41.5,
    required_effective_n: 563,
    calendar_days: 20,
    minimum_calendar_days: 90,
    regimes_seen: 1,
    regimes_required: 3,
    power_estimate: 0.12,
    legacy_reference_trades: 100,
    reasons: ["N hiệu dụng 41.5 < 563 cần", "mới 20 ngày lịch (cần 90)"],
  },
  updated_at: NOW,
  decay: null,
  expected_vs_realised: {
    signals_per_week_expected: 5,
    signals_per_week_realised: 3,
    mean_r_expected: { lo: 0.02, hi: 0.2, mean: 0.1 },
    mean_r_realised: -0.05,
    mfe_expected: 1.2,
    mfe_realised: 1.0,
    mae_expected: -0.8,
    mae_realised: -0.9,
    spread_assumed: 20,
    spread_observed: 26,
    slippage_assumed: 3,
    slippage_observed: 4,
    latency_ms: 180,
  },
};

const CALIBRATION = {
  status: "unknown",
  source: "data/execution/calibration.json",
  assumed: { slippage_points: 3, commission_per_lot_per_side: 0, swap_long_points: -76.05, swap_short_points: -4.2 },
  measured: null,
  message: "chưa đo chi phí thật (sprint P12); các số trên là GIẢ ĐỊNH",
};

const SOAK = {
  status: "ok",
  source: "data/execution/cycles.jsonl",
  cycles: 8,
  decided_bars: 6,
  duplicate_bars: 2,
  expected_bars: 6,
  uptime_m15: 1,
  days_covered: 0.05,
  target: { soak_days: 14, uptime_min: 0.99, duplicates_max: 0, demo_weeks: 4 },
  alerts: { lines: 2 },
  funded_rules: { status: "ok", source: "configs/prop/ftmo_funded.yaml", pending: ["daily_loss_limit_pct", "news_trading_window"], total: 14 },
};

const PROVENANCE = { generated_at: "2026-10-09T02:00:00+00:00", code_commit: "0beba0c1d2e3" };

const LABELS_REFUSED = {
  VALIDATED: { allowed: false, reasons: ["evidence class SCREENING không đủ để gắn nhãn VALIDATED", "thiếu Test-H"] },
  ADEQUATELY_POWERED: { allowed: true, reasons: [] },
  REPRODUCIBLE: { allowed: false, reasons: ["manifest chưa được xác minh"] },
};

const stage1Row = (name: string, i: number) => ({
  variant: name,
  hypothesis: name.slice(0, 3),
  window: "dev2",
  evidence_class: "SCREENING",
  k: 20,
  alpha_bonferroni: 0.0025,
  n_events: 2142 - i,
  n_effective: 2100 - i,
  unique_days: 1502,
  mean_gross_mid_r: -0.1439,
  mean_net_base_r: -0.2821 + i * 0.001,
  mean_net_pess_r: -0.2993,
  ci95_net_base: [-0.3352, -0.2281],
  p_value_one_sided: 1.0,
  survivor: false,
  mde_effective: 0.1025,
  adequately_powered: true,
  dependence_status: "DEPENDENCE_STABLE",
  intrabar_status: "INTRABAR_ROBUST",
  era_status: "UNKNOWN",
  attribution: {
    observed_mean_r: -0.2821,
    direction_edge: -0.1227,
    timing_edge: 0.0682,
    drift_exposure: -0.0674,
    counterfactuals: [
      { name: "B random direction (expected)", mean_r: -0.1594, incremental_r: -0.1227, ci_low: -0.1723, ci_high: -0.0732, effect_size: -0.1025 },
      { name: "C always long", mean_r: -0.2268, incremental_r: -0.0554, ci_low: -0.1305, ci_high: 0.0198, effect_size: -0.0322 },
    ],
    note: "descriptive decomposition from paired differences; not a causal claim",
  },
  placebo: { kind: "same-hour random timestamps, random direction", real: -0.2821, median: -0.2292, p95: -0.1819, p99: -0.1534, empirical_percentile: 0.039, draws: 1000 },
  by_year: { "2011": { n: 217, mean_net_base_r: -0.2282 }, "2012": { n: 283, mean_net_base_r: -0.2572 } },
  dataset_ids: { H1: "8e64dd6561015b72", H4: "b438f1794bd11402" },
  code_commit_sha: "09cc1281a9c703786c043674fa6fcac113f329e7",
  experiment_id: "879964467ba6f8b886eff278fb84d61b",
  manifest_verified: true,
  provenance: "REPRODUCIBLE",
  recorded_at: "2026-10-09T01:51:56+00:00",
  labels: LABELS_REFUSED,
});
const STAGE1_NAMES = [
  ...["ASIA-e0", "ASIA-e0.25", "ASIA-e0.5", "PD-e0", "PD-e0.25", "PD-e0.5"].map((v) => `H07-${v}`),
  ...["ASIA-e0", "ASIA-e0.25"].map((v) => `H08-${v}`),
  ...["ASIA_LONDON", "LONDON_NY"].flatMap((w) => ["t0.2", "t0.3", "t0.4"].map((t) => `H09-${w}-${t}`)),
  ...["c0.8", "c0.9"].flatMap((c) => ["L20", "L50", "L100"].map((l) => `H10-${c}-${l}`)),
];
const STAGE1 = {
  status: "ok",
  source: "experiments/edge_program_v2_stage1",
  evidence_class: "SCREENING",
  k: 20,
  survivors: [] as string[],
  variants: STAGE1_NAMES.map(stage1Row),
  problems: [],
  note: "Stage 1 là sàng lọc: không tạo bằng chứng; chưa có Test-H hay holdout.",
};

const LONG_HASH = "9b521cda6648c08e5a2ff3e67c62e3345c66ae8c8e38946c076fbee431ebf93a";
const STAGE_ORDER = ["RAW_SOURCE", "RAW_DATASET", "CERTIFIED_DATASET", "DERIVED_DATASET", "EVENT_DATASET", "EXPERIMENT", "RESULT", "CANDIDATE", "FORWARD_SIGNAL", "EXECUTION"];
const LINEAGE = {
  status: "ok",
  source: "docs/research/edge-program-v2/lineage.json",
  stages: STAGE_ORDER,
  empty_stages: ["DERIVED_DATASET", "EVENT_DATASET", "EXPERIMENT", "RESULT", "CANDIDATE", "FORWARD_SIGNAL", "EXECUTION"],
  problems: [],
  nodes: [
    { id: "4788efe042a15c64", parent_hash: null, stage: "RAW_SOURCE", label: "MetaTrader 5 history, FTMO demo server", parents: [], source: "mt5-ftmo-demo-history", broker: "FTMO (demo)", symbol: "XAUUSD", timeframe: null, timezone: "server wall clock converted to UTC at import", broker_clock: "NY+7 assumed at import", first_timestamp: null, last_timestamp: null, fetched_at: null, raw_hash: null, transformation: null, transform_version: null, validator_result: null, detail: {} },
    { id: "5b9ea1994249d8d9", parent_hash: LONG_HASH, stage: "RAW_DATASET", label: "XAUUSD H1 raw parquet", parents: ["4788efe042a15c64"], source: "mt5-ftmo-demo-history", broker: "FTMO (demo)", symbol: "XAUUSD", timeframe: "H1", timezone: "UTC", broker_clock: "NY+7 assumed", first_timestamp: "2010-01-24T23:00:00+00:00", last_timestamp: "2025-04-30T23:00:00+00:00", fetched_at: "2026-10-08T14:13:53+00:00", raw_hash: LONG_HASH, transformation: "fetch (immutable raw store)", transform_version: "raw-store-v1", validator_result: null, detail: { rows: 91655 } },
    { id: "a1b2c3d4e5f60718", parent_hash: LONG_HASH, stage: "CERTIFIED_DATASET", label: "XAUUSD H1 validated", parents: ["5b9ea1994249d8d9"], source: "mt5-ftmo-demo-history", broker: "FTMO (demo)", symbol: "XAUUSD", timeframe: "H1", timezone: "UTC", broker_clock: "NY+7 assumed", first_timestamp: "2010-01-24T23:00:00+00:00", last_timestamp: "2025-04-30T23:00:00+00:00", fetched_at: null, raw_hash: LONG_HASH, transformation: "validate", transform_version: "validator-v2", validator_result: "FAILED: MISSING_BARS x 1003", detail: {} },
  ],
};

const PROSPECTIVE_EMPTY = { status: "empty", source: "data/forward/prospective.jsonl", generated_at: NOW, evidence_class: "PROSPECTIVE", label: "NO PROSPECTIVE EVIDENCE YET", signals: 0, outcomes: 0, problems: [] };
const PROSPECTIVE_OK = { ...PROSPECTIVE_EMPTY, status: "ok", label: "SEALED BEFORE OUTCOME", signals: 4, outcomes: 2, head_hash_prefix: "abcdef012345" };

const ROLLOUT = {
  status: "ok",
  source: "configs/execution/rollout.yaml",
  current_tier: null,
  current_tier_state: "KHÔNG RÕ",
  current_tier_reason: "tier hiện tại nằm trong cơ sở dữ liệu trạng thái funded, mà console không bao giờ mở",
  tiers: [
    { tier: 0, name: "dry-run", send_orders: false, lot_cap: 0, risk_pct: 0, requires_validated: false, exit: { min_trading_days: 5, min_orders: 0, max_rejected_or_unknown: 0, min_weeks: 1 }, progress: "KHÔNG RÕ" },
    { tier: 1, name: "micro-lot demo", send_orders: true, lot_cap: 0.01, risk_pct: 0.1, requires_validated: true, exit: { min_trading_days: 20, min_orders: 30, max_rejected_or_unknown: 0, min_weeks: 4 }, progress: "KHÔNG RÕ" },
  ],
  note: "funded vẫn bị chặn: cần ứng viên VALIDATED, luật đã xác minh, chủ dự án cho phép.",
};

const GATES = {
  status: "ok",
  source: "docs/research/edge-program-v2/gate-calibration.json",
  evidence_class: "DESCRIPTIVE",
  seed: 20261009,
  assumptions: { sd_per_trade_r: 1.3, gates: "8 years x 150 trades; neighbour correlation 0.8; broker correlation 0.7", power: "K=21; 250 days x 3 trades; clustered rho 0.3; overlapping hold 4" },
  gates: [
    { gate: "temporal", pass_rate: { "0.00R": 0.0487, "0.05R": 0.3247, "0.10R": 0.746, "0.20R": 0.9973 }, classification: "SUPPORTED", reason: "false positives 5%, power 75%" },
    { gate: "parameter", pass_rate: { "0.00R": 0.1413, "0.05R": 0.568, "0.10R": 0.8947, "0.20R": 1.0 }, classification: "CONSERVATIVE", reason: "false positives 14%, power 89%" },
    { gate: "broker", pass_rate: { "0.00R": 0.4493, "0.05R": 0.8293, "0.10R": 0.976, "0.20R": 1.0 }, classification: "UNDER-STRICT", reason: "passes 45% of no-edge strategies" },
  ],
  power: {
    "0.00R": { independent: 0.0033, clustered: 0.0017, overlapping: 0.0217 },
    "0.05R": { independent: 0.0383, clustered: 0.02, overlapping: 0.05 },
    "0.10R": { independent: 0.2167, clustered: 0.115, overlapping: 0.12 },
    "0.20R": { independent: 0.8833, clustered: 0.6417, overlapping: 0.4567 },
  },
  note: "Class D diagnostic; no threshold was changed.",
};

const power = (url: URL) => {
  const n = Number(url.searchParams.get("n"));
  const mde = n <= 500 ? 0.25 : 0.1;
  return {
    status: "ok",
    k: Number(url.searchParams.get("k")),
    n,
    sd: Number(url.searchParams.get("sd")),
    alpha: 0.05 / Number(url.searchParams.get("k")),
    mde,
    underpowered_by_design: mde > 0.2,
    underpowered_threshold: 0.2,
    trades_needed: { "0.05": 6000, "0.1": 1500, "0.15": 700, "0.2": 400 },
    curve: [100, 200, 500, 1000, 2000, 3000].map((m) => ({ n: m, mde: 2.5 / Math.sqrt(m) })),
    formula: "(z(1-0.05/K) + z(0.8)) * sd / sqrt(n)",
    source: "docs/PROFITABILITY_ROADMAP.md (section 5.1)",
  };
};

type Mock = { status?: number; json?: unknown };
type Overrides = Record<string, Mock>;

const ROUTES: Record<string, (url: URL) => unknown> = {
  "/research/overview": () => OVERVIEW,
  "/research/ledger": () => LEDGER,
  "/research/power": power,
  "/research/hypotheses": () => HYPOTHESES,
  "/research/candidates": () => CANDIDATES,
  "/research/candidates/H01-theta0.3": () => CANDIDATE,
  "/research/data": () => DATA,
  "/research/locks": () => LOCKS,
  "/research/calibration": () => CALIBRATION,
  "/research/soak": () => SOAK,
  "/research/stage1": () => STAGE1,
  "/research/lineage": () => LINEAGE,
  "/research/prospective": () => PROSPECTIVE_EMPTY,
  "/research/rollout": () => ROLLOUT,
  "/research/gates": () => GATES,
  "/lifecycle/strategies": () => STRATEGIES,
  "/lifecycle/DEMO-STRAT/forward": () => FORWARD,
  "/lifecycle/H01-theta0.3/forward": () => ({ status: "unknown", source: "data/forward/H01-theta0.3/summary.json", reason: "không có file", message: "KHÔNG CÓ MẪU FORWARD cho chiến lược này" }),
};

const CORS = { "access-control-allow-origin": "*" };

async function mockApi(page: Page, overrides: Overrides = {}): Promise<string[]> {
  const requests: string[] = [];
  await page.route(
    (url) => url.port === "8000",
    async (route: Route) => {
      const url = new URL(route.request().url());
      requests.push(route.request().method() + " " + url.pathname + url.search);
      const over = overrides[url.pathname];
      if (over) return route.fulfill({ status: over.status ?? 200, json: { provenance: PROVENANCE, ...(over.json as object) }, headers: CORS });
      const path = decodeURIComponent(url.pathname);
      let make = ROUTES[path];
      if (!make && path.startsWith("/research/stage1/")) {
        const row = STAGE1.variants.find((v) => v.variant === path.slice("/research/stage1/".length));
        if (row) make = () => ({ status: "ok", source: STAGE1.source, evidence_class: "SCREENING", k: 20, survivors: [], variant: row });
      }
      if (!make) return route.fulfill({ status: 404, json: { detail: "no" }, headers: CORS });
      const body = make(url) as Record<string, unknown>;
      return route.fulfill({ json: { provenance: PROVENANCE, ...body }, headers: CORS });
    },
  );
  return requests;
}

const PAGES: { path: string; ready: string }[] = [
  { path: "/research", ready: "(B) NO EDGE WITHIN BUDGET" },
  { path: "/research/ledger", ready: "H01-theta0.3" },
  { path: "/research/hypotheses", ready: "H01: Động lượng ở giờ mở phiên" },
  { path: "/research/evidence", ready: "Không có biến thể nào sống sót Stage 1" },
  { path: "/research/candidates", ready: "H01-theta0.3" },
  { path: "/research/data", ready: "Development-2" },
  { path: "/research/lineage", ready: "TRỐNG: chưa có" },
  { path: "/research/forward", ready: "DEMO-STRAT" },
  { path: "/research/operations", ready: "Soak 14 ngày" },
];

// whole words only: a cited file name such as PROFITABILITY_ROADMAP.md is a source path, not a claim
const FORBIDDEN_WORDS = /(profit|winning|guaranteed)|will make money/i;
const FORBIDDEN_BUTTON = /backtest|Test-H|holdout|funded|chạy thực nghiệm|gửi lệnh/i;

for (const size of [
  { name: "1440x900", width: 1440, height: 900 },
  { name: "390", width: 390, height: 844 },
]) {
  for (const { path, ready } of PAGES) {
    test(`renders ${path} at ${size.name} without horizontal scroll or console errors`, async ({ page }) => {
      const errors: string[] = [];
      page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
      page.on("pageerror", (e) => errors.push(String(e)));
      await page.setViewportSize({ width: size.width, height: size.height });
      await mockApi(page);
      await page.goto(path);
      await expect(page.getByText(ready, { exact: false }).first()).toBeVisible();
      await expect(page.getByRole("navigation", { name: "Điều hướng Research Console" })).toBeVisible();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow).toBeLessThanOrEqual(0);
      expect(errors).toEqual([]);
    });
  }
}

test("every page shows a visible warning when the API fails or says unknown", async ({ page }) => {
  for (const { path } of PAGES) {
    const unknown: Overrides = {};
    for (const route of Object.keys(ROUTES)) unknown[route] = { status: 500, json: {} };
    unknown["/research/candidates"] = { json: { status: "unknown", source: "experiments", reason: "không đọc được" } };
    await page.unrouteAll({ behavior: "ignoreErrors" });
    await mockApi(page, unknown);
    await page.goto(path);
    await expect(page.getByRole("alert").filter({ hasText: "KHÔNG RÕ" }).first()).toBeVisible();
    await expect(page.getByText("PASS", { exact: true })).toHaveCount(0);
  }
});

test("a network failure is shown as KHÔNG RÕ, not as empty data", async ({ page }) => {
  await page.route((url) => url.port === "8000", (route) => route.abort());
  await page.goto("/research");
  await expect(page.getByRole("alert").filter({ hasText: "không kết nối được API" })).toBeVisible();
  await expect(page.getByText("Chưa đạt điều kiện dừng nào")).toHaveCount(0);
});

test("overview shows the fixed banner, K used/cap, budgets, stop conditions and pending decisions", async ({ page }) => {
  await mockApi(page);
  await page.goto("/research");
  await expect(page.getByText("Không có edge được kiểm định.")).toBeVisible();
  await expect(page.getByText("21 / 21").first()).toBeVisible();
  await expect(page.getByText("6 / 6")).toBeVisible();
  await expect(page.getByText("0 / 8")).toBeVisible();
  await expect(page.getByText("V1: K chạm trần")).toBeVisible();
  await expect(page.getByText("D-1", { exact: true })).toBeVisible();
  await expect(page.getByText("ĐANG CHỜ").first()).toBeVisible();
});

test("the banner is absent when the API sends none", async ({ page }) => {
  await mockApi(page, { "/research/overview": { json: { ...OVERVIEW, banner: null, validated_strategies: ["X"] } } });
  await page.goto("/research");
  await expect(page.getByText("(B) NO EDGE WITHIN BUDGET")).toBeVisible();
  await expect(page.getByText("Không có edge được kiểm định.")).toHaveCount(0);
});

test("ledger filters rows and the MDE calculator flags underpowered by design", async ({ page }) => {
  const requests = await mockApi(page);
  await page.goto("/research/ledger");
  await expect(page.getByText("K = 21 / 21")).toBeVisible();
  await expect(page.getByText("alpha = 0,05 / K = 0.002381")).toBeVisible();
  await page.getByLabel("Giả thuyết").selectOption("H02");
  await expect(page.getByRole("cell", { name: "H01-theta0.3" })).toHaveCount(0);
  await expect(page.getByRole("cell", { name: "H02-b0.0" })).toHaveCount(2);
  await expect(page.getByText("underpowered by design")).toBeVisible();
  await expect(page.getByRole("img", { name: /Đường MDE/ })).toBeVisible();
  await page.getByLabel("n (số lệnh)").fill("3000");
  await expect(page.getByText("đủ công suất")).toBeVisible();
  expect(requests.some((r) => r.includes("/research/power?k=21&n=3000&sd=1.3"))).toBe(true);
  await page.getByLabel("sd (độ lệch chuẩn R)").fill("0");
  await expect(page.getByText("Giá trị ngoài miền hợp lệ")).toBeVisible();
});

test("a pre-registration violation is red and explicit", async ({ page }) => {
  await mockApi(page);
  await page.goto("/research/hypotheses");
  await expect(page.getByText("VI PHẠM ĐĂNG KÝ TRƯỚC", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "VI PHẠM" })).toContainText("H02");
  await expect(page.getByText("H11", { exact: true })).toBeVisible();
});

test("not-run robustness gates never look like a pass", async ({ page }) => {
  await mockApi(page);
  await page.goto("/research/candidates");
  await page.getByRole("button", { name: "Xem chi tiết H01-theta0.3" }).click();
  const gates = page.getByRole("list", { name: "Bốn cổng robustness" });
  await expect(gates).toBeVisible();
  await expect(gates.getByText("CHƯA CHẠY")).toHaveCount(4);
  await expect(gates.getByText("PASS")).toHaveCount(0);
  await expect(page.getByText("chưa có: cột gross-at-mid")).toBeVisible();
  await expect(page.getByRole("cell", { name: "KHÔNG ĐẠT" }).first()).toBeVisible();
  // 7 criteria per period, the null value renders as "chưa có", never as a number
  await expect(page.getByRole("row", { name: /Tập trung theo phiên/ }).first()).toContainText("chưa có");
});

test("data page highlights blocked clock years and lock states", async ({ page }) => {
  await mockApi(page);
  await page.goto("/research/data");
  await expect(page.locator('li[data-blocked="true"]')).toHaveCount(1);
  await expect(page.locator('li[data-blocked="true"]')).toContainText("2011");
  await expect(page.getByText("MISSING_BARS × 1003")).toBeVisible();
  await expect(page.getByText("NGUYÊN VẸN")).toBeVisible();
  await expect(page.getByText("ĐÃ DÙNG THIẾT KẾ").first()).toBeVisible();
  await expect(page.getByText("KHÔNG RÕ", { exact: true }).first()).toBeVisible();
});

test("data without a clock certificate is not OK", async ({ page }) => {
  const cert = { ...DATA.clock_certificate, present: false, years: DATA.clock_certificate.years.map((y) => ({ ...y, certified: false, state: "CHƯA CHỨNG NHẬN" })) };
  await mockApi(page, { "/research/data": { json: { ...DATA, clock_certificate: cert } } });
  await page.goto("/research/data");
  await expect(page.getByText("chưa có file chứng nhận giờ broker")).toBeVisible();
  await expect(page.locator('li[data-blocked="true"]')).toHaveCount(2);
});

test("forward with raw N 100 is INCONCLUSIVE and shows raw vs effective N, days, regimes, power and reasons", async ({ page }) => {
  await mockApi(page);
  await page.goto("/research/forward");
  await page.getByRole("button", { name: "Chọn DEMO-STRAT" }).click();
  const card = page.getByRole("group", { name: "Mức sẵn sàng kết luận forward" });
  await expect(card.getByText("INCONCLUSIVE: chưa đủ để kết luận")).toBeVisible();
  await expect(card.getByRole("row", { name: /N thô/ })).toContainText("100");
  await expect(card.getByRole("row", { name: /N hiệu dụng cần/ })).toContainText("563");
  await expect(card.getByRole("row", { name: /^N hiệu dụng 41/ })).toContainText("41.5");
  await expect(card.getByRole("row", { name: /Số ngày lịch/ })).toContainText("20");
  await expect(card.getByRole("row", { name: /Chế độ thị trường/ })).toContainText("cần 3");
  await expect(card.getByRole("row", { name: /Power ước tính/ })).toContainText("12%");
  await expect(card.getByText("mới 20 ngày lịch (cần 90)")).toBeVisible();
  await expect(card.getByText("mốc tham chiếu cũ, không đủ để kết luận")).toBeVisible();
  await expect(page.getByText("n = 100")).toBeVisible();
  await expect(page.getByText("K = 21")).toBeVisible();
  await expect(page.getByText("UNVALIDATED").first()).toBeVisible();
  await expect(page.getByText("Chưa đánh giá")).toBeVisible();
  // never a conclusion from raw N alone
  await expect(page.getByText("CONSISTENT", { exact: true })).toHaveCount(0);
});

test("a CONSISTENT claim without enough effective N is shown as KHÔNG RÕ", async ({ page }) => {
  const readiness = { ...FORWARD.readiness, conclusion: "CONSISTENT", effective_n: null };
  await mockApi(page, { "/lifecycle/DEMO-STRAT/forward": { json: { ...FORWARD, readiness } } });
  await page.goto("/research/forward");
  await page.getByRole("button", { name: "Chọn DEMO-STRAT" }).click();
  await expect(page.getByText("KHÔNG RÕ (API báo CONSISTENT", { exact: false })).toBeVisible();
  await expect(page.getByText("CONSISTENT", { exact: true })).toHaveCount(0);
});

test("a strategy without forward data shows the warning", async ({ page }) => {
  await mockApi(page);
  await page.goto("/research/forward");
  await page.getByRole("button", { name: "Chọn H01-theta0.3" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "KHÔNG RÕ" })).toBeVisible();
});

test("demote form: only for demotable strategies, needs the typed word, sends exactly the expected body", async ({ page }) => {
  await mockApi(page);
  const posted: { path: string; body: unknown; key: string | null }[] = [];
  await page.route("**/api/control/**", async (route) => {
    const request = route.request();
    posted.push({ path: new URL(request.url()).pathname, body: request.postDataJSON(), key: request.headers()["idempotency-key"] ?? null });
    return route.fulfill({
      status: 200,
      json: { event: { strategy_id: "DEMO-STRAT", from_state: "DEMO", to_state: "WATCH", at: NOW, source: "web", reason: "drift" } },
    });
  });
  await page.goto("/research/forward");

  await page.getByRole("button", { name: "Chọn H01-theta0.3" }).click();
  await expect(page.getByRole("form", { name: "Hạ trạng thái chiến lược" })).toHaveCount(0);
  await expect(page.getByText("không thể hạ từ web")).toBeVisible();

  await page.getByRole("button", { name: "Chọn DEMO-STRAT" }).click();
  const form = page.getByRole("form", { name: "Hạ trạng thái chiến lược" });
  await expect(form).toBeVisible();
  await expect(form.getByRole("button", { name: "Hạ trạng thái" })).toBeDisabled();
  await form.getByLabel("Hạ xuống").selectOption("WATCH");
  await form.getByLabel(/Lý do/).fill("drift chi phí");
  await form.getByRole("button", { name: "Hạ trạng thái" }).click();

  await page.getByRole("button", { name: "Tiếp tục" }).click();
  const confirm = page.getByRole("button", { name: "Xác nhận DEMOTE" });
  await expect(confirm).toBeDisabled();
  await page.getByRole("dialog").getByRole("textbox").fill("demote");
  await expect(confirm).toBeDisabled();
  expect(posted).toHaveLength(0);
  await page.getByRole("dialog").getByRole("textbox").fill("DEMOTE");
  await confirm.click();

  await expect(page.getByText("Đã hạ DEMO-STRAT: DEMO → WATCH.")).toBeVisible();
  expect(posted).toHaveLength(1);
  expect(posted[0].path).toBe("/api/control/lifecycle/demote");
  expect(posted[0].body).toEqual({ strategy_id: "DEMO-STRAT", to: "WATCH", reason: "drift chi phí", confirm: "DEMOTE" });
  expect(posted[0].key).toMatch(/^[A-Za-z0-9_-]{8,100}$/);
});

test("a refused demote shows the server message and says the state did not change", async ({ page }) => {
  await mockApi(page);
  await page.route("**/api/control/**", (route) =>
    route.fulfill({ status: 409, json: { detail: { code: "DEMOTE_REFUSED", message: "chỉ được hạ bậc" } } }),
  );
  await page.goto("/research/forward");
  await page.getByRole("button", { name: "Chọn DEMO-STRAT" }).click();
  const form = page.getByRole("form", { name: "Hạ trạng thái chiến lược" });
  await form.getByLabel(/Lý do/).fill("thử");
  await form.getByRole("button", { name: "Hạ trạng thái" }).click();
  await page.getByRole("button", { name: "Tiếp tục" }).click();
  await page.getByRole("dialog").getByRole("textbox").fill("DEMOTE");
  await page.getByRole("button", { name: "Xác nhận DEMOTE" }).click();
  await expect(page.getByText("DEMOTE_REFUSED: chỉ được hạ bậc")).toBeVisible();
  await expect(page.getByText("Trạng thái không đổi.")).toBeVisible();
});

test("operations shows assumed costs as GIẢ ĐỊNH, soak progress and the pending-rules count", async ({ page }) => {
  await mockApi(page);
  await page.goto("/research/operations");
  await expect(page.getByText("GIẢ ĐỊNH").first()).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "KHÔNG RÕ" }).first()).toBeVisible();
  await expect(page.getByText("0.05 / 14 ngày")).toBeVisible();
  await expect(page.getByText("2 / 14")).toBeVisible();
  await expect(page.getByText("daily_loss_limit_pct")).toBeVisible();
});

test("no page offers an action that runs experiments, opens locked data, trades or edits the ledger", async ({ page }) => {
  await mockApi(page);
  await page.route("**/api/control/**", (route) => route.fulfill({ status: 500, json: {} }));
  for (const { path, ready } of PAGES) {
    await page.goto(path);
    await expect(page.getByText(ready, { exact: false }).first()).toBeVisible();
    if (path.endsWith("/candidates")) await page.getByRole("button", { name: "Xem chi tiết H01-theta0.3" }).click();
    if (path.endsWith("/forward")) await page.getByRole("button", { name: "Chọn DEMO-STRAT" }).click();
    const text = await page.locator("body").innerText();
    const html = await page.content();
    expect(text).not.toMatch(FORBIDDEN_WORDS);
    expect(html).not.toMatch(FORBIDDEN_WORDS);
    const labels = await page
      .locator("button, a, input[type=submit], input[type=button], [role=button], [role=link]")
      .evaluateAll((els) => els.map((e) => `${e.textContent ?? ""} ${e.getAttribute("aria-label") ?? ""} ${(e as HTMLInputElement).value ?? ""}`));
    for (const label of labels) expect(label).not.toMatch(FORBIDDEN_BUTTON);
    const forms = await page.locator("form").count();
    expect(forms).toBe(path.endsWith("/forward") ? 1 : 0);
    const inputs = await page.locator("input, textarea, select").count();
    if (!path.endsWith("/forward") && !path.endsWith("/ledger")) expect(inputs).toBe(0);
  }
});


// ---------------------------------------------------------------------------------------------
// Research-integrity pages (RI-09)
// ---------------------------------------------------------------------------------------------

test("provenance (source, generated_at, code commit) is shown on every page", async ({ page }) => {
  await mockApi(page);
  for (const { path, ready } of PAGES) {
    await page.goto(path);
    await expect(page.getByText(ready, { exact: false }).first()).toBeVisible();
    const note = page.locator('[data-source-note="provenance"]').first();
    await expect(note).toContainText("2026-10-09T02:00:00+00:00");
    await expect(note).toContainText("0beba0c1");
  }
});

test("provenance missing from the API shows KHÔNG RÕ, not a blank", async ({ page }) => {
  await mockApi(page);
  await page.route(
    (url) => url.port === "8000" && url.pathname === "/research/lineage",
    (route) => route.fulfill({ json: { ...LINEAGE }, headers: CORS }),
  );
  await page.goto("/research/lineage");
  await expect(page.locator('[data-source-note="provenance"]').first()).toContainText("KHÔNG RÕ");
});

test("evidence badges: eight classes, each with text; SCREENING is dashed and never green", async ({ page }) => {
  await mockApi(page);
  await page.goto("/research/evidence");
  const badge = page.locator('[data-evidence-class="SCREENING"]').first();
  await expect(badge).toBeVisible();
  await expect(badge).toContainText("SCREENING");
  const style = await badge.evaluate((el) => ({ border: getComputedStyle(el).borderTopStyle, cls: el.className }));
  expect(style.border).toBe("dashed");
  expect(style.cls).not.toMatch(/green|emerald|lime|teal/);
  await expect(page.locator('[data-evidence-class="DESCRIPTIVE"]').first()).toBeVisible();
});

test("evidence page: 20 variants, no-survivor banner, SCREENING rows never look like a pass, refusal reasons shown", async ({ page }) => {
  await mockApi(page);
  await page.goto("/research/evidence");
  await expect(page.getByRole("status").filter({ hasText: "Không có biến thể nào sống sót Stage 1" })).toBeVisible();
  const table = page.getByRole("region", { name: "Bảng biến thể Stage 1" });
  await expect(table.locator("tbody tr")).toHaveCount(20);
  await expect(table.locator('[data-evidence-class="SCREENING"]')).toHaveCount(20);
  // mean net R is shown as a plain number; no PASS / VALIDATED / ok-toned badge anywhere on the page
  await expect(page.getByText("PASS", { exact: true })).toHaveCount(0);
  await expect(page.locator('[data-badge="ok"]')).toHaveCount(0);
  await expect(page.locator('[data-badge]').filter({ hasText: /^(VALIDATED|PASS)$/ })).toHaveCount(0);
  await expect(table.getByRole("columnheader", { name: "n thô" })).toBeVisible();
  await expect(table.getByRole("columnheader", { name: "K", exact: true })).toBeVisible();
  // detail panel sections (first variant is selected by default)
  for (const name of [
    "Edge Attribution",
    "Placebo Comparison",
    "Dependence Sensitivity",
    "Power",
    "Intrabar Ambiguity",
    "Structural Stability (era)",
    "Cost Distribution",
    "Provenance",
  ]) {
    await expect(page.getByRole("region", { name })).toBeVisible();
  }
  await expect(page.getByText("CHƯA CÓ: cần dữ liệu demo")).toBeVisible();
  const labels = page.getByRole("region", { name: "Quyền gắn nhãn của biến thể" });
  await expect(labels.getByText("evidence class SCREENING không đủ để gắn nhãn VALIDATED")).toBeVisible();
  await expect(labels.getByText("thiếu Test-H")).toBeVisible();
  await expect(labels.getByText("manifest chưa được xác minh")).toBeVisible();
  await expect(labels.locator('[data-badge="fail"]')).toHaveCount(2);
  await expect(page.getByRole("region", { name: "Provenance" })).toContainText("manifest_verified");
  // choosing another variant loads its detail
  await page.getByRole("button", { name: "Xem chi tiết H10-c0.9-L100" }).click();
  await expect(page.getByText("Chi tiết H10-c0.9-L100")).toBeVisible();
});

test("evidence page: a survivor is labelled as screening only, empty and unknown are not 'no survivors'", async ({ page }) => {
  await mockApi(page, { "/research/stage1": { json: { ...STAGE1, survivors: ["H07-ASIA-e0"], variants: STAGE1.variants.map((v, i) => ({ ...v, survivor: i === 0 })) } } });
  await page.goto("/research/evidence");
  await expect(page.getByText("chỉ là sàng lọc (SCREENING), chưa phải bằng chứng", { exact: false })).toBeVisible();
  await expect(page.getByText("Không có biến thể nào sống sót")).toHaveCount(0);
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await mockApi(page, { "/research/stage1": { json: { status: "empty", source: "experiments/edge_program_v2_stage1", variants: [], survivors: [] } } });
  await page.goto("/research/evidence");
  await expect(page.getByText("CHƯA CÓ kết quả Stage 1")).toBeVisible();
  await expect(page.getByText("Không có biến thể nào sống sót")).toHaveCount(0);
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await mockApi(page, { "/research/stage1": { json: { status: "unknown", source: "experiments/edge_program_v2_stage1", reason: "không đọc được" } } });
  await page.goto("/research/evidence");
  await expect(page.getByRole("alert").filter({ hasText: "KHÔNG RÕ" }).first()).toBeVisible();
  await expect(page.getByText("Không có biến thể nào sống sót")).toHaveCount(0);
});

test("evidence page: gate calibration and power with n/K assumptions and classification badges", async ({ page }) => {
  await mockApi(page);
  await page.goto("/research/evidence");
  await expect(page.getByRole("heading", { name: "Hiệu chuẩn cổng & công suất" })).toBeVisible();
  const gates = page.getByRole("region", { name: "Tỉ lệ qua cổng theo hiệu ứng" });
  await expect(gates.getByText("SUPPORTED", { exact: true })).toBeVisible();
  await expect(gates.getByText("CONSERVATIVE", { exact: true })).toBeVisible();
  await expect(gates.getByText("UNDER-STRICT", { exact: true })).toBeVisible();
  await expect(gates.getByText("Cổng này không phải bộ lọc overfitting")).toBeVisible();
  await expect(gates.getByRole("row", { name: /broker/ })).toContainText("44.9%");
  await expect(page.getByText("K=21; 250 days x 3 trades")).toBeVisible();
  await expect(page.getByText("sd_per_trade_r")).toBeVisible();
  await expect(page.getByRole("region", { name: "Công suất theo hiệu ứng và mô hình phụ thuộc" })).toContainText("88.3%");
  // an unknown classification is not an implicit pass
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await mockApi(page, { "/research/gates": { json: { ...GATES, gates: [{ ...GATES.gates[0], classification: "WHATEVER" }] } } });
  await page.goto("/research/evidence");
  await expect(page.getByText("KHÔNG RÕ (WHATEVER)")).toBeVisible();
});

test("lineage page: ten stages in order, empty stages marked, short ids with full id in title, problems on unknown", async ({ page }) => {
  await mockApi(page);
  await page.goto("/research/lineage");
  const stages = page.locator("ol > li > h3");
  await expect(stages).toHaveCount(10);
  const names = await page.locator("[data-stage]").evaluateAll((els) => els.map((e) => e.getAttribute("data-stage")));
  expect(names).toEqual(STAGE_ORDER);
  await expect(page.getByText("TRỐNG: chưa có")).toHaveCount(7);
  const parent = page.getByRole("link", { name: "nút cha 4788efe042a15c64" });
  await expect(parent).toHaveAttribute("title", "4788efe042a15c64");
  await expect(parent).toHaveText("4788efe0…");
  await expect(page.getByTitle(LONG_HASH).first()).toBeVisible();
  expect(await page.locator("body").innerText()).not.toContain(LONG_HASH);
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await mockApi(page, { "/research/lineage": { json: { ...LINEAGE, status: "unknown", problems: ["cha 5b9e… không tồn tại"], reason: "lineage không nhất quán" } } });
  await page.goto("/research/lineage");
  await expect(page.getByRole("alert").filter({ hasText: "KHÔNG RÕ" }).first()).toBeVisible();
  await expect(page.getByText("cha 5b9e… không tồn tại")).toBeVisible();
});

test("prospective card shows exactly the API label; SEALED BEFORE OUTCOME only when status is ok", async ({ page }) => {
  await mockApi(page);
  await page.goto("/research/forward");
  await expect(page.getByText("NO PROSPECTIVE EVIDENCE YET", { exact: true })).toBeVisible();
  await expect(page.getByText("SEALED BEFORE OUTCOME")).toHaveCount(0);

  await page.unrouteAll({ behavior: "ignoreErrors" });
  await mockApi(page, { "/research/prospective": { json: PROSPECTIVE_OK } });
  await page.goto("/research/forward");
  await expect(page.getByText("SEALED BEFORE OUTCOME", { exact: true })).toBeVisible();

  // a lying payload (label says SEALED but status is not ok) is never shown as sealed
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await mockApi(page, { "/research/prospective": { json: { ...PROSPECTIVE_OK, status: "invalid", problems: ["chuỗi băm sai ở dòng 3"] } } });
  await page.goto("/research/forward");
  await expect(page.getByText("SEALED BEFORE OUTCOME")).toHaveCount(0);
  await expect(page.getByText("chuỗi băm sai ở dòng 3")).toBeVisible();

  for (const [status, label] of [
    ["invalid", "PROVENANCE INVALID"],
    ["unknown", "KHÔNG RÕ"],
  ]) {
    await page.unrouteAll({ behavior: "ignoreErrors" });
    await mockApi(page, { "/research/prospective": { json: { ...PROSPECTIVE_EMPTY, status, label, problems: [] } } });
    await page.goto("/research/forward");
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
    await expect(page.getByText("SEALED BEFORE OUTCOME")).toHaveCount(0);
  }
  // API failure
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await mockApi(page, { "/research/prospective": { status: 500, json: {} } });
  await page.goto("/research/forward");
  await expect(page.getByRole("alert").filter({ hasText: "KHÔNG RÕ: sổ bằng chứng tiền cứu" })).toBeVisible();
  await expect(page.getByText("SEALED BEFORE OUTCOME")).toHaveCount(0);
});

test("hypotheses table shows expected N, effective N, MDE, K and variants from the API payload; detail separates observed from hypothesized", async ({ page }) => {
  await mockApi(page);
  await page.goto("/research/hypotheses");
  const row = page.getByRole("row", { name: /H07 V2/ });
  await expect(row).toContainText("2142");
  await expect(row).toContainText("1900");
  await expect(row).toContainText("0.102 / 0.109 R");
  await expect(row).toContainText("20");
  await expect(row).toContainText("bỏ 1: H07-PD-e0.5");
  await expect(row).toContainText("HYPOTHESIZED");
  // legacy V1 rows keep the old note; an unknown registration is KHÔNG RÕ
  await expect(page.getByRole("row", { name: /H01 V1/ })).toContainText("chưa có trong file đăng ký (legacy V1)");
  await expect(page.getByRole("row", { name: /H08 V2/ })).toContainText("KHÔNG RÕ");
  await expect(page.getByRole("row", { name: /H08 V2/ })).not.toContainText("chưa có trong file đăng ký");
  await expect(row).not.toContainText("chưa có trong file đăng ký");
  // detail (H07 is the default selection)
  const observed = page.getByRole("region", { name: "Đã quan sát (thống kê)" });
  const hypothesized = page.getByRole("region", { name: "Giải thích được giả thuyết (HYPOTHESIZED)" });
  await expect(observed).toContainText("Giá thường đảo chiều");
  await expect(observed).not.toContainText("Lệnh dừng bị kích hoạt");
  await expect(hypothesized).toContainText("Lệnh dừng bị kích hoạt");
  await expect(hypothesized).not.toContainText("Giá thường đảo chiều");
  await expect(page.getByText("Bác bỏ nếu mean net R CI95 chứa 0")).toBeVisible();
  await expect(page.getByText("cccccccc")).toBeVisible();
  await expect(page.getByText("dddddddd")).toBeVisible();
  await expect(page.getByText("ĐĂNG KÝ TRƯỚC: OK").first()).toBeVisible();
  // another hypothesis: V1 legacy
  await page.getByRole("button", { name: "Xem chi tiết H01" }).click();
  await expect(page.getByText("Chương trình V1: chưa có trong file đăng ký có cấu trúc (legacy).")).toBeVisible();
  await expect(page.getByText("aaaaaaaa")).toBeVisible();
});

test("data page shows the outcome state of each lock ('—' when null)", async ({ page }) => {
  await mockApi(page);
  await page.goto("/research/data");
  const table = page.getByRole("region", { name: "Bảng khóa dữ liệu" });
  await expect(table.getByRole("row", { name: /Test-H/ })).toContainText("LOCKED");
  await expect(table.getByRole("row", { name: /Holdout/ })).toContainText("KHÔNG RÕ (UNKNOWN)");
  await expect(table.getByRole("row", { name: /Development-2/ })).toContainText("—");
  await expect(table.getByRole("row", { name: /Forward/ })).toContainText("—");
});

test("operations shows the real rollout tier table with progress KHÔNG RÕ and funded still blocked", async ({ page }) => {
  await mockApi(page);
  await page.goto("/research/operations");
  const table = page.getByRole("region", { name: "Bảng tier rollout" });
  await expect(table.locator("tbody tr")).toHaveCount(2);
  await expect(table.getByRole("row", { name: /micro-lot demo/ })).toContainText("0.01");
  await expect(table.locator('[data-badge="unknown"]')).toHaveCount(2);
  await expect(page.getByText("funded vẫn bị chặn").first()).toBeVisible();
  await expect(page.getByText("chưa có nguồn dữ liệu cho tiến độ rollout")).toHaveCount(0);
});

test("API failure, unknown status and aborted network show KHÔNG RÕ on the new pages", async ({ page }) => {
  for (const path of ["/research/evidence", "/research/lineage", "/research/forward", "/research/operations", "/research/hypotheses"]) {
    for (const mode of ["500", "unknown", "abort"]) {
      await page.unrouteAll({ behavior: "ignoreErrors" });
      if (mode === "abort") {
        await page.route((url) => url.port === "8000", (route) => route.abort());
      } else {
        const over: Overrides = {};
        for (const route of Object.keys(ROUTES)) over[route] = mode === "500" ? { status: 500, json: {} } : { json: { status: "unknown", source: "x", reason: "không rõ" } };
        await mockApi(page, over);
      }
      await page.goto(path);
      await expect(page.getByRole("alert").filter({ hasText: "KHÔNG RÕ" }).first()).toBeVisible();
      await expect(page.getByText("PASS", { exact: true })).toHaveCount(0);
      await expect(page.getByText("SEALED BEFORE OUTCOME")).toHaveCount(0);
      await expect(page.getByText("Không có biến thể nào sống sót")).toHaveCount(0);
    }
  }
});

test("only GET requests are made and the only form is the demote form", async ({ page }) => {
  const requests = await mockApi(page);
  const posts: string[] = [];
  page.on("request", (r) => {
    if (r.method() !== "GET" && r.method() !== "OPTIONS" && r.method() !== "HEAD") posts.push(`${r.method()} ${r.url()}`);
  });
  for (const { path, ready } of PAGES) {
    await page.goto(path);
    await expect(page.getByText(ready, { exact: false }).first()).toBeVisible();
    if (path.endsWith("/forward")) await page.getByRole("button", { name: "Chọn DEMO-STRAT" }).click();
    await expect(page.locator("form")).toHaveCount(path.endsWith("/forward") ? 1 : 0);
    await expect(page.locator("form[aria-label]")).toHaveCount(path.endsWith("/forward") ? 1 : 0);
  }
  expect(posts).toEqual([]);
  expect(requests.filter((r) => !r.startsWith("GET "))).toEqual([]);
});

test("keyboard: Tab reaches every nav link with a visible focus ring; Escape cancels the demote confirmation and returns focus", async ({ page }) => {
  await mockApi(page);
  await page.goto("/research/evidence");
  await expect(page.getByText("Không có biến thể nào sống sót")).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Điều hướng Research Console" });
  const links = nav.getByRole("link");
  const count = await links.count();
  expect(count).toBe(10);
  const seen: string[] = [];
  for (let i = 0; i < count + 3 && seen.length < count; i++) {
    await page.keyboard.press("Tab");
    const info = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el.tagName !== "A" || !el.closest("nav")) return null;
      return { text: el.textContent ?? "", outline: getComputedStyle(el).outlineStyle, width: getComputedStyle(el).outlineWidth };
    });
    if (info) {
      seen.push(info.text);
      expect(info.outline).not.toBe("none");
      expect(parseFloat(info.width)).toBeGreaterThan(0);
    }
  }
  expect(seen).toContain("Bằng chứng");
  expect(seen).toContain("Lineage");
  expect(seen).toHaveLength(count);

  await page.goto("/research/forward");
  await page.getByRole("button", { name: "Chọn DEMO-STRAT" }).click();
  const form = page.getByRole("form", { name: "Hạ trạng thái chiến lược" });
  await form.getByLabel(/Lý do/).fill("thử");
  const submit = form.getByRole("button", { name: "Hạ trạng thái" });
  await submit.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(submit).toBeFocused();
  // Escape in the form itself clears the reason
  await form.getByLabel(/Lý do/).focus();
  await page.keyboard.press("Escape");
  await expect(form.getByLabel(/Lý do/)).toHaveValue("");
});

test("tables have captions and column scopes; form controls are labelled", async ({ page }) => {
  await mockApi(page);
  for (const path of ["/research/hypotheses", "/research/evidence", "/research/operations"]) {
    await page.goto(path);
    await expect(page.locator("table").first()).toBeVisible();
    const bad = await page.evaluate(() => {
      const out: string[] = [];
      document.querySelectorAll("table").forEach((t, i) => {
        if (!t.querySelector("caption") && !t.closest("[aria-label]")) out.push(`table ${i} no caption/label`);
        t.querySelectorAll("thead th").forEach((th) => {
          if (th.getAttribute("scope") !== "col") out.push(`th without scope in table ${i}`);
        });
      });
      return out;
    });
    expect(bad).toEqual([]);
  }
});
