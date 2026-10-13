import { defineConfig } from "@playwright/test";

const PORT = 8201; // tests use their own port so they never touch a developer's running service
const chromium = process.env.XAU_V2_CHROMIUM; // optional: an already-installed Chromium

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    viewport: { width: 1440, height: 900 },
    launchOptions: chromium ? { executablePath: chromium } : {},
  },
  webServer: {
    command: "uv run python -m xau_edge_v2",
    cwd: "../..",
    url: `http://127.0.0.1:${PORT}/api/v2/health`,
    env: {
      XAU_V2_PORT: String(PORT),
      XAU_V2_HEARTBEAT_SECONDS: "1",
      // the test server never touches a developer's paper book and never opens positions by itself
      XAU_V2_PAPER_DB: "test-results/paper-e2e.sqlite3",
      XAU_V2_AUTO_PAPER: "false",
    },
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
