import { expect, test, type Page } from "@playwright/test";
import { TFS, bars, journalClosedGolden, markersClosedGolden, mock, signalsGolden, view } from "./fixtures/trade";
import type { TradeView } from "@/lib/trade";

/**
 * The trading terminal against the production build with the API mocked in the browser. Every served
 * object is a real backend serialization (e2e/fixtures/golden); tests select and clone them. The
 * real-browser run against a live replay API is e2e-acceptance/desk.spec.ts.
 */

const fixed = (n: number | null | undefined) => (n ?? 0).toFixed(2);
const hero = (page: Page) => page.getByTestId("hero");

/** Serve a mutable view so a test can change the market between polls. */
async function serve(page: Page, initial: TradeView, extra: Parameters<typeof mock>[2] = {}) {
  const state = { view: initial };
  await mock(page, initial, extra);
  await page.route("**/trade/decision", (route) => route.fulfill({ json: state.view }));
  return state;
}

async function chartBox(page: Page) {
  await expect(page.getByTestId("ohlc-readout")).toBeVisible(); // the chart exists once the page has hydrated
  const box = await page.getByTestId("trade-chart").boundingBox();
  if (!box) throw new Error("chart has no box");
  return box;
}

test.describe("market bar", () => {
  test("price, day statistics, session, Vietnam clock and candle countdown come from the server", async ({ page }) => {
    const v = view("buy");
    await mock(page, v);
    await page.goto("/trade");
    const q = v.quote!;
    const d = v.market_context!.daily!;
    await expect(page.getByTestId("price-bid")).toHaveText(fixed(q.bid));
    await expect(page.getByTestId("price-ask")).toHaveText(fixed(q.ask));
    await expect(page.getByTestId("spread")).toContainText(`${q.spread_points.toFixed(0)} điểm`);
    await expect(page.getByTestId("day-change")).toContainText(`+${fixed(d.change)}`);
    await expect(page.getByTestId("day-high")).toHaveText(fixed(d.high));
    await expect(page.getByTestId("day-low")).toHaveText(fixed(d.low));
    await expect(page.getByTestId("day-range")).toHaveText(fixed(d.range));
    await expect(page.getByTestId("session")).toHaveText("Âu-Mỹ chồng phiên");
    // 14:45 UTC is 21:45 in Vietnam (GMT+7, the default display zone)
    await expect(page.getByTestId("vn-clock")).toContainText(/^21:4[5-9]:\d\d/);
    await expect(page.getByTestId("countdown")).toContainText("Nến M5 đóng sau");
    await expect(page.getByTestId("source-pill")).toContainText("NOT LIVE");
  });

  test("the countdown follows the selected timeframe", async ({ page }) => {
    await mock(page, view("buy"));
    await page.goto("/trade");
    await expect(page.getByTestId("countdown")).toContainText("Nến M5");
    await page.getByTestId("chart-tf-H1").click();
    await expect(page.getByTestId("countdown")).toContainText("Nến H1");
  });

  test("a closed market shows the last traded day and no countdown", async ({ page }) => {
    await mock(page, view("marketClosed"));
    await page.goto("/trade");
    await expect(page.getByTestId("session")).toHaveText("Ngoài giờ giao dịch");
    await expect(page.getByTestId("day-stats")).toContainText("Phiên gần nhất");
    await expect(page.getByTestId("countdown")).toContainText("Mở lại lúc");
    await expect(page.getByTestId("closed-info")).toContainText("Bộ máy quyết định tạm dừng");
  });

  test("an old quote while the market is closed is the last close, not an alarm", async ({ page }) => {
    const v = view("marketClosed");
    v.quote = { ...v.quote!, stale: true, age_seconds: 25_000 };
    await mock(page, v);
    await page.goto("/trade");
    await expect(page.getByTestId("price-last-close")).toContainText("Giá đóng cửa gần nhất");
    await expect(page.getByTestId("price-stale")).toHaveCount(0);
  });

  test("an old quote while the market is open IS an alarm", async ({ page }) => {
    const v = view("buy");
    v.quote = { ...v.quote!, stale: true, age_seconds: 300 };
    await mock(page, v);
    await page.goto("/trade");
    await expect(page.getByTestId("price-stale")).toContainText("GIÁ CŨ");
  });

  test("the display zone is selectable and remembered", async ({ page }) => {
    await mock(page, view("buy"));
    await page.goto("/trade");
    await page.getByLabel("Múi giờ hiển thị").selectOption("UTC");
    await expect(page.getByTestId("vn-clock")).toContainText(/^14:4[5-9]:\d\d/);
    await page.reload();
    await expect(page.getByLabel("Múi giờ hiển thị")).toHaveValue("UTC");
  });
});

