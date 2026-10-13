import { defineConfig, devices } from "@playwright/test";

/**
 * E2E tests of the Control page against the production build. The control API is mocked inside the
 * browser (page.route), so no Python API, no token file and no MT5 terminal are involved.
 * Run: `npm run build` then `npm run test:e2e`.
 */
const PORT = 3100;

/**
 * SCOPE (2026-10-12): the product is supported on DESKTOP only (1280-2560 CSS px wide, browser zoom up to 200%, i.e. down to
 * 720x450). Phone layouts are frozen: their layout tests carry `@mobile` and do not gate. Run them on purpose with
 * `XAU_E2E_MOBILE=1` (PowerShell: `$env:XAU_E2E_MOBILE=1`). Fail-closed safety tests at narrow widths are NOT tagged: they gate.
 */
const MOBILE = process.env.XAU_E2E_MOBILE === "1";

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000, // a multi-state test (seven page loads) exceeded 30 s on a loaded desktop
  expect: { timeout: 10_000 }, // a loaded desktop (live stack, MT5, editor) made a 5 s wait flaky across ~500 tests
  retries: 0,
  grep: MOBILE ? /@mobile/ : undefined,
  grepInvert: MOBILE ? undefined : /@mobile/,
  reporter: "list",
  use: { baseURL: `http://127.0.0.1:${PORT}` },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `npx next start -p ${PORT} -H 127.0.0.1`,
    url: `http://127.0.0.1:${PORT}/control`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
