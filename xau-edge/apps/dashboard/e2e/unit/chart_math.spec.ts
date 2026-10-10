import { expect, test } from "@playwright/test";
import { TF_SECONDS, barIndexAt, countdownText, signalBarIndex } from "../../lib/chartMath";

/** Pure chart logic: where a signal is drawn on each timeframe, and the candle countdown. */

const at = (iso: string) => Date.parse(iso) / 1000;
const grid = (start: string, count: number, tf: number) => Array.from({ length: count }, (_, i) => at(start) + i * tf);

// the real BUY of the acceptance replay: made at 14:45 UTC, confirmed by the M5 bar that closed at 14:45
const SIGNAL = at("2025-12-05T14:45:00Z");

test("on M1 the marker sits on the last CLOSED bar (14:44), never on a bar before the signal could exist", () => {
  const times = grid("2025-12-05T13:00:00Z", 120, 60);
  const idx = signalBarIndex(times, SIGNAL, TF_SECONDS.M1);
  expect(new Date(times[idx] * 1000).toISOString()).toBe("2025-12-05T14:44:00.000Z");
});

test("on M5 it sits on the trigger bar that closed at the signal (14:40)", () => {
  const times = grid("2025-12-05T12:00:00Z", 60, 300);
  expect(new Date(times[signalBarIndex(times, SIGNAL, TF_SECONDS.M5)] * 1000).toISOString()).toBe("2025-12-05T14:40:00.000Z");
});

test("above M5 it sits on the bar that was still forming when the signal was made", () => {
  const m15 = grid("2025-12-05T10:00:00Z", 24, 900);
  expect(new Date(m15[signalBarIndex(m15, SIGNAL, TF_SECONDS.M15)] * 1000).toISOString()).toBe("2025-12-05T14:45:00.000Z");
  const h1 = grid("2025-12-05T00:00:00Z", 24, 3600);
  expect(new Date(h1[signalBarIndex(h1, SIGNAL, TF_SECONDS.H1)] * 1000).toISOString()).toBe("2025-12-05T14:00:00.000Z");
});

test("a signal before the first loaded bar is not drawn", () => {
  expect(signalBarIndex(grid("2025-12-05T16:00:00Z", 10, 300), SIGNAL, 300)).toBe(-1);
  expect(barIndexAt([], 5)).toBe(-1);
});

test("the countdown runs on the server clock and never goes negative", () => {
  const close = Date.parse("2025-12-05T14:50:00Z");
  expect(countdownText(close, Date.parse("2025-12-05T14:47:47Z"))).toBe("02:13");
  expect(countdownText(close, Date.parse("2025-12-05T14:50:30Z"))).toBe("00:00");
  expect(countdownText(Date.parse("2025-12-05T18:00:00Z"), Date.parse("2025-12-05T14:45:00Z"))).toBe("3:15:00");
  expect(countdownText(null, 0)).toBeNull();
});
