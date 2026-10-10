import { expect, test } from "@playwright/test";
import { DEFAULT_RR, distToSegment, fibLevels, fromLogical, rayEnd, rrForTarget, rrGeometry, sessionRanges, toLogical, validDrawings, weekLevels } from "../lib/drawings";

/** DRAW-01: the pure maths behind the drawings and the key levels. */

test("fibonacci: 0 is the end point, 1 the start, 0.5 in the middle", () => {
  const levels = fibLevels({ t: 1, p: 4000 }, { t: 2, p: 4100 });
  expect(levels.map((l) => l.ratio)).toEqual([0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]);
  expect(levels[0].price).toBe(4100);
  expect(levels[6].price).toBe(4000);
  expect(levels[3].price).toBe(4050);
  expect(levels[4].price).toBeCloseTo(4038.2, 6);
});

test("risk-reward: stop below entry is a long idea, above is a short idea; take-profit is rr x risk away", () => {
  const long = rrGeometry({ a: { t: 1, p: 4000 }, b: { t: 2, p: 3990 }, rr: 2 });
  expect(long.side).toBe("BUY");
  expect(long.tp).toBe(4020);
  expect(long.riskPoints).toBeCloseTo(1000, 6); // 10.00 of price = 1000 gold points
  expect(long.rewardPoints).toBeCloseTo(2000, 6);
  const short = rrGeometry({ a: { t: 1, p: 4000 }, b: { t: 2, p: 4010 }, rr: 1.5 });
  expect(short.side).toBe("SELL");
  expect(short.tp).toBe(3985);
  expect(rrGeometry({ a: { t: 1, p: 4000 }, b: { t: 2, p: 4000 } }).side).toBe("NONE");
  expect(rrGeometry({ a: { t: 1, p: 4000 }, b: { t: 2, p: 3990 } }).rr).toBe(DEFAULT_RR);
});

test("dragging the take-profit gives the reward multiple, clamped and never NaN", () => {
  expect(rrForTarget(4000, 3990, 4030)).toBe(3);
  expect(rrForTarget(4000, 4010, 3970)).toBe(3);
  expect(rrForTarget(4000, 3990, 3000)).toBe(0.1); // on the wrong side of entry: the smallest allowed
  expect(rrForTarget(4000, 3990, 9000)).toBe(20);
  expect(rrForTarget(4000, 4000, 4010)).toBe(DEFAULT_RR);
  expect(rrForTarget(4000, 3990, Number.NaN)).toBe(DEFAULT_RR);
});

test("time to logical index and back: exact inside the data, extended by whole timeframes past the last bar", () => {
  const times = [0, 300, 600, 3600]; // a gap between the third and fourth bar takes no room
  expect(toLogical(300, times, 300)).toBe(1);
  expect(toLogical(450, times, 300)).toBeCloseTo(1.5, 6);
  expect(toLogical(3600, times, 300)).toBe(3);
  expect(toLogical(3600 + 600, times, 300)).toBe(5); // two timeframes after the last bar
  expect(toLogical(-300, times, 300)).toBe(-1);
  for (const l of [-2, 0, 0.25, 1.5, 2.9, 3, 7.5]) expect(toLogical(fromLogical(l, times, 300), times, 300)).toBeCloseTo(l, 6);
  expect(toLogical(5, [], 300)).toBe(0);
});

test("a ray runs to the right edge; a vertical one has no direction; a segment distance is in pixels", () => {
  expect(rayEnd(0, 100, 100, 50, 400)).toEqual({ x: 400, y: -100 });
  expect(rayEnd(100, 100, 100, 50, 400)).toBeNull();
  expect(distToSegment(5, 5, 0, 0, 10, 0)).toBe(5);
  expect(distToSegment(15, 0, 0, 0, 10, 0)).toBe(5); // beyond the end: distance to the end point
});

