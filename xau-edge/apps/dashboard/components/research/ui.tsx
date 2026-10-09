"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { ResearchNav } from "@/components/research/ResearchNav";
import { SourceNote } from "@/components/research/SourceNote";
import { ageText, clean, type Provenance, type Result } from "@/lib/research";

export const card = "rounded-xl border border-slate-300/60 bg-white/60 p-4 dark:border-slate-700 dark:bg-slate-900/60";
export const th = "px-2 py-1 text-left text-xs font-semibold uppercase tracking-wide text-slate-500";
export const td = "px-2 py-1 align-top text-sm";

/** Text coming from a source file: the forbidden words are replaced before it is rendered. */
export function Txt({ children }: { children: string | null | undefined }) {
  return <>{children == null ? "" : clean(children)}</>;
}

function subscribe(onChange: () => void): () => void {
  const id = setInterval(onChange, 15000);
  return () => clearInterval(id);
}

function snapshot(): number {
  return Math.floor(Date.now() / 15000) * 15000;
}

/** Current time in ms (0 during server render), refreshed every 15 s, for "age of the data" labels. */
export function useNow(): number {
  return useSyncExternalStore(subscribe, snapshot, () => 0);
}

/** Load once from the API (and again when `reload` is called). `loader` must be a stable function. */
export function useLoad<T>(loader: (signal: AbortSignal) => Promise<Result<T>>): {
  result: Result<T> | null;
  reload: () => void;
} {
  const [result, setResult] = useState<Result<T> | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    loader(controller.signal)
      .then(setResult)
      .catch(() => undefined);
    return () => controller.abort();
  }, [loader, tick]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { result, reload };
}

export function ResearchShell({
  current,
  title,
  subtitle,
  children,
}: {
  current: string;
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <main className="mx-auto w-full max-w-[1440px] min-w-0 space-y-4 p-4 lg:p-6">
      <header className="space-y-2">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <Link href="/" className="text-xs text-slate-500 underline">
            XAU EDGE
          </Link>
        </div>
        <p className="text-sm text-slate-500">{subtitle}</p>
        <ResearchNav current={current} />
      </header>
      <p className="rounded-md border border-slate-300/60 p-2 text-xs text-slate-500 dark:border-slate-700">
        Console chỉ đọc: không có nút chạy thực nghiệm, mở dữ liệu khóa, bật giao dịch thật hay sửa ledger. Thao tác duy nhất là hạ
        trạng thái chiến lược (trang Forward).
      </p>
      {children}
    </main>
  );
}

export function Panel({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`${card} min-w-0 ${className}`} aria-label={title}>
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h2>
      {children}
    </section>
  );
}

export function Warning({ children }: { children: React.ReactNode }) {
  return (
    <p role="alert" className="rounded-md border-2 border-dashed border-amber-500 bg-amber-500/10 p-2 text-sm text-amber-900 dark:text-amber-200">
      {children}
    </p>
  );
}

/** "Fetched ... ago" (and the age of the data's own timestamp, flagged when older than a day). */
export function AgeNote({ fetchedAt, dataAt, dataLabel = "dữ liệu cập nhật" }: { fetchedAt: number; dataAt?: string | null; dataLabel?: string }) {
  const now = useNow();
  const data = ageText(dataAt, now);
  const fetched = ageText(new Date(fetchedAt).toISOString(), now);
  return (
    <p className="mt-2 text-[11px] text-slate-500">
      tải {fetched ? fetched.text : "…"}
      {data && (
        <>
          {" · "}
          <span className={data.stale ? "font-semibold text-amber-700 dark:text-amber-300" : ""}>
            {dataLabel} {data.text}
            {data.stale ? " (CŨ)" : ""}
          </span>
        </>
      )}
    </p>
  );
}

/**
 * Renders `children(data)` only when the API said "ok". A failed or unknown source shows a visible
 * warning instead (never an implicit OK). `partial` may show whatever the API still returned.
 */
export function Gate<T>({
  result,
  what,
  children,
  partial,
  dataAt,
}: {
  result: Result<T> | null;
  what: string;
  children: (data: T) => React.ReactNode;
  partial?: (data: T) => React.ReactNode;
  dataAt?: (data: T) => string | null | undefined;
}) {
  if (result === null) {
    return (
      <p aria-busy="true" className="text-sm text-slate-500">
        Đang tải {what}…
      </p>
    );
  }
  if (result.kind === "unknown") {
    return (
      <div className="space-y-2">
        <Warning>
          KHÔNG RÕ: {what}. <Txt>{result.reason}</Txt>
          {result.source ? <span className="font-mono"> (nguồn: {result.source})</span> : null}
        </Warning>
        {partial && result.partial ? partial(result.partial) : null}
        <SourceNote source={result.source} provenance={result.provenance} showProvenance />
        <AgeNote fetchedAt={result.fetchedAt} />
      </div>
    );
  }
  return (
    <>
      {children(result.data)}
      <SourceNote
        source={(result.data as { source?: string }).source}
        provenance={(result.data as { provenance?: Provenance | null }).provenance}
        showProvenance
      />
      <AgeNote fetchedAt={result.fetchedAt} dataAt={dataAt?.(result.data)} />
    </>
  );
}

export function RefreshButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="rounded-md border border-slate-400 px-3 py-1 text-sm hover:bg-slate-200 dark:hover:bg-slate-800">
      Tải lại
    </button>
  );
}

export function TableWrap({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <div className="max-w-full overflow-x-auto" tabIndex={0} role="region" aria-label={label}>
      {children}
    </div>
  );
}

export function Bar({ value, max, label, tone = "info" }: { value: number; max: number; label: string; tone?: "info" | "ok" | "fail" | "warn" }) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  const color = { info: "bg-sky-500", ok: "bg-green-600", fail: "bg-red-600", warn: "bg-amber-500" }[tone];
  return (
    <div
      className="h-2.5 w-full overflow-hidden rounded bg-slate-200 dark:bg-slate-800"
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
    >
      <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export { SourceNote };
