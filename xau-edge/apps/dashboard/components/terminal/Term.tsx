"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { GLOSSARY, type TermId } from "@/lib/glossary";

/**
 * A trading term with a one-sentence explanation: hover, keyboard focus or tap opens it, Esc / outside tap closes it.
 * The label stays plain text for screen readers; the sentence is wired with aria-describedby.
 */
export function Term({ id, children }: { id: TermId; children?: ReactNode }) {
  const g = GLOSSARY[id];
  const [open, setOpen] = useState(false);
  const tipId = useId();
  const box = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        setOpen(false);
      }
    };
    const onDown = (e: PointerEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey, true);
    document.addEventListener("pointerdown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      document.removeEventListener("pointerdown", onDown);
    };
  }, [open]);
  return (
    <span ref={box} className="relative inline-block" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        data-testid={`term-${id}`}
        aria-describedby={open ? tipId : undefined}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="cursor-help rounded-sm underline decoration-dotted underline-offset-2"
      >
        {children ?? g.title.split(" (")[0]}
      </button>
      {open && (
        <span id={tipId} role="tooltip" data-testid={`tip-${id}`} className="absolute left-0 top-full z-30 mt-1 w-60 max-w-[80vw] rounded-md border border-slate-400 bg-white p-2 text-left text-xs font-normal normal-case leading-snug text-slate-900 shadow-lg dark:bg-slate-900 dark:text-slate-100">
          <b className="block">{g.title}</b>
          {g.text}
        </span>
      )}
    </span>
  );
}
