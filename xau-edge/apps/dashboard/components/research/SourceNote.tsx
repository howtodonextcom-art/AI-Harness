/** Shows where a figure comes from: small text plus a title attribute (hover). */
export function SourceNote({ source, label = "nguồn" }: { source: string | string[] | null | undefined; label?: string }) {
  const text = Array.isArray(source) ? source.join(", ") : source;
  if (!text) return <p className="mt-2 text-[11px] text-amber-700 dark:text-amber-300">{label}: KHÔNG RÕ</p>;
  return (
    <p className="mt-2 break-all text-[11px] text-slate-500" title={`${label}: ${text}`}>
      {label}: <span className="font-mono">{text}</span>
    </p>
  );
}