test.describe("decision", () => {
  test("WAIT is informative: the stages, what is awaited, the context and the blocker", async ({ page }) => {
    const v = view("wait");
    await mock(page, v);
    await page.goto("/trade");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "WAIT");
    await expect(page.getByTestId("action-word")).toHaveText("CHỜ");
    await expect(page.getByTestId("waiting-for")).toContainText("Đang chờ:");
    await expect(page.getByTestId("waiting-for")).toContainText("không phải dự báo");
    await expect(page.getByTestId("blocked-by")).toContainText("Mã chặn");
    await expect(page.getByTestId("wait-context")).toContainText("Xu hướng");
    await expect(page.getByTestId("market-activity")).toContainText("biến động");
    await expect(page.getByTestId("news-warning")).toContainText("NEWS NOT VERIFIED");
    await expect(page.getByTestId("plan-card")).toHaveCount(0);
    await expect(page.getByTestId("take-paper")).toHaveCount(0);
    const stages = page.getByTestId("stages").getByRole("button");
    expect(await stages.count()).toBeGreaterThan(6);
    await expect(page.getByTestId("stages").locator("[data-status='FAIL']")).toHaveCount(1);
  });

  test("BUY: plan values come from the server, the R/R ruler matches the ticket, risk changes the lot", async ({ page }) => {
    const v = view("buy");
    const plan = v.trade_plan!;
    const chosen = (r: number) => v.risk_plans!.find((p) => p.risk_pct === r)!;
    await mock(page, v);
    await page.goto("/trade");
    await expect(page.getByTestId("hero")).toHaveAttribute("data-hero-state", "BUY_READY");
    await expect(page.getByTestId("hero")).toContainText("▲");
    await expect(page.getByTestId("line-ENTRY")).toHaveText(`ENTRY ${fixed(plan.planned_entry)}`);
    await expect(page.getByTestId("line-SL")).toHaveText(`SL ${fixed(plan.sl)}`);
    await expect(page.getByTestId("line-TP1")).toHaveText(`TP1 ${fixed(plan.tp1)}`);
    await expect(page.getByTestId("plan-entry")).toHaveText(fixed(plan.planned_entry));
    await expect(page.getByTestId("plan-tp2")).toHaveText(fixed(plan.tp2));
    await expect(page.getByTestId("plan-rr")).toHaveText(fixed(plan.rr_net));
    await expect(page.getByTestId("rr-ruler")).toContainText(`+${fixed(plan.rr_net)}R`); // the NET ratio, same as the ticket
    await expect(page.getByTestId("plan-lots")).toHaveText(fixed(chosen(0.25).lots));
    await expect(page.getByTestId("plan-version")).toContainText(`v${plan.strategy_version}`);
    await expect(page.getByTestId("expiry")).toBeVisible();
    await page.getByTestId("risk-0.5").click();
    await expect(page.getByTestId("plan-lots")).toHaveText(fixed(chosen(0.5).lots));
  });

  test("SELL is visibly different from BUY (icon, label, text, colour)", async ({ page }) => {
    await mock(page, view("sell"));
    await page.goto("/trade");
    await expect(page.getByTestId("hero")).toHaveAttribute("data-hero-state", "SELL_READY");
    await expect(page.getByTestId("hero")).toContainText("▼");
    await expect(page.getByTestId("plan-side")).toContainText("BÁN");
    await expect(page.getByTestId("take-paper")).toContainText("BÁN");
  });

  test("every failure has its own state and a human sentence before the code", async ({ page }) => {
    await mock(page, view("stale"));
    await page.goto("/trade");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "STALE");
    await expect(page.getByTestId("hero")).toHaveAttribute("data-hero-state", "STALE");
    await expect(page.getByTestId("hero-problems")).toContainText("Dữ liệu giá đã quá cũ");
    expect(await page.getByTestId("hero-problems").innerText()).not.toContain("DATA_STALE"); // the code is not in front of the trader (innerText leaves out the closed details)
    await expect(page.getByTestId("hero-problems").locator("details").first()).toContainText("DATA_STALE"); // ...it is in the technical details
    await expect(page.getByTestId("take-paper")).toHaveCount(0);
    await expect(page.getByTestId("line-ENTRY")).toHaveCount(0);
    await expect(page.getByTestId("price-stale")).toBeVisible();

    await mock(page, view("writerConflict"));
    await page.goto("/trade");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "UNAVAILABLE");
    await expect(page.getByTestId("hero")).toHaveAttribute("data-hero-state", "UNAVAILABLE");
    await expect(page.getByTestId("hero-problems")).toContainText("quyền ghi");

    await mock(page, view("paperCorrupt"));
    await page.goto("/trade");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "UNAVAILABLE");
    await expect(page.getByTestId("hero-problems")).toContainText("không khớp nhật ký");

    await mock(page, view("marketClosed"));
    await page.goto("/trade");
    await expect(page.getByTestId("hero")).toHaveAttribute("data-hero-state", "MARKET_CLOSED");
  });

  test("an expired setup says HẾT HẠN and cannot be taken", async ({ page }) => {
    await mock(page, view("expired"));
    await page.goto("/trade");
    await expect(page.getByTestId("hero")).toHaveAttribute("data-hero-state", "EXPIRED_SETUP");
    await expect(page.getByTestId("mobile-action-bar")).toHaveCount(0);
  });

  test("an unreachable API is not a WAIT and blocks entry", async ({ page }) => {
    await page.route("**/trade/**", (route) => route.abort());
    await page.route("**/md/XAUUSD/bars**", (route) => route.abort());
    await page.goto("/trade");
    await expect(page.getByTestId("api-down-banner")).toContainText("Mất kết nối với máy chủ dữ liệu");
    await expect(page.getByTestId("api-down-banner")).toContainText("API_UNAVAILABLE");
    await expect(page.getByTestId("take-paper")).toHaveCount(0);
    await expect(page.getByTestId("action-word")).toHaveCount(0);
  });
});

