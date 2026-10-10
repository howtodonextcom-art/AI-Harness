/**
 * Harmless UI preferences and the trader's own chart annotations, kept in this browser only.
 * Never stored here: anything about authorization, strategy choice, risk approval or credentials.
 * Every read/write is guarded: with storage blocked the terminal still works, it just forgets.
 */

import type { DisplayZone } from "@/lib/time";

export type Tab = "overview" | "why" | "position" | "activity" | "system";

export interface Overlays {
  signals: boolean;
  plan: boolean;
  paper: boolean;
  structure: boolean;
  volume: boolean;
  sessions: boolean;
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
}

export const DEFAULT_PREFS: Prefs = {
  tf: "M5",
  overlays: { signals: true, plan: true, paper: true, structure: false, volume: true, sessions: false },
  follow: true,
  zone: "VN",
  tab: "overview",
  history: false,
  risk: 0.25,
  shortcuts: true,
};

const PREFS_KEY = "xau-edge.trade.prefs.v1";
const LEVELS_KEY = "xau-edge.trade.levels.v1";
const ALERTS_KEY = "xau-edge.trade.price-alerts.v1";

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
    },
    follow: bool(raw.follow, DEFAULT_PREFS.follow),
    zone: ZONES.includes(raw.zone as DisplayZone) ? (raw.zone as DisplayZone) : DEFAULT_PREFS.zone,
    tab: TABS.includes(raw.tab as Tab) ? (raw.tab as Tab) : DEFAULT_PREFS.tab,
    history: bool(raw.history, DEFAULT_PREFS.history),
    risk: typeof raw.risk === "number" && RISKS.includes(raw.risk) ? raw.risk : DEFAULT_PREFS.risk,
    shortcuts: bool(raw.shortcuts, DEFAULT_PREFS.shortcuts),
  };
}

export function savePrefs(prefs: Prefs): void {
  write(PREFS_KEY, prefs);
}

// ---- the trader's own horizontal lines (no effect on any decision) ------------------------------

export interface ManualLevel {
  id: string;
  price: number;
  label: string;
}

const validPrice = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v) && v > 0;

export function loadLevels(): ManualLevel[] {
  const raw = read<ManualLevel[]>(LEVELS_KEY);
  if (!Array.isArray(raw)) return [];
  return raw.filter((l) => l && typeof l.id === "string" && validPrice(l.price)).slice(0, 20);
}

export function saveLevels(levels: ManualLevel[]): void {
  write(LEVELS_KEY, levels.slice(0, 20));
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

export function loadAlerts(): PriceAlert[] {
  const raw = read<PriceAlert[]>(ALERTS_KEY);
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((a) => a && typeof a.id === "string" && validPrice(a.price) && (a.direction === "UP" || a.direction === "DOWN"))
    .slice(0, 30);
}

export function saveAlerts(alerts: PriceAlert[]): void {
  write(ALERTS_KEY, alerts.slice(0, 30));
}

/** Pure crossing test: which alerts fire when the price moves from ``prev`` to ``now``. */
export function crossed(alert: PriceAlert, prev: number | null, now: number): boolean {
  if (alert.firedAt !== null || prev === null) return false;
  return alert.direction === "UP" ? prev < alert.price && now >= alert.price : prev > alert.price && now <= alert.price;
}

export function newId(): string {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
}
