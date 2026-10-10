import { expect, test } from "@playwright/test";
import table from "../../../../tests/fixtures/session_table.json";
import { sessionAt, sessionRuns } from "../../lib/sessions";

/**
 * The browser's trading-session rules must equal the server's (`features/sessions.py`) at every
 * instant of this table, which straddles the US (Mar 8 / Nov 1) and UK (Mar 29 / Oct 25) clock changes.
 * The same table is asserted on the Python side (tests/unit/trading/test_session_table.py).
 */
test("sessions match the server at DST-sensitive instants", () => {
  for (const [iso, expected] of Object.entries(table as Record<string, string>)) {
    expect(sessionAt(Date.parse(`${iso}:00Z`)), iso).toBe(expected);
  }
});

test("a run of bars groups consecutive bars of the same session", () => {
  const start = Date.parse("2026-07-15T06:00:00Z");
  const opens = Array.from({ length: 48 }, (_, i) => start + i * 15 * 60_000);
  const runs = sessionRuns(opens);
  expect(runs.map((r) => r[2])).toEqual(["ASIA", "LONDON", "LONDON_NY_OVERLAP", "NEW_YORK"]);
  expect(runs[0][0]).toBe(0);
  expect(runs[runs.length - 1][1]).toBe(48);
});