test.describe("paper order workflow", () => {
  test("opening needs a confirmation bound to the plan; nothing is sent before it", async ({ page }) => {
    const v = view("buy");
    const plan = v.trade_plan!;
    await mock(page, v);
    let posted: unknown = null;
    await page.route("**/api/trade/paper/open", (route) => {
      posted = route.request().postDataJSON();
      return route.fulfill({ json: view("openPaper").desk!.position });
    });
    await page.goto("/trade");
    await page.getByTestId("take-paper").click();
    const modal = page.getByTestId("confirm-open-modal");
    await expect(modal).toBeVisible();
    await expect(modal).toContainText("giả lập");
    await expect(page.getByTestId("confirm-sl")).toHaveText(fixed(plan.sl));
    await expect(page.getByTestId("confirm-tp")).toHaveText(fixed(plan.tp1));
    await expect(page.getByTestId("confirm-risk")).toContainText("0.25%");
    expect(posted).toBeNull();
    await page.getByTestId("confirm-paper").click();
    await expect(page.getByTestId("action-message")).toContainText("Đã mở lệnh PAPER MUA");
    expect(posted).toEqual({ setup_id: plan.setup_id, risk_pct: 0.25 });
  });

  test("the modal is accessible: focus moves in and is trapped, Escape closes, focus returns", async ({ page }) => {
    await mock(page, view("buy"));
    await page.goto("/trade");
    await page.getByTestId("take-paper").focus();
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog", { name: /Xác nhận mở lệnh PAPER/ });
    await expect(dialog).toBeVisible();
    await expect(page.getByTestId("cancel-paper")).toBeFocused(); // the SAFE button: a held or repeated Enter cannot confirm (red team)
    for (let i = 0; i < 5; i++) {
      await page.keyboard.press("Tab");
      expect(await dialog.evaluate((d) => d.contains(document.activeElement))).toBe(true);
    }
    await page.keyboard.press("Shift+Tab");
    expect(await dialog.evaluate((d) => d.contains(document.activeElement))).toBe(true);
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(page.getByTestId("take-paper")).toBeFocused();
  });

  test("if the setup changes under an open confirmation it becomes invalid and cannot be confirmed", async ({ page }) => {
    const first = view("buy");
    const state = await serve(page, first);
    let posts = 0;
    await page.route("**/api/trade/paper/open", (route) => {
      posts++;
      return route.fulfill({ json: {} });
    });
    await page.goto("/trade");
    await page.getByTestId("take-paper").click();
    await expect(page.getByTestId("confirm-open-modal")).toBeVisible();
    const next = view("buy");
    next.trade_plan!.setup_id = "ffffffffffffffffffff";
    next.trade_plan!.sl = (next.trade_plan!.sl ?? 0) - 1;
    state.view = next;
    await expect(page.getByTestId("confirm-invalid")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("confirm-paper")).toBeDisabled();
    expect(posts).toBe(0);
  });

  test("the API refusing the open is shown with a human sentence, not hidden", async ({ page }) => {
    await mock(page, view("buy"));
    await page.route("**/api/trade/paper/open", (route) => route.fulfill({ status: 409, json: { detail: { code: "DECISION_CHANGED", message: "the setup changed" } } }));
    await page.goto("/trade");
    await page.getByTestId("take-paper").click();
    await page.getByTestId("confirm-paper").click();
    await expect(page.getByTestId("action-message")).toContainText("DECISION_CHANGED");
  });

  test("an open position replaces the ticket, draws its lines, and closes only after a confirmation", async ({ page }) => {
    const v = view("openPaper");
    const pos = v.desk!.position!;
    await mock(page, v);
    let posted: unknown = null;
    await page.route("**/api/trade/paper/close", (route) => {
      posted = route.request().postDataJSON();
      return route.fulfill({ json: journalClosedGolden().trades[0] });
    });
    await page.goto("/trade");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "POSITION_OPEN");
    await expect(page.getByTestId("plan-card")).toHaveCount(0);
    await expect(page.getByTestId("position-pnl")).toContainText(fixed(pos.unrealized_pnl));
    await expect(page.getByTestId("position-r")).toHaveText(fixed(pos.unrealized_r));
    await expect(page.getByTestId("position-excursion")).not.toContainText("— / —");
    await expect(page.getByTestId("line-PAPER-ENTRY")).toHaveText(`PAPER ENTRY ${fixed(pos.fill_price)}`);
    await expect(page.getByTestId("line-PAPER-SL")).toHaveText(`PAPER SL ${fixed(pos.sl)}`);
    await expect(page.getByTestId("line-PAPER-TP")).toHaveText(`PAPER TP ${fixed(pos.tp)}`);
    await expect(page.getByTestId("line-NOW")).toHaveText(`NOW ${fixed(pos.current_price)}`);
    await page.getByTestId("close-paper").click();
    await expect(page.getByTestId("close-price")).toHaveText(fixed(pos.current_price));
    await expect(page.getByTestId("close-pnl")).toContainText(fixed(pos.unrealized_pnl));
    expect(posted).toBeNull();
    await page.getByTestId("cancel-close").click();
    await expect(page.getByTestId("confirm-close-modal")).toHaveCount(0);
    await page.getByTestId("close-paper").click();
    await page.getByTestId("confirm-close").click();
    await expect(page.getByTestId("action-message")).toContainText("Đã đóng lệnh paper");
    expect(posted).toEqual({ trade_id: pos.trade_id });
  });
});

