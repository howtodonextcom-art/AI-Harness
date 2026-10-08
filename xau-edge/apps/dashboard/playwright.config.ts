import { defineConfig, devices } from "@playwright/test";

/**
 * E2E tests of the Control page against the production build. The control API is mocked inside the
 * browser (page.route), so no Python API, no token file and no MT5 terminal are involved.
 * Run: `npm run build` then `npm run test:e2e`.
 */
const PORT = 3100;

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: 0,
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
