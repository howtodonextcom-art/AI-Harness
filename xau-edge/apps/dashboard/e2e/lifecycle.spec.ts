import { expect, test } from "@playwright/test";
import { mock, view, type GoldenName } from "./fixtures/trade";

/**
 * Signal lifecycle, action-first: on every state the page must answer "what should I do now?" with ONE
 * of WAIT / WATCH BUY / WATCH SELL / BUY / SELL / HOLD / EXIT / UNAVAILABLE and say WHEN. Every view
 * here is a real backend serialization (acceptance replay), never hand-written.
 */

const CASES: [GoldenName, string, string, RegExp][] = [
  ["wait", "WAIT", "CHỜ", /Chưa làm gì/],
  ["buyWatch", "WATCH_BUY", "THEO DÕI MUA", /Mua khi: \(1\) M15 có nhịp pullback/],
  ["buyArmed", "WATCH_BUY", "THEO DÕI MUA", /nến M5 kế tiếp đóng kích hoạt tăng/],
  ["buy", "BUY", "MUA", /Mua ngay ở khoảng 4236\.47/],
  ["sellWatch", "WATCH_SELL", "THEO DÕI BÁN", /Bán khi: \(1\) M15 có nhịp pullback/],
  ["sellArmed", "WATCH_SELL", "THEO DÕI BÁN", /nến M5 kế tiếp đóng kích hoạt giảm/],
  ["sell", "SELL", "BÁN", /Bán ngay ở khoảng/],
  ["openPaper", "HOLD", "GIỮ LỆNH", /Bàn tự thoát khi chạm SL 4229\.45 \(-1R\) hoặc TP 4250\.51/],
  ["closedPaper", "EXIT", "ĐÃ THOÁT", /Lệnh đã đóng/],
  ["sellInvalidated", "WAIT", "CHỜ", /Chưa làm gì/],
  ["expired", "WAIT", "CHỜ", /Chưa làm gì/],
  ["marketClosed", "WAIT", "CHỜ", /tự tính lại khi thị trường mở cửa/],
  ["stale", "UNAVAILABLE", "KHÔNG KHẢ DỤNG", /Đừng vào lệnh/],
  ["writerConflict", "UNAVAILABLE", "KHÔNG KHẢ DỤNG", /Đừng vào lệnh/],
];

for (const [name, code, word, when] of CASES) {
  test(`${name}: the action is ${code} (${word}) and says when`, async ({ page }) => {
    const v = view(name);
    expect(v.hero.action.code === "WAIT" || v.hero.action.code === code).toBe(true);
    await mock(page, v);
    await page.goto("/trade");
    const hero = page.getByTestId("hero");
    await expect(hero).toHaveAttribute("data-action", code);
    await expect(page.getByTestId("action-word")).toHaveText(word);
    await expect(page.getByTestId("action-when")).toContainText("Khi nào?");
    await expect(page.getByTestId("action-when")).toContainText(when);
  });
}

test("a WATCH is never styled like an order: dashed border, amber, an eye icon", async ({ page }) => {
  await mock(page, view("buyArmed"));
  await page.goto("/trade");
  const hero = page.getByTestId("hero");
  await expect(hero).toHaveClass(/border-dashed/);
  await expect(hero).toContainText("👁");
  await expect(page.getByTestId("take-paper")).toHaveCount(0);
  await expect(page.getByTestId("mobile-action-bar")).toHaveCount(0);
});

test("an armed setup says how many M5 bars it still has", async ({ page }) => {
  await mock(page, view("sellArmed"));
  await page.goto("/trade");
  await expect(page.getByTestId("action-when")).toContainText(/còn \d M5? ?nến|còn \d nến M5/);
  await expect(page.getByTestId("action-sub")).toContainText("Setup đã hình thành");
});

test("HOLD names the exit rule and whether the entry thesis still stands; the stale entry never dominates", async ({ page }) => {
  const v = view("openPaper");
  expect(v.hero.action.thesis).toBe("INTACT");
  await mock(page, v);
  await page.goto("/trade");
  await expect(page.getByTestId("action-when")).toContainText("luận điểm còn vững");
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

test("EXIT shows the reason, result and R", async ({ page }) => {
  await mock(page, view("closedPaper"));
  await page.goto("/trade");
  await expect(page.getByTestId("action-sub")).toContainText("Chạm TP");
  await expect(page.getByTestId("action-sub")).toContainText("R");
});

test("on a phone the 'when' sentence is collapsed to two lines and can be expanded", async ({ page }) => {
  await mock(page, view("buyWatch"));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/trade");
  const toggle = page.getByTestId("action-when-toggle");
  await expect(toggle).toBeVisible();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  const h1 = (await page.getByTestId("action-when").boundingBox())!.height;
  await toggle.click();
  const h2 = (await page.getByTestId("action-when").boundingBox())!.height;
  expect(h2).toBeGreaterThan(h1);
});

test("server-expired plan says the plan is gone; a plan that expires in the browser flips READY to SKIP", async ({ page }) => {
  await mock(page, view("expired"));
  await page.goto("/trade");
  await expect(page.getByTestId("action-sub")).toContainText("hết hạn");
  const v = view("buy");
  v.trade_plan!.expires_at = new Date(Date.parse(v.served_at!) - 1000).toISOString(); // already past on the server clock
  await mock(page, v);
  await page.reload();
  await expect(page.getByTestId("action-word")).toHaveText("BỎ QUA");
  await expect(page.getByTestId("take-paper")).toBeDisabled();
});
