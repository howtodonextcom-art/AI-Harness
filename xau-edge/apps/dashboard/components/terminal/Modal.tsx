"use client";

import { useEffect, useRef, type ReactNode } from "react";

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface Props {
  title: string;
  labelledBy?: string;
  onClose: () => void;
  children: ReactNode;
  testId: string;
  tone?: "buy" | "sell" | "neutral";
}

/**
 * Accessible modal: role=dialog + aria-modal, focus moves in and is trapped, Escape closes, the
 * previously focused control gets focus back. Clicking the backdrop closes it too.
 */
export function Modal({ title, onClose, children, testId, tone = "neutral" }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  useEffect(() => {
    closeRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const node = box.current;
    const first = node?.querySelector<HTMLElement>("[data-autofocus]") ?? node?.querySelector<HTMLElement>(FOCUSABLE);
    first?.focus();
    if (node && !node.contains(document.activeElement)) node.focus(); // nothing focusable yet: keep focus inside the dialog
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        closeRef.current();
        return;
      }
      if (e.key !== "Tab" || !node) return;
      const items = Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (items.length === 0) return;
      const head = items[0];
      const tail = items[items.length - 1];
      if (e.shiftKey && document.activeElement === head) {
        e.preventDefault();
        tail.focus();
      } else if (!e.shiftKey && document.activeElement === tail) {
        e.preventDefault();
        head.focus();
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      previous?.focus?.();
    };
  }, []);

  const border = tone === "buy" ? "border-emerald-600" : tone === "sell" ? "border-red-600" : "border-slate-500";
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={box} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title} data-testid={testId} className={`max-h-[92vh] w-full overflow-y-auto rounded-t-xl border-2 bg-white p-4 shadow-2xl dark:bg-slate-900 sm:max-w-md sm:rounded-xl ${border}`}>
        <h2 className="mb-2 text-lg font-bold">{title}</h2>
        {children}
      </div>
    </div>
  );
}
