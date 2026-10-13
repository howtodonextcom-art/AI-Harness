/**
 * The trader's own chart drawings (trendline, ray, vertical line, zone, Fibonacci, manual risk-reward) and the
 * key levels computed from bars (previous week high/low, session high/low). Pure functions, no React, no chart
 * library, so they can be unit-tested.
 *
 * A drawing is an ANNOTATION: it never reaches the decision, the strategy, the paper desk or any order. Its points
 * are real UTC epoch seconds + price, so changing the display time zone or the timeframe never moves it.
 */

export type DrawingKind = "trend" | "ray" | "vline" | "rect" | "fib" | "rr";

export interface Pt {
  /** UTC epoch seconds (a real instant, independent of the display zone) */
  t: number;
  p: number;
}

export interface Drawing {
  id: string;
  kind: DrawingKind;
  a: Pt;
  /** second anchor; for a vertical line it equals ``a``; for the risk-reward tool ``b.p`` is the STOP price and ``b.t`` its right edge */
  b: Pt;
  label: string;
  color: string;
  locked: boolean;
  createdAt: number;
  /** risk-reward tool only: reward as a multiple of risk (the take-profit distance) */
  rr?: number;
}

export const DRAWING_KINDS: DrawingKind[] = ["trend", "ray", "vline", "rect", "fib", "rr"];
export const MAX_DRAWINGS = 60;
export const DEFAULT_RR = 2;
export const DRAWING_COLORS = ["#0ea5e9", "#d97706", "#7c3aed", "#0891b2", "#16a34a", "#dc2626"];

export const KIND_VI: Record<DrawingKind, string> = {
  trend: "Đường xu hướng",
  ray: "Tia",
  vline: "Đường dọc",
  rect: "Vùng (hộp)",
  fib: "Fibonacci",
  rr: "R:R thủ công",
};

export const RR_NOT_A_SIGNAL = "PHÂN TÍCH THỦ CÔNG — KHÔNG PHẢI TÍN HIỆU";

const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const validPt = (v: unknown): v is Pt => !!v && finite((v as Pt).t) && finite((v as Pt).p) && (v as Pt).p > 0 && (v as Pt).t > 0;

/** Validate whatever came out of storage: a hand-edited or old value is dropped, never crashes the chart. */
export function validDrawings(raw: unknown): Drawing[] {
  if (!Array.isArray(raw)) return [];
  const out: Drawing[] = [];
  const seen = new Set<string>();
  for (const d of raw) {
    if (!d || typeof d.id !== "string" || seen.has(d.id) || !DRAWING_KINDS.includes(d.kind) || !validPt(d.a) || !validPt(d.b)) continue;
    seen.add(d.id);
    out.push({
      id: d.id,
      kind: d.kind,
      a: { t: d.a.t, p: d.a.p },
      b: { t: d.b.t, p: d.b.p },
      label: typeof d.label === "string" ? d.label.slice(0, 40) : "",
      color: typeof d.color === "string" && /^#[0-9a-fA-F]{6}$/.test(d.color) ? d.color : DRAWING_COLORS[0],
      locked: d.locked === true,
      createdAt: finite(d.createdAt) ? d.createdAt : 0,
      ...(d.kind === "rr" ? { rr: finite(d.rr) && d.rr > 0 && d.rr <= 20 ? d.rr : DEFAULT_RR } : {}),
    });
    if (out.length >= MAX_DRAWINGS) break;
  }
  return out;
}

// ---- time <-> logical index (bars are index-spaced: weekends and gaps take no room) -------------------

/** Index of the last time <= ``s`` (-1 when none). */
function floorIndex(times: number[], s: number): number {
  let lo = 0;
  let hi = times.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (times[mid] <= s) {
      found = mid;
      lo = mid + 1;
    } else hi = mid - 1;
  }
  return found;
}

/** Fractional logical index of a (display-shifted) instant. Past the last bar it extends by whole timeframes. */
export function toLogical(shifted: number, times: number[], tf: number): number {
  const n = times.length;
  if (n === 0) return 0;
  if (shifted >= times[n - 1]) return n - 1 + (shifted - times[n - 1]) / tf;
  if (shifted <= times[0]) return (shifted - times[0]) / tf;
  const i = floorIndex(times, shifted);
  const span = times[i + 1] - times[i];
  return i + Math.min(1, (shifted - times[i]) / span);
}

/** Inverse of ``toLogical``. */
export function fromLogical(logical: number, times: number[], tf: number): number {
  const n = times.length;
  if (n === 0) return 0;
  if (logical >= n - 1) return times[n - 1] + (logical - (n - 1)) * tf;
  if (logical <= 0) return times[0] + logical * tf;
  const i = Math.floor(logical);
  return times[i] + (logical - i) * (times[i + 1] - times[i]);
}

// ---- geometry --------------------------------------------------------------------------------------------

export const FIB_RATIOS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];

/** Retracement levels between the two anchors: ratio 0 is at the end point ``b``, 1 at the start ``a``. */
export function fibLevels(a: Pt, b: Pt): { ratio: number; price: number }[] {
  return FIB_RATIOS.map((ratio) => ({ ratio, price: b.p - (b.p - a.p) * ratio }));
}

