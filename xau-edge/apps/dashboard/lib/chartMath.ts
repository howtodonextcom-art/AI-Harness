/** Pure chart helpers (no React, no chart library) so they can be unit-tested. */

export const TF_SECONDS: Record<string, number> = { M1: 60, M5: 300, M15: 900, M30: 1800, H1: 3600, H4: 14400 };

/** Index of the last bar whose open time is <= ``seconds`` (-1 when none). */
export function barIndexAt(times: number[], seconds: number): number {
  let lo = 0;
  let hi = times.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (times[mid] <= seconds) {
      found = mid;
      lo = mid + 1;
    } else hi = mid - 1;
  }
  return found;
}

/**
 * The bar a signal made at ``atSeconds`` belongs to on a chart of ``tfSeconds``.
 * The M5 trigger is a CLOSED bar: on charts up to M5 the marker sits on the last bar that had closed
 * when the signal was made (the bar that confirmed it, never one that was still forming); on
 * higher timeframes the signal falls inside a bar that is still forming, so it sits on that bar.
 */
export function signalBarIndex(times: number[], atSeconds: number, tfSeconds: number): number {
  return tfSeconds <= 300 ? barIndexAt(times, atSeconds - tfSeconds) : barIndexAt(times, atSeconds);
}

/** A number typed on a Vietnamese keyboard may use a decimal comma ("4050,5"); NaN when it is not a number. */
export function parseDecimal(text: string): number {
  const t = text.trim().replace(/\s/g, "");
  if (t === "") return Number.NaN;
  return Number(t.includes(",") && !t.includes(".") ? t.replace(",", ".") : t);
}

/** Countdown text ``mm:ss`` (or ``h:mm:ss``) to ``closeMs`` on the server-corrected clock. */
export function countdownText(closeMs: number | null, serverNowMs: number): string | null {
  if (closeMs === null) return null;
  const left = Math.max(0, Math.round((closeMs - serverNowMs) / 1000));
  const h = Math.floor(left / 3600);
  const m = Math.floor((left % 3600) / 60);
  const s = left % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}
