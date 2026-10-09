export type Tone = "ok" | "warn" | "fail" | "unknown" | "neutral" | "info";

const TONE: Record<Tone, string> = {
  ok: "border-green-600 bg-green-500/10 text-green-800 dark:text-green-300",
  warn: "border-amber-500 bg-amber-500/10 text-amber-800 dark:text-amber-300",
  fail: "border-red-600 bg-red-500/10 text-red-800 dark:text-red-300",
  unknown: "border-amber-500 border-dashed bg-amber-500/10 text-amber-800 dark:text-amber-300",
  neutral: "border-slate-400 bg-slate-500/10 text-slate-700 dark:text-slate-300",
  info: "border-sky-600 bg-sky-500/10 text-sky-800 dark:text-sky-300",
};

/** One small pill used for every status in the console (text always says the state, never colour alone). */
export function StatusBadge({ tone, children, title }: { tone: Tone; children: React.ReactNode; title?: string }) {
  return (
    <span
      title={title}
      className={`inline-block max-w-full whitespace-normal break-words rounded border px-1.5 py-0.5 text-xs font-semibold ${TONE[tone]}`}
    >
      {children}
    </span>
  );
}
