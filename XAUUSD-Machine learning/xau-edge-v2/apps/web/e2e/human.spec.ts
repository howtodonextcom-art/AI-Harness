import AxeBuilder from "@axe-core/playwright";
import { type Page, expect, test } from "@playwright/test";

const SHOTS = "../../reports/evidence/g9_g10";

type Sys = Record<string, unknown>;

const m1 = (state: string, quality: string) => ({
  applicable: true, reason: "ok", direction: "BUY", state, quality, reasons: [], features: {},
  planned_entry: 4165.8, planned_stop: 4160.0, planned_target: 4177.4, net_rr_now: 1.9, price_now: 4165.9,
});
const NA = { applicable: false, reason: "chưa có setup được H1/M15 ủng hộ", reasons: [], features: {} };

function system(rec: string, over: Sys = {}, m1x: unknown = m1("EXECUTION_WINDOW", "GOOD")): Sys {
  return {
    recommendation: rec, reasons: [`Hệ thống: ${rec}`], primary_blocker: null, blocker_text: null, secondary: [],
    secondary_text: [], bias: "BUY", setup_state: "ARMED", trigger_state: "CONFIRMED", strategy_action: "BUY",
    strategy_version: "1.1.0", m1: m1x, ...over,
  };
}

const PLAN = {
  side: "BUY", entry: 4165.8, stop_loss: 4160.0, take_profit_1: 4177.4, take_profit_2: null, net_rr: 1.9,
  expires_at: "2099-01-01T00:00:00Z",
};

const RECORD = {
  id: "h1", timestamp: "2026-10-13T10:00:00Z", decision_id: "d1", setup_id: "s-1", system_action: "BUY",
  system_recommendation: "BUY_CANDIDATE", system_bias: "BUY", setup_state: "ARMED", trigger_state: "CONFIRMED",
  m1_execution_state: "EXECUTION_WINDOW", m1_quality: "GOOD", entry: 4165.8, sl: 4160.0, tp: 4177.4, rr: 1.9,
  risk_pct: 0.25, risk_amount: 25, price: 4165.9, expiry: null, human_choice: "ACCEPT", human_reason: "",
  paper_mode: "PAPER", strategy_version: "1.1.0", evidence_label: "UNVALIDATED",
};

interface Scene {
  name: string;
  sys: Sys;
  candidate: boolean;
  action: string;
}

const SCENES: Scene[] = [
  { name: "buy-candidate", sys: system("BUY_CANDIDATE"), candidate: true, action: "BUY" },
  {
    name: "late-wait",
    sys: system("WAIT", { primary_blocker: "M1_TOO_LATE", blocker_text: "M1: quá muộn", secondary_text: ["spread hơi rộng"] }, m1("TOO_LATE", "BAD")),
    candidate: false, action: "BUY",
  },
  { name: "no-setup", sys: system("WAIT", { setup_state: "NONE", trigger_state: "NONE", strategy_action: "WAIT" }, NA), candidate: false, action: "WAIT" },
  { name: "hold", sys: system("HOLD", { strategy_action: "WAIT" }, NA), candidate: false, action: "HOLD" },
  { name: "exit-watch", sys: system("EXIT_WATCH", { strategy_action: "WAIT" }, NA), candidate: false, action: "HOLD" },
];

async function mock(page: Page, scene: Scene, human: unknown = null) {
  const posts: unknown[] = [];
  let current = human;
  await page.route("**/api/v2/state", async (r) => {
    try {
      const real = await r.fetch();
      const body = await real.json();
      const plan = scene.candidate ? PLAN : null;
      await r.fulfill({
        json: {
          ...body, action: scene.action, plan, setup_id: scene.candidate ? "s-1" : null, system: scene.sys,
          human: current, expires_at: scene.candidate ? PLAN.expires_at : null,
        },
      });
    } catch {
      // page closed while in flight
    }
  });
  await page.route("**/api/v2/human/decision", async (r) => {
    const body = JSON.parse(r.request().postData() ?? "{}");
    posts.push(body);
    current = { ...RECORD, human_choice: body.choice, human_reason: body.reason };
    await r.fulfill({ json: { ok: true, message: "đã ghi nhận quyết định của bạn", record: current } });
  });
  return posts;
}

