"use client";

import type { TimeframeRow } from "@/lib/trade";
import { TF_ROLE_VI } from "@/lib/vi";

/** Short trader wording for a timeframe's server state. */
export function shortState(state: string): { text: string; tone: "up" | "down" | "flat" } {
  const s = state.toUpperCase();
  const up = s.includes("UP") || s.includes("BULL");
  const down = s.includes("DOWN") || s.includes("BEAR");
  const tone: "up" | "down" | "flat" = up && !down ? "up" : down && !up ? "down" : "flat";
  if (s.includes("TRIGGERED")) return { text: `KÍCH HOẠT ${tone === "up" ? "↑" : tone === "down" ? "↓" : ""}`.trim(), tone };
  if (s.includes("PULLBACK")) return { text: `PULLBACK ${tone === "up" ? "↑" : tone === "down" ? "↓" : ""}`.trim(), tone };
  if (s.startsWith("BULL")) return { text: "TĂNG", tone: "up" };
  if (s.startsWith("BEAR")) return { text: "GIẢM", tone: "down" };
  if (s === "UP") return { text: "↑ TĂNG", tone: "up" };
  if (s === "DOWN") return { text: "↓ GIẢM", tone: "down" };
  if (s.includes("REVERSAL")) return { text: `ĐẢO CHIỀU ${tone === "up" ? "↑" : tone === "down" ? "↓" : ""}`.trim(), tone };
  const table: Record<string, string> = { RANGE: "ĐI NGANG", SPREAD_WIDE: "SPREAD RỘNG", WIDE: "RỘNG", ELEVATED: "NHỈNH", NEUTRAL: "TRUNG TÍNH", FLAT: "ĐỨNG", GOOD: "TỐT", NORMAL: "BÌNH THƯỜNG", STALE: "CŨ", NONE: "—" };
  return { text: table[s] ?? state, tone };
}

const TONE_CLASS = { up: "text-emerald-700 dark:text-emerald-300", down: "text-red-700 dark:text-red-300", flat: "text-slate-600 dark:text-slate-300" };

/** Multi-timeframe context in one row; a click switches the chart to that timeframe. */
export function MtfStrip({ rows, tf, onFocus }: { rows: TimeframeRow[]; tf: string; onFocus: (tf: string) => void }) {
  return (
    <div data-testid="matrix" role="group" aria-label="Bối cảnh đa khung thời gian" className="grid grid-cols-3 gap-1 text-xs sm:grid-cols-6">
      {rows.map((r) => {
        const s = shortState(r.state);
        return (
          <button
            key={r.timeframe}
            type="button"
            data-testid={`matrix-${r.timeframe}`}
            aria-pressed={tf === r.timeframe}
            onClick={() => onFocus(r.timeframe)}
            title={`${r.timeframe} · ${TF_ROLE_VI[r.timeframe] ?? r.role} · ${r.state} — bấm để xem biểu đồ`}
            className={`rounded-md border px-2 py-1 text-left hover:bg-slate-500/10 ${tf === r.timeframe ? "border-sky-600 bg-sky-500/10" : "border-slate-300 dark:border-slate-700"}`}
          >
            <div className="flex items-center justify-between">
              <span className="font-bold">{r.timeframe}</span>
              <span className="text-[11px] text-slate-600 dark:text-slate-400">{TF_ROLE_VI[r.timeframe] ?? ""}</span>
            </div>
            <div className={`truncate font-semibold ${TONE_CLASS[s.tone]}`}>{s.text}</div>
          </button>
        );
      })}
    </div>
  );
}
