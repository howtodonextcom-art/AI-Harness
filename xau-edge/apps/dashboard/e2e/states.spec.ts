import { expect, test } from "@playwright/test";
import { mock, view, type GoldenName } from "./fixtures/trade";

/**
 * BROWSER-CI-01: every lifecycle state the trader can meet, rendered from a REAL backend serialization
 * (scripts/generate_trade_goldens.py), asserted at the level of "what does the screen say I may do".
 */

const STATES: { golden: GoldenName; code: string; word: RegExp; note: string }[] = [
  { golden: "wait", code: "WAIT", word: /CHỜ/, note: "an ordinary WAIT" },
  { golden: "buy", code: "BUY", word: /MUA/, note: "a real BUY setup" },
  { golden: "sell", code: "SELL", word: /BÁN/, note: "a real SELL setup" },
  { golden: "openPaper", code: "HOLD", word: /GIỮ VỊ THẾ/, note: "a paper position is open" },
  { golden: "closedPaper", code: "EXIT", word: /THOÁT/, note: "exited by TAKE_PROFIT" },
  { golden: "closedSl", code: "EXIT", word: /THOÁT/, note: "exited by STOP_LOSS" },
  { golden: "closedTime", code: "EXIT", word: /THOÁT/, note: "exited by TIME_EXIT" },
  { golden: "sellInvalidated", code: "WAIT", word: /CHỜ/, note: "an armed setup was INVALIDATED" },
  { golden: "stale", code: "UNAVAILABLE", word: /KHÔNG KHẢ DỤNG/, note: "stale data" },
  { golden: "paperCorrupt", code: "UNAVAILABLE", word: /KHÔNG KHẢ DỤNG/, note: "a corrupt paper state" },
  { golden: "writerConflict", code: "UNAVAILABLE", word: /KHÔNG KHẢ DỤNG/, note: "another process holds the desk" },
];

for (const s of STATES) {
  test(`${s.golden}: ${s.note} -> action ${s.code}`, async ({ page }) => {
    const v = view(s.golden);
    expect(v.hero.action.code).toBe(s.code); // the golden really is that state
    await mock(page, v);
    await page.goto("/trade");
    await expect(page.getByTestId("hero")).toBeVisible();
    await expect(page.getByTestId("action-word")).toContainText(s.word);
    // a state that is not BUY/SELL never offers to open a position
    if (s.code !== "BUY" && s.code !== "SELL") await expect(page.getByTestId("take-paper")).toHaveCount(0);
  });
}

const REASONS: [GoldenName, string][] = [
  ["closedPaper", "TAKE_PROFIT"],
  ["closedSl", "STOP_LOSS"],
  ["closedTime", "TIME_EXIT"],
];
for (const [golden, reason] of REASONS) {
  test(`${golden}: the last exit is ${reason} and the trader is told why in words`, async ({ page }) => {
    const v = view(golden);
    expect(v.desk?.last_exit?.exit_reason).toBe(reason);
    await mock(page, v);
    await page.goto("/trade");
    const words = { TAKE_PROFIT: "Chạm TP", STOP_LOSS: "Chạm SL", TIME_EXIT: "Hết thời gian giữ" }[reason];
    await expect(page.getByTestId("hero")).toContainText(words as string);
  });
}

test("API down is UNAVAILABLE with the last decision folded away, never shown as a live plan", async ({ page }) => {
  await mock(page, view("buy"));
  await page.route("**/trade/decision", (route) => route.abort());
  await page.goto("/trade");
  await expect(page.getByTestId("api-down-banner")).toBeVisible();
  await expect(page.getByTestId("take-paper")).toHaveCount(0);
});
