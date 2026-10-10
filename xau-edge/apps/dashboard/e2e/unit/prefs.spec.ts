import { expect, test } from "@playwright/test";
import { DEFAULT_PREFS, crossed, loadAlerts, loadLevels, loadPrefs, savePrefs, type PriceAlert } from "../../lib/prefs";

/** Local preferences: validated on read, never crash, never hold anything that authorises a trade. */

function fakeStorage(initial: Record<string, string> = {}) {
  const data = { ...initial };
  const storage = { getItem: (k: string) => data[k] ?? null, setItem: (k: string, v: string) => { data[k] = v; }, removeItem: (k: string) => { delete data[k]; } };
  (globalThis as unknown as { window: unknown }).window = { localStorage: storage };
  return data;
}

test("a hand-edited or old value falls back to the defaults field by field", () => {
  fakeStorage({ "xau-edge.trade.prefs.v1": JSON.stringify({ tf: "H99", overlays: { signals: "yes", plan: false }, zone: "MARS", tab: "nope", risk: 7, follow: false }) });
  const p = loadPrefs();
  expect(p.tf).toBe(DEFAULT_PREFS.tf);
  expect(p.overlays.signals).toBe(true);
  expect(p.overlays.plan).toBe(false);
  expect(p.zone).toBe(DEFAULT_PREFS.zone);
  expect(p.tab).toBe(DEFAULT_PREFS.tab);
  expect(p.risk).toBe(DEFAULT_PREFS.risk);
  expect(p.follow).toBe(false);
});

test("corrupt JSON and blocked storage never throw", () => {
  fakeStorage({ "xau-edge.trade.prefs.v1": "{not json", "xau-edge.trade.levels.v1": "5", "xau-edge.trade.price-alerts.v1": "null" });
  expect(loadPrefs()).toEqual(DEFAULT_PREFS);
  expect(loadLevels()).toEqual([]);
  expect(loadAlerts()).toEqual([]);
  (globalThis as unknown as { window: unknown }).window = { localStorage: { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } } };
  expect(loadPrefs()).toEqual(DEFAULT_PREFS);
  expect(() => savePrefs(DEFAULT_PREFS)).not.toThrow();
});

test("preferences hold no authorisation, strategy choice or credential", () => {
  expect(Object.keys(DEFAULT_PREFS).sort()).toEqual(["follow", "history", "notify", "overlays", "risk", "shortcuts", "sound", "tab", "tf", "zone"]);
});

test("a price alert fires once, only when the bid crosses in its direction", () => {
  const up: PriceAlert = { id: "a", price: 4240, direction: "UP", createdAt: "", firedAt: null };
  expect(crossed(up, 4236, 4241)).toBe(true);
  expect(crossed(up, 4241, 4243)).toBe(false); // already above: no crossing
  expect(crossed(up, null, 4241)).toBe(false); // no previous price
  expect(crossed({ ...up, firedAt: "x" }, 4236, 4241)).toBe(false); // fired alerts stay quiet
  const down: PriceAlert = { ...up, direction: "DOWN", price: 4230 };
  expect(crossed(down, 4231, 4229.5)).toBe(true);
  expect(crossed(down, 4229, 4228)).toBe(false);
});
