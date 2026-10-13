/** Pure chart-data rules (no React, no chart library): merge, forming bar, paging triggers. */

export interface ChartBar {
  /** Bar open time, seconds since the epoch (UTC). */
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ApiBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  tick_volume: number;
}

export const toChartBar = (b: ApiBar): ChartBar => ({
  time: Math.floor(Date.parse(b.time) / 1000),
  open: b.open,
  high: b.high,
  low: b.low,
  close: b.close,
  volume: b.tick_volume,
});

/**
 * Union of two bar lists: strictly increasing by time, one bar per time, the incoming bar wins on a
 * tie (a refetch corrects an old copy). Never mutates its inputs, so a prepend can never duplicate.
 */
export function mergeBars(existing: readonly ChartBar[], incoming: readonly ChartBar[]): ChartBar[] {
  if (incoming.length === 0) return existing.slice();
  const byTime = new Map<number, ChartBar>();
  for (const b of existing) byTime.set(b.time, b);
  for (const b of incoming) byTime.set(b.time, b);
  return [...byTime.values()].sort((a, b) => a.time - b.time);
}

/**
 * The chart series: closed bars plus the still-open bar. A forming bar older than or equal to the
 * newest closed bar is ignored (the closed copy is authoritative), so the join never duplicates.
 */
export function withForming(closed: readonly ChartBar[], forming: ChartBar | null): ChartBar[] {
  const last = closed.at(-1);
  if (forming === null || (last !== undefined && forming.time <= last.time)) return closed.slice();
  return [...closed, forming];
}

/** True when the visible window is close enough to the oldest loaded bar to fetch older history. */
export function wantsOlder(
  visibleFromIndex: number,
  state: { hasMore: boolean; loading: boolean; loaded: number },
  margin = 40,
): boolean {
  return state.hasMore && !state.loading && state.loaded > 0 && visibleFromIndex < margin;
}

/** Strictly increasing and duplicate free (the invariant the chart relies on). */
export function isStrictlyIncreasing(bars: readonly ChartBar[]): boolean {
  return bars.every((b, i) => i === 0 || b.time > (bars[i - 1] as ChartBar).time);
}

export const TIMEFRAME_SECONDS = { M1: 60, M5: 300, M15: 900, M30: 1800, H1: 3600, H4: 14400 } as const;
export type Tf = keyof typeof TIMEFRAME_SECONDS;
export const TIMEFRAMES = Object.keys(TIMEFRAME_SECONDS) as Tf[];

export interface Mark {
  time: number;
  position: "aboveBar" | "belowBar";
  shape: "arrowUp" | "arrowDown" | "circle";
  color: string;
  text: string;
}

interface MarkablePosition {
  side: "BUY" | "SELL";
  opened_at: string;
  closed_at?: string | null;
  exit_reason?: string | null;
  status: "OPEN" | "CLOSED";
  net_pnl_usd?: number | null;
}

const bucket = (iso: string, step: number) => Math.floor(Date.parse(iso) / 1000 / step) * step;

/**
 * Entry and exit markers on the bar (of this timeframe) they happened in. Several events in one bar
 * are kept (the chart library draws them stacked); order is by time, as the library requires.
 */
export function positionMarkers(positions: readonly MarkablePosition[], step: number): Mark[] {
  const out: Mark[] = [];
  for (const p of positions) {
    const buy = p.side === "BUY";
    out.push({
      time: bucket(p.opened_at, step),
      position: buy ? "belowBar" : "aboveBar",
      shape: buy ? "arrowUp" : "arrowDown",
      color: buy ? "#15803d" : "#b91c1c",
      text: buy ? "MUA" : "BÁN",
    });
    if (p.status === "CLOSED" && p.closed_at) {
      const pnl = p.net_pnl_usd ?? 0;
      out.push({
        time: bucket(p.closed_at, step),
        position: buy ? "aboveBar" : "belowBar",
        shape: "circle",
        color: pnl >= 0 ? "#15803d" : "#b91c1c",
        text: `${p.exit_reason === "TAKE_PROFIT" ? "TP" : p.exit_reason === "STOP_LOSS" ? "SL" : "Đóng"} ${pnl >= 0 ? "+" : "-"}$${Math.abs(pnl).toFixed(0)}`,
      });
    }
  }
  return out.sort((a, b) => a.time - b.time);
}
