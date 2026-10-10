import { expect, test } from "@playwright/test";
import { mock, view, type GoldenName } from "./fixtures/trade";

/**
 * Signal lifecycle, action-first: on every state the page must answer "what am I allowed to do now?" with ONE of
 * CHỜ / MUA PAPER / BÁN PAPER / GIỮ VỊ THẾ / ĐÃ THOÁT / KHÔNG KHẢ DỤNG, and say WHEN. A lean of the market is a BIAS shown
 * beside it and never in its place. Every view here is a real backend serialization (acceptance replay), never hand-written.
 */

// [golden, action code, action word, bias, "when" regex]
const CASES: [GoldenName, string, string, string, RegExp][] = [
  ["wait", "WAIT", "CHỜ", "NONE", /Chưa làm gì/],
  ["buyWatch", "WAIT", "CHỜ", "BUY", /Chỉ MUA khi: M15 có nhịp pullback/],
  ["buyArmed", "WAIT", "CHỜ", "BUY", /Chỉ MUA khi: nến M5 kế tiếp đóng xác nhận trigger tăng/],
  ["buy", "BUY", "MUA PAPER", "BUY", /Tín hiệu MUA đã xác nhận\. Mua ngay ở khoảng 4236\.47/],
  ["sellWatch", "WAIT", "CHỜ", "SELL", /Chỉ BÁN khi: M15 có nhịp pullback/],
  ["sellArmed", "WAIT", "CHỜ", "SELL", /Chỉ BÁN khi: nến M5 kế tiếp đóng xác nhận trigger giảm/],
  ["sell", "SELL", "BÁN PAPER", "SELL", /Tín hiệu BÁN đã xác nhận\. Bán ngay ở khoảng/],
  ["openPaper", "HOLD", "GIỮ VỊ THẾ", "BUY", /Chưa có điều kiện thoát\./],
  ["closedPaper", "EXIT", "ĐÃ THOÁT", "NONE", /Đã thoát vì chạm tp/i],
  ["sellInvalidated", "WAIT", "CHỜ", "NONE", /Chưa làm gì/],
  ["expired", "WAIT", "CHỜ", "NONE", /Chưa làm gì/],
  ["marketClosed", "WAIT", "CHỜ", "NONE", /tự tính lại khi thị trường mở cửa/],
  ["stale", "UNAVAILABLE", "KHÔNG KHẢ DỤNG", "NONE", /Đừng vào lệnh/],
  ["writerConflict", "UNAVAILABLE", "KHÔNG KHẢ DỤNG", "NONE", /Đừng vào lệnh/],
];

for (const [name, code, word, bias, when] of CASES) {
  test(`${name}: the action is ${code} (${word}), the bias is ${bias}, and it says when`, async ({ page }) => {
    const v = view(name);
    expect(v.hero.action.code).toBe(code);
    await mock(page, v);
    await page.goto("/trade");
    const hero = page.getByTestId("hero");
    await expect(hero).toHaveAttribute("data-action", code);
    await expect(page.getByTestId("action-word")).toHaveText(word);
    await expect(page.getByTestId("action-when")).toContainText(when);
    if (code === "WAIT" && bias !== "NONE") await expect(hero).toHaveAttribute("data-bias", bias);
  });
}

test("a lean of the market is a BIAS beside a prohibited action, never an order", async ({ page }) => {
  for (const name of ["buyWatch", "buyArmed", "sellWatch", "sellArmed"] as const) {
    await mock(page, view(name));
    await page.goto("/trade");
    const hero = page.getByTestId("hero");
    await expect(hero).toHaveAttribute("data-action", "WAIT");
    // the dominant word is CHỜ, never MUA/BÁN; the prohibition sits next to it
    await expect(page.getByTestId("action-word")).toHaveText("CHỜ");
    await expect(page.getByTestId("action-word")).not.toContainText(/MUA|BÁN/);
    await expect(page.getByTestId("no-entry")).toHaveText("Không vào lệnh");
    // the bias is small, labelled and explicitly "not an order"; it is not styled like a BUY/SELL card
    await expect(page.getByTestId("bias-value")).toContainText("không phải lệnh");
    await expect(hero).not.toHaveClass(/bg-emerald|bg-red-7/);
    // no way to open anything, no sticky action bar
    await expect(page.getByTestId("take-paper")).toHaveCount(0);
    await expect(page.getByTestId("mobile-action-bar")).toHaveCount(0);
    // the biggest text of the card is the action word, much larger than the bias
    const sizes = await page.evaluate(() => ({
      word: parseFloat(getComputedStyle(document.querySelector("[data-testid=action-word]")!).fontSize),
      bias: parseFloat(getComputedStyle(document.querySelector("[data-testid=bias-value]")!).fontSize),
    }));
    expect(sizes.word).toBeGreaterThanOrEqual(sizes.bias * 2);
  }
});

