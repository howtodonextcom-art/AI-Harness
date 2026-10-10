import { expect, test, type Page, type Route } from "@playwright/test";

const blocked = (code: string, message: string) => ({ allowed: false, blockers: [{ code, message }] });
const allowed = { allowed: true, blockers: [] };

const STATUS = {
  now: "2026-10-08T12:00:00+00:00",
  bot: {
    state: "STOPPED",
    backend: "subprocess",
    pid: null,
    detail: "bot không chạy",
    running_mode: null,
    status_updated_at: null,
    last_cycle: null,
  },
  configured_mode: "DRY_RUN",
  mode_ceiling: "DEMO",
  kill_switch: { tripped: false, reason: "" },
  account_label: "DEMO ***678",
  strategy_validated: false,
  wait_banner: "Không có edge được kiểm định: bot sẽ WAIT",
  preflight: { generated_at: "2026-10-08T12:00:00+00:00", has_fail: true, counts: { ok: 2, warn: 1, fail: 1, unknown: 0 }, last_probe_at: null },
  actions: {
    start: blocked("PREFLIGHT_FAIL", "preflight có mục fail: clock.ntp"),
    stop: blocked("BOT_NOT_RUNNING", "bot không chạy"),
    restart: blocked("BOT_NOT_RUNNING", "bot không chạy"),
    mode_demo: allowed,
    mode_dry_run: blocked("ALREADY_DRY_RUN", "đang ở DRY-RUN"),
    smoke: blocked("MODE_NOT_DEMO", "chuyển sang DEMO trước"),
    flatten: allowed,
  },
  active_job: null,
  recent_jobs: [],
  reset_command: 'uv run python scripts/kill_switch.py reset --confirm "I understand the risk"',
  smoke_limits: "tối đa 1 lần / 10 phút và 5 lần / ngày",
};

const PREFLIGHT = {
  generated_at: "2026-10-08T12:00:00+00:00",
  checks: [
    { id: "env.file", label: "File .env", status: "ok", detail: "có", fix_hint: "" },
    { id: "mt5.connection", label: "Kết nối terminal", status: "ok", detail: "đã kết nối (chỉ đọc, có timeout)", fix_hint: "" },
    { id: "strategy", label: "Chiến lược VALIDATED", status: "warn", detail: "Không có edge được kiểm định: bot sẽ WAIT", fix_hint: "" },
    { id: "clock.ntp", label: "Đồng hồ so với NTP", status: "fail", detail: "lệch +12.00 s", fix_hint: "Đồng bộ giờ Windows (w32tm /resync)." },
  ],
  has_fail: true,
  counts: { ok: 2, warn: 1, fail: 1, unknown: 0 },
  terminal_source: "terminal",
  account_label: "DEMO ***678",
  strategy_validated: false,
  configured_mode: "DRY_RUN",
  mode_ceiling: "DEMO",
  demo_blockers: [],
  demo_unverified: [],
  smoke_enabled: false,
};

type Posted = { path: string; body: unknown; key: string | null };

async function mockControl(page: Page): Promise<Posted[]> {
  const posted: Posted[] = [];
  await page.route("**/api/control/**", async (route: Route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/control/", "");
    if (request.method() === "POST") {
      posted.push({ path, body: request.postDataJSON(), key: request.headers()["idempotency-key"] ?? null });
      const job = { id: "a".repeat(32), kind: path, status: "RUNNING", created_at: STATUS.now, finished_at: null, steps: [], result: {}, error_code: null, message: "" };
      return route.fulfill({ status: 202, json: { job, replayed: false } });
    }
    if (path.startsWith("status")) return route.fulfill({ json: STATUS });
    if (path.startsWith("preflight")) return route.fulfill({ json: PREFLIGHT });
    if (path.startsWith("journal")) return route.fulfill({ json: { events: [] } });
    return route.fulfill({ status: 404, json: {} });
  });
  return posted;
}

test("preflight checks are shown with their status, fix hint and the WAIT banner", async ({ page }) => {
  await mockControl(page);
  await page.goto("/control");
  const ntp = page.locator('[data-check="clock.ntp"]');
  await expect(ntp).toHaveAttribute("data-status", "fail");
  await expect(ntp).toContainText("LỖI");
  await expect(ntp).toContainText("w32tm /resync");
  await expect(page.locator('[data-check="env.file"]')).toHaveAttribute("data-status", "ok");
  await expect(page.getByRole("status").filter({ hasText: "bot sẽ WAIT" })).toBeVisible();
  await expect(page.getByText("Tài khoản: DEMO ***678")).toBeVisible();
  await expect(page.getByRole("button", { name: "Khởi động", exact: true })).toBeDisabled();
  await expect(page.getByText("PREFLIGHT_FAIL")).toBeVisible();
  await expect(page.getByRole("button", { name: "Chạy smoke…" })).toBeDisabled();
});

test("flatten needs two steps and the exact word before anything is sent", async ({ page }) => {
  const posted = await mockControl(page);
  await page.goto("/control");
  await page.getByRole("button", { name: "FLATTEN…" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("Kill switch bật NGAY");
  await dialog.getByRole("button", { name: "Tiếp tục" }).click();
  const confirm = dialog.getByRole("button", { name: "Xác nhận FLATTEN" });
  await expect(confirm).toBeDisabled();
  await dialog.getByRole("textbox").fill("flatten");
  await expect(confirm).toBeDisabled();
  expect(posted).toEqual([]);
  await dialog.getByRole("textbox").fill("FLATTEN");
  await expect(confirm).toBeEnabled();
  await confirm.click();
  await expect.poll(() => posted.length).toBe(1);
  expect(posted[0].path).toBe("flatten");
  expect(posted[0].body).toEqual({ confirm: "FLATTEN" });
  expect(posted[0].key).toMatch(/^[a-f0-9]{32}$/);
});

test("cancelling the DEMO dialog sends nothing", async ({ page }) => {
  const posted = await mockControl(page);
  await page.goto("/control");
  await page.getByRole("button", { name: "Chuyển sang DEMO…" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Tiếp tục" }).click();
  await page.getByRole("dialog").getByRole("textbox").fill("DEMO");
  await page.getByRole("dialog").getByRole("button", { name: "Hủy" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(posted).toEqual([]);
});

test("the page has no field for an order parameter", async ({ page }) => {
  await mockControl(page);
  await page.goto("/control");
  await expect(page.locator('[data-check="env.file"]')).toBeVisible();
  // the only control is the display-time-zone selector (no order parameter of any kind)
  await expect(page.locator('input, textarea, select:not([data-testid="control-zone"])')).toHaveCount(0);
});
