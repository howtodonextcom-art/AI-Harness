import { expect, test } from "@playwright/test";
import { mock, view } from "./fixtures/trade";

/** CONSIST-01: one display zone for every page, and a disabled control plane that is not polled. */

const ZONE_KEY = "xau-edge.market.zone";

test("a disabled control plane says CONTROL DISABLED, stops polling, and can be re-checked on request", async ({ page }) => {
  let calls = 0;
  await page.route("**/api/control/**", (route) => {
    calls += 1;
    return route.fulfill({ status: 503, json: { detail: { code: "CONTROL_UNAVAILABLE", message: "API chưa chạy với XAU_EDGE_WEB_CONTROL=true (không có file token)" } } });
  });
  await page.goto("/control");
  await expect(page.getByTestId("control-disabled")).toContainText("CONTROL DISABLED");
  await expect(page.getByTestId("control-disabled")).toContainText("Đây không phải lỗi");
  await expect(page.getByRole("button", { name: /Bắt đầu|Khởi động bot/ })).toHaveCount(0); // nothing to operate
  await page.waitForTimeout(500);
  const settled = calls;
  expect(settled).toBeGreaterThanOrEqual(1);
  expect(settled).toBeLessThanOrEqual(3); // the first status, preflight and journal reads, once each
  await page.waitForTimeout(7000); // two status periods and a journal period
  expect(calls).toBe(settled); // no polling while disabled
  await page.getByTestId("control-recheck").click();
  await expect.poll(() => calls).toBeGreaterThan(settled);
  await expect(page.getByTestId("control-disabled")).toBeVisible(); // still disabled: the page settles again
});

test("the display zone is one preference: set on the market page, followed by the journal and the terminal", async ({ page }) => {
  await mock(page, view("wait"));
  await page.route("**/api/control/**", (route) => route.fulfill({ status: 503, json: { detail: { code: "CONTROL_UNAVAILABLE", message: "x" } } }));
  await page.goto("/market");
  await page.getByTestId("zone-select").selectOption("BROKER");
  expect(await page.evaluate((k) => window.localStorage.getItem(k), ZONE_KEY)).toBe("BROKER");
  await page.goto("/journal");
  await expect(page.getByTestId("journal-zone")).toHaveValue("BROKER");
  await page.getByTestId("journal-zone").selectOption("UTC");
  await page.goto("/trade");
  await expect(page.getByLabel("Múi giờ hiển thị")).toHaveValue("UTC");
  await page.getByLabel("Múi giờ hiển thị").selectOption("LOCAL");
  await page.goto("/market");
  await expect(page.getByTestId("zone-select")).toHaveValue("LOCAL");
});

test("a zone change on another tab is followed live", async ({ page, context }) => {
  await mock(page, view("wait"));
  await page.goto("/trade");
  await page.getByLabel("Múi giờ hiển thị").selectOption("VN");
  const other = await context.newPage();
  await mock(other, view("wait"));
  await other.goto("/market");
  await other.getByTestId("zone-select").selectOption("UTC");
  await expect(page.getByLabel("Múi giờ hiển thị")).toHaveValue("UTC"); // the trade page follows the market page's tab
});

test("System health lists every component; a replay says it is not live and its collector rows are UNKNOWN, not OK", async ({ page }) => {
  await mock(page, view("wait"));
  await page.goto("/trade");
  await page.getByTestId("tab-system").click();
  const card = page.getByTestId("system-health-card");
  for (const id of ["mt5", "collector", "bar_parity", "tick_storage", "disk", "api", "decision_coverage", "news", "writer_lock", "strategy", "source_mode", "dashboard"]) {
    await expect(card.getByTestId(`health-${id}`)).toBeVisible();
  }
  await expect(card.getByTestId("health-collector")).toHaveAttribute("data-state", "UNKNOWN");
  await expect(card.getByTestId("health-source_mode")).toHaveAttribute("data-state", "WARN");
  await expect(card.getByTestId("health-source_mode")).toContainText("KHÔNG PHẢI LIVE");
  await expect(card.getByTestId("health-overall")).not.toHaveAttribute("data-state", "OK");
});

test("data ages are the server's: a closed market is not stale, but a dead collector heartbeat is", async ({ page }) => {
  const v = view("wait");
  v.data_ages = {
    live: true,
    market_open: false,
    quote: { age_seconds: 73_131, state: "MARKET_CLOSED" },
    last_bar: { age_seconds: 73_127, state: "MARKET_CLOSED" },
    collector_heartbeat: { age_seconds: 900, state: "STALE" },
    last_decision: { age_seconds: 40, state: "MARKET_CLOSED" },
  };
  v.system_health = v.system_health.map((r) => (r.id === "collector" ? { ...r, state: "ERROR", detail: "không còn ghi nhịp tim (lần cuối 900 s trước)" } : r));
  await mock(page, v);
  await page.goto("/trade");
  await page.getByTestId("tab-system").click();
  await expect(page.getByTestId("age-quote")).toHaveAttribute("data-state", "MARKET_CLOSED");
  await expect(page.getByTestId("age-quote")).toContainText("20.3 giờ");
  await expect(page.getByTestId("age-last_bar")).toContainText("THỊ TRƯỜNG ĐÓNG");
  await expect(page.getByTestId("age-collector_heartbeat")).toHaveAttribute("data-state", "STALE");
  await expect(page.getByTestId("age-collector_heartbeat")).toContainText("15 phút");
  await expect(page.getByTestId("health-collector")).toHaveAttribute("data-state", "ERROR");
  await expect(page.getByTestId("health-overall")).toHaveAttribute("data-state", "ERROR");
  for (const name of ["QUOTE AGE", "LAST BAR AGE", "COLLECTOR HEARTBEAT AGE", "LAST DECISION AGE"]) await expect(page.getByTestId("data-ages-card")).toContainText(name);
});
