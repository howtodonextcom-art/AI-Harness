import assert from "node:assert/strict";
import { test } from "node:test";
import { type ChartBar, isStrictlyIncreasing, mergeBars, positionMarkers, toChartBar, wantsOlder, withForming } from "./bars.ts";

const bar = (time: number, close = 1): ChartBar => ({ time, open: 1, high: 2, low: 0.5, close, volume: 1 });
const series = (from: number, count: number, step = 60): ChartBar[] =>
  Array.from({ length: count }, (_, i) => bar(from + i * step));

test("mergeBars prepends older history without duplicates or gaps", () => {
  const newest = series(1000, 5);
  const older = series(1000 - 5 * 60, 5);
  const merged = mergeBars(newest, older);
  assert.equal(merged.length, 10);
  assert.ok(isStrictlyIncreasing(merged));
  assert.equal(merged[0]?.time, 700);
});

test("mergeBars with overlapping pages keeps one bar per time and the incoming copy wins", () => {
  const a = series(0, 6);
  const b = [bar(120, 9), ...series(180, 4)];
  const merged = mergeBars(a, b);
  assert.equal(merged.length, 7); // 0..360 every 60 s
  assert.equal(merged.find((x) => x.time === 120)?.close, 9);
  assert.ok(isStrictlyIncreasing(merged));
});

test("mergeBars is idempotent and never mutates its inputs", () => {
  const a = series(0, 4);
  const frozen = JSON.stringify(a);
  const once = mergeBars(a, series(0, 4));
  const twice = mergeBars(once, series(0, 4));
  assert.deepEqual(once, twice);
  assert.equal(JSON.stringify(a), frozen);
  assert.deepEqual(mergeBars(a, []), a);
});

test("mergeBars sorts unordered input", () => {
  const merged = mergeBars([bar(300), bar(60)], [bar(180), bar(0)]);
  assert.deepEqual(merged.map((b) => b.time), [0, 60, 180, 300]);
});

test("withForming appends a newer open bar and drops a stale or equal one", () => {
  const closed = series(0, 3);
  assert.equal(withForming(closed, bar(180)).length, 4);
  assert.equal(withForming(closed, bar(120)).length, 3); // already closed: the closed copy wins
  assert.equal(withForming(closed, bar(60)).length, 3);
  assert.equal(withForming(closed, null).length, 3);
  assert.equal(withForming([], bar(0)).length, 1);
  assert.ok(isStrictlyIncreasing(withForming(closed, bar(180))));
});

test("wantsOlder only fires near the left edge, with more history, and not while loading", () => {
  const ok = { hasMore: true, loading: false, loaded: 500 };
  assert.equal(wantsOlder(10, ok), true);
  assert.equal(wantsOlder(200, ok), false);
  assert.equal(wantsOlder(-5, ok), true);
  assert.equal(wantsOlder(10, { ...ok, loading: true }), false);
  assert.equal(wantsOlder(10, { ...ok, hasMore: false }), false);
  assert.equal(wantsOlder(10, { ...ok, loaded: 0 }), false);
});

test("toChartBar converts ISO time to epoch seconds", () => {
  const b = toChartBar({ time: "2026-10-12T18:09:00Z", open: 1, high: 2, low: 0.5, close: 1.5, tick_volume: 7 });
  assert.equal(b.time, Date.parse("2026-10-12T18:09:00Z") / 1000);
  assert.equal(b.volume, 7);
});

test("positionMarkers puts entry and exit on the bar they happened in and sorts by time", () => {
  const step = 900; // M15
  const closed = {
    side: "BUY" as const, status: "CLOSED" as const, opened_at: "2026-10-12T10:07:30Z",
    closed_at: "2026-10-12T10:41:00Z", exit_reason: "TAKE_PROFIT", net_pnl_usd: 42.4,
  };
  const open = { side: "SELL" as const, status: "OPEN" as const, opened_at: "2026-10-12T09:01:00Z" };
  const marks = positionMarkers([closed, open], step);
  assert.deepEqual(marks.map((m) => m.time), [
    Date.parse("2026-10-12T09:00:00Z") / 1000, // the SELL entry, bucketed to its M15 bar
    Date.parse("2026-10-12T10:00:00Z") / 1000, // the BUY entry
    Date.parse("2026-10-12T10:30:00Z") / 1000, // the exit
  ]);
  assert.equal(marks[0]?.shape, "arrowDown");
  assert.equal(marks[1]?.shape, "arrowUp");
  assert.match(marks[2]?.text ?? "", /^TP \+\$42$/);
  assert.equal(positionMarkers([], step).length, 0);
});

test("positionMarkers draws a losing exit in red", () => {
  const lost = { side: "SELL" as const, status: "CLOSED" as const, opened_at: "2026-10-12T10:00:00Z", closed_at: "2026-10-12T10:05:00Z", exit_reason: "STOP_LOSS", net_pnl_usd: -30 };
  const exit = positionMarkers([lost], 60).at(-1);
  assert.equal(exit?.color, "#b91c1c");
  assert.match(exit?.text ?? "", /^SL -\$30$/);
});
