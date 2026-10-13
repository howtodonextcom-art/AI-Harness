import AxeBuilder from "@axe-core/playwright";
import { type Page, expect, test } from "@playwright/test";

const SUMMARY = {
  mode: "PAPER", auto_paper: false, start_equity: 10000, realized_pnl_usd: -31.2, floating_pnl_usd: 12.5,
  equity: 9981.3, day_start_equity: 10000, day_pnl_usd: -18.7, open_count: 1, closed_count: 2, wins: 1, losses: 1,
  total_r: -0.2,
  governor: {
    open_positions: 1, trades_today: 3, trades_last_hour: 1, loss_streak: 1, daily_loss_pct: 0.19,
    daily_loss_stop_pct: 2, cooldown_until: null, refusals: ["RISK_LIMIT"],
  },
  assumptions: ["Equity paper là giả định cấu hình, không phải số dư tài khoản thật."],
};

const position = (over: Record<string, unknown>) => ({
  id: "p1", setup_id: "s1", decision_id: "d1", side: "BUY", lots: 0.05, entry: 4165.78, quote_entry: 4165.75,
  stop_loss: 4160.0, take_profit: 4177.0, take_profit_2: null, net_rr: 1.9, risk_amount: 29.0, risk_pct: 0.25,
  source: "AUTO", session: "LONDON", opened_at: "2026-10-12T10:07:30Z", status: "OPEN", closed_at: null,
  exit_price: null, exit_reason: null, ambiguous: false, pnl_usd: null, swap_usd: null, net_pnl_usd: null,
  r_multiple: null, floating_pnl_usd: 12.5, mae_points: 40, mfe_points: 130, ...over,
});

const CLOSED = position({
  id: "p0", status: "CLOSED", closed_at: "2026-10-12T09:20:00Z", opened_at: "2026-10-12T09:05:00Z", exit_price: 4159.97,
  exit_reason: "STOP_LOSS", ambiguous: true, pnl_usd: -29.1, swap_usd: 0, net_pnl_usd: -29.1, r_multiple: -1.0,
  floating_pnl_usd: null, source: "MANUAL",
});

async function mockPaper(page: Page, opts: { action: string; positions: unknown[] }) {
  const posts: { url: string; body: string | null }[] = [];
  await page.route("**/api/v2/paper/summary", (r) => r.fulfill({ json: SUMMARY }));
  await page.route("**/api/v2/paper/positions?*", (r) => r.fulfill({ json: { positions: opts.positions } }));
  await page.route("**/api/v2/paper/journal?*", (r) =>
    r.fulfill({
      json: {
        events: [
          { seq: 2, ts: "2026-10-12T09:20:00Z", kind: "CLOSED", position_id: "p0", detail: { reason: "STOP_LOSS", exit_price: 4159.97, net_usd: -29.1, r: -1.0 } },
          { seq: 1, ts: "2026-10-12T09:05:00Z", kind: "OPENED", position_id: "p0", detail: { side: "BUY", lots: 0.05, fill: 4165.78, source: "MANUAL" } },
        ],
      },
    }),
  );
  await page.route("**/api/v2/state", async (r) => {
    try {
      const real = await r.fetch();
      const body = await real.json();
      await r.fulfill({ json: { ...body, action: opts.action } });
    } catch {
      // the page was closed while this request was in flight (the test already ended)
    }
  });
  await page.route("**/api/v2/paper/open-current", (r) => {
    posts.push({ url: r.request().url(), body: r.request().postData() });
    return r.fulfill({ json: { ok: true, message: "đã mở lệnh PAPER", position: position({}) } });
  });
  await page.route("**/api/v2/paper/positions/*/close", (r) => {
    posts.push({ url: r.request().url(), body: r.request().postData() });
    return r.fulfill({ status: 409, json: { error_code: "QUOTE_UNAVAILABLE", message: "không có quote mới để đóng lệnh" } });
  });
  return posts;
}

test("an empty book says so and cannot open without a valid plan", async ({ page }) => {
  await mockPaper(page, { action: "WAIT", positions: [] });
  await page.goto("/#journal");
  await expect(page.getByTestId("drawer-panel")).toContainText("Chưa có lệnh PAPER");
  await expect(page.getByTestId("open-current")).toBeDisabled();
  await expect(page.getByTestId("auto-paper")).toHaveText("TẮT");
  await expect(page.getByTestId("paper-chip")).toContainText("Sổ PAPER $9981");
  await expect(page.getByTestId("paper-chip")).toContainText("hôm nay -$18.70");
});

test("positions, R, MAE/MFE, the ambiguous bar and the governor are all shown", async ({ page }) => {
  await mockPaper(page, { action: "HOLD", positions: [position({}), CLOSED] });
  await page.goto("/#journal");
  const table = page.getByTestId("paper-positions");
  await expect(table.getByTestId("pos-p1")).toContainText("+$12.50 (nổi)");
  await expect(table.getByTestId("pos-p0")).toContainText("chạm SL");
  await expect(table.getByTestId("pos-p0")).toContainText("nến chạm cả hai, tính SL");
  await expect(table.getByTestId("pos-p0")).toContainText("-1.00");
  await expect(table.getByTestId("pos-p0")).toContainText("thủ công");
  await expect(page.getByTestId("paper-equity")).toContainText("$9981.30");
  await expect(page.getByTestId("governor")).toContainText("lệnh mới bị chặn: RISK_LIMIT");
  await expect(page.getByTestId("journal-events")).toContainText("OPENED");
  await expect(page.getByTestId("open-current")).toBeDisabled(); // HOLD: a position is already open
  const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(result.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
});

test("opening sends no price, size or level; the server decides everything", async ({ page }) => {
  const posts = await mockPaper(page, { action: "BUY", positions: [] });
  await page.goto("/#journal");
  await expect(page.getByTestId("open-current")).toBeEnabled();
  await page.getByTestId("open-current").click();
  await expect(page.getByTestId("paper-message")).toContainText("đã mở lệnh PAPER");
  expect(posts).toHaveLength(1);
  expect(posts[0]?.url).toMatch(/\/api\/v2\/paper\/open-current$/);
  expect(posts[0]?.body ?? "").toBe(""); // no body at all
});

test("a refused write shows the server's error code and stays usable", async ({ page }) => {
  const posts = await mockPaper(page, { action: "HOLD", positions: [position({})] });
  await page.goto("/#journal");
  await page.getByTestId("close-position").click();
  await expect(page.getByTestId("paper-message")).toContainText("QUOTE_UNAVAILABLE");
  await expect(page.getByRole("alert").filter({ hasText: "QUOTE_UNAVAILABLE" })).toBeVisible();
  expect(posts[0]?.url).toMatch(/\/api\/v2\/paper\/positions\/p1\/close$/);
  await expect(page.getByTestId("close-position")).toBeEnabled();
});

test("the real server: an empty paper book, auto off, nothing opened by the test run", async ({ request }) => {
  const summary = await (await request.get("/api/v2/paper/summary")).json();
  expect(summary.mode).toBe("PAPER");
  expect(summary.auto_paper).toBe(false);
  expect(summary.closed_count).toBe(0);
  expect(summary.assumptions.length).toBeGreaterThan(3);
  const foreign = await request.post("/api/v2/paper/open-current", { headers: { origin: "http://evil.example" } });
  expect(foreign.status()).toBe(403);
});
