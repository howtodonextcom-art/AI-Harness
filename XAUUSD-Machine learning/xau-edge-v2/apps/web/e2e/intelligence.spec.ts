import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

/** The market description: layered reasons on the first screen, the full panel in a drawer. */

test("the first screen names the market's reason, the gates and the governor apart", async ({ page }) => {
  // a deterministic scene: no direction on H1, a wide spread AND a cooldown at the same time
  await page.route("**/api/v2/intelligence", async (route) => {
    const real = await (await route.fetch()).json();
    real.authorization.chain_verdict = "NO_DIRECTION";
    real.authorization.chain_blocker = { code: "NO_DIRECTION", text: "H1 chưa có xu hướng rõ", category: "STRATEGY" };
    real.authorization.next_condition = "H1 chuyển sang tăng hoặc giảm rõ ràng";
    real.authorization.gates = [{ code: "SPREAD_TOO_WIDE", text: "Spread đang rộng", category: "COST" }];
    real.authorization.system_hold = [{ code: "COOLDOWN", text: "Đang nghỉ sau lệnh", category: "GOVERNOR" }];
    await route.fulfill({ json: real });
  });
  await page.route("**/api/v2/state", async (route) => {
    const real = await (await route.fetch()).json();
    real.action = "WAIT";
    if (real.system) real.system.recommendation = "WAIT";
    await route.fulfill({ json: real });
  });
  await page.goto("/");
  await expect(page.getByTestId("why-gates")).toBeVisible();
  await expect(page.getByTestId("why-market")).toContainText("H1 chưa có xu hướng rõ");
  await expect(page.getByTestId("why-market")).toContainText("cần: H1 chuyển sang tăng hoặc giảm");
  await expect(page.getByTestId("why-gates")).toContainText("Spread đang rộng");
  await expect(page.getByTestId("why-gates")).toContainText("TK: Đang nghỉ sau lệnh");
  await expect(page.getByTestId("why-market")).not.toContainText("Spread");
});

for (const [width, height] of [
  [1440, 900],
  [1152, 720],
] as const) {
  test(`${width}x${height}: the decision and the reasons fit on the first screen`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await page.goto("/");
    await expect(page.getByTestId("recommendation")).toBeVisible();
    for (const id of ["recommendation", "blocker", "secondary"]) {
      const box = await page.getByTestId(id).boundingBox();
      expect(box, id).not.toBeNull();
      expect(box!.y + box!.height, `${id} fits in ${height}px`).toBeLessThanOrEqual(height);
    }
  });
}

test("the market drawer shows observation, scenarios, the funnel and the freshness", async ({ page }) => {
  await page.goto("/#market");
  const panel = page.getByTestId("intel-panel");
  await expect(panel).toBeVisible();
  await expect(page.getByTestId("intel-summary")).not.toBeEmpty();
  for (const key of ["NO_TRADE", "CONTINUATION", "BREAKOUT", "REVERSAL", "RANGE"]) {
    await expect(page.getByTestId(`scenario-${key}`)).toBeVisible();
  }
  await expect(page.getByTestId("step-H1_DIRECTION")).toBeVisible();
  await expect(page.getByTestId("step-GATE_GOVERNOR")).toBeVisible();
  const fresh = (await page.getByTestId("intel-fresh").textContent()) ?? "";
  expect(fresh).toContain("nến đã đóng");
  expect(fresh).toContain("không có quyền đặt lệnh");
  const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(result.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
});

test("the description never offers an action", async ({ page }) => {
  await page.goto("/#market");
  await expect(page.getByTestId("intel-panel")).toBeVisible();
  const buttons = await page.getByTestId("intel-panel").getByRole("button").count();
  expect(buttons).toBe(0);
});

test("an unreliable state says NOT_EVALUABLE instead of inventing a market reason", async ({ page }) => {
  await page.route("**/api/v2/intelligence", async (route) => {
    const real = await (await route.fetch()).json();
    real.authorization.chain_evaluable = false;
    real.authorization.chain_not_evaluable_reason = "STALE_DATA";
    real.authorization.chain_verdict = "NOT_EVALUABLE";
    real.authorization.chain_blocker = null;
    real.authorization.next_condition = null;
    await route.fulfill({ json: real });
  });
  await page.route("**/api/v2/state", async (route) => {
    const real = await (await route.fetch()).json();
    real.action = "WAIT";
    if (real.system) real.system.recommendation = "WAIT";
    await route.fulfill({ json: real });
  });
  await page.goto("/");
  const why = page.getByTestId("why-market");
  await expect(why).toContainText("không đánh giá được (STALE_DATA)");
  await expect(why).toHaveAttribute("data-chain", "NOT_EVALUABLE");
});
