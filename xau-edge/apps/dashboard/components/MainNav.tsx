"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS: [string, string][] = [
  ["/trade", "Trade"],
  ["/market", "Market"],
  ["/journal", "Journal"],
  ["/research", "Research"],
  ["/control", "System"],
];

/** The five places the owner needs. Plain links only: no actions. */
export function MainNav() {
  const path = usePathname() ?? "";
  return (
    <nav aria-label="Điều hướng chính" data-testid="main-nav" className="flex flex-wrap items-center gap-1 border-b border-slate-300 px-2 py-2 text-sm sm:gap-1.5 sm:px-4 dark:border-slate-700">
      <span className="mr-2 hidden font-bold sm:inline">XAU EDGE</span>
      {LINKS.map(([href, label]) => {
        const active = path === href || path.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`rounded-md border px-2 py-1 sm:px-3 ${active ? "border-sky-600 bg-sky-500/15 font-semibold" : "border-transparent text-slate-600 dark:text-slate-300"}`}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
