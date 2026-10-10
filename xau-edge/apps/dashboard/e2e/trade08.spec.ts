import { expect, test } from "@playwright/test";
import { mock, setupsGolden, view } from "./fixtures/trade";

/** TRADE-08: plain language first, help on the basic words, tools that belong to ONE source, the hold deadline, the last event. */

test("a technical code is never in front of the trader: the human sentence first, the code under 'Chi tiết kỹ thuật'", async ({ page }) => {
  await mock(page, view("writerConflict"));
  await page.goto("/trade");
  const banner = page.getByTestId("hero-problems");
  await expect(banner).toContainText("Một tiến trình khác đang giữ quyền ghi bàn PAPER");
  const visible = await banner.innerText(); // innerText leaves out the closed <details> body
  expect(visible).not.toContain("WRITER_LOCK");
  const detail = banner.locator("details").first();
  await expect(detail).toContainText("WRITER_LOCK"); // ...it is attached
  await detail.locator("summary").click();
  await expect(detail).toHaveAttribute("open", "");
  expect(await detail.innerText()).toContain("WRITER_LOCK"); // ...and shown on request
});

test("API loss shows a Vietnamese sentence and keeps API_UNAVAILABLE in the technical details", async ({ page }) => {
  await mock(page, view("buy"));
  await page.route("**/trade/decision", (route) => route.abort());
  await page.goto("/trade");
  const banner = page.getByTestId("api-down-banner");
  await expect(banner).toContainText("Mất kết nối với máy chủ dữ liệu");
  expect(await banner.innerText()).not.toContain("API_UNAVAILABLE");
  await expect(banner.locator("details")).toContainText("API_UNAVAILABLE");
});

test("the basic words have a one-sentence help: hover, keyboard focus and Esc", async ({ page }) => {
  await mock(page, view("buyArmed"));
  await page.goto("/trade");
  for (const [id, phrase] of [["bid", "Giá bạn nhận được khi BÁN"], ["ask", "Giá bạn phải trả khi MUA"], ["spread", "Chênh lệch Ask - Bid"], ["bias", "KHÔNG phải tín hiệu vào lệnh"]] as const) {
    const term = page.getByTestId(`term-${id}`).first();
    await term.hover();
    await expect(page.getByTestId(`tip-${id}`).first()).toContainText(phrase);
    await page.mouse.move(2, 2);
    await expect(page.getByTestId(`tip-${id}`)).toHaveCount(0);
  }
  // keyboard: focus opens it, Esc closes it, and the tip is wired with aria-describedby
  const term = page.getByTestId("term-setup").first();
  await term.focus();
  const tip = page.getByTestId("tip-setup");
  await expect(tip).toBeVisible();
  await expect(term).toHaveAttribute("aria-describedby", /.+/);
  await page.keyboard.press("Escape");
  await expect(tip).toHaveCount(0);
});

test("a BUY plan and an open position explain SL, TP, R/R, MFE and MAE", async ({ page }) => {
  await mock(page, view("buy"));
  await page.goto("/trade");
  for (const id of ["sl", "tp", "rr"] as const) await expect(page.getByTestId(`term-${id}`).first()).toBeVisible();
  await mock(page, view("openPaper"));
  await page.reload();
  for (const id of ["mfe", "mae", "hold"] as const) await expect(page.getByTestId(`term-${id}`).first()).toBeVisible();
});

test("an open position shows the server's latest time exit and how long is left", async ({ page }) => {
  const v = view("openPaper");
  const until = v.desk!.position!.max_hold_until!;
  expect(until).toBeTruthy();
  await mock(page, v);
  await page.goto("/trade");
  const row = page.getByTestId("position-max-hold");
  await expect(row).toHaveAttribute("data-until", until);
  await expect(row).toContainText(/tới \d\d:\d\d · còn/);
  // the same instant is in the hero sentence ("muộn nhất lúc HH:MM")
  const hhmm = (await row.innerText()).match(/tới (\d\d:\d\d)/)![1];
  await expect(page.getByTestId("action-when")).toContainText(`muộn nhất lúc ${hhmm}`);
});

test("levels and alerts belong to ONE source: a replay line never shows on LIVE, and the page says which source it is for", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("xau-edge:v3:LIVE:XAUUSD:levels", JSON.stringify([{ id: "live1", price: 4200, label: "Đường" }]));
    localStorage.setItem("xau-edge:v3:REPLAY:XAUUSD:levels", JSON.stringify([{ id: "rep1", price: 3340, label: "Đường" }]));
    localStorage.setItem("xau-edge:v3:REPLAY:XAUUSD:alerts", JSON.stringify([{ id: "repA", price: 3350, direction: "UP", createdAt: "", firedAt: null }]));
  });
  const live = view("wait");
  live.source_mode = "LIVE";
  await mock(page, live);
  await page.goto("/trade");
  await expect(page.getByTestId("tools-scope")).toContainText("Chỉ dùng cho: LIVE XAUUSD");
  await expect(page.getByTestId("my-levels")).toContainText("4200.00");
  await expect(page.getByTestId("my-levels")).not.toContainText("3340.00");
  await expect(page.getByTestId("my-alerts")).not.toContainText("3350.00"); // the replay alert is not here
  const replay = view("wait");
  await mock(page, replay);
  await page.reload();
  await expect(page.getByTestId("tools-scope")).toContainText("REPLAY (không phải live) XAUUSD");
  await expect(page.getByTestId("my-levels")).toContainText("3340.00");
  await expect(page.getByTestId("my-alerts")).toContainText("3350.00");
  await expect(page.getByTestId("my-levels")).not.toContainText("4200.00");
});

