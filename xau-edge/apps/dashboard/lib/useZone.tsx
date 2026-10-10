"use client";

import { useCallback, useEffect, useState } from "react";
import { ZONE_KEY, ZONE_LABEL, loadZone, saveZone, type DisplayZone } from "@/lib/time";

/**
 * THE display-zone preference, shared by /trade, /market, /journal and /control: one value in this browser's
 * storage, read on load and followed live when another tab or page changes it. It only shifts what is drawn.
 */
export function useDisplayZone(fallback: DisplayZone = "VN"): [DisplayZone, (zone: DisplayZone) => void] {
  const [zone, setZone] = useState<DisplayZone>(fallback);
  useEffect(() => {
    const t = setTimeout(() => setZone(loadZone(fallback)), 0);
    const onStorage = (e: StorageEvent) => {
      if (e.key === ZONE_KEY || e.key === null) setZone(loadZone(fallback));
    };
    window.addEventListener("storage", onStorage);
    return () => {
      clearTimeout(t);
      window.removeEventListener("storage", onStorage);
    };
  }, [fallback]);
  const change = useCallback((next: DisplayZone) => {
    saveZone(next);
    setZone(next);
  }, []);
  return [zone, change];
}

/** The same selector everywhere (the market page keeps its own test id). */
export function ZoneSelect({ zone, onChange, testId = "zone-select" }: { zone: DisplayZone; onChange: (zone: DisplayZone) => void; testId?: string }) {
  return (
    <label className="flex items-center gap-2 text-sm">
      Múi giờ hiển thị
      <select value={zone} onChange={(e) => onChange(e.target.value as DisplayZone)} data-testid={testId} className="rounded-md border border-slate-400 bg-transparent px-2 py-1">
        {(Object.keys(ZONE_LABEL) as DisplayZone[]).map((z) => (
          <option key={z} value={z}>
            {ZONE_LABEL[z]}
          </option>
        ))}
      </select>
    </label>
  );
}