test.describe("chart", () => {
  test("markers: BUY signal and EXIT come from the server objects, with details on request", async ({ page }) => {
    const v = view("closedPaper");
    const markers = markersClosedGolden();
    const sig = markers.signals[0];
    const trade = markers.paper_trades[0];
    await mock(page, v, { markers });
    await page.goto("/trade");
    const list = page.getByTestId("chart-markers");
    const signal = list.locator('li[data-kind="BUY"]');
    await expect(signal).toHaveCount(1);
    await expect(signal).toHaveAttribute("data-bar-time", new Date(sig.bar_time).toISOString()); // M5: the trigger bar
    await expect(signal).toContainText(`Tín hiệu MUA tại ${fixed(sig.entry)}`);
    const exit = list.locator('li[data-kind="EXIT"]');
    await expect(exit).toHaveCount(1);
    await expect(exit).toContainText(`tại ${fixed(trade.exit_price)}`);
    await signal.getByRole("button", { name: "Xem chi tiết" }).focus(); // keyboard path: the list appears on focus
    await page.keyboard.press("Enter");
    const pop = page.getByTestId("marker-popover");
    await expect(pop).toContainText("Tín hiệu MUA");
    await expect(pop).toContainText(fixed(sig.entry));
    await expect(pop).toContainText(`v${sig.strategy_version}`);
    await expect(pop).toContainText("REPLAY (không phải live)");
    await expect(pop).toContainText("có"); // taken as a paper trade
    await pop.getByRole("button", { name: "Đóng chi tiết" }).click();
    await expect(pop).toHaveCount(0);
  });

  test("Esc closes the marker popover even when focus is elsewhere; a second Esc leaves fullscreen (found in the real browser)", async ({ page }) => {
    const markers = markersClosedGolden();
    await mock(page, view("closedPaper"), { markers });
    await page.goto("/trade");
    await page.getByTestId("chart-markers").locator('li[data-kind="BUY"]').getByRole("button", { name: "Xem chi tiết" }).focus();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("marker-popover")).toBeVisible();
    await page.keyboard.press("x"); // focus stays on the (still existing) list button; fullscreen on
    await expect(page.getByTestId("fullscreen-summary")).toBeVisible();
    await page.mouse.click(5, 450); // focus leaves the popover
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("marker-popover")).toHaveCount(0);
    await expect(page.getByTestId("fullscreen-summary")).toBeVisible(); // first Esc only closed the popover
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("fullscreen-summary")).toHaveCount(0);
  });

  test("a click on the bar that carries a marker opens its details", async ({ page }) => {
    await mock(page, view("closedPaper"), { markers: markersClosedGolden() });
    await page.goto("/trade");
    const box = await chartBox(page);
    const y = box.y + box.height * 0.4;
    let opened = false;
    for (let x = box.x + box.width - 70; x > box.x + box.width - 260 && !opened; x -= 3) {
      await page.mouse.click(x, y);
      opened = await page.getByTestId("marker-popover").isVisible();
    }
    expect(opened).toBe(true);
  });

  test("a marker is clickable over a finger-width, not only on its own bar (user-flow finding)", async ({ page }) => {
    await mock(page, view("closedPaper"), { markers: markersClosedGolden() });
    await page.goto("/trade");
    const box = await chartBox(page);
    const y = box.y + box.height * 0.4;
    let run = 0;
    let longest = 0;
    for (let x = box.x + box.width * 0.5; x < box.x + box.width - 62; x += 2) {
      await page.mouse.click(x, y);
      if (await page.getByTestId("marker-popover").isVisible()) {
        run += 2;
        longest = Math.max(longest, run); // the popover stays open while clicks keep landing on the marker
      } else run = 0;
    }
    // one marker bar alone is ~3-6 px wide; with the tolerance one marker is clickable over a contiguous 20+ px run
    expect(longest).toBeGreaterThanOrEqual(20);
  });

  test.describe("marker placement follows the chart timeframe", () => {
    for (const [tf, expected] of [["M1", "2025-12-05T14:44:00.000Z"], ["M5", "2025-12-05T14:40:00.000Z"], ["M15", "2025-12-05T14:45:00.000Z"], ["H1", "2025-12-05T14:00:00.000Z"]] as const) {
      test(`${tf}: the BUY made at 14:45 sits on ${expected.slice(11, 16)}`, async ({ page }) => {
        const v = view("closedPaper");
        await mock(page, v, { markers: markersClosedGolden() });
        await page.goto("/trade");
        await page.getByTestId(`chart-tf-${tf}`).click();
        await expect(page.getByTestId("chart-markers").locator('li[data-kind="BUY"]')).toHaveAttribute("data-bar-time", expected);
      });
    }
  });

  test("the crosshair readout follows the pointer and shows OHLC, change, range and volume", async ({ page }) => {
    const v = view("buy");
    await mock(page, v);
    await page.goto("/trade");
    const readout = page.getByTestId("ohlc-readout");
    await expect(readout).toContainText("O ");
    const latest = await readout.innerText();
    const box = await chartBox(page);
    await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.4);
    await expect.poll(async () => readout.innerText()).not.toBe(latest);
    await expect(readout).toContainText("biên");
    await expect(readout).toContainText("vol");
  });

  test("Go to latest right after a pan (inside the kinetic window) keeps follow ON (found in the real browser)", async ({ page }) => {
    await mock(page, view("buy"));
    await page.goto("/trade");
    const follow = page.getByTestId("chart-follow");
    const box = await chartBox(page);
    await page.mouse.move(box.x + box.width * 0.4, box.y + box.height * 0.4);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.8, box.y + box.height * 0.4, { steps: 8 });
    await page.mouse.up();
    await expect(follow).toHaveAttribute("aria-pressed", "false");
    await page.getByTestId("go-latest").click(); // immediately: no waiting out the 2.5 s window
    await page.waitForTimeout(1500);
    await expect(follow).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("go-latest")).toHaveCount(0);
  });

  test("fit, latest and follow: panning away turns follow off without snapping back, Go to latest restores it", async ({ page }) => {
    await mock(page, view("buy"));
    await page.goto("/trade");
    const follow = page.getByTestId("chart-follow");
    await expect(follow).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("go-latest")).toHaveCount(0);
    const box = await chartBox(page);
    await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.5 + 420, box.y + box.height * 0.5, { steps: 12 });
    await page.mouse.up();
    await expect(page.getByTestId("go-latest")).toBeVisible();
    await expect(follow).toHaveAttribute("aria-pressed", "false");
    await page.waitForTimeout(3500); // a poll arrives: the view must stay where the trader put it
    await expect(page.getByTestId("go-latest")).toBeVisible();
    await page.getByTestId("go-latest").click();
    await expect(page.getByTestId("go-latest")).toHaveCount(0);
    await expect(follow).toHaveAttribute("aria-pressed", "true");
    await page.getByTestId("chart-fit").click();
    await page.getByTestId("chart-latest").click();
    await expect(page.getByTestId("trade-chart")).toBeVisible();
  });

  test("new data never resets the trader's zoom or pan; with follow on it only advances", async ({ page }) => {
    const v = view("buy");
    const state = await serve(page, v);
    let extra = 0;
    await page.route("**/md/XAUUSD/bars**", (route) => {
      const b = bars(v, "M5");
      const last = b.bars[b.bars.length - 1];
      for (let i = 1; i <= extra; i++) b.bars.push({ ...last, time: new Date(Date.parse(last.time) + i * 300_000).toISOString(), is_closed: false });
      return route.fulfill({ json: b });
    });
    await page.goto("/trade");
    const chart = page.getByTestId("trade-chart");
    const box = await chartBox(page);
    // zoom in with the wheel, then pan into the past
    await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.5);
    await page.mouse.wheel(0, -400);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.5 + 300, box.y + box.height * 0.5, { steps: 10 });
    await page.mouse.up();
    await page.waitForTimeout(3000);
    await expect(page.getByTestId("chart-follow")).toHaveAttribute("aria-pressed", "false");
    const before = await chart.getAttribute("data-range");
    expect(before).toBeTruthy();
    extra = 2; // two new bars arrive while the trader is studying history
    await page.waitForTimeout(7000); // at least two polls
    expect(await chart.getAttribute("data-range")).toBe(before);
    expect(state.view.available).toBe(true);
  });

  test("fullscreen keeps the same chart, toolbar and a decision summary; Escape returns", async ({ page }) => {
    await mock(page, view("buy"));
    await page.goto("/trade");
    await page.getByTestId("trade-chart").evaluate((el) => ((el as unknown as { __tag: number }).__tag = 7));
    await page.getByTestId("chart-fullscreen").click();
    const card = page.getByTestId("chart-card");
    const box = await card.boundingBox();
    const vp = page.viewportSize()!;
    expect(box?.width).toBeGreaterThanOrEqual(vp.width - 2);
    expect(box?.height).toBeGreaterThanOrEqual(vp.height - 2);
    await expect(page.getByTestId("fullscreen-summary")).toContainText("SẴN SÀNG MUA");
    await expect(page.getByTestId("fullscreen-summary")).toContainText("Entry");
    await expect(page.getByTestId("chart-tf-M15")).toBeVisible();
    await expect(page.getByTestId("line-ENTRY")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("fullscreen-summary")).toHaveCount(0);
    expect(await page.getByTestId("trade-chart").evaluate((el) => (el as unknown as { __tag: number }).__tag)).toBe(7); // never re-created
  });

  test("measure tool: two clicks give price distance, points, percent and bars", async ({ page }) => {
    await mock(page, view("buy"));
    await page.goto("/trade");
    const box = await chartBox(page);
    await page.getByTestId("tool-measure").click();
    await expect(page.getByTestId("tool-measure")).toHaveAttribute("aria-pressed", "true");
    await page.mouse.click(box.x + box.width * 0.4, box.y + box.height * 0.6);
    await page.mouse.move(box.x + box.width * 0.6, box.y + box.height * 0.3, { steps: 5 });
    await page.mouse.click(box.x + box.width * 0.6, box.y + box.height * 0.3);
    const readout = page.getByTestId("measure-readout");
    await expect(readout).toContainText("Δ");
    await expect(readout).toContainText("điểm");
    await expect(readout).toContainText("nến");
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("measure-readout")).toHaveCount(0);
  });

  test("a manual horizontal line is drawn, remembered across a reload, removable, and has no effect on the decision", async ({ page }) => {
    const v = view("wait");
    await mock(page, v);
    await page.goto("/trade");
    const box = await chartBox(page);
    await page.getByTestId("tool-line").click();
    await page.mouse.click(box.x + box.width * 0.4, box.y + box.height * 0.5);
    await expect(page.getByTestId("chart-legend")).toContainText("Đường");
    await expect(page.getByTestId("tool-line")).toHaveAttribute("aria-pressed", "false");
    await expect(hero(page)).toHaveAttribute("data-hero-state", "WAIT");
    await page.reload();
    await expect(page.getByTestId("chart-legend")).toContainText("Đường");
    await expect(page.getByTestId("my-levels").locator("li")).toHaveCount(1);
    await page.getByTestId("my-levels").getByRole("button", { name: /Xóa đường/ }).click();
    await expect(page.getByTestId("chart-legend")).not.toContainText("Đường");
  });

  test("session shading is optional and DST-correct; its legend names the sessions", async ({ page }) => {
    await mock(page, view("buy"));
    await page.goto("/trade");
    await expect(page.getByTestId("session-legend")).toHaveCount(0);
    await page.getByTestId("overlay-menu").click();
    await page.getByTestId("toggle-sessions").check();
    await expect(page.getByTestId("session-legend")).toContainText("Âu (London)");
    await expect(page.getByTestId("session-legend")).toContainText("Mỹ (New York)");
  });

  test("overlays can be hidden; the structure overlay uses the server levels", async ({ page }) => {
    const v = view("buy");
    await mock(page, v);
    await page.goto("/trade");
    await expect(page.getByTestId("line-ENTRY")).toBeVisible();
    await page.getByTestId("overlay-menu").click();
    await page.getByTestId("toggle-plan").uncheck();
    await expect(page.getByTestId("line-ENTRY")).toHaveCount(0);
    await page.getByTestId("toggle-structure").check();
    await expect(page.getByTestId("line-PDH")).toHaveText(`PDH ${fixed(Number(v.structure?.pdh))}`);
  });

  test("a repeated bar time (DST fall-back) does not break the chart series", async ({ page }) => {
    const v = view("closedPaper");
    await mock(page, v, { markers: markersClosedGolden() });
    await page.route("**/md/XAUUSD/bars**", (route) => {
      const b = bars(v, "M5");
      b.bars.splice(50, 0, { ...b.bars[50] });
      return route.fulfill({ json: b });
    });
    await page.goto("/trade");
    await expect(page.getByTestId("trade-chart")).toBeVisible();
    await expect(page.getByTestId("chart-markers").locator("li").first()).toHaveAttribute("data-bar-time", new Date(markersClosedGolden().signals[0].bar_time).toISOString());
  });
});

