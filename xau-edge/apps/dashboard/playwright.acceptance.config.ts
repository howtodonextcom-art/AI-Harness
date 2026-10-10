import { defineConfig, devices } from "@playwright/test";

/**
 * REAL-BROWSER acceptance of the Trading Desk over an ACCEPTANCE REPLAY (burned FTMO bars through the
 * real TradeEngine / PaperDesk / journal; nothing is mocked in the browser except the API port).
 *
 * Two servers start: the replay API (scripts/serve_acceptance.py, :8100) and the production
 * dashboard build (:3200) whose server-side proxy forwards the two paper actions to :8100.
 * Run: `npm run build` then `npx playwright test -c playwright.acceptance.config.ts`.
 * Everything it shows is labelled ACCEPTANCE REPLAY - NOT LIVE.
 */
export default defineConfig({
  testDir: "./e2e-acceptance",
  timeout: 90_000,
  workers: 1, // one replay world at a time
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:3200" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: [
    {
      command: "uv run python scripts/serve_acceptance.py --port 8100",
      cwd: "../..",
      url: "http://127.0.0.1:8100/acceptance/state",
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: "npx next start -p 3200 -H 127.0.0.1",
      url: "http://127.0.0.1:3200/trade",
      env: { XAU_EDGE_API_URL: "http://127.0.0.1:8100" },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
