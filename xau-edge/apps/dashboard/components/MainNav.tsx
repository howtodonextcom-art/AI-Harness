"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS: [string, string][] = [
  ["/trade", "Trade"],
  ["/market", "Dữ liệu"],
  ["/journal", "Journal"],
  ["/research", "Research"],
];

/** Operations (DEMO bot, preflight, emergency flatten) is not a trader page: it sits apart, after the trader links. */
const OPS: [string, string] = ["/control", "Vận hành"];

/** The trader's places, then Operations. Plain links only: no actions. */
export function MainNav() {
  const path = usePathname() ?? "";
  const cls = (active: boolean) => `rounded-md border px-2 py-1 short:py-0 sm:px-3 ${active ? "border-sky-600 bg-sky-500/15 font-semibold" : "border-transparent text-slate-600 dark:text-slate-300"}`;
  const isActive = (href: string) => path === href || path.startsWith(`${href}/`);
  return (
    <nav aria-label="Điều hướng chính" data-testid="main-nav" className="flex flex-wrap items-center gap-1 border-b border-slate-300 px-2 py-2 short:py-0.5 text-sm sm:gap-1.5 sm:px-4 dark:border-slate-700">
      <span className="mr-2 hidden font-bold sm:inline">XAU EDGE</span>
      {LINKS.map(([href, label]) => (
        <Link key={href} href={href} aria-current={isActive(href) ? "page" : undefined} className={cls(isActive(href))}>
          {label}
        </Link>
      ))}
      <Link
        href={OPS[0]}
        data-testid="nav-ops"
        title="Vận hành bot DEMO (đang khóa). Không phải trang giao dịch."
        aria-current={isActive(OPS[0]) ? "page" : undefined}
        className={`ml-auto text-xs ${cls(isActive(OPS[0]))}`}
      >
        {OPS[1]}
      </Link>
    </nav>
  );
}
