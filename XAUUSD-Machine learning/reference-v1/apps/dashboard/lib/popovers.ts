"use client";

import { useEffect } from "react";

/**
 * One top-level popover or dialog at a time. The toolbar's popovers (alert, overlays), the drawing menu and manager and
 * the shortcut dialog live in different components; opening one announces itself and every other closes (QA round 3, L-01:
 * three dialogs could be open at once and Escape closed only the top one).
 */
const EVENT = "xau:popover-open";

export function announcePopover(id: string): void {
  window.dispatchEvent(new CustomEvent(EVENT, { detail: id }));
}

export function useClosedByOtherPopover(id: string, close: () => void): void {
  useEffect(() => {
    const handler = (e: Event) => {
      if ((e as CustomEvent<string>).detail !== id) close();
    };
    window.addEventListener(EVENT, handler);
    return () => window.removeEventListener(EVENT, handler);
  }, [id, close]);
}
