// Screenshots of the running terminal (read-only): node scripts/audit/shoot.mjs <outDir>
import { chromium } from "../../apps/web/node_modules/playwright/index.mjs";

const out = process.argv[2] ?? ".";
const sizes = [
  [1440, 900],
  [1152, 720],
];
const browser = await chromium.launch();
for (const [w, h] of sizes) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  await page.goto("http://127.0.0.1:8200/", { waitUntil: "networkidle" });
  await page.waitForSelector('[data-testid="why-market"]', { timeout: 15000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${out}/intel_${w}x${h}_fold.png` });
  await page.screenshot({ path: `${out}/intel_${w}x${h}_full.png`, fullPage: true });
  await page.goto("http://127.0.0.1:8200/#market", { waitUntil: "networkidle" });
  await page.waitForSelector('[data-testid="intel-panel"]', { timeout: 15000 });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${out}/intel_${w}x${h}_market_drawer.png`, fullPage: true });
  await page.goto("http://127.0.0.1:8200/", { waitUntil: "networkidle" });
  await page.waitForSelector('[data-testid="why-market"]', { timeout: 15000 });
  const metrics = await page.evaluate(() => {
    const q = (id) => document.querySelector(`[data-testid="${id}"]`);
    const r = (id) => {
      const e = q(id);
      if (!e) return null;
      const b = e.getBoundingClientRect();
      return { top: Math.round(b.top), bottom: Math.round(b.bottom), visibleInFold: b.top < innerHeight };
    };
    return {
      why: r("why-market"),
      recommendation: r("recommendation"),
      blocker: r("blocker"), gates: r("secondary"),
      docHeight: document.documentElement.scrollHeight,
      whyText: q("why-market")?.textContent, gatesText: q("why-gates")?.textContent,
    };
  });
  console.log(w, h, JSON.stringify(metrics));
  await page.close();
}
await browser.close();
