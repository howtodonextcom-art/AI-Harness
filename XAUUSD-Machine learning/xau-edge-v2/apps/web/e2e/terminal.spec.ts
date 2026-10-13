import AxeBuilder from "@axe-core/playwright";
import { type Page, expect, test } from "@playwright/test";

/** Collects everything that should never happen on a clean page. */
function watch(page: Page) {
  const problems: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error" || m.type() === "warning") problems.push(`console.${m.type()}: ${m.text()}`);
  });
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("requestfailed", (r) => problems.push(`requestfailed: ${r.url()}`));
  page.on("response", (r) => {
    if (r.status() >= 400) problems.push(`HTTP ${r.status()}: ${r.url()}`);
  });
  return problems;
}

test("5-second contract: the page answers the Human's questions", async ({ page }) => {
  const problems = watch(page);
  const t0 = Date.now();
  await page.goto("/");
  await expect(page.getByTestId("recommendation")).toBeVisible();
  await expect(page.getByTestId("ws-status")).toHaveAttribute("data-state", "open", { timeout: 5000 });
  expect(Date.now() - t0).toBeLessThan(5000);

  // 1 bias · 2 can I trade · 3 why not · 4 how close · 5 what next · 6 entry/sl/tp · 7 risk · 8 trust
  // the data behind the test server is the real shared store, so the answer varies; the contract
  // is that there IS an answer, from the closed set, with a reason unless it is a plan
  const code = await page.getByTestId("recommendation").getAttribute("data-code");
  expect(["WAIT", "UNAVAILABLE", "BUY_CANDIDATE", "SELL_CANDIDATE", "HOLD", "EXIT_WATCH"]).toContain(code);
  await expect(page.getByTestId("sys-bias")).not.toBeEmpty();
  await expect(page.getByTestId("sys-setup")).not.toBeEmpty();
  if (code === "WAIT" || code === "UNAVAILABLE") {
    await expect(page.getByTestId("blocker")).not.toBeEmpty();
    await expect(page.getByTestId("secondary")).not.toBeEmpty();
    await expect(page.getByTestId("plan")).toContainText("chưa có kế hoạch để cân nhắc");
  }
  await expect(page.getByTestId("risk")).toBeVisible();
  await expect(page.getByTestId("cost")).toContainText("không coi là 0");
  await expect(page.getByTestId("mode")).toContainText("PAPER");
  await expect(page.getByTestId("evidence")).toContainText("UNVALIDATED");
  await expect(page.getByTestId("data-chip")).toContainText("M1");
  expect(problems).toEqual([]);
});

test("one route, no navigation, no hidden pages", async ({ page }) => {
  await page.goto("/");
  // the only link is the chart library's attribution (its licence), inside the chart
  expect(await page.locator("a[href]:not([data-testid=chart-host] a), nav").count()).toBe(0);
  await page.goto("/legacy");
  await expect(page.getByTestId("recommendation")).toBeVisible(); // any path is the same single page
  await expect(page.getByTestId("chart-panel")).toBeVisible();
});

test("honest placeholders: nothing is faked", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("chart-meta")).toHaveAttribute("data-count", /^\d+$/); // a real count, never a fake chart
  const text = (await page.locator("body").innerText()).toLowerCase();
  expect(text).not.toMatch(/\d+\s?%\s*(tự tin|confidence)/);
  expect(text).not.toContain("strong buy");
  await page.goto("/#journal");
  await expect(page.getByTestId("drawer-panel")).toContainText("Chưa có lệnh PAPER");
});

const VIEWPORTS = [
  { name: "1920x1080", width: 1920, height: 1080, full: true },
  { name: "1440x900", width: 1440, height: 900, full: true },
  { name: "1152x864", width: 1152, height: 864, full: true },
  { name: "960x720", width: 960, height: 720, full: true },
  { name: "200% zoom of 1440x900", width: 720, height: 450, full: false },
  { name: "390x844", width: 390, height: 844, full: false },
];

