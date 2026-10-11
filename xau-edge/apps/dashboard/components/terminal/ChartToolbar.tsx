"use client";

import { useCallback, useState } from "react";
import { announcePopover, useClosedByOtherPopover } from "@/lib/popovers";
import { parseDecimal } from "@/lib/chartMath";
import type { ManualLevel, Overlays, PriceAlert } from "@/lib/prefs";
import type { Tool } from "@/components/terminal/TerminalChart";
import { DrawingMenu } from "@/components/terminal/DrawingMenu";
import type { Drawing } from "@/lib/drawings";

const TFS = ["M1", "M5", "M15", "M30", "H1", "H4"];

interface Props {
  tf: string;
  onTf: (tf: string) => void;
  overlays: Overlays;
  onOverlays: (o: Overlays) => void;
  history: boolean;
  onHistory: (v: boolean) => void;
  follow: boolean;
  onFollow: (v: boolean) => void;
  fullscreen: boolean;
  onFullscreen: (v: boolean) => void;
  tool: Tool;
  onTool: (t: Tool) => void;
  onFit: () => void;
  onLatest: () => void;
  onAlert: (price: number) => void;
  bid: number | null;
  alertCount: number;
  alerts: PriceAlert[];
  onRemoveAlert: (id: string) => void;
  levels: ManualLevel[];
  onRemoveLevel: (id: string) => void;
  onHelp: () => void;
  drawings: Drawing[];
  selectedDrawing: string | null;
  onSelectDrawing: (id: string | null) => void;
  onPatchDrawing: (id: string, patch: Partial<Drawing>) => void;
  onDeleteDrawing: (id: string) => void;
  onClearDrawings: () => void;
  scopeLabel: string | null;
}

const btn = "h-8 short:h-7 min-w-8 items-center justify-center rounded-md border px-2 text-xs font-semibold";
const shown = "inline-flex";
const on = "border-sky-600 bg-sky-500/15 text-sky-800 dark:text-sky-200";
const off = "border-slate-400 hover:bg-slate-500/10";

const OVERLAY_LABELS: [keyof Overlays, string][] = [
  ["signals", "Tín hiệu MUA/BÁN"],
  ["plan", "Kế hoạch (Entry/SL/TP)"],
  ["paper", "Lệnh paper"],
  ["structure", "Hỗ trợ/kháng cự, PDH/PDL"],
  ["volume", "Tick volume"],
  ["sessions", "Phiên Tokyo / London / New York (nền màu)"],
  ["keyLevels", "Tuần trước cao/thấp, phiên cao/thấp"],
  ["news", "Tin tức sắp tới (đường dọc)"],
];

