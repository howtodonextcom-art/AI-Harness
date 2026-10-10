/**
 * Trading-session label of an instant, DST-correct: the sessions are local exchange hours in their
 * own IANA zones, so the tz database moves them when the clocks change. These are the SAME rules as
 * the server's `features/sessions.py` (ADR-0011); a test pins both to the same table of instants.
 *
 *   ASIA      09:00-18:00 Asia/Tokyo
 *   LONDON    08:00-17:00 Europe/London
 *   NEW_YORK  08:00-17:00 America/New_York
 *   both Europe and US open -> LONDON_NY_OVERLAP; Asia overlapping London is labelled LONDON.
 */

export type Session = "ASIA" | "LONDON" | "NEW_YORK" | "LONDON_NY_OVERLAP" | "OFF_HOURS";

const ZONES = {
  tokyo: { zone: "Asia/Tokyo", from: 9 * 60, to: 18 * 60 },
  london: { zone: "Europe/London", from: 8 * 60, to: 17 * 60 },
  newYork: { zone: "America/New_York", from: 8 * 60, to: 17 * 60 },
} as const;

const formatters = new Map<string, Intl.DateTimeFormat>();

function minutesInZone(ms: number, zone: string): number {
  let f = formatters.get(zone);
  if (!f) {
    f = new Intl.DateTimeFormat("en-GB", { timeZone: zone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
    formatters.set(zone, f);
  }
  const parts = f.formatToParts(new Date(ms));
  const h = Number(parts.find((p) => p.type === "hour")?.value ?? 0);
  const m = Number(parts.find((p) => p.type === "minute")?.value ?? 0);
  return h * 60 + m;
}

const within = (ms: number, z: (typeof ZONES)[keyof typeof ZONES]) => {
  const t = minutesInZone(ms, z.zone);
  return t >= z.from && t < z.to;
};

const memo = new Map<number, Session>();

export function sessionAt(ms: number): Session {
  const key = Math.floor(ms / 60_000); // the label only changes on minute boundaries
  const hit = memo.get(key);
  if (hit !== undefined) return hit;
  const value = labelAt(ms);
  if (memo.size > 20_000) memo.clear();
  memo.set(key, value);
  return value;
}

function labelAt(ms: number): Session {
  const london = within(ms, ZONES.london);
  const ny = within(ms, ZONES.newYork);
  if (london && ny) return "LONDON_NY_OVERLAP";
  if (london) return "LONDON";
  if (ny) return "NEW_YORK";
  if (within(ms, ZONES.tokyo)) return "ASIA";
  return "OFF_HOURS";
}

export const SESSION_COLORS: Record<Session, string> = {
  ASIA: "rgba(14,165,233,0.07)",
  LONDON: "rgba(245,158,11,0.09)",
  NEW_YORK: "rgba(34,197,94,0.08)",
  LONDON_NY_OVERLAP: "rgba(168,85,247,0.11)",
  OFF_HOURS: "rgba(0,0,0,0)",
};

export const SESSION_NAMES: Record<Session, string> = {
  ASIA: "Á (Tokyo)",
  LONDON: "Âu (London)",
  NEW_YORK: "Mỹ (New York)",
  LONDON_NY_OVERLAP: "Âu-Mỹ chồng phiên",
  OFF_HOURS: "Ngoài phiên",
};

/** Contiguous runs of bars in the same session: [startIndex, endIndexExclusive, session]. */
export function sessionRuns(openMs: number[]): [number, number, Session][] {
  const runs: [number, number, Session][] = [];
  let start = 0;
  let current: Session | null = null;
  openMs.forEach((ms, i) => {
    const s = sessionAt(ms);
    if (current === null) current = s;
    if (s !== current) {
      runs.push([start, i, current]);
      start = i;
      current = s;
    }
  });
  if (current !== null && openMs.length > 0) runs.push([start, openMs.length, current]);
  return runs;
}
