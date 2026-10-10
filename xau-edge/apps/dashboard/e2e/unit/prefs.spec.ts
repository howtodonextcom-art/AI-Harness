import { expect, test } from "@playwright/test";
import { DEFAULT_PREFS, crossed, loadAlerts, loadLevels, loadPrefs, migrateLegacy, saveAlerts, saveLevels, savePrefs, scopeOf, storageKey, type PriceAlert } from "../../lib/prefs";

const LIVE = scopeOf("LIVE", "XAUUSD");
const REPLAY = scopeOf("ACCEPTANCE_REPLAY", "XAUUSD");

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
  fakeStorage({ "xau-edge.trade.prefs.v1": "{not json", [storageKey(LIVE, "levels")]: "5", [storageKey(LIVE, "alerts")]: "null" });
  expect(loadPrefs()).toEqual(DEFAULT_PREFS);
  expect(loadLevels(LIVE)).toEqual([]);
  expect(loadAlerts(LIVE)).toEqual([]);
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

const alert = (price: number): PriceAlert => ({ id: `a${price}`, price, direction: "UP", createdAt: "", firedAt: null });

test("levels and alerts are scoped by source mode and symbol: a replay tool never appears on LIVE", () => {
  const data = fakeStorage();
  saveAlerts(REPLAY, [alert(3350)]);
  saveLevels(REPLAY, [{ id: "l", price: 3340, label: "Đường" }]);
  expect(loadAlerts(LIVE)).toEqual([]);
  expect(loadLevels(LIVE)).toEqual([]);
  expect(loadAlerts(REPLAY).map((a) => a.price)).toEqual([3350]);
  expect(loadAlerts(scopeOf("LIVE", "EURUSD"))).toEqual([]); // another symbol is another scope
  expect(Object.keys(data).every((k) => k.startsWith("xau-edge:v3:"))).toBe(true);
  expect(storageKey(LIVE, "alerts")).toBe("xau-edge:v3:LIVE:XAUUSD:alerts");
  expect(storageKey(REPLAY, "levels")).toBe("xau-edge:v3:REPLAY:XAUUSD:levels");
});

test("migration moves the TRADE-06/07 keys into the first scope that loads, once, without destroying anything newer", () => {
  const old = { "xau-edge.trade.price-alerts.v1": JSON.stringify([alert(4240)]), "xau-edge.trade.levels.v1": JSON.stringify([{ id: "l", price: 4200, label: "Đường" }, { id: "bad", price: -1, label: "x" }]) };
  const data = fakeStorage(old);
  expect(migrateLegacy(LIVE)).toEqual({ alerts: 1, levels: 1 });
  expect(loadAlerts(LIVE).map((a) => a.price)).toEqual([4240]);
  expect(loadLevels(LIVE).map((l) => l.price)).toEqual([4200]); // the invalid line is dropped, not carried over
  expect("xau-edge.trade.price-alerts.v1" in data).toBe(false); // retired
  expect(loadAlerts(REPLAY)).toEqual([]); // a second scope never inherits it
  expect(migrateLegacy(REPLAY)).toEqual({ alerts: 0, levels: 0 });
  // a scope that already has data keeps it: the old key is not read into it
  const d2 = fakeStorage({ ...old, [storageKey(LIVE, "alerts")]: JSON.stringify([alert(5000)]) });
  expect(migrateLegacy(LIVE).alerts).toBe(0);
  expect(loadAlerts(LIVE).map((a) => a.price)).toEqual([5000]);
  expect("xau-edge.trade.price-alerts.v1" in d2).toBe(false);
});

test("migration never throws when storage is blocked or the old value is corrupt", () => {
  fakeStorage({ "xau-edge.trade.price-alerts.v1": "{broken", "xau-edge.trade.levels.v1": "7" });
  expect(() => migrateLegacy(LIVE)).not.toThrow();
  (globalThis as unknown as { window: unknown }).window = { localStorage: { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); }, removeItem() { throw new Error("blocked"); } } };
  expect(migrateLegacy(LIVE)).toEqual({ alerts: 0, levels: 0 });
});
