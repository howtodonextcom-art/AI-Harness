import type { ReactNode } from "react";

export const GOOD = "border-emerald-600 bg-emerald-500/15 text-emerald-800 dark:text-emerald-200";
export const WARN = "border-amber-600 bg-amber-500/15 text-amber-800 dark:text-amber-200";
export const BAD = "border-red-600 bg-red-500/15 text-red-800 dark:text-red-200";
export const NEUTRAL = "border-slate-500 bg-slate-500/15 text-slate-700 dark:text-slate-300";
export const INFO = "border-sky-600 bg-sky-500/15 text-sky-800 dark:text-sky-200";

export const TONE_STYLE: Record<string, string> = {
  buy: GOOD,
  sell: BAD,
  neutral: NEUTRAL,
  info: INFO,
  warn: WARN,
  error: BAD,
};

/** Not colour alone: every state also has an icon and a text label. */
export const TONE_ICON: Record<string, string> = {
  BUY_READY: "▲",
  SELL_READY: "▼",
  WAIT: "⏸",
  SETUP_ARMED: "◔",
  POSITION_OPEN: "●",
  EXITED: "✓",
  UNAVAILABLE: "⚠",
  STALE: "⌛",
  MARKET_CLOSED: "☾",
  EXPIRED_SETUP: "⏱",
  NOT_ACTIONABLE: "⚠",
};

export const fmt = (v: number | null | undefined, d = 2) => (v === null || v === undefined ? "—" : v.toFixed(d));
export const money = (v: number | null | undefined) =>
  v === null || v === undefined ? "—" : `${v >= 0 ? "" : "-"}$${Math.abs(v).toFixed(2)}`;

export function ageText(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  const s = Math.max(0, Math.round(seconds));
  if (s < 90) return `${s}s`;
  if (s < 5400) return `${Math.round(s / 60)} phút`;
  return `${(s / 3600).toFixed(1)} giờ`;
}

export function Pill({ label, value, tone, testId }: { label?: string; value: string; tone: string; testId?: string }) {
  return (
    <span data-testid={testId} className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold ${tone}`}>
      {label ? <span className="font-normal">{label}</span> : null}
      {value}
    </span>
  );
}

export function Card({ title, children, testId, className = "" }: { title: string; children: ReactNode; testId?: string; className?: string }) {
  return (
    <section data-testid={testId} className={`min-w-0 rounded-lg border border-slate-300 p-3 dark:border-slate-700 ${className}`}>
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">{title}</h2>
      {children}
    </section>
  );
}

export function Row({ k, v, testId }: { k: string; v: ReactNode; testId?: string }) {
  return (
    <div className="flex justify-between gap-3 py-0.5 text-sm">
      <span className="text-slate-600 dark:text-slate-400">{k}</span>
      <span data-testid={testId} className="font-mono tabular-nums">{v}</span>
    </div>
  );
}

export function biasText(bias: number | null): string {
  return bias === null ? "—" : bias > 0 ? "▲" : bias < 0 ? "▼" : "•";
}