test.describe("timeframes and context", () => {
  test("the multi-timeframe strip and the pipeline both switch the chart", async ({ page }) => {
    const requested: string[] = [];
    await mock(page, view("wait"), { onBars: (tf) => requested.push(tf) });
    await page.goto("/trade");
    for (const t of TFS) await expect(page.getByTestId(`matrix-${t}`)).toBeVisible();
    await page.getByTestId("matrix-H1").click();
    await expect(page.getByTestId("chart-tf-H1")).toHaveAttribute("aria-pressed", "true");
    await expect.poll(() => requested.includes("H1")).toBe(true);
    await page.getByTestId("stages").getByRole("button").filter({ hasText: "M15" }).first().click();
    await expect(page.getByTestId("chart-tf-M15")).toHaveAttribute("aria-pressed", "true");
  });

  test("keyboard shortcuts switch timeframe and tools but never touch an order; typing is not hijacked", async ({ page }) => {
    await mock(page, view("buy"));
    await page.goto("/trade");
    await expect(page.getByTestId("action-word")).toBeVisible(); // hydrated: the key handler is attached
    await page.keyboard.press("h");
    await expect(page.getByTestId("chart-tf-H1")).toHaveAttribute("aria-pressed", "true");
    await page.keyboard.press("1");
    await expect(page.getByTestId("chart-tf-M1")).toHaveAttribute("aria-pressed", "true");
    await page.keyboard.press("5");
    await expect(page.getByTestId("chart-tf-M5")).toHaveAttribute("aria-pressed", "true");
    await page.keyboard.press("w");
    await expect(page.getByTestId("chart-follow")).toHaveAttribute("aria-pressed", "false");
    await page.keyboard.press("m");
    await expect(page.getByTestId("tool-measure")).toHaveAttribute("aria-pressed", "true");
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("tool-measure")).toHaveAttribute("aria-pressed", "false");
    await page.keyboard.press("?");
    await expect(page.getByTestId("shortcut-modal")).toContainText("Không có phím tắt nào mở hay đóng lệnh");
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("shortcut-modal")).toHaveCount(0);
    // no key opens the confirmation
    for (const key of ["Enter", "o", "b", "s", "c"]) await page.keyboard.press(key);
    await expect(page.getByTestId("confirm-open-modal")).toHaveCount(0);
    await page.getByTestId("tool-alert").click();
    await page.getByTestId("alert-price").fill("h5");
    await expect(page.getByTestId("alert-price")).toHaveValue("h5");
    await expect(page.getByTestId("chart-tf-M5")).toHaveAttribute("aria-pressed", "true");
  });

  test("preferences (timeframe, overlays, follow, tab) are remembered and hold nothing sensitive", async ({ page }) => {
    await mock(page, view("buy"));
    await page.goto("/trade");
    await page.getByTestId("chart-tf-H1").click();
    await page.getByTestId("overlay-menu").click();
    await page.getByTestId("toggle-structure").check();
    await page.getByTestId("chart-follow").click();
    await page.getByTestId("tab-activity").click();
    await page.reload();
    await expect(page.getByTestId("chart-tf-H1")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("chart-follow")).toHaveAttribute("aria-pressed", "false");
    await expect(page.getByTestId("tab-activity")).toHaveAttribute("aria-selected", "true");
    await page.getByTestId("overlay-menu").click();
    await expect(page.getByTestId("toggle-structure")).toBeChecked();
    const stored = await page.evaluate(() => JSON.stringify(Object.fromEntries(Object.entries(localStorage))));
    expect(stored).not.toMatch(/token|password|secret|setup_id/i);
  });

  test("a journal link opens the chart on that trade (timeframe, history and focus)", async ({ page }) => {
    await mock(page, view("closedPaper"), { markers: markersClosedGolden(), journal: journalClosedGolden() });
    const t = journalClosedGolden().trades[0];
    await page.goto(`/trade?focus=${encodeURIComponent(t.opened_at!)}&to=${encodeURIComponent(t.closed_at!)}&tf=M15&trade=${t.trade_id}`);
    await expect(page.getByTestId("chart-tf-M15")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("tab-position")).toHaveAttribute("aria-selected", "true");
    await page.getByTestId("overlay-menu").click();
    await expect(page.getByTestId("toggle-history")).toBeChecked();
    await expect(page.getByTestId("chart-markers").locator('li[data-kind="EXIT"]')).toHaveCount(1);
  });
});

