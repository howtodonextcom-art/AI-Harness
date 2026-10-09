import Link from "next/link";

const LINKS: [string, string][] = [
  ["/research", "Tổng quan"],
  ["/research/ledger", "Ledger & K"],
  ["/research/hypotheses", "Giả thuyết"],
  ["/research/evidence", "Bằng chứng"],
  ["/research/candidates", "Ứng viên"],
  ["/research/data", "Dữ liệu & khóa"],
  ["/research/lineage", "Lineage"],
  ["/research/forward", "Forward & vòng đời"],
  ["/research/operations", "Vận hành"],
];

/** Links to every console page and back to the main dashboard. Plain links only: no actions. */
export function ResearchNav({ current }: { current: string }) {
  return (
    <nav aria-label="Điều hướng Research Console" className="flex flex-wrap gap-1.5 text-xs sm:gap-2 sm:text-sm">
      <Link href="/" className="rounded-md border border-slate-400 px-2 py-1 sm:px-3">
        ← Dashboard chính
      </Link>
      {LINKS.map(([href, label]) => (
        <Link
          key={href}
          href={href}
          aria-current={href === current ? "page" : undefined}
          className={`rounded-md border px-2 py-1 sm:px-3 ${
            href === current
              ? "border-sky-600 bg-sky-500/15 font-semibold text-sky-800 dark:text-sky-200"
              : "border-slate-400 text-slate-700 dark:text-slate-300"
          }`}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}
