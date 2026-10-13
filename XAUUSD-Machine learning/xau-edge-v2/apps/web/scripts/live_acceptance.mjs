// Live acceptance against the REAL running service (not a test double): the page, the socket, the
// chart and the decision for a few minutes. Usage: node scripts/live_acceptance.mjs [seconds] [url]
// Set XAU_V2_CHROMIUM to an installed Chromium. Writes a JSON report to stdout.
import { chromium } from "@playwright/test";

const seconds = Number(process.argv[2] ?? 90);
const url = process.argv[3] ?? "http://127.0.0.1:8200/";
const browser = await chromium.launch({ executablePath: process.env.XAU_V2_CHROMIUM || undefined });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

const problems = [];
const events = [];
const apiCalls = {};
page.on("console", (m) => (m.type() === "error" || m.type() === "warning") && problems.push(`console.${m.type()}: ${m.text()}`));
page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
page.on("requestfailed", (r) => problems.push(`requestfailed: ${r.url()}`));
page.on("response", (r) => {
  if (r.status() >= 400) problems.push(`HTTP ${r.status()}: ${r.url()}`);
  const u = new URL(r.url());
  if (u.pathname.startsWith("/api/")) apiCalls[u.pathname] = (apiCalls[u.pathname] ?? 0) + 1;
});
page.on("websocket", (ws) =>
  ws.on("framereceived", (f) => {
    try {
      const e = JSON.parse(f.payload);
      events.push({ t: Date.now(), type: e.type, seq: e.seq, v: e.data_version });
    } catch {
      problems.push("unparseable socket frame");
    }
  }),
);

const t0 = Date.now();
await page.goto(url);
await page.getByTestId("action").waitFor();
await page.getByTestId("chart-meta").waitFor();
await page.waitForFunction(() => Number(document.querySelector("[data-testid=chart-meta]")?.dataset.count) > 0);
const firstPaintMs = Date.now() - t0;
const quotes = new Set();
const samples = [];
const end = Date.now() + seconds * 1000;
while (Date.now() < end) {
  const q = await page.getByTestId("chart-quote").textContent().catch(() => null);
  if (q) quotes.add(q.trim());
  samples.push({
    action: await page.getByTestId("action").getAttribute("data-code"),
    ws: await page.getByTestId("ws-status").getAttribute("data-state"),
    count: Number(await page.getByTestId("chart-meta").getAttribute("data-count")),
  });
  await page.waitForTimeout(2000);
}
// switch every timeframe once on the live service
const tfCounts = {};
for (const tf of ["M1", "M5", "M30", "H1", "H4", "M15"]) {
  await page.getByTestId(`tf-${tf}`).click();
  await page.waitForFunction(
    (t) => document.querySelector("[data-testid=chart-meta]")?.dataset.tf === t && document.querySelector("[data-testid=chart-meta]")?.dataset.loading === "false",
    tf,
  );
  tfCounts[tf] = Number(await page.getByTestId("chart-meta").getAttribute("data-count"));
}
const seqs = events.map((e) => e.seq);
let gaps = 0;
for (let i = 1; i < seqs.length; i++) if (seqs[i] !== seqs[i - 1] + 1) gaps++;
const byType = {};
for (const e of events) byType[e.type] = (byType[e.type] ?? 0) + 1;
const overflow = await page.evaluate(() => document.documentElement.scrollHeight - document.documentElement.clientHeight);
await page.screenshot({ path: process.env.SHOT ?? "live_acceptance.png" });
console.log(
  JSON.stringify(
    {
      url, seconds, firstPaintMs, socketEvents: events.length, byType, seqGaps: gaps,
      distinctQuotesSeen: quotes.size, actions: [...new Set(samples.map((s) => s.action))],
      wsStates: [...new Set(samples.map((s) => s.ws))], tfCounts, apiCalls, pageOverflowPx: overflow, problems,
    },
    null,
    2,
  ),
);
await browser.close();
process.exit(problems.length ? 1 : 0);