test("storage validation drops junk, de-duplicates ids, clamps rr and caps the count", () => {
  const good = { id: "a", kind: "rr", a: { t: 1_700_000_000, p: 4000 }, b: { t: 1_700_000_600, p: 3990 }, label: "x".repeat(100), color: "#112233", locked: true, createdAt: 5, rr: 99 };
  const out = validDrawings([good, { ...good }, { id: "b", kind: "nope" }, null, "x", { ...good, id: "c", a: { t: 0, p: 4000 } }, { ...good, id: "d", color: "red", rr: undefined }]);
  expect(out.map((d) => d.id)).toEqual(["a", "d"]);
  expect(out[0].label).toHaveLength(40);
  expect(out[0].rr).toBe(DEFAULT_RR); // 99 is out of range
  expect(out[1].color).toBe("#0ea5e9");
  expect(validDrawings("nope")).toEqual([]);
  const many = Array.from({ length: 200 }, (_, i) => ({ ...good, id: `id${i}` }));
  expect(validDrawings(many)).toHaveLength(60);
});

// ---- key levels ----------------------------------------------------------------------------------------------

const H = 3_600_000;
function week(startIso: string, hours: number, high: number, low: number) {
  const start = Date.parse(startIso);
  return Array.from({ length: hours }, (_, i) => ({ time: new Date(start + i * H).toISOString(), high: i === 5 ? high : high - 10, low: i === 7 ? low : low + 10 }));
}

test("previous week high/low: the week before the running one, or the week that just ended on a weekend", () => {
  const w1 = week("2026-09-20T22:00:00Z", 100, 4100, 3900); // week 1 (oldest: cut by history, never used)
  const w2 = week("2026-09-27T22:00:00Z", 100, 4200, 4000); // week 2
  const w3 = week("2026-10-04T22:00:00Z", 60, 4300, 4150); // week 3: running on Wed 2026-10-07
  const all = [...w1, ...w2, ...w3];
  const midweek = Date.parse("2026-10-07T12:00:00Z");
  const run = weekLevels(all, midweek, H);
  expect(run).not.toBeNull();
  expect(run?.pwh).toBe(4200);
  expect(run?.pwl).toBe(4000);
  // on the weekend the week that just ended is the "previous" one
  const weekend = Date.parse("2026-10-10T20:00:00Z"); // 2026-10-09 22:00 + ... no bar for > 40 h is needed
  const afterClose = weekLevels(all, Date.parse("2026-10-11T12:00:00Z"), H);
  expect(afterClose?.pwh).toBe(4300);
  expect(afterClose?.pwl).toBe(4150);
  void weekend;
  // not enough history: the only earlier run is cut off, so there is nothing trustworthy to show
  expect(weekLevels([...w2, ...w3], midweek, H)).toBeNull();
  expect(weekLevels(w3, midweek, H)).toBeNull();
  expect(weekLevels([], midweek, H)).toBeNull();
});

test("session ranges: the most recent run of each session; live when it is the newest bar", () => {
  const start = Date.parse("2026-10-07T00:00:00Z");
  const bars = Array.from({ length: 24 }, (_, i) => ({ time: new Date(start + i * H).toISOString(), high: 4000 + i, low: 3990 + i }));
  const hourOf = (ms: number) => new Date(ms).getUTCHours();
  const inSession = (ms: number, s: "ASIA" | "LONDON" | "NEW_YORK") => {
    const h = hourOf(ms);
    return s === "ASIA" ? h < 9 : s === "LONDON" ? h >= 7 && h < 16 : h >= 12 && h < 21;
  };
  const out = sessionRanges(bars, inSession);
  const asia = out.find((r) => r.session === "ASIA");
  const london = out.find((r) => r.session === "LONDON");
  const ny = out.find((r) => r.session === "NEW_YORK");
  expect(asia).toMatchObject({ high: 4008, low: 3990, live: false });
  expect(london).toMatchObject({ high: 4015, low: 3997, live: false });
  expect(ny).toMatchObject({ high: 4020, low: 4002, live: false });
  expect(sessionRanges(bars.slice(0, 10), inSession).find((r) => r.session === "ASIA")?.live).toBe(false);
  expect(sessionRanges(bars.slice(0, 9), inSession).find((r) => r.session === "ASIA")?.live).toBe(true);
  expect(sessionRanges([], inSession)).toEqual([]);
});
