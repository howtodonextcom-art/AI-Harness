import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("the model drawer shows RETIRED (rejected at Validation), no authority, locked windows and the pre-registered criteria", async ({ page }) => {
  await page.goto("/#model");
  await expect(page.getByTestId("model-status")).toHaveText("RETIRED");
  const panel = page.getByTestId("model-panel");
  await expect(panel).toContainText("thẩm quyền NONE");
  await expect(page.getByTestId("model-locks")).toContainText("Test-H: KHÓA (chưa mở)");
  await expect(page.getByTestId("model-locks")).toContainText("Holdout: KHÓA (chưa mở)");
  await expect(page.getByTestId("model-locks")).toContainText("K_V2_VOL_V0 = 2");
  await expect(page.getByTestId("model-locks")).toContainText("har_ridge + lightgbm_regressor");
  const rows = page.getByTestId("model-stages").locator("tbody tr");
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(1)).toContainText("Kiểm định 2019");
  await expect(rows.nth(1)).toContainText("Cải thiện dương ≥ 75% số năm");
  await expect(rows.nth(1).locator('li[data-passed="false"]')).toHaveCount(1); // the criterion that fails is shown
  await expect(page.getByTestId("model-notes")).toContainText("Class D");
  await expect(page.getByTestId("model-display")).toContainText("KHÔNG được hiển thị");
});

test("no forecast, probability or direction is shown anywhere on the page", async ({ page }) => {
  await page.goto("/#model");
  await expect(page.getByTestId("model-panel")).toBeVisible();
  const text = (await page.locator("body").innerText()).toLowerCase();
  for (const banned of ["tự tin", "confidence", "xác suất thắng", "win probability", "biên độ kỳ vọng"]) {
    expect(text, banned).not.toContain(banned);
  }
});

test("the model drawer has no accessibility violations", async ({ page }) => {
  await page.goto("/#model");
  await expect(page.getByTestId("model-stages")).toBeVisible();
  const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(result.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
});

test("the real API says RETIRED and carries no forecast field", async ({ request }) => {
  const body = await (await request.get("/api/v2/model")).json();
  expect(body.status).toBe("RETIRED");
  expect(body.authority).toBe("NONE");
  expect(body.test_h).toBe("LOCKED");
  for (const key of ["forecast", "prediction", "expected_range", "confidence", "probability"]) {
    expect(Object.keys(body)).not.toContain(key);
  }
  const state = await (await request.get("/api/v2/state")).json();
  expect(state.model.status).toBe("RETIRED");
});

test("the rejection and the open criterion are stated plainly", async ({ page }) => {
  await page.goto("/#model");
  await expect(page.getByTestId("model-notes")).toContainText("bị LOẠI tại Kiểm định");
  await expect(page.getByTestId("model-notes")).toContainText("Tiêu chí đăng ký trước KHÔNG đạt");
  await expect(page.getByTestId("model-stages")).toContainText("MỘT PHÍA 97,5%");
});
