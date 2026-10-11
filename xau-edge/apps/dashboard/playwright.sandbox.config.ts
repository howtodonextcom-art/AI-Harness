import { defineConfig, devices } from "@playwright/test";

/**
 * Card-B / honesty e2e against a sandbox Next server. Uses NEXT_DIST_DIR=.next-sandbox so
 * the LIVE stack's apps/dashboard/.next is never rebuilt.
 */
const PORT = 3210;

export default defineConfig({
  testDir: "./e2e",
  testMatch: process.env.PW_MATCH ? new RegExp(process.env.PW_MATCH) : /honesty\.spec\.ts|lifecycle\.spec\.ts/,
  timeout: 45_000,
  retries: 0,
  reporter: "list",
  use: { baseURL: `http://127.0.0.1:${PORT}` },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `npx next dev -p ${PORT} -H 127.0.0.1`,
    url: `http://127.0.0.1:${PORT}/control`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: { ...process.env, NEXT_DIST_DIR: ".next-sandbox" },
  },
});
