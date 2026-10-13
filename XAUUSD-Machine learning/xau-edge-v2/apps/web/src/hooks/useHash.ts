import { useCallback, useEffect, useState } from "react";

export const DRAWERS = ["journal", "evidence", "data", "model"] as const;
export type Drawer = (typeof DRAWERS)[number];

const read = (): Drawer | null => {
  const raw = location.hash.replace(/^#/, "");
  return (DRAWERS as readonly string[]).includes(raw) ? (raw as Drawer) : null;
};

/** The open drawer lives in the URL hash so a link opens the page with it open. */
export function useDrawer(): [Drawer | null, (d: Drawer | null) => void] {
  const [drawer, setDrawer] = useState<Drawer | null>(read);
  useEffect(() => {
    const onChange = () => setDrawer(read());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  const set = useCallback((d: Drawer | null) => {
    history.replaceState(null, "", d ? `#${d}` : location.pathname);
    setDrawer(d);
  }, []);
  return [drawer, set];
}
