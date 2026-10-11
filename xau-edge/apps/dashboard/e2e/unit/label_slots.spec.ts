import { expect, test } from "@playwright/test";
import { allocateLabelSlots } from "../../lib/labelSlots";

test("labels never share a slot and the best priority keeps its own height", () => {
  const m = allocateLabelSlots([
    { id: "tp2", y: 100, priority: 4 },
    { id: "entry", y: 100, priority: 0 },
    { id: "sl", y: 104, priority: 1 },
  ], 14, 500);
  expect(m.get("entry")).toBe(100);
  expect(Math.abs(m.get("sl")! - 100)).toBeGreaterThanOrEqual(16);
  const ys = [...m.values()];
  for (let i = 0; i < ys.length; i++) for (let j = i + 1; j < ys.length; j++) expect(Math.abs(ys[i] - ys[j])).toBeGreaterThanOrEqual(16);
});

test("regression: levels far outside the visible range all clamp to one edge and the allocator still terminates", () => {
  const t0 = Date.now();
  const m = allocateLabelSlots(
    ["entry", "sl", "tp1", "now", "tp2"].map((id, i) => ({ id, y: 5000 + i, priority: i })),
    14,
    300,
  );
  expect(Date.now() - t0).toBeLessThan(200);
  expect(m.size).toBe(5);
  expect(m.get("entry")).toBe(300);
});

test("when the band is too small for every label the weakest are dropped, not stacked", () => {
  const m = allocateLabelSlots(
    ["entry", "sl", "tp1", "now", "tp2"].map((id, i) => ({ id, y: 20, priority: i })),
    14,
    40,
  );
  expect(m.has("entry")).toBe(true);
  expect(m.size).toBeLessThan(5);
  const ys = [...m.values()];
  for (let i = 0; i < ys.length; i++) for (let j = i + 1; j < ys.length; j++) expect(Math.abs(ys[i] - ys[j])).toBeGreaterThanOrEqual(16);
});

test("degenerate input is safe", () => {
  expect(allocateLabelSlots([], 14, 100).size).toBe(0);
  expect(allocateLabelSlots([{ id: "a", y: Number.NaN, priority: 0 }], 14, 100).size).toBe(0);
  expect(allocateLabelSlots([{ id: "a", y: 5, priority: 0 }], 50, 10).size).toBe(0);
});

test("maxShift: a label never sits far from its own line, it yields instead", () => {
  const m = allocateLabelSlots(
    [
      { id: "entry", y: 100, priority: 0 },
      { id: "sl", y: 100, priority: 1 },
      { id: "tp1", y: 100, priority: 2 },
      { id: "tp2", y: 100, priority: 3 },
      { id: "now", y: 100, priority: 4 },
      { id: "extra", y: 100, priority: 5 },
    ],
    14,
    500,
    16,
    40,
  );
  for (const [id, y] of m) expect(Math.abs(y - 100), id).toBeLessThanOrEqual(40);
  expect(m.size).toBe(5); // 100, 116, 84, 132, 68: the sixth would be more than 40 px away
  expect(m.has("extra")).toBe(false);
  expect(m.get("entry")).toBe(100);
});
