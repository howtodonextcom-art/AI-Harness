import { expect, test, type Page } from "@playwright/test";
import { bars, journalClosedGolden, markersClosedGolden, mock, view } from "./fixtures/trade";
import type { TradeView } from "@/lib/trade";

/** Regression tests for the defects the independent engineering review found in the terminal. */

async function serve(page: Page, initial: TradeView, extra: Parameters<typeof mock>[2] = {}) {
  const state = { view: initial };
  await mock(page, initial, extra);
  await page.route("**/trade/decision", (route) => route.fulfill({ json: state.view }));
  return state;
}

async function panBy(page: Page, dx: number) {
  const box = (await page.getByTestId("trade-chart").boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.5 + dx, box.y + box.height * 0.5, { steps: 10 });
  await page.mouse.up();
}

test("a journal focus is one-shot: the trader pans away and later polls do not drag the view back", async ({ page }) => {
  const t = journalClosedGolden().trades[0];
  await mock(page, view("closedPaper"), { markers: markersClosedGolden(), journal: journalClosedGolden() });
  await page.goto(`/trade?focus=${encodeURIComponent(t.opened_at!)}&to=${encodeURIComponent(t.closed_at!)}&tf=M5`);
  const chart = page.getByTestId("trade-chart");
  await expect.poll(() => chart.getAttribute("data-range")).toBeTruthy();
  await panBy(page, -250);
  await page.waitForTimeout(3000);
  const moved = await chart.getAttribute("data-range");
  await page.waitForTimeout(7000); // at least two polls
  expect(await chart.getAttribute("data-range")).toBe(moved);
});

test("candles of another timeframe are never shown under the selected one", async ({ page }) => {
  const v = view("buy");
  await mock(page, v);
  let failH4 = true;
  await page.route("**/md/XAUUSD/bars**", async (route) => {
    const tf = new URL(route.request().url()).searchParams.get("timeframe") ?? "M5";
    if (tf === "H4" && failH4) return route.fulfill({ status: 503, json: {} });
    return route.fulfill({ json: bars(v, tf) });
  });
  await page.goto("/trade");
  await expect(page.getByTestId("ohlc-readout")).toBeVisible();
  await page.getByTestId("chart-tf-H4").click();
  await expect(page.getByTestId("ohlc-readout")).toHaveCount(0); // no M5 candles under an H4 label
  await expect(page.getByTestId("chart-unavailable")).toBeVisible({ timeout: 10_000 });
  failH4 = false;
  await expect(page.getByTestId("ohlc-readout")).toBeVisible({ timeout: 10_000 });
});

test("a sliding 400-bar window does not drift a panned view", async ({ page }) => {
  const v = view("buy");
  await serve(page, v);
  let shift = 0;
  await page.route("**/md/XAUUSD/bars**", (route) => {
    const b = bars(v, "M5");
    const last = b.bars[b.bars.length - 1];
    for (let i = 1; i <= shift; i++) b.bars.push({ ...last, time: new Date(Date.parse(last.time) + i * 300_000).toISOString(), is_closed: false });
    b.bars.splice(0, shift); // the oldest bars drop off
    return route.fulfill({ json: b });
  });
  await page.goto("/trade");
  await panBy(page, 300);
  await page.waitForTimeout(3000);
  const chart = page.getByTestId("trade-chart");
  const before = await chart.getAttribute("data-range");
  shift = 3;
  await page.waitForTimeout(7000);
  expect(await chart.getAttribute("data-range")).toBe(before);
});

