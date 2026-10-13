import AxeBuilder from "@axe-core/playwright";
import { type Page, expect, test } from "@playwright/test";


const SUMMARY = {
  mode: "PAPER", evidence: "FORWARD_ACCUMULATING", protocol: "docs/forward/FORWARD_EVIDENCE_PROTOCOL.md",
  started: "2026-10-13T08:00:00Z", last: "2026-10-14T08:00:00Z", logged_bars: 270, expected_bars: 289,
  funnel: {
    by_action: { WAIT: 268, BUY: 2 },
    by_readiness: { NEUTRAL: 40, BIAS: 150, WATCH: 40, SETUP_ARMED: 20, TRIGGER: 15, PLAN_VALID: 3, READY: 2 },
    first_refusal: { SPREAD_TOO_WIDE: 120, NO_SETUP: 80, NO_DIRECTION: 40, TIMEFRAME_CONFLICT: 20 },
    signals: 2, distinct_setups: 1,
  },
  gaps: [{ start: "2026-10-13T20:00:00Z", end: "2026-10-13T21:35:00Z", bars: 19 }],
  trades: [{ strategy_version: "1.1.0", closed: 1, wins: 0, losses: 1, total_r: -1.05, mean_r: -1.05, win_rate: 0, win_rate_ci95: [0, 0.79] }],
  progress: {
    closed_trades: 1, min_closed_trades: 100, observed_days: 1.0, min_days: 60, coverage: 0.934, min_coverage: 0.95,
    trades_per_day: 1, eta_days_to_min_trades: 99, claim_allowed: false,
    reason: "mới 1/100 lệnh đã đóng; mới 1.0/60 ngày quan sát; độ phủ quan sát 93.4% < 95%; chưa có giả thuyết forward được chủ dự án duyệt (họ K riêng)",
  },
  buy_and_hold_pct: 0.42, paper_return_pct: -0.10,
  notes: ["Đây là MÔ TẢ quan sát, không phải bằng chứng. Nhãn bằng chứng của hệ thống vẫn là UNVALIDATED.", "Mẫu lệnh quá nhỏ: tỉ lệ thắng và R trung bình có khoảng tin cậy rất rộng."],
};

async function mock(page: Page, body: unknown) {
  await page.route("**/api/v2/forward/summary", (r) => r.fulfill({ json: body }));
}

test("forward evidence shows coverage, the funnel and the protocol minimums, and refuses to claim", async ({ page }) => {
  await mock(page, SUMMARY);
  await page.goto("/#evidence");
  await expect(page.getByTestId("evidence-label")).toHaveText("UNVALIDATED");
  await expect(page.getByTestId("forward-state")).toHaveText("đang tích lũy");
  await expect(page.getByTestId("forward-coverage")).toContainText("270/289");
  await expect(page.getByTestId("forward-coverage")).toContainText("93.4%");
  await expect(page.getByTestId("forward-coverage")).toContainText("1 khoảng trống");
  await expect(page.getByTestId("forward-progress")).toContainText("1/100");
  await expect(page.getByTestId("forward-progress")).toContainText("được phép kết luận: CHƯA");
  await expect(page.getByTestId("forward-progress")).toContainText("độ phủ quan sát 93.4% < 95%");
  await expect(page.getByTestId("forward-funnel").locator("tbody tr")).toHaveCount(7);
  await expect(page.getByTestId("forward-signals")).toContainText("tín hiệu MUA/BÁN 2");
  await expect(page.getByTestId("forward-signals")).toContainText("SPREAD_TOO_WIDE 120");
  await expect(page.getByTestId("forward-trades")).toContainText("Wilson 95%");
  await expect(page.getByTestId("forward-benchmark")).toContainText("+0.42%");
  await expect(page.getByTestId("forward-notes")).toContainText("MÔ TẢ");
  const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(result.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
});

test("before any observation the panel says there is none and nothing is claimed", async ({ page }) => {
  await mock(page, {
    mode: "PAPER", evidence: "NO_OBSERVATIONS", protocol: "docs/forward/FORWARD_EVIDENCE_PROTOCOL.md", started: null, last: null,
    logged_bars: 0, expected_bars: 0, funnel: null, gaps: [], trades: [],
    progress: { closed_trades: 0, min_closed_trades: 100, observed_days: 0, min_days: 60, coverage: null, min_coverage: 0.95, trades_per_day: null, eta_days_to_min_trades: null, claim_allowed: false, reason: "chưa có quan sát nào" },
    buy_and_hold_pct: null, paper_return_pct: 0, notes: ["Chưa ghi nhận nến M5 nào."],
  });
  await page.goto("/#evidence");
  await expect(page.getByTestId("forward-state")).toHaveText("chưa có");
  await expect(page.getByTestId("forward-progress")).toContainText("CHƯA");
  await expect(page.getByTestId("forward-trades")).toContainText("Chưa có lệnh PAPER nào đóng");
});

test("the real server answers with a well-formed summary and never allows a claim", async ({ request }) => {
  const body = await (await request.get("/api/v2/forward/summary")).json();
  expect(body.mode).toBe("PAPER");
  expect(["NO_OBSERVATIONS", "FORWARD_ACCUMULATING"]).toContain(body.evidence);
  expect(body.progress.claim_allowed).toBe(false);
  expect(body.progress.min_closed_trades).toBe(100);
});
