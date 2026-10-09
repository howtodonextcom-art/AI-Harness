import Link from "next/link";

const LINKS: [string, string][] = [
  ["/research", "Tổng quan"],
  ["/research/ledger", "Ledger & K"],
  ["/research/hypotheses", "Giả thuyết"],
  ["/research/candidates", "Ứng viên"],
  ["/research/data", "Dữ liệu & khóa"],
  ["/research/forward", "Forward & vòng đời"],
  ["/research/operations", "Vận hành"],
];

/** Links to every console page and back to the main dashboard. Plain links only: no actions. */
export function ResearchNav({ current }: { current: string }) {
  return (
    <nav aria-label="Điều hướng Research Console" className="flex flex-wrap gap-2 text-sm">
      <Link href="/" className="rounded-md border border-slate-400 px-3 py-1">
        ← Dashboard chính
      </Link>
      {LINKS.map(([href, label]) => (
        <Link
          key={href}
          href={href}
          aria-current={href === current ? "page" : undefined}
          className={`rounded-md border px-3 py-1 ${
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
