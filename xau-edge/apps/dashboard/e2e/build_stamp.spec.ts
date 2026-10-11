import { execFileSync } from "node:child_process";
import { expect, test } from "@playwright/test";

/** A served build must be the build of the current source. Found 2026-10-11: the live `.next` predated the overlay
 * commit and nothing said so. The page carries the commit it was built from; the dashboard source must not have
 * changed between that commit and HEAD (a later docs/backend-only commit does not make the build stale). */
test("the served build was made from the current dashboard source (no stale .next under test)", async ({ page }) => {
  await page.goto("/trade");
  const built = await page.locator("html").getAttribute("data-build-sha");
  expect(built, "build stamp missing: rebuild with `npm run build`").toBeTruthy();
  expect(built, "build made without git").not.toBe("unknown");
  // only files that change what the browser is served: tests, Playwright configs and report assets do not make a build stale
  const exclude = ["e2e", "e2e-acceptance", "playwright.config.ts", "playwright.acceptance.config.ts", "playwright.sandbox.config.ts", "test-results"].map((p) => `:(exclude)${p}`);
  const changed = execFileSync("git", ["diff", "--name-only", built!, "HEAD", "--", ".", ...exclude]).toString().trim();
  expect(changed, `dashboard source changed since the served build ${built}: rebuild`).toBe("");
});
