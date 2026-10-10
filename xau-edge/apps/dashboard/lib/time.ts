/**
 * Display-time conversion in ONE place. Every timestamp the API returns is canonical UTC; the page
 * may show it as UTC, as broker time (FTMO server = New York + 7 h) or in the browser's zone.
 * Nothing here changes data: it only shifts what is drawn.
 */

export type DisplayZone = "VN" | "UTC" | "BROKER" | "LOCAL";

export const ZONE_LABEL: Record<DisplayZone, string> = {
  VN: "Giờ Việt Nam (GMT+7)",
  UTC: "UTC",
  BROKER: "Giờ broker (NY+7)",
  LOCAL: "Giờ máy tôi",
};

const NY = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", timeZoneName: "longOffset" });

function newYorkOffsetSeconds(ms: number): number {
  const name = NY.formatToParts(new Date(ms)).find((p) => p.type === "timeZoneName")?.value ?? "GMT-05:00";
  const match = /GMT([+-])(\d{1,2})(?::(\d{2}))?/.exec(name);
  if (!match) return -5 * 3600;
  const sign = match[1] === "-" ? -1 : 1;
  return sign * (Number(match[2]) * 3600 + Number(match[3] ?? 0) * 60);
}

export function offsetSeconds(zone: DisplayZone, ms: number): number {
  if (zone === "UTC") return 0;
  if (zone === "VN") return 7 * 3600; // Vietnam has no daylight saving
  if (zone === "LOCAL") return -new Date(ms).getTimezoneOffset() * 60;
  return newYorkOffsetSeconds(ms) + 7 * 3600;
}

/** Epoch seconds shifted so that UTC formatting of the result reads as wall-clock in ``zone``. */
export function shiftedSeconds(iso: string, zone: DisplayZone): number {
  const ms = Date.parse(iso);
  return ms / 1000 + offsetSeconds(zone, ms);
}

/** ``YYYY-MM-DD HH:mm:ss`` in the chosen zone (``—`` for a missing value). */
export function formatInZone(iso: string | null | undefined, zone: DisplayZone): string {
  if (!iso) return "—";
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return "—";
  return new Date(ms + offsetSeconds(zone, ms) * 1000).toISOString().slice(0, 19).replace("T", " ");
}

const KEY = "xau-edge.market.zone";

export function loadZone(fallback: DisplayZone = "UTC"): DisplayZone {
  try {
    const value = window.localStorage.getItem(KEY);
    if (value === "VN" || value === "UTC" || value === "BROKER" || value === "LOCAL") return value;
  } catch {
    /* storage unavailable: fall back */
  }
  return fallback;
}

/** ``HH:mm:ss`` in the chosen zone. */
export function clockInZone(ms: number, zone: DisplayZone): string {
  return new Date(ms + offsetSeconds(zone, ms) * 1000).toISOString().slice(11, 19);
}

export function saveZone(zone: DisplayZone): void {
  try {
    window.localStorage.setItem(KEY, zone);
  } catch {
    /* storage unavailable: the choice just is not remembered */
  }
}