for (const scene of SCENES) {
  test(`state matrix: ${scene.name}`, async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    page.on("pageerror", (e) => errors.push(String(e)));
    await mock(page, scene);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    await expect(page.getByTestId("recommendation")).toHaveAttribute("data-code", String(scene.sys.recommendation));
    await expect(page.getByTestId("strategy-action")).toHaveText(scene.action === "HOLD" ? "WAIT" : scene.action);
    for (const id of ["human-accept", "human-wait", "human-reject"]) {
      if (scene.candidate) await expect(page.getByTestId(id)).toBeEnabled();
      else await expect(page.getByTestId(id)).toBeDisabled();
    }
    if (!scene.candidate) await expect(page.getByTestId("human-disabled-why")).not.toBeEmpty();
    await expect(page.getByTestId("auto-paper-strip")).toContainText("AUTO PAPER: CHỈ ĐỂ NGHIÊN CỨU");
    await page.screenshot({ path: `${SHOTS}/matrix-${scene.name}.png` });
    const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
    expect(axe.violations.map((v) => v.id)).toEqual([]);
    expect(errors).toEqual([]);
  });
}

test("ACCEPT / WAIT / REJECT send only the choice, the candidate id and the reason", async ({ page }) => {
  const posts = await mock(page, SCENES[0]!);
  await page.goto("/");
  await page.getByTestId("human-reason").fill("giá còn gần entry");
  await page.getByTestId("human-accept").click();
  await expect(page.getByTestId("human-message")).toContainText("đã ghi nhận");
  await expect(page.getByTestId("human-last")).toHaveAttribute("data-choice", "ACCEPT");
  await page.getByTestId("human-reject").click();
  await expect(page.getByTestId("human-last")).toHaveAttribute("data-choice", "REJECT");
  await page.getByTestId("human-wait").click();
  await expect(page.getByTestId("human-last")).toHaveAttribute("data-choice", "WAIT");
  expect(posts).toEqual([
    { choice: "ACCEPT", setup_id: "s-1", reason: "giá còn gần entry" },
    { choice: "REJECT", setup_id: "s-1", reason: "" },
    { choice: "WAIT", setup_id: "s-1", reason: "" },
  ]);
  // the system's signal is untouched by the human's answer
  await expect(page.getByTestId("recommendation")).toHaveAttribute("data-code", "BUY_CANDIDATE");
  await expect(page.getByTestId("strategy-action")).toHaveText("BUY");
  await page.screenshot({ path: `${SHOTS}/human-after-choice.png` });
});

test("a refusal from the server is shown, not swallowed", async ({ page }) => {
  await mock(page, SCENES[0]!);
  await page.route("**/api/v2/human/decision", (r) =>
    r.fulfill({ status: 409, json: { error_code: "STALE_CANDIDATE", message: "kế hoạch đã đổi" } }),
  );
  await page.goto("/");
  await page.getByTestId("human-accept").click();
  await expect(page.getByTestId("human-message")).toContainText("STALE_CANDIDATE");
});

test("the human's last choice is shown after a reload (persisted by the server)", async ({ page }) => {
  await mock(page, SCENES[0]!, { ...RECORD, human_choice: "REJECT", human_reason: "tin sắp ra" });
  await page.goto("/");
  await expect(page.getByTestId("human-last")).toContainText("BỎ QUA");
  await expect(page.getByTestId("human-last")).toContainText("tin sắp ra");
  await page.reload();
  await expect(page.getByTestId("human-last")).toContainText("BỎ QUA");
});

test("the journal lists the human's decisions, newest first, read-only", async ({ page }) => {
  await mock(page, SCENES[0]!);
  await page.route("**/api/v2/human/decisions?*", (r) =>
    r.fulfill({ json: { decisions: [{ ...RECORD, id: "h2", human_choice: "REJECT", human_reason: "tin sắp ra" }, RECORD] } }),
  );
  await page.goto("/#journal");
  const log = page.getByTestId("human-log");
  await expect(log.getByTestId("human-row-h2")).toContainText("BỎ QUA");
  await expect(log.getByTestId("human-row-h1")).toContainText("CHẤP NHẬN");
  await expect(log.locator("button, input")).toHaveCount(0);
  await page.screenshot({ path: `${SHOTS}/journal-human-log.png`, fullPage: true });
});