for (const vp of VIEWPORTS) {
  test(`layout at ${vp.name}: no horizontal scroll; decision visible`, async ({ page }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto("/");
    await expect(page.getByTestId("recommendation")).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
    const rows = vp.full
      ? ["recommendation", "sys-bias", "sys-setup", "sys-m1", "blocker", "plan", "risk", "cost", "human-panel"]
      : ["recommendation"];
    for (const id of rows) {
      const box = await page.getByTestId(id).boundingBox();
      expect(box, `${id} has a box`).not.toBeNull();
      expect(box!.y + box!.height, `${id} fits in ${vp.height}px without scrolling`).toBeLessThanOrEqual(
        vp.height,
      );
    }
  });
}

for (const vp of VIEWPORTS.filter((v) => v.full && v.width >= 1152)) { // narrower screens may scroll past the decision
  test(`fills the screen at ${vp.name}: one screen, no dead space`, async ({ page }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto("/");
    await expect(page.getByTestId("recommendation")).toBeVisible();
    const m = await page.evaluate(() => {
      const r = (id: string) => document.querySelector(`[data-testid=${id}]`)!.getBoundingClientRect();
      return {
        scroll: document.documentElement.scrollHeight - document.documentElement.clientHeight,
        chartBottom: r("left-col").bottom,
        mtfTop: r("mtf").top,
        drawersBottom: r("drawers").bottom,
        vh: window.innerHeight,
      };
    });
    expect(m.scroll).toBeLessThanOrEqual(1); // everything on one screen
    expect(m.mtfTop - m.chartBottom).toBeLessThan(24); // the chart takes the free height
    expect(m.vh - m.drawersBottom).toBeLessThan(24); // no empty band at the bottom
  });
}

test("accessibility: no axe violations (page and open drawer)", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("recommendation")).toBeVisible();
  let result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(result.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
  await page.getByRole("tab", { name: "Sức khỏe dữ liệu" }).click();
  await expect(page.getByTestId("health-status")).toBeVisible();
  result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(result.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
});

test("drawers: hash opens, tab toggles, link restores", async ({ page }) => {
  await page.goto("/#data");
  await expect(page.getByTestId("health-status")).toBeVisible();
  await page.getByRole("tab", { name: "Mô hình" }).click();
  await expect(page).toHaveURL(/#model$/);
  await expect(page.getByTestId("drawer-panel")).toContainText("RETIRED");
  await page.getByRole("tab", { name: "Mô hình" }).click(); // toggle closed
  await expect(page.getByTestId("drawer-panel")).toHaveCount(0);
});

function mockSocket(page: Page, plan: (n: number) => number[], closeAfterFirst: boolean) {
  let connection = 0;
  return page.routeWebSocket("**/ws", (route) => {
    connection += 1;
    const n = connection;
    const send = (type: "hello" | "heartbeat", seq: number) =>
      route.send(
        JSON.stringify({ type, seq, ts: new Date().toISOString(), schema_version: "2.0.0-g2", data_version: "t" }),
      );
    const seqs = plan(n);
    seqs.forEach((seq, i) => send(i === 0 ? "hello" : "heartbeat", seq));
    if (closeAfterFirst && n === 1) route.close();
  });
}

test("reconnect: a dropped socket is retried and the state is refetched", async ({ page }) => {
  await mockSocket(page, (n) => (n === 1 ? [0] : [0, 1, 2]), true);
  let stateCalls = 0;
  page.on("request", (r) => {
    if (r.url().endsWith("/api/v2/state")) stateCalls += 1;
  });
  await page.goto("/");
  await expect(page.getByTestId("ws-status")).toHaveAttribute("data-state", "retrying");
  await expect(page.getByTestId("ws-status")).toHaveAttribute("data-state", "open", { timeout: 6000 });
  expect(stateCalls).toBeGreaterThanOrEqual(3); // initial + hello + hello after reconnect
});

test("gap in seq is detected and triggers a refetch", async ({ page }) => {
  await mockSocket(page, () => [0, 1, 5], false); // 2, 3, 4 were missed
  let stateCalls = 0;
  page.on("request", (r) => {
    if (r.url().endsWith("/api/v2/state")) stateCalls += 1;
  });
  await page.goto("/");
  await expect(page.getByTestId("ws-status")).toHaveAttribute("data-state", "open");
  await expect.poll(() => stateCalls).toBeGreaterThanOrEqual(3); // initial + hello + gap
});

test("API failure is shown, never silent", async ({ page }) => {
  await page.route("**/api/v2/state", (route) => route.abort());
  await page.goto("/");
  await expect(page.getByTestId("api-error")).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("Không đọc được API");
});