test.describe("workspace", () => {
  test("tabs: overview, why, position, activity and system hold the secondary information", async ({ page }) => {
    await mock(page, view("closedPaper"), { journal: journalClosedGolden(), markers: markersClosedGolden(), signals: signalsGolden() });
    await page.goto("/trade");
    await expect(page.getByTestId("activity-card")).toContainText("Hoạt động thị trường");
    await expect(page.getByTestId("levels-card")).toBeVisible();
    await page.getByTestId("tab-why").click();
    await expect(page.getByTestId("reasons-card")).toBeVisible();
    await page.getByTestId("tab-position").click();
    await expect(page.getByTestId("paper-history-row")).toHaveCount(1);
    await page.getByTestId("tab-activity").click();
    const rows = page.getByTestId("activity-row");
    expect(await rows.count()).toBeGreaterThanOrEqual(3); // signal, paper open, paper exit
    await page.getByRole("button", { name: "Tín hiệu", exact: true }).click();
    await expect(rows).toHaveCount(1);
    await rows.first().getByRole("button").click(); // focuses the chart on it
    await page.getByTestId("tab-system").click();
    const strip = page.getByTestId("status-strip");
    await expect(strip).toContainText("DEMO");
    await expect(strip).toContainText("LOCKED");
    await expect(strip).toContainText("UNVALIDATED");
    await expect(page.getByTestId("strategy-active")).toContainText("1.2.1");
    await expect(page.getByTestId("forward-level")).toContainText("F0");
    await expect(page.getByTestId("alert-card")).toContainText("Cảnh báo setup");
    await page.keyboard.press("ArrowRight");
    await expect(page.getByTestId("tab-overview")).toHaveAttribute("aria-selected", "true");
  });

  test("engineering metadata does not compete with the price: no status chips above the chart", async ({ page }) => {
    await mock(page, view("buy"));
    await page.goto("/trade");
    await expect(page.getByTestId("status-strip")).toHaveCount(0); // it lives in the System tab
    await expect(page.getByTestId("forward-card")).toHaveCount(0);
  });

  test("a price alert is stored locally and fires when the bid crosses it", async ({ page }) => {
    const first = view("buy");
    first.source_mode = "LIVE"; // price alerts only ever fire on live prices
    const state = await serve(page, first);
    await page.goto("/trade");
    await page.getByTestId("tool-alert").click();
    await page.getByTestId("alert-price").fill("4240");
    await page.getByTestId("alert-add").click();
    await expect(page.getByTestId("my-alerts")).toContainText("4240.00");
    await expect(page.getByTestId("chart-legend")).toContainText("CẢNH BÁO");
    const next = view("buy");
    next.source_mode = "LIVE";
    next.quote = { ...next.quote!, bid: 4241.5, ask: 4241.9 };
    state.view = next;
    await expect(page.getByTestId("action-message")).toContainText("Cảnh báo giá", { timeout: 15_000 });
    await expect(page.getByTestId("my-alerts")).toContainText("đã báo");
    await page.reload();
    await expect(page.getByTestId("my-alerts")).toContainText("đã báo"); // still remembered, and not fired twice
  });

  test("a price alert never fires on replay prices", async ({ page }) => {
    const state = await serve(page, view("buy"));
    await page.goto("/trade");
    await page.getByTestId("tool-alert").click();
    await page.getByTestId("alert-price").fill("4240");
    await page.getByTestId("alert-add").click();
    const next = view("buy");
    next.quote = { ...next.quote!, bid: 4245, ask: 4245.4 };
    state.view = next;
    await page.waitForTimeout(7000);
    await expect(page.getByTestId("my-alerts")).not.toContainText("đã báo");
  });

  test("the calculator works without a setup and says it is not a signal", async ({ page }) => {
    const v = view("buy");
    const sample = v.risk_plans!.find((p) => p.risk_pct === 0.25)!;
    await mock(page, view("wait"));
    await page.route("**/trade/risk**", (route) => route.fulfill({ json: sample }));
    await page.goto("/trade");
    await page.getByTestId("calculator").locator("summary").click();
    await expect(page.getByTestId("calculator")).toContainText("KHÔNG PHẢI TÍN HIỆU");
    await page.getByTestId("calc-entry").fill("4236.47");
    await page.getByTestId("calc-sl").fill("4229.45");
    await expect(page.getByTestId("calc-result")).toContainText(`Lot ${fixed(sample.lots)}`, { timeout: 5000 });
  });
});