test("after opening, an older response cannot bring the open button back", async ({ page }) => {
  const buy = view("buy");
  const open = view("openPaper");
  const state = await serve(page, buy);
  let slowOld = false;
  await page.route("**/trade/decision", async (route) => {
    if (slowOld) {
      slowOld = false;
      await new Promise((r) => setTimeout(r, 1500));
      return route.fulfill({ json: buy }); // answers late with the PRE-open decision
    }
    return route.fulfill({ json: state.view });
  });
  await page.route("**/api/trade/paper/open", (route) => {
    state.view = open;
    return route.fulfill({ json: open.desk!.position });
  });
  await page.goto("/trade");
  await page.getByTestId("take-paper").click();
  slowOld = true; // the next poll is slow and will be answered after the action
  await page.getByTestId("confirm-paper").click();
  await expect(page.getByTestId("paper-position")).toBeVisible({ timeout: 10_000 });
  await page.waitForTimeout(3500);
  await expect(page.getByTestId("paper-position")).toBeVisible();
  await expect(page.getByTestId("take-paper")).toHaveCount(0);
});

test("with the API failing there is no live ticket to click", async ({ page }) => {
  await mock(page, view("buy"));
  await page.goto("/trade");
  await expect(page.getByTestId("take-paper")).toBeEnabled();
  await page.route("**/trade/decision", (route) => route.abort());
  await expect(page.getByTestId("api-down-banner")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("take-paper")).toBeDisabled();
  await expect(page.getByTestId("plan-stale")).toBeVisible();
});

test("a decimal comma works in the price alert and the calculator", async ({ page }) => {
  await mock(page, view("wait"));
  await page.route("**/trade/risk**", (route) => route.fulfill({ json: view("buy").risk_plans![1] }));
  await page.goto("/trade");
  await page.getByTestId("tool-alert").click();
  await page.getByTestId("alert-price").fill("4250,5");
  await page.getByTestId("alert-add").click();
  await expect(page.getByTestId("my-alerts")).toContainText("4250.50");
  await page.getByTestId("calculator").locator("summary").click();
  await page.getByTestId("calc-entry").fill("4236,47");
  await page.getByTestId("calc-sl").fill("4229,45");
  await expect(page.getByTestId("calc-result")).toContainText("Lot", { timeout: 5000 });
});

test("single-key shortcuts can be switched off (WCAG 2.1.4) and the choice is remembered", async ({ page }) => {
  await mock(page, view("buy"));
  await page.goto("/trade");
  await expect(page.getByTestId("decision")).toBeVisible();
  await page.keyboard.press("?");
  await page.getByTestId("shortcuts-enabled").uncheck();
  await page.keyboard.press("Escape");
  await page.keyboard.press("h");
  await expect(page.getByTestId("chart-tf-H1")).toHaveAttribute("aria-pressed", "false");
  await page.reload();
  await expect(page.getByTestId("decision")).toBeVisible();
  await page.keyboard.press("h");
  await expect(page.getByTestId("chart-tf-H1")).toHaveAttribute("aria-pressed", "false"); // still off
});

test("the page behind a modal is inert, and tab arrows move focus with the selection", async ({ page }) => {
  await mock(page, view("buy"));
  await page.goto("/trade");
  await page.getByTestId("take-paper").click();
  await expect(page.getByTestId("confirm-open-modal")).toBeVisible();
  expect(await page.getByTestId("market-bar").evaluate((el) => !!el.closest("[inert]"))).toBe(true);
  await page.keyboard.press("Escape");
  await page.getByTestId("tab-overview").focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("tab-why")).toBeFocused();
});

test("the close modal warns when the connection is not trustworthy", async ({ page }) => {
  await mock(page, view("openPaper"));
  await page.goto("/trade");
  await page.getByTestId("close-paper").click();
  await expect(page.getByTestId("close-unsure")).toHaveCount(0);
  await page.route("**/trade/decision", (route) => route.abort());
  await expect(page.getByTestId("close-unsure")).toBeVisible({ timeout: 15_000 });
});

test("markers of another source mode are never drawn on this chart", async ({ page }) => {
  const markers = { ...markersClosedGolden(), source_mode: "LIVE" as const }; // the view is a replay
  await mock(page, view("closedPaper"), { markers });
  await page.goto("/trade");
  await expect(page.getByTestId("decision")).toBeVisible();
  await expect(page.getByTestId("chart-markers").locator("li")).toHaveCount(0);
});