export interface RrGeometry {
  side: "BUY" | "SELL" | "NONE";
  entry: number;
  sl: number;
  tp: number;
  risk: number;
  reward: number;
  /** distance in gold "points" (0.01) */
  riskPoints: number;
  rewardPoints: number;
  rr: number;
}

/** The manual risk-reward box: entry = ``a.p``, stop = ``b.p`` (below entry means long), take-profit = ``rr`` x risk away. */
export function rrGeometry(d: Pick<Drawing, "a" | "b" | "rr">): RrGeometry {
  const rr = d.rr ?? DEFAULT_RR;
  const risk = Math.abs(d.a.p - d.b.p);
  const side = d.b.p < d.a.p ? "BUY" : d.b.p > d.a.p ? "SELL" : "NONE";
  const dir = side === "BUY" ? 1 : -1;
  const tp = side === "NONE" ? d.a.p : d.a.p + dir * risk * rr;
  return { side, entry: d.a.p, sl: d.b.p, tp, risk, reward: risk * rr, riskPoints: risk / 0.01, rewardPoints: (risk * rr) / 0.01, rr };
}

/** The reward multiple that puts the take-profit at ``price`` (clamped to a sane range; NaN-safe). */
export function rrForTarget(entry: number, sl: number, price: number): number {
  const risk = Math.abs(entry - sl);
  if (risk === 0) return DEFAULT_RR;
  const dir = sl < entry ? 1 : -1;
  const rr = ((price - entry) * dir) / risk;
  return Number.isFinite(rr) ? Math.min(20, Math.max(0.1, Math.round(rr * 100) / 100)) : DEFAULT_RR;
}

/** Distance from a point to a segment, in pixels. */
export function distToSegment(px: number, py: number, x1: number, y1: number, x2: number, y2: number): number {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len2 = dx * dx + dy * dy;
  const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / len2));
  return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}

/** Extend the line through two screen points to the right edge ``xMax`` (a ray); null for a vertical or a leftward degenerate ray. */
export function rayEnd(x1: number, y1: number, x2: number, y2: number, xMax: number): { x: number; y: number } | null {
  if (x2 === x1) return null;
  const dir = x2 > x1 ? 1 : -1;
  const x = dir > 0 ? Math.max(xMax, x2) : Math.min(0, x2);
  return { x, y: y1 + ((y2 - y1) / (x2 - x1)) * (x - x1) };
}

// ---- key levels computed from bars -------------------------------------------------------------------------

export interface OhlcBar {
  time: string;
  high: number;
  low: number;
}

export interface WeekLevels {
  pwh: number;
  pwl: number;
  /** open time of the first and last bar of the week the levels come from */
  from: string;
  to: string;
}

const WEEK_GAP_MS = 40 * 3600_000; // the weekend gap is about 49 h; a holiday gap is shorter

/**
 * High/low of the PREVIOUS trading week. A week is a run of bars without a gap of 40 h or more (the weekend).
 * While the market is in a week the previous week is the one before the last run; on a weekend (no bar for 40 h)
 * the week that just ended is the "previous" one. null when the bars do not hold a whole earlier week.
 */
export function weekLevels(bars: OhlcBar[], nowMs: number, barMs: number): WeekLevels | null {
  if (bars.length < 2) return null;
  const runs: OhlcBar[][] = [];
  let run: OhlcBar[] = [bars[0]];
  for (let i = 1; i < bars.length; i++) {
    if (Date.parse(bars[i].time) - Date.parse(bars[i - 1].time) >= WEEK_GAP_MS) {
      runs.push(run);
      run = [];
    }
    run.push(bars[i]);
  }
  runs.push(run);
  const last = run[run.length - 1];
  const weekend = nowMs - (Date.parse(last.time) + barMs) >= WEEK_GAP_MS;
  const index = weekend ? runs.length - 1 : runs.length - 2;
  const week = runs[index];
  if (index < 1 || !week || week.length === 0) return null; // the oldest run is cut off by the history limit
  return { pwh: Math.max(...week.map((b) => b.high)), pwl: Math.min(...week.map((b) => b.low)), from: week[0].time, to: week[week.length - 1].time };
}

export interface SessionRange {
  session: "ASIA" | "LONDON" | "NEW_YORK";
  high: number;
  low: number;
  /** open time of the first bar of the run */
  from: string;
  /** the session is still running (its last bar is the newest bar) */
  live: boolean;
}

/**
 * High/low of the most recent run of each session, from bars ``inSession`` says belong to it. Only whole-hour
 * session boundaries are exact, so use hourly (or finer) bars.
 */
export function sessionRanges(bars: OhlcBar[], inSession: (ms: number, s: SessionRange["session"]) => boolean): SessionRange[] {
  const out: SessionRange[] = [];
  for (const session of ["ASIA", "LONDON", "NEW_YORK"] as const) {
    let end = -1;
    for (let i = bars.length - 1; i >= 0; i--) {
      if (inSession(Date.parse(bars[i].time), session)) {
        end = i;
        break;
      }
    }
    if (end < 0) continue;
    let start = end;
    while (start > 0 && inSession(Date.parse(bars[start - 1].time), session)) start--;
    const run = bars.slice(start, end + 1);
    out.push({ session, high: Math.max(...run.map((b) => b.high)), low: Math.min(...run.map((b) => b.low)), from: run[0].time, live: end === bars.length - 1 });
  }
  return out;
}
