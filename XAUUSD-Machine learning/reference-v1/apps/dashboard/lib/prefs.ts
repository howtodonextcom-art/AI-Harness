/**
 * Harmless UI preferences and the trader's own chart annotations, kept in this browser only.
 * Never stored here: anything about authorization, strategy choice, risk approval or credentials.
 * Every read/write is guarded: with storage blocked the terminal still works, it just forgets.
 */

import { MAX_DRAWINGS, validDrawings, type Drawing } from "@/lib/drawings";
import type { DisplayZone } from "@/lib/time";

export type Tab = "overview" | "why" | "position" | "activity" | "system";

export interface Overlays {
  signals: boolean;
  plan: boolean;
  paper: boolean;
  structure: boolean;
  volume: boolean;
  sessions: boolean;
  /** previous week high/low and the session highs/lows, computed from H1 bars */
  keyLevels: boolean;
  /** upcoming news events as vertical lines (server calendar) */
  news: boolean;
}

export interface Prefs {
  tf: string;
  overlays: Overlays;
  follow: boolean;
  zone: DisplayZone;
  tab: Tab;
  history: boolean;
  risk: number;
  shortcuts: boolean;
  notify: boolean;
  sound: boolean;
}

export const DEFAULT_PREFS: Prefs = {
  tf: "M5",
  overlays: { signals: true, plan: true, paper: true, structure: false, volume: true, sessions: false, keyLevels: false, news: true },
  follow: true,
  zone: "VN",
  tab: "overview",
  history: false,
  risk: 0.25,
  shortcuts: true,
  notify: true,
  sound: false,
};

const PREFS_KEY = "xau-edge.trade.prefs.v1";
// TRADE-06/07 keys (not scoped by source): read once by `migrateLegacy`, then retired
const LEGACY_LEVELS_KEY = "xau-edge.trade.levels.v1";
const LEGACY_ALERTS_KEY = "xau-edge.trade.price-alerts.v1";

const RISKS = [0.1, 0.25, 0.5];
const TFS = ["M1", "M5", "M15", "M30", "H1", "H4"];
const TABS: Tab[] = ["overview", "why", "position", "activity", "system"];
const ZONES: DisplayZone[] = ["VN", "UTC", "BROKER", "LOCAL"];

function read<T>(key: string): T | null {
  try {
    const raw = window.localStorage.getItem(key);
    return raw === null ? null : (JSON.parse(raw) as T);
  } catch {
    return null;
  }
}

function write(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable: the choice is simply not remembered */
  }
}

/** Validate every field: a hand-edited or old value falls back to the default, never crashes. */
export function loadPrefs(): Prefs {
  const raw = read<Partial<Prefs>>(PREFS_KEY) ?? {};
  const o = (raw.overlays ?? {}) as Partial<Overlays>;
  const bool = (v: unknown, d: boolean) => (typeof v === "boolean" ? v : d);
  return {
    tf: typeof raw.tf === "string" && TFS.includes(raw.tf) ? raw.tf : DEFAULT_PREFS.tf,
    overlays: {
      signals: bool(o.signals, DEFAULT_PREFS.overlays.signals),
      plan: bool(o.plan, DEFAULT_PREFS.overlays.plan),
      paper: bool(o.paper, DEFAULT_PREFS.overlays.paper),
      structure: bool(o.structure, DEFAULT_PREFS.overlays.structure),
      volume: bool(o.volume, DEFAULT_PREFS.overlays.volume),
      sessions: bool(o.sessions, DEFAULT_PREFS.overlays.sessions),
      keyLevels: bool(o.keyLevels, DEFAULT_PREFS.overlays.keyLevels),
      news: bool(o.news, DEFAULT_PREFS.overlays.news),
    },
    follow: bool(raw.follow, DEFAULT_PREFS.follow),
    zone: ZONES.includes(raw.zone as DisplayZone) ? (raw.zone as DisplayZone) : DEFAULT_PREFS.zone,
    tab: TABS.includes(raw.tab as Tab) ? (raw.tab as Tab) : DEFAULT_PREFS.tab,
    history: bool(raw.history, DEFAULT_PREFS.history),
    risk: typeof raw.risk === "number" && RISKS.includes(raw.risk) ? raw.risk : DEFAULT_PREFS.risk,
    shortcuts: bool(raw.shortcuts, DEFAULT_PREFS.shortcuts),
    notify: bool(raw.notify, DEFAULT_PREFS.notify),
    sound: bool(raw.sound, DEFAULT_PREFS.sound),
  };
}

export function savePrefs(prefs: Prefs): void {
  write(PREFS_KEY, prefs);
}

// ---- where the trader's own tools live: one scope per source mode and symbol ------------------------
//
// A level or an alert drawn on REPLAY prices must never appear on the LIVE chart (or the reverse), even
// when both are served from the same browser origin: the storage key itself carries the source.