test("only a READY setup is permission: it is the only state with a coloured card and a take-paper button", async ({ page }) => {
  for (const [name, expectOrder] of [["wait", false], ["buyArmed", false], ["buy", true], ["sell", true], ["openPaper", false], ["closedPaper", false], ["stale", false]] as const) {
    await mock(page, view(name));
    await page.goto("/trade");
    await expect(page.getByTestId("take-paper")).toHaveCount(expectOrder ? 1 : 0);
    const cls = (await page.getByTestId("hero").getAttribute("class")) ?? "";
    expect(/bg-emerald-700|bg-red-700/.test(cls), name).toBe(expectOrder);
  }
});

test("an armed setup says how many M5 bars it still has, and that it is not yet allowed", async ({ page }) => {
  await mock(page, view("sellArmed"));
  await page.goto("/trade");
  await expect(page.getByTestId("action-when")).toContainText(/còn \d nến M5/);
  await expect(page.getByTestId("action-sub")).toContainText("Setup đã hình thành");
  await expect(page.getByTestId("action-sub")).toContainText("chưa được vào lệnh");
  await expect(page.getByTestId("setup-stage")).toContainText("chờ trigger M5");
});

test("HOLD names the exit rule and the latest time exit; the stale entry never dominates", async ({ page }) => {
  const v = view("openPaper");
  expect(v.hero.action.thesis).toBe("INTACT");
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("action-when")).toContainText("luận điểm còn vững");
  await expect(page.getByTestId("action-when")).toContainText(/Bàn tự thoát khi chạm SL 4229\.45 \(-1R\) hoặc TP 4250\.51, hoặc muộn nhất lúc \d\d:\d\d/);
  await expect(page.getByTestId("action-word")).not.toHaveText(/MUA|BÁN/);
  await expect(page.getByTestId("plan-card")).toHaveCount(0);
  await expect(page.getByTestId("take-paper")).toHaveCount(0);
  await expect(page.getByTestId("action-sub")).toContainText("MUA từ");
});

test("a weak thesis is stated, not hidden", async ({ page }) => {
  const v = view("openPaper");
  v.hero.action = { ...v.hero.action, thesis: "WEAK" };
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("action-when")).toContainText("luận điểm đang YẾU");
});

test("EXIT shows the reason, result, R and how long, and no BUY/SELL command lingers", async ({ page }) => {
  await mock(page, view("closedPaper"));
  await page.goto("/trade");
  await expect(page.getByTestId("action-sub")).toContainText("Chạm TP");
  await expect(page.getByTestId("action-sub")).toContainText("R");
  await expect(page.getByTestId("action-sub")).toContainText("phút");
  await expect(page.getByTestId("take-paper")).toHaveCount(0);
  await expect(page.getByTestId("action-word")).toHaveText("ĐÃ THOÁT");
});

test("an invalidated or expired setup is CHỜ with a plain note, not an exit and not an order", async ({ page }) => {
  await mock(page, view("sellInvalidated"));
  await page.goto("/trade");
  await expect(page.getByTestId("action-word")).toHaveText("CHỜ");
  await expect(page.getByTestId("take-paper")).toHaveCount(0);
  await mock(page, view("expired"));
  await page.reload();
  await expect(page.getByTestId("action-sub")).toContainText("hết hiệu lực");
});