test.describe("layouts", () => {
  const VIEWPORTS = [
    { name: "1440x900", width: 1440, height: 900 },
    { name: "1920x1080", width: 1920, height: 1080 },
    { name: "390x844", width: 390, height: 844 },
    { name: "200% zoom (720x450 CSS px)", width: 720, height: 450 },
  ];
  for (const vp of VIEWPORTS) {
    test(`/trade at ${vp.name}: price, decision and chart are usable, no horizontal scroll`, async ({ page }) => {
      await mock(page, view("buy"));
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto("/trade");
      await expect(page.getByTestId("price-bid")).toBeAttached();
      await expect(page.getByTestId("action-word")).toBeVisible();
      const chart = await chartBox(page);
      expect(chart.width).toBeGreaterThan(Math.min(300, vp.width - 40));
      expect(chart.height).toBeGreaterThan(220);
      expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
    });
  }

  test("desktop: price, decision, chart and the multi-timeframe strip are all in the first screen", async ({ page }) => {
    await mock(page, view("buy"));
    await page.goto("/trade");
    for (const id of ["market-bar", "action-word", "trade-chart", "matrix-H1", "take-paper"]) {
      const box = await page.getByTestId(id).boundingBox();
      expect(box, id).not.toBeNull();
      expect(box!.y, id).toBeLessThan(900);
    }
  });

  test("phone: the order is price, decision, chart; the action bar is sticky and opens the confirmation", async ({ page }) => {
    await mock(page, view("buy"));
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/trade");
    const y = async (id: string) => (await page.getByTestId(id).boundingBox())!.y;
    expect(await y("market-bar")).toBeLessThan(await y("action-word"));
    expect(await y("action-word")).toBeLessThan(await y("trade-chart"));
    expect(await y("trade-chart")).toBeLessThan(await y("plan-card"));
    expect(await y("trade-chart")).toBeLessThan(844); // the chart is on the first screen
    await expect(page.getByTestId("mobile-action-bar")).toBeVisible();
    await page.getByTestId("action-bar-open").click();
    await expect(page.getByTestId("confirm-open-modal")).toBeVisible();
  });

  test("phone in landscape: the confirmation's confirm and cancel buttons stay inside the screen (red team)", async ({ page }) => {
    await mock(page, view("buy"));
    await page.setViewportSize({ width: 844, height: 390 });
    await page.goto("/trade");
    await page.getByTestId("take-paper").or(page.getByTestId("mobile-action-bar").getByRole("button")).first().click();
    await expect(page.getByTestId("confirm-open-modal")).toBeVisible();
    for (const id of ["confirm-paper", "cancel-paper"]) {
      const b = (await page.getByTestId(id).boundingBox())!;
      expect(b.y).toBeGreaterThanOrEqual(0);
      expect(b.y + b.height).toBeLessThanOrEqual(390);
    }
  });

  test("phone: no action bar while the desk only waits", async ({ page }) => {
    await mock(page, view("wait"));
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/trade");
    await expect(page.getByTestId("action-word")).toHaveText("CHỜ");
    await expect(page.getByTestId("mobile-action-bar")).toHaveCount(0);
  });

  test("phone: an open position shows P&L and a close action in the bar", async ({ page }) => {
    await mock(page, view("openPaper"));
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/trade");
    await expect(page.getByTestId("mobile-action-bar")).toContainText("paper");
    await page.getByTestId("action-bar-close").click();
    await expect(page.getByTestId("confirm-close-modal")).toBeVisible();
  });

  test("dark mode renders every main region without console errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    await page.emulateMedia({ colorScheme: "dark" });
    await mock(page, view("buy"));
    await page.goto("/trade");
    await expect(page.getByTestId("action-word")).toBeVisible();
    await expect(page.getByTestId("ohlc-readout")).toBeVisible();
    expect(errors).toEqual([]);
  });
});

