import type { Provenance } from "@/lib/research";

/** Shows where a figure comes from: small text plus a title attribute (hover). */
export function SourceNote({
  source,
  label = "nguồn",
  provenance,
  showProvenance = false,
}: {
  source: string | string[] | null | undefined;
  label?: string;
  provenance?: Provenance | null;
  showProvenance?: boolean;
}) {
  const text = Array.isArray(source) ? source.join(", ") : source;
  const commit = provenance?.code_commit ? provenance.code_commit.slice(0, 8) : null;
  const when = provenance?.generated_at ?? null;
  return (
    <p
      data-source-note={showProvenance ? "provenance" : "source"}
      className={`mt-2 break-all text-[11px] ${text ? "text-slate-500" : "text-amber-700 dark:text-amber-300"}`}
      title={`${label}: ${text ?? "KHÔNG RÕ"}`}
    >
      {label}: {text ? <span className="font-mono">{text}</span> : "KHÔNG RÕ"}
      {showProvenance && (
        <>
          {" · tạo lúc: "}
          <span className="font-mono">{when ?? "KHÔNG RÕ"}</span>
          {" · commit mã: "}
          <span className="font-mono">{commit ?? "KHÔNG RÕ"}</span>
        </>
      )}
    </p>
  );
}
