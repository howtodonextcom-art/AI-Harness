"use client";

import { useState } from "react";
import { KIND_VI, RR_NOT_A_SIGNAL, rrGeometry, type Drawing, type DrawingKind } from "@/lib/drawings";
import type { Tool } from "@/components/terminal/TerminalChart";

const TOOLS: { kind: DrawingKind; icon: string; how: string }[] = [
  { kind: "trend", icon: "⟋", how: "Bấm 2 điểm" },
  { kind: "ray", icon: "↗", how: "Bấm 2 điểm, kéo dài sang phải" },
  { kind: "vline", icon: "│", how: "Bấm 1 điểm" },
  { kind: "rect", icon: "▭", how: "Bấm 2 góc" },
  { kind: "fib", icon: "𝑓", how: "Bấm đỉnh/đáy rồi đáy/đỉnh" },
  { kind: "rr", icon: "⇅", how: "Bấm điểm vào, rồi điểm cắt lỗ" },
];

interface Props {
  tool: Tool;
  onTool: (t: Tool) => void;
  drawings: Drawing[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onPatch: (id: string, patch: Partial<Drawing>) => void;
  onDelete: (id: string) => void;
  onClear: () => void;
  scopeLabel: string | null;
  btn: string;
  on: string;
  off: string;
  roomy: string;
}

const summary = (d: Drawing): string => {
  if (d.kind === "rr") {
    const g = rrGeometry(d);
    return `${g.side === "BUY" ? "MUA" : g.side === "SELL" ? "BÁN" : "—"} ${g.entry.toFixed(2)} · SL ${Math.round(g.riskPoints)} đ · R:R 1:${g.rr}`;
  }
  if (d.kind === "vline") return new Date(d.a.t * 1000).toISOString().slice(0, 16).replace("T", " ") + " UTC";
  return `${d.a.p.toFixed(2)} → ${d.b.p.toFixed(2)}`;
};

/** Drawing tools menu and the compact object manager. Drawings are the trader's own notes: nothing here touches a decision. */
export function DrawingMenu(p: Props) {
  const [menu, setMenu] = useState(false);
  const [manager, setManager] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const drawing = TOOLS.some((t) => t.kind === p.tool);
  return (
    <>
      <div className={`relative ${p.roomy}`}>
        <button type="button" data-testid="draw-menu" title="Công cụ vẽ" aria-expanded={menu} aria-haspopup="true" onClick={() => { setMenu(!menu); setManager(false); }} className={`inline-flex ${p.btn} ${menu || drawing ? p.on : p.off}`}>
          ✎&nbsp;Vẽ
        </button>
        {menu && (
          <div role="menu" aria-label="Công cụ vẽ" data-testid="draw-menu-list" className="absolute left-0 top-9 z-30 w-72 space-y-0.5 rounded-lg border border-slate-400 bg-white p-1 text-xs shadow-lg dark:bg-slate-900" onKeyDown={(e) => e.key === "Escape" && setMenu(false)}>
            {TOOLS.map((t) => (
              <button key={t.kind} role="menuitemradio" aria-checked={p.tool === t.kind} type="button" data-testid={`tool-${t.kind}`} onClick={() => { p.onTool(p.tool === t.kind ? "none" : t.kind); setMenu(false); }} className={`flex w-full items-center gap-2 rounded px-2 py-1 text-left hover:bg-slate-500/10 ${p.tool === t.kind ? p.on : ""}`}>
                <span className="w-5 text-center text-sm" aria-hidden="true">{t.icon}</span>
                <span className="font-semibold">{KIND_VI[t.kind]}</span>
                <span className="ml-auto text-[11px] text-slate-600 dark:text-slate-400">{t.how}</span>
              </button>
            ))}
            <p className="px-2 pt-1 text-[11px] text-slate-600 dark:text-slate-400">Chỉ là ghi chú của bạn: không ảnh hưởng quyết định hay giao dịch. Esc để hủy.</p>
          </div>
        )}
      </div>
      <div className={`relative ${p.roomy}`}>
        <button type="button" data-testid="drawing-manager-btn" title="Quản lý các nét vẽ" aria-expanded={manager} onClick={() => { setManager(!manager); setMenu(false); setConfirmClear(false); }} className={`inline-flex ${p.btn} ${manager ? p.on : p.off}`}>
          ☷&nbsp;Nét vẽ ({p.drawings.length})
        </button>
        {manager && (
          <div role="dialog" aria-label="Quản lý các nét vẽ" data-testid="drawing-manager" className="absolute left-0 top-9 z-30 w-80 max-w-[calc(100vw-1rem)] rounded-lg border border-slate-400 bg-white p-2 text-xs shadow-lg dark:bg-slate-900" onKeyDown={(e) => e.key === "Escape" && setManager(false)}>
            {p.scopeLabel && <p data-testid="drawing-scope" className="mb-1 inline-block rounded border border-slate-500 px-1.5 py-0.5 font-bold">Chỉ dùng cho: {p.scopeLabel}</p>}
            {p.drawings.length === 0 ? (
              <p className="text-slate-600 dark:text-slate-400">Chưa có nét vẽ nào. Chọn “Vẽ” để thêm đường xu hướng, vùng, Fibonacci hoặc R:R thủ công.</p>
            ) : (
              <ul className="max-h-64 space-y-1 overflow-auto">
                {p.drawings.map((d) => (
                  <li key={d.id} data-testid={`manager-row-${d.id}`} className={`rounded border p-1 ${d.id === p.selectedId ? "border-sky-600 bg-sky-500/10" : "border-slate-300 dark:border-slate-700"}`}>
                    <div className="flex items-center gap-1">
                      <button type="button" onClick={() => p.onSelect(d.id === p.selectedId ? null : d.id)} className="font-semibold underline decoration-dotted" aria-label={`Chọn ${KIND_VI[d.kind]}`}>{KIND_VI[d.kind]}</button>
                      <span className="ml-1 truncate font-mono text-[11px] text-slate-600 dark:text-slate-400">{summary(d)}</span>
                      <button type="button" data-testid="manager-lock" aria-pressed={d.locked} title={d.locked ? "Đang khóa: bấm để mở" : "Khóa để không kéo nhầm"} onClick={() => p.onPatch(d.id, { locked: !d.locked })} className="ml-auto rounded border border-slate-400 px-1">{d.locked ? "🔒" : "🔓"}</button>
                      <button type="button" data-testid="manager-delete" disabled={d.locked} title={d.locked ? "Mở khóa trước khi xóa" : "Xóa"} aria-label={`Xóa ${KIND_VI[d.kind]}`} onClick={() => p.onDelete(d.id)} className="rounded border border-slate-400 px-1 disabled:opacity-40">🗑</button>
                    </div>
                    <input data-testid="manager-label" aria-label="Tên nét vẽ" maxLength={40} value={d.label} placeholder="Tên / ghi chú (tùy chọn)" onChange={(e) => p.onPatch(d.id, { label: e.target.value })} className="mt-1 w-full rounded border border-slate-400 bg-transparent px-1 py-0.5 text-inherit" />
                    {d.kind === "rr" && <p className="mt-0.5 text-[10px] font-bold text-slate-600 dark:text-slate-400">{RR_NOT_A_SIGNAL}</p>}
                  </li>
                ))}
              </ul>
            )}
            {p.drawings.length > 0 && (
              <div className="mt-2 flex items-center gap-2">
                {confirmClear ? (
                  <>
                    <span>Xóa tất cả (trừ nét đã khóa)?</span>
                    <button type="button" data-testid="manager-clear-confirm" onClick={() => { p.onClear(); setConfirmClear(false); }} className="rounded border border-red-600 px-2 py-0.5 font-bold text-red-700 dark:text-red-300">Xóa</button>
                    <button type="button" onClick={() => setConfirmClear(false)} className="rounded border border-slate-400 px-2 py-0.5">Hủy</button>
                  </>
                ) : (
                  <button type="button" data-testid="manager-clear" onClick={() => setConfirmClear(true)} className="rounded border border-slate-400 px-2 py-0.5">Xóa tất cả…</button>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}
