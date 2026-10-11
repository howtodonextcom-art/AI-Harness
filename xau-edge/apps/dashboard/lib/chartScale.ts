/**
 * What the price scale and the first view of the chart show. Pure, so it is unit-tested.
 *
 * Found by comparing /trade with the FTMO web terminal (2026-10-11): the candles filled 70% of the plot there and
 * 20-30% here, because (1) the scale also contained PDH/PDL/structure lines tens of points from the candles and
 * (2) the first view fitted all 400 loaded bars (3.5 px per M1 candle).
 */
export interface PriceRange {
  minValue: number;
  maxValue: number;
}

/** A context level may stretch the scale by at most this share of the candles' own range, on each side. */
export const CONTEXT_REACH = 0.5;
/** Target distance between two candles in the first view, in CSS px. */
export const TARGET_PITCH_PX = 9;
export const MIN_VISIBLE_BARS = 40;
export const MAX_VISIBLE_BARS = 160;

/**
 * Plan/position levels (`always`) are always inside the scale: the trader acts on them. Context levels
 * (structure, key levels, manual levels, alerts, TP2) join only when within CONTEXT_REACH of the candles' range;
 * a far level stays drawn and listed in the legend but never shrinks the candles.
 */
export function scaleRange(base: PriceRange, always: readonly number[], context: readonly number[]): PriceRange {
  let lo = base.minValue;
  let hi = base.maxValue;
  const span = Math.max(hi - lo, 1e-9);
  const reach = span * CONTEXT_REACH;
  for (const p of context) {
    if (!Number.isFinite(p)) continue;
    if (p >= lo - reach && p <= hi + reach) {
      lo = Math.min(lo, p);
      hi = Math.max(hi, p);
    }
  }
  for (const p of always) {
    if (!Number.isFinite(p)) continue;
    lo = Math.min(lo, p);
    hi = Math.max(hi, p);
  }
  return { minValue: lo, maxValue: hi };
}

/** How many bars the first view shows: wide enough to read each candle, never the whole history. */
export function defaultWindowBars(widthPx: number): number {
  if (!Number.isFinite(widthPx) || widthPx <= 0) return MAX_VISIBLE_BARS;
  return Math.min(MAX_VISIBLE_BARS, Math.max(MIN_VISIBLE_BARS, Math.floor(widthPx / TARGET_PITCH_PX)));
}