test("TRADE-06/07 storage is migrated once into the first source that loads it, and retired", async ({ page }) => {
  await page.addInitScript(() => {
    if (sessionStorage.getItem("seeded")) return; // seed only on the very first load, not after the page retired the keys
    sessionStorage.setItem("seeded", "1");
    localStorage.setItem("xau-edge.trade.levels.v1", JSON.stringify([{ id: "old", price: 4210, label: "Đường" }]));
    localStorage.setItem("xau-edge.trade.price-alerts.v1", JSON.stringify([{ id: "olda", price: 4260, direction: "UP", createdAt: "", firedAt: null }]));
  });
  const live = view("wait");
  live.source_mode = "LIVE";
  await mock(page, live);
  await page.goto("/trade");
  await expect(page.getByTestId("my-levels")).toContainText("4210.00");
  await expect(page.getByTestId("my-alerts")).toContainText("4260.00");
  const keys = await page.evaluate(() => Object.keys(localStorage));
  expect(keys).not.toContain("xau-edge.trade.levels.v1");
  expect(keys).not.toContain("xau-edge.trade.price-alerts.v1");
  expect(keys).toContain("xau-edge:v3:LIVE:XAUUSD:levels");
  expect(keys).toContain("xau-edge:v3:LIVE:XAUUSD:alerts");
  await page.reload();
  await expect(page.getByTestId("my-levels")).toContainText("4210.00"); // still there after the keys were retired
});

test("during a long WAIT the page still says what happened last", async ({ page }) => {
  const setups = setupsGolden();
  expect(setups.setups.length).toBeGreaterThan(0);
  await mock(page, view("wait"), { setups });
  await page.goto("/trade");
  await expect(page.getByTestId("last-event")).toContainText("Lần gần nhất:");
  await expect(page.getByTestId("last-event")).toContainText(/Setup|Tín hiệu|Lệnh/);
});

test("a replay page leaves the old TRADE-06/07 keys alone (they were the owner's live tools)", async ({ page }) => {
  await page.addInitScript(() => {
    if (sessionStorage.getItem("seeded")) return;
    sessionStorage.setItem("seeded", "1");
    localStorage.setItem("xau-edge.trade.levels.v1", JSON.stringify([{ id: "old", price: 4210, label: "Đường" }]));
  });
  await mock(page, view("wait")); // a replay view
  await page.goto("/trade");
  await expect(page.getByTestId("tools-scope")).toContainText("REPLAY");
  await expect(page.getByTestId("my-levels")).not.toContainText("4210.00");
  expect(await page.evaluate(() => localStorage.getItem("xau-edge.trade.levels.v1"))).not.toBeNull();
});

test("a refused open says one Vietnamese sentence; the code and the server's English text are in the technical details", async ({ page }) => {
  await mock(page, view("buy"));
  await page.route("**/api/trade/paper/open", (route) => route.fulfill({ status: 409, json: { detail: { code: "DECISION_CHANGED", message: "the setup changed or is gone; refresh and look again" } } }));
  await page.goto("/trade");
  await page.getByTestId("take-paper").click();
  await page.getByTestId("confirm-paper").click();
  const msg = page.getByTestId("action-message");
  await expect(msg).toContainText("Không mở được lệnh PAPER: Kế hoạch đã thay đổi hoặc hết hạn");
  const visible = await msg.innerText();
  expect(visible).not.toContain("DECISION_CHANGED");
  expect(visible).not.toContain("the setup changed");
  await expect(msg.locator("details")).toContainText("DECISION_CHANGED");
});

test("changing the display zone keeps the chart on the current candles", async ({ page }) => {
  await mock(page, view("buy"));
  await page.goto("/trade");
  await expect(page.getByTestId("ohlc-readout")).toBeVisible();
  const zone = page.getByRole("combobox", { name: "Múi giờ hiển thị" });
  for (const z of ["UTC", "BROKER", "LOCAL", "VN"]) {
    await zone.selectOption({ label: await zone.locator(`option[value="${z}"]`).innerText() });
    await page.waitForTimeout(500);
    await expect(page.getByTestId("go-latest")).toHaveCount(0); // still at the latest candle, nothing is out of view
  }
});

test("offline, the ages keep counting and the market pill says 'Mất kết nối'", async ({ page }) => {
  await page.clock.install();
  const online = { on: true };
  const v = view("buy");
  await mock(page, v);
  await page.route("**/trade/decision", (route) => (online.on ? route.fulfill({ json: v }) : route.abort()));
  await page.goto("/trade");
  await expect(page.getByTestId("action-word")).toHaveText("MUA PAPER");
  online.on = false;
  await page.clock.fastForward(95_000);
  await expect(page.getByTestId("market-pill")).toHaveText("Mất kết nối");
  await expect(page.getByTestId("price-stale")).not.toContainText(/· 0\s?s/);
  await expect(page.getByTestId("data-age")).not.toHaveText(/dữ liệu: 0\s?s$/);
});