// Pre-registered mobile gate (docs/reports/TRADE08_AB_RUBRIC.md): at 390x844, without scrolling, the trader sees the price, the
// action, the one sentence "when", and at least 280 px of candles; the sticky bar never covers them.
for (const name of ["wait", "buyWatch", "sellArmed", "buy", "openPaper", "closedPaper"] as const) {
  test(`phone 390x844 (${name}): price, action and 'when' on the first screen, chart at least 280 px`, async ({ page }) => {
    await mock(page, view(name));
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/trade");
    await expect(page.getByTestId("action-word")).toBeVisible();
    await page.waitForTimeout(500);
    const m = await page.evaluate(() => {
      const q = (id: string) => document.querySelector(`[data-testid=${id}]`)!;
      const bar = document.querySelector("[data-testid=mobile-action-bar]");
      const floor = bar ? bar.getBoundingClientRect().top : innerHeight;
      const c = q("trade-chart").getBoundingClientRect();
      return {
        priceBottom: q("price-bid").getBoundingClientRect().bottom,
        wordBottom: q("action-word").getBoundingClientRect().bottom,
        whenBottom: q("action-when").getBoundingClientRect().bottom,
        floor,
        chartVisible: Math.max(0, Math.min(floor, c.bottom, innerHeight) - Math.max(0, c.top)),
        scrollW: document.documentElement.scrollWidth,
      };
    });
    expect(m.priceBottom).toBeLessThan(m.floor);
    expect(m.wordBottom).toBeLessThan(m.floor);
    expect(m.whenBottom).toBeLessThan(m.floor);
    expect(m.chartVisible).toBeGreaterThanOrEqual(280);
    expect(m.scrollW).toBeLessThanOrEqual(390);
  });
}

test("server-expired plan says the plan is gone; a plan that expires in the browser flips READY to SKIP", async ({ page }) => {
  await mock(page, view("expired"));
  await page.goto("/trade");
  await expect(page.getByTestId("action-sub")).toContainText("hết hiệu lực");
  const v = view("buy");
  v.trade_plan!.expires_at = new Date(Date.parse(v.served_at!) - 1000).toISOString(); // already past on the server clock
  await mock(page, v);
  await page.reload();
  await expect(page.getByTestId("action-word")).toHaveText("BỎ QUA");
  await expect(page.getByTestId("take-paper")).toBeDisabled();
});

test("replay: countdowns run on the replay clock only, they never tick up and down on the wall clock (TRADE-07 jitter)", async ({ page }) => {
  const v = view("buy");
  expect(v.source_mode).not.toBe("LIVE");
  await mock(page, v);
  await page.goto("/trade");
  const countdown = page.getByTestId("countdown");
  const expiry = page.getByTestId("expiry");
  await expect(countdown).toContainText("đóng sau"); // the view has arrived
  await expect(expiry).toBeAttached();
  const c0 = await countdown.innerText();
  const e0 = await expiry.innerText();
  const seen = new Set<string>();
  for (let i = 0; i < 6; i++) {
    await page.waitForTimeout(1000); // wall time passes; the replay clock (served_at) does not move
    seen.add(`${await countdown.innerText()}|${await expiry.innerText()}`);
  }
  expect(seen).toEqual(new Set([`${c0}|${e0}`]));
});

test("the lifecycle stepper follows the action: Thiên hướng → Setup → Trigger → Sẵn sàng → Mở PAPER → Giữ → Thoát", async ({ page }) => {
  const ord = ["BIAS", "SETUP", "TRIGGER", "READY", "OPENED", "HOLD", "EXIT"];
  for (const [name, current] of [["wait", "BIAS"], ["buyWatch", "SETUP"], ["buyArmed", "TRIGGER"], ["buy", "READY"], ["openPaper", "HOLD"], ["closedPaper", "EXIT"]] as const) {
    await mock(page, view(name));
    await page.goto("/trade");
    const steps = page.getByTestId("lifecycle").locator("li");
    await expect(steps).toHaveCount(7);
    const status = await steps.evaluateAll((els) => els.map((e) => `${e.getAttribute("data-step")}:${e.getAttribute("data-status")}`));
    const idx = ord.indexOf(current);
    expect(status, name).toEqual(ord.map((k, i) => `${k}:${i < idx ? "done" : i === idx ? (k === "EXIT" ? "done" : "current") : "pending"}`));
  }
});