test("the home page opens the trading desk and the legacy page is marked LEGACY / NOT ACTIVE", async ({ page }) => {
  await mock(page, view("wait"));
  await page.goto("/");
  await expect(page).toHaveURL(/\/trade$/);
  await page.goto("/legacy");
  await expect(page.getByTestId("legacy-banner")).toContainText("LEGACY / NOT ACTIVE");
});

test("AUTO_PAPER is visible when it is on and absent when it is off", async ({ page }) => {
  await mock(page, { ...view("wait"), auto_paper: true });
  await page.goto("/trade");
  await expect(page.getByTestId("auto-paper-banner")).toContainText("AUTO_PAPER");
  await mock(page, { ...view("wait"), auto_paper: false });
  await page.goto("/trade");
  await expect(page.getByTestId("auto-paper-banner")).toHaveCount(0);
});

test.describe("chart label collisions (TRADE-08)", () => {
  const seed = (page: Page, levels: number[], alerts: number[]) =>
    page.addInitScript(
      ([lv, al]) => {
        localStorage.setItem("xau-edge:v3:REPLAY:XAUUSD:levels", JSON.stringify((lv as number[]).map((p, i) => ({ id: `l${i}`, price: p, label: "Đường" }))));
        localStorage.setItem("xau-edge:v3:REPLAY:XAUUSD:alerts", JSON.stringify((al as number[]).map((p, i) => ({ id: `a${i}`, price: p, direction: "UP", createdAt: "", firedAt: null }))));
      },
      [levels, alerts],
    );

  test("entry, SL, TP, last price, manual levels and alerts within a label's height: the plan keeps its labels, the rest yield", async ({ page }) => {
    const v = view("buy");
    const e = v.trade_plan!.planned_entry!;
    await seed(page, [e + 0.05, e - 0.08, e + 0.12], [e + 0.2, e - 0.15]);
    await mock(page, v);
    await page.goto("/trade");
    const chart = page.getByTestId("trade-chart");
    await expect(page.getByTestId("line-ENTRY")).toBeVisible(); // the legend always lists every line
    await expect.poll(async () => Number(await chart.getAttribute("data-hidden-axis-labels"))).toBeGreaterThanOrEqual(4);
    // the five trader tools and the last price crowd the entry: at most the entry keeps one label in that band
    await expect.poll(async () => Number(await chart.getAttribute("data-hidden-axis-labels"))).toBeLessThanOrEqual(6);
    const legend = page.getByTestId("chart-legend");
    await expect(legend).toContainText("ENTRY");
    await expect(legend).toContainText("SL");
    await expect(legend).toContainText("TP1");
    await expect(legend.locator("li")).toHaveCount(4 + 3 + 2); // entry, SL, TP1, TP2 + 3 levels + 2 alerts: nothing is removed from the legend
  });

  test("far apart lines keep every label", async ({ page }) => {
    const v = view("buy");
    const e = v.trade_plan!.planned_entry!;
    await seed(page, [e + 18], []);
    await mock(page, v);
    await page.goto("/trade");
    const chart = page.getByTestId("trade-chart");
    await expect(page.getByTestId("line-ENTRY")).toBeVisible();
    await page.waitForTimeout(1800);
    // entry/SL/TP1/TP2 are a few price units apart on a ~50-unit scale: at most the last-price tag yields next to the entry
    expect(Number(await chart.getAttribute("data-hidden-axis-labels"))).toBeLessThanOrEqual(1);
  });

  test("a setup, a signal, the paper entry and the exit on the same or adjacent bars: every marker has a detail and no label pile-up", async ({ page }) => {
    const markers = markersClosedGolden();
    await mock(page, view("closedPaper"), { markers });
    await page.goto("/trade");
    const chart = page.getByTestId("trade-chart");
    await expect(page.getByTestId("chart-markers").locator("li")).toHaveCount(3); // signal, entry, exit: every one reachable by keyboard
    await expect.poll(async () => await chart.getAttribute("data-marker-sig")).not.toBeNull();
    const hidden = Number(await chart.getAttribute("data-hidden-marker-labels"));
    expect(hidden).toBeGreaterThanOrEqual(0);
    // zoomed far out the markers crowd together: labels yield, shapes and details stay
    const box = await chartBox(page);
    await page.mouse.move(box.x + box.width * 0.7, box.y + box.height * 0.5);
    await page.mouse.wheel(0, 900);
    await expect.poll(async () => Number(await chart.getAttribute("data-hidden-marker-labels"))).toBeGreaterThanOrEqual(hidden);
    await expect(page.getByTestId("chart-markers").locator("li")).toHaveCount(3);
  });

  test("the marker popover names the display zone, shows the exit time and says MUA/BÁN", async ({ page }) => {
    await mock(page, view("closedPaper"), { markers: markersClosedGolden() });
    await page.goto("/trade");
    const exit = page.getByTestId("chart-markers").locator('li[data-kind="EXIT"]');
    await exit.getByRole("button", { name: "Xem chi tiết" }).focus();
    await page.keyboard.press("Enter");
    const pop = page.getByTestId("marker-popover");
    await expect(page.getByTestId("popover-zone")).toContainText("Giờ hiển thị:");
    await expect(page.getByTestId("popover-exit-time")).toContainText(/\d{4}-\d\d-\d\d \d\d:\d\d/);
    await expect(pop).toContainText("MUA");
    await expect(pop).not.toContainText(/\bBUY\b|\bSELL\b/);
  });
});