/** Compact, stable chart toolbar: icons with accessible names and tooltips (nothing shifts on hover). */
export function ChartToolbar(p: Props) {
  const [alertOpen, setAlertOpen] = useState(false);
  const [overlayOpen, setOverlayOpen] = useState(false);
  const [price, setPrice] = useState("");
  const [more, setMore] = useState(false); // phone only: the secondary tools
  const closeAlert = useCallback(() => setAlertOpen(false), []);
  const closeOverlay = useCallback(() => setOverlayOpen(false), []);
  useClosedByOtherPopover("alert", closeAlert);
  useClosedByOtherPopover("overlay", closeOverlay);
  const sec = `${more ? "inline-flex" : "hidden"} roomy:inline-flex`; // a phone shows only the timeframes, fullscreen and ⋯

  const submitAlert = () => {
    const v = parseDecimal(price);
    if (v > 0 && Number.isFinite(v)) {
      p.onAlert(v);
      setPrice("");
      setAlertOpen(false);
    }
  };

  return (
    <div data-testid="chart-toolbar" role="toolbar" aria-label="Công cụ biểu đồ" className="relative flex flex-wrap items-center gap-1">
      <div role="group" aria-label="Khung thời gian biểu đồ" className="flex gap-1">
        {TFS.map((t) => (
          <button key={t} type="button" data-testid={`chart-tf-${t}`} aria-pressed={t === p.tf} onClick={() => p.onTf(t)} className={`${shown} ${btn} ${t === p.tf ? on : off}`}>
            {t}
          </button>
        ))}
      </div>
      <span className="mx-1 hidden h-5 w-px bg-slate-400/50 sm:block" aria-hidden="true" />
      <button type="button" data-testid="chart-fit" title="Vừa khung (F)" aria-label="Vừa khung nhìn" onClick={p.onFit} className={`${btn} ${off} ${sec}`}>⤢</button>
      <button type="button" data-testid="chart-latest" title="Về nến mới nhất (L)" aria-label="Về nến mới nhất" onClick={p.onLatest} className={`${btn} ${off} ${sec}`}>⇥</button>
      <button type="button" data-testid="chart-follow" title="Tự theo nến mới (W)" aria-pressed={p.follow} onClick={() => p.onFollow(!p.follow)} className={`${btn} ${p.follow ? on : off} ${sec}`}>
        ⟳<span className="hidden sm:inline">&nbsp;Theo nến</span>&nbsp;{p.follow ? "BẬT" : "TẮT"}
      </button>
      <button type="button" data-testid="chart-fullscreen" title="Toàn màn hình (X)" aria-pressed={p.fullscreen} aria-label={p.fullscreen ? "Thoát toàn màn hình" : "Toàn màn hình"} onClick={() => p.onFullscreen(!p.fullscreen)} className={`${shown} ${btn} ${p.fullscreen ? on : off}`}>
        {p.fullscreen ? "⤡" : "⛶"}
      </button>
      <span className="mx-1 hidden h-5 w-px bg-slate-400/50 sm:block" aria-hidden="true" />
      <button type="button" data-testid="tool-measure" title="Đo giá/thời gian (M)" aria-pressed={p.tool === "measure"} onClick={() => p.onTool(p.tool === "measure" ? "none" : "measure")} aria-label="Đo giá và thời gian" className={`${btn} ${p.tool === "measure" ? on : off} ${sec}`}>📏&nbsp;Đo</button>
      <button type="button" data-testid="tool-line" title="Vẽ đường ngang (T)" aria-pressed={p.tool === "line"} onClick={() => p.onTool(p.tool === "line" ? "none" : "line")} aria-label="Vẽ đường ngang" className={`${btn} ${p.tool === "line" ? on : off} ${sec}`}>—&nbsp;Đường</button>
      <DrawingMenu tool={p.tool} onTool={p.onTool} drawings={p.drawings} selectedId={p.selectedDrawing} onSelect={p.onSelectDrawing} onPatch={p.onPatchDrawing} onDelete={p.onDeleteDrawing} onClear={p.onClearDrawings} levels={p.levels} onRemoveLevel={p.onRemoveLevel} scopeLabel={p.scopeLabel} btn={btn} on={on} off={off} roomy={`${more ? "block" : "hidden"} roomy:block`} />
      <div className={`relative ${more ? "block" : "hidden"} roomy:block`}>
        <button type="button" data-testid="tool-alert" title="Cảnh báo giá" aria-expanded={alertOpen} onClick={() => { if (!alertOpen) announcePopover("alert"); setAlertOpen(!alertOpen); setOverlayOpen(false); }} className={`${shown} ${btn} ${alertOpen ? on : off}`}>
          🔔&nbsp;Báo giá{p.alertCount > 0 ? ` (${p.alertCount})` : ""}
        </button>
        {alertOpen && (
          <div data-testid="alert-popover" role="dialog" aria-label="Thêm cảnh báo giá" className="absolute left-0 top-9 z-30 w-64 rounded-lg border border-slate-400 bg-white p-2 text-xs shadow-lg dark:bg-slate-900" onKeyDown={(e) => e.key === "Escape" && setAlertOpen(false)}>
            <label className="flex flex-col gap-1">
              Báo khi bid chạm giá
              <input name="alert-price" data-testid="alert-price" autoFocus inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submitAlert()} placeholder={p.bid ? p.bid.toFixed(2) : "4050.00"} className="rounded border border-slate-400 bg-transparent px-1 py-1 font-mono text-sm text-inherit" />
            </label>
            <button type="button" data-testid="alert-add" onClick={submitAlert} className="mt-2 w-full rounded border border-sky-600 bg-sky-500/15 px-2 py-1 font-semibold">Thêm cảnh báo</button>
            {p.alerts.some((a) => !a.firedAt) && (
              <ul data-testid="alert-list" className="mt-2 space-y-0.5">
                {p.alerts.filter((a) => !a.firedAt).map((a) => (
                  <li key={a.id} className="flex items-center gap-2">
                    <span className="font-mono">{a.direction === "UP" ? "↑" : "↓"} {a.price.toFixed(2)}</span>
                    <button type="button" data-testid="alert-delete" aria-label={`Xóa cảnh báo ${a.price.toFixed(2)}`} onClick={() => p.onRemoveAlert(a.id)} className="ml-auto rounded px-1.5 hover:bg-slate-500/20">✕</button>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-1 text-[11px] text-slate-600 dark:text-slate-400">Chỉ hoạt động khi trang này đang mở. Không giao dịch gì cả.</p>
          </div>
        )}
      </div>
      <div className={`relative ${more ? "block" : "hidden"} roomy:block`}>
        <button type="button" data-testid="overlay-menu" title="Lớp phủ" aria-expanded={overlayOpen} aria-haspopup="true" onClick={() => { if (!overlayOpen) announcePopover("overlay"); setOverlayOpen(!overlayOpen); setAlertOpen(false); }} aria-label="Lớp phủ trên biểu đồ" className={`${shown} ${btn} ${overlayOpen ? on : off}`}>☰&nbsp;Lớp phủ</button>
        {overlayOpen && (
          <div role="group" aria-label="Lớp phủ trên biểu đồ" className="absolute right-0 top-9 z-30 w-56 space-y-1 rounded-lg border border-slate-400 bg-white p-2 text-xs shadow-lg sm:left-0 sm:right-auto dark:bg-slate-900" onKeyDown={(e) => e.key === "Escape" && setOverlayOpen(false)}>
            {OVERLAY_LABELS.map(([key, label]) => (
              <label key={key} className="flex items-center gap-2">
                <input type="checkbox" name={`overlay-${key}`} data-testid={`toggle-${key}`} checked={p.overlays[key]} onChange={(e) => p.onOverlays({ ...p.overlays, [key]: e.target.checked })} />
                {label}
              </label>
            ))}
            <label className="flex items-center gap-2">
              <input type="checkbox" name="toggle-history" data-testid="toggle-history" checked={p.history} onChange={(e) => p.onHistory(e.target.checked)} />
              Lịch sử lệnh paper
            </label>
          </div>
        )}
      </div>
      <button type="button" data-testid="shortcut-help" title="Phím tắt (?)" aria-label="Xem phím tắt" onClick={() => { announcePopover("help"); p.onHelp(); }} className={`${btn} ${off} ${sec}`}>⌨</button>
      <button type="button" data-testid="toolbar-more" aria-expanded={more} aria-label={more ? "Ẩn công cụ" : "Thêm công cụ"} onClick={() => setMore(!more)} className={`${shown} ${btn} ${more ? on : off} roomy:hidden`}>⋯</button>
    </div>
  );
}