test("offline for more than a minute: the hero is UNAVAILABLE, the old plan is folded away, nothing can be opened; reconnection recovers by itself", async ({ page }) => {
  await page.clock.install();
  const online = { on: true };
  const v = view("buy");
  await mock(page, v);
  await page.route("**/trade/decision", (route) => (online.on ? route.fulfill({ json: v }) : route.abort()));
  await page.goto("/trade");
  await expect(page.getByTestId("action-word")).toHaveText("MUA PAPER");
  await expect(page.getByTestId("take-paper")).toBeEnabled();

  online.on = false;
  await page.clock.fastForward(65_000); // a minute of failed polls
  await expect(page.getByTestId("action-word")).toHaveText("KHÔNG KHẢ DỤNG");
  await expect(page.getByTestId("hero")).toHaveAttribute("data-action", "UNAVAILABLE");
  await expect(page.getByTestId("api-down-banner")).toContainText("Mất kết nối với máy chủ dữ liệu");
  await expect(page.getByTestId("api-down-banner")).toContainText("tự cập nhật"); // it says it will recover on its own
  await expect(page.getByTestId("stale-plan")).toBeVisible();
  await expect(page.getByTestId("stale-plan")).not.toHaveAttribute("open", ""); // folded: entry/SL/TP are not in front of the trader
  await expect(page.getByTestId("take-paper")).toBeDisabled();
  await expect(page.getByTestId("mobile-action-bar")).toHaveCount(0);
  await expect(page.getByTestId("line-ENTRY")).toHaveCount(0); // the plan is not drawn on the chart either

  online.on = true;
  await page.clock.fastForward(4_000); // the next poll succeeds
  await expect(page.getByTestId("action-word")).toHaveText("MUA PAPER", { timeout: 10_000 });
  await expect(page.getByTestId("api-down-banner")).toHaveCount(0);
  await expect(page.getByTestId("stale-plan")).toHaveCount(0);
  await expect(page.getByTestId("take-paper")).toBeEnabled();
});

// Pre-registered landscape/zoom gate: a wide but SHORT viewport gets two columns (chart | decision) and folded market details.
for (const [w, h, label] of [[844, 390, "phone landscape"], [720, 450, "200% zoom"]] as const) {
  for (const name of ["wait", "buyWatch", "buy", "openPaper"] as const) {
    test(`${label} ${w}x${h} (${name}): price, action and at least 160 px of chart on the first screen, nothing overflows`, async ({ page }) => {
      await mock(page, view(name));
      await page.setViewportSize({ width: w, height: h });
      await page.goto("/trade");
      await expect(page.getByTestId("action-word")).toBeVisible();
      await page.waitForTimeout(500);
      const m = await page.evaluate(() => {
        const q = (id: string) => document.querySelector(`[data-testid=${id}]`)!;
        const c = q("trade-chart").getBoundingClientRect();
        const bar = document.querySelector("[data-testid=mobile-action-bar]");
        const bb = bar ? bar.getBoundingClientRect() : null;
        const floor = bb && bb.left < c.right ? bb.top : innerHeight; // in a short viewport the bar sits under the side column only, never over the chart
        return {
          priceBottom: q("price-bid").getBoundingClientRect().bottom,
          wordBottom: q("action-word").getBoundingClientRect().bottom,
          chartVisible: Math.max(0, Math.min(floor, c.bottom, innerHeight) - Math.max(0, c.top)),
          sideBySide: q("action-word").getBoundingClientRect().left > c.right - 4,
          scrollW: document.documentElement.scrollWidth,
          vw: innerWidth,
        };
      });
      expect(m.priceBottom).toBeLessThan(h);
      expect(m.wordBottom).toBeLessThan(h);
      expect(m.chartVisible).toBeGreaterThanOrEqual(160);
      expect(m.sideBySide).toBe(true);
      expect(m.scrollW).toBeLessThanOrEqual(m.vw);
      if (name === "buy" || name === "openPaper") {
        // the open/close button must be reachable WITHOUT scrolling (red team: it was below the fold)
        const btn = page.getByTestId(name === "buy" ? "action-bar-open" : "action-bar-close");
        await expect(btn).toBeVisible();
        const b = (await btn.boundingBox())!;
        expect(b.y + b.height).toBeLessThanOrEqual(h);
        expect(b.x).toBeGreaterThan(w * 0.55); // under the decision column, not over the chart
      }
    });
  }
}