export interface Scope {
  /** LIVE, or REPLAY for every non-live source (acceptance replay, ...) */
  mode: "LIVE" | "REPLAY";
  symbol: string;
}

export const scopeOf = (sourceMode: string | null | undefined, symbol: string | null | undefined): Scope => ({
  mode: sourceMode === "LIVE" ? "LIVE" : "REPLAY",
  symbol: (symbol ?? "XAUUSD").toUpperCase(),
});

export const scopeId = (s: Scope) => `${s.mode}:${s.symbol}`;
export const scopeLabel = (s: Scope) => `${s.mode === "LIVE" ? "LIVE" : "REPLAY (không phải live)"} ${s.symbol}`;
export const storageKey = (s: Scope, kind: "alerts" | "levels" | "drawings") => `xau-edge:v3:${s.mode}:${s.symbol}:${kind}`;

// ---- the trader's own horizontal lines (no effect on any decision) ------------------------------

export interface ManualLevel {
  id: string;
  price: number;
  label: string;
}

const validPrice = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v) && v > 0;
const validLevels = (raw: unknown): ManualLevel[] =>
  Array.isArray(raw) ? raw.filter((l) => l && typeof l.id === "string" && validPrice(l.price)).slice(0, 20) : [];

export function loadLevels(scope: Scope): ManualLevel[] {
  return validLevels(read<ManualLevel[]>(storageKey(scope, "levels")));
}

export function saveLevels(scope: Scope, levels: ManualLevel[]): void {
  write(storageKey(scope, "levels"), levels.slice(0, 20));
}

// ---- drawings: trendlines, zones, Fibonacci, manual risk-reward (annotations; no effect on any decision) ----

export function loadDrawings(scope: Scope): Drawing[] {
  return validDrawings(read<Drawing[]>(storageKey(scope, "drawings")));
}

export function saveDrawings(scope: Scope, drawings: Drawing[]): void {
  write(storageKey(scope, "drawings"), drawings.slice(0, MAX_DRAWINGS));
}

// ---- price alerts: evaluated in the open page only, they never trade ----------------------------

export interface PriceAlert {
  id: string;
  price: number;
  /** Fire when the bid crosses this price going up or going down. */
  direction: "UP" | "DOWN";
  createdAt: string;
  firedAt: string | null;
}

const validAlerts = (raw: unknown): PriceAlert[] =>
  Array.isArray(raw)
    ? raw.filter((a) => a && typeof a.id === "string" && validPrice(a.price) && (a.direction === "UP" || a.direction === "DOWN")).slice(0, 30)
    : [];

export function loadAlerts(scope: Scope): PriceAlert[] {
  return validAlerts(read<PriceAlert[]>(storageKey(scope, "alerts")));
}

export function saveAlerts(scope: Scope, alerts: PriceAlert[]): void {
  write(storageKey(scope, "alerts"), alerts.slice(0, 30));
}

/**
 * One-time, non-destructive migration of the TRADE-06/07 keys. The old data was drawn on live prices, so only
 * the LIVE scope adopts it (a replay page leaves it alone):
 * it is copied into that scope (only when the scope has nothing of its own) and the old key is retired.
 * If the scope already has data the old key is left untouched and never read again.
 */
export function migrateLegacy(scope: Scope): { alerts: number; levels: number } {
  const moved = { alerts: 0, levels: 0 };
  if (scope.mode !== "LIVE") return moved; // the owner's tools were drawn on live prices: a replay page never adopts (or deletes) them
  try {
    const ls = window.localStorage;
    const oldAlerts = validAlerts(read<PriceAlert[]>(LEGACY_ALERTS_KEY));
    if (ls.getItem(LEGACY_ALERTS_KEY) !== null) {
      if (ls.getItem(storageKey(scope, "alerts")) === null && oldAlerts.length > 0) {
        write(storageKey(scope, "alerts"), oldAlerts);
        moved.alerts = oldAlerts.length;
      }
      ls.removeItem(LEGACY_ALERTS_KEY);
    }
    const oldLevels = validLevels(read<ManualLevel[]>(LEGACY_LEVELS_KEY));
    if (ls.getItem(LEGACY_LEVELS_KEY) !== null) {
      if (ls.getItem(storageKey(scope, "levels")) === null && oldLevels.length > 0) {
        write(storageKey(scope, "levels"), oldLevels);
        moved.levels = oldLevels.length;
      }
      ls.removeItem(LEGACY_LEVELS_KEY);
    }
  } catch {
    /* storage unavailable: nothing to migrate */
  }
  return moved;
}

/** Pure crossing test: which alerts fire when the price moves from ``prev`` to ``now``. */
export function crossed(alert: PriceAlert, prev: number | null, now: number): boolean {
  if (alert.firedAt !== null || prev === null) return false;
  return alert.direction === "UP" ? prev < alert.price && now >= alert.price : prev > alert.price && now <= alert.price;
}

export function newId(): string {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
}
