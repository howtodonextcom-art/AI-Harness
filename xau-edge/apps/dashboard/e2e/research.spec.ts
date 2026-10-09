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
  planned: [{ id: "H07", name: "Liquidity-sweep reversal", batch: "A" }],
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
    { id: "dev2", name: "Development-2", from: "2011-01-01", to: "2018-12-31", use: "thiết kế, Stage 1", burned: true, state: "ĐÃ DÙNG THIẾT KẾ" },
    { id: "val2", name: "Validation-2", from: "2019-01-01", to: "2021-12-31", use: "Stage 1/2", burned: true, state: "ĐÃ DÙNG THIẾT KẾ" },
    { id: "testH", name: "Test-H", from: "2022-01-01", to: "2025-04-30", use: "xác nhận", burned: false, state: "NGUYÊN VẸN" },
    { id: "holdout", name: "Holdout", from: "2026-05-01", to: "2026-10-07", use: "cuối cùng", burned: false, state: "KHÔNG RÕ" },
    { id: "forward", name: "Forward", from: "2026-10-09", to: null, use: "paper rồi demo", burned: false, state: "ĐANG TÍCH LŨY" },
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
  n_trades: 12,
  min_trades_for_conclusion: 100,
  conclusion: "KHÔNG KẾT LUẬN",
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
      if (over) return route.fulfill({ status: over.status ?? 200, json: over.json ?? {}, headers: CORS });
      const make = ROUTES[decodeURIComponent(url.pathname)];
      if (!make) return route.fulfill({ status: 404, json: { detail: "no" }, headers: CORS });
      return route.fulfill({ json: make(url), headers: CORS });
    },
  );
  return requests;
}

const PAGES: { path: string; ready: string }[] = [
  { path: "/research", ready: "(B) NO EDGE WITHIN BUDGET" },
  { path: "/research/ledger", ready: "H01-theta0.3" },
  { path: "/research/hypotheses", ready: "H01: Động lượng ở giờ mở phiên" },
  { path: "/research/candidates", ready: "H01-theta0.3" },
  { path: "/research/data", ready: "Development-2" },
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
  await expect(page.getByText("H07")).toBeVisible();
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

test("forward below 100 trades says KHÔNG KẾT LUẬN and shows n, K and the evidence label", async ({ page }) => {
  await mockApi(page);
  await page.goto("/research/forward");
  await page.getByRole("button", { name: "Chọn DEMO-STRAT" }).click();
  await expect(page.getByText("KHÔNG KẾT LUẬN", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("n = 12")).toBeVisible();
  await expect(page.getByText("K = 21")).toBeVisible();
  await expect(page.getByText("UNVALIDATED").first()).toBeVisible();
  await expect(page.getByText("Chưa đánh giá")).toBeVisible();
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
