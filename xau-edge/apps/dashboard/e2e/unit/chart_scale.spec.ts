import { expect, test } from "@playwright/test";
import { CONTEXT_REACH, MAX_VISIBLE_BARS, MIN_VISIBLE_BARS, defaultWindowBars, scaleRange } from "../../lib/chartScale";

const base = { minValue: 4194, maxValue: 4197 }; // candles span 3.0

test("a far context level (PDL/PDH) never stretches the scale", () => {
  const r = scaleRange(base, [], [4131.73, 4207.4, 4141.56]);
  expect(r).toEqual(base);
});

test("a near context level joins the scale, up to half of the candles' own range", () => {
  const near = base.maxValue + CONTEXT_REACH * 3 - 0.01;
  expect(scaleRange(base, [], [near]).maxValue).toBe(near);
  expect(scaleRange(base, [], [base.maxValue + CONTEXT_REACH * 3 + 0.5]).maxValue).toBe(base.maxValue);
});

test("plan and position levels are always inside the scale, even when far", () => {
  const r = scaleRange(base, [4229.45, 4250.51, 4236.47], [4131.73]);
  expect(r.minValue).toBe(4194);
  expect(r.maxValue).toBe(4250.51);
});

test("with no plan the candles keep at least two thirds of the plot", () => {
  const r = scaleRange(base, [], [4195.5, 4198.2, 4192.5, 4131.73, 4207.4]);
  expect((base.maxValue - base.minValue) / (r.maxValue - r.minValue)).toBeGreaterThanOrEqual(1 / (1 + 2 * CONTEXT_REACH));
});

test("non-finite prices are ignored", () => {
  expect(scaleRange(base, [Number.NaN], [Number.POSITIVE_INFINITY])).toEqual(base);
});

test("the first view shows a readable number of bars for the width, never the whole history", () => {
  expect(defaultWindowBars(1000)).toBe(111);
  expect(defaultWindowBars(330)).toBe(MIN_VISIBLE_BARS);
  expect(defaultWindowBars(4000)).toBe(MAX_VISIBLE_BARS);
  expect(defaultWindowBars(0)).toBe(MAX_VISIBLE_BARS);
  expect(defaultWindowBars(Number.NaN)).toBe(MAX_VISIBLE_BARS);
});
