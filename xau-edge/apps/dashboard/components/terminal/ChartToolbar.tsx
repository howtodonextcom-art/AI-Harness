"use client";

import { useState } from "react";
import { parseDecimal } from "@/lib/chartMath";
import type { Overlays } from "@/lib/prefs";
import type { Tool } from "@/components/terminal/TerminalChart";

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
  onHelp: () => void;
}

const btn = "inline-flex h-8 min-w-8 items-center justify-center rounded-md border px-2 text-xs font-semibold";
const on = "border-sky-600 bg-sky-500/15 text-sky-800 dark:text-sky-200";
const off = "border-slate-400 hover:bg-slate-500/10";

const OVERLAY_LABELS: [keyof Overlays, string][] = [
  ["signals", "Tín hiệu MUA/BÁN"],
  ["plan", "Kế hoạch (Entry/SL/TP)"],
  ["paper", "Lệnh paper"],
  ["structure", "Hỗ trợ/kháng cự, PDH/PDL"],
  ["volume", "Tick volume"],
  ["sessions", "Phiên Á/Âu/Mỹ (nền màu)"],
];

/** Compact, stable chart toolbar: icons with accessible names and tooltips (nothing shifts on hover). */
export function ChartToolbar(p: Props) {
  const [alertOpen, setAlertOpen] = useState(false);
  const [overlayOpen, setOverlayOpen] = useState(false);
  const [price, setPrice] = useState("");

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
          <button key={t} type="button" data-testid={`chart-tf-${t}`} aria-pressed={t === p.tf} onClick={() => p.onTf(t)} className={`${btn} ${t === p.tf ? on : off}`}>
            {t}
          </button>
        ))}
      </div>
      <span className="mx-1 hidden h-5 w-px bg-slate-400/50 sm:block" aria-hidden="true" />
      <button type="button" data-testid="chart-fit" title="Vừa khung (F)" aria-label="Vừa khung nhìn" onClick={p.onFit} className={`${btn} ${off}`}>⤢</button>
      <button type="button" data-testid="chart-latest" title="Về nến mới nhất (L)" aria-label="Về nến mới nhất" onClick={p.onLatest} className={`${btn} ${off}`}>⇥</button>
      <button type="button" data-testid="chart-follow" title="Tự theo nến mới (W)" aria-pressed={p.follow} onClick={() => p.onFollow(!p.follow)} className={`${btn} ${p.follow ? on : off}`}>
        ⟳<span className="hidden sm:inline">&nbsp;Theo nến</span>&nbsp;{p.follow ? "BẬT" : "TẮT"}
      </button>
      <button type="button" data-testid="chart-fullscreen" title="Toàn màn hình (X)" aria-pressed={p.fullscreen} aria-label={p.fullscreen ? "Thoát toàn màn hình" : "Toàn màn hình"} onClick={() => p.onFullscreen(!p.fullscreen)} className={`${btn} ${p.fullscreen ? on : off}`}>
        {p.fullscreen ? "⤡" : "⛶"}
      </button>
      <span className="mx-1 hidden h-5 w-px bg-slate-400/50 sm:block" aria-hidden="true" />
      <button type="button" data-testid="tool-measure" title="Đo giá/thời gian (M)" aria-pressed={p.tool === "measure"} onClick={() => p.onTool(p.tool === "measure" ? "none" : "measure")} aria-label="Đo giá và thời gian" className={`${btn} ${p.tool === "measure" ? on : off}`}>📏<span className="hidden sm:inline">&nbsp;Đo</span></button>
      <button type="button" data-testid="tool-line" title="Vẽ đường ngang (T)" aria-pressed={p.tool === "line"} onClick={() => p.onTool(p.tool === "line" ? "none" : "line")} aria-label="Vẽ đường ngang" className={`${btn} ${p.tool === "line" ? on : off}`}>—<span className="hidden sm:inline">&nbsp;Đường ngang</span></button>
      <div className="relative">
        <button type="button" data-testid="tool-alert" title="Cảnh báo giá" aria-expanded={alertOpen} onClick={() => { setAlertOpen(!alertOpen); setOverlayOpen(false); }} className={`${btn} ${alertOpen ? on : off}`}>
          🔔<span className="hidden sm:inline">&nbsp;Cảnh báo giá</span>{p.alertCount > 0 ? ` (${p.alertCount})` : ""}
        </button>
        {alertOpen && (
          <div data-testid="alert-popover" role="dialog" aria-label="Thêm cảnh báo giá" className="absolute left-0 top-9 z-30 w-64 rounded-lg border border-slate-400 bg-white p-2 text-xs shadow-lg dark:bg-slate-900" onKeyDown={(e) => e.key === "Escape" && setAlertOpen(false)}>
            <label className="flex flex-col gap-1">
              Báo khi bid chạm giá
              <input data-testid="alert-price" autoFocus inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submitAlert()} placeholder={p.bid ? p.bid.toFixed(2) : "4050.00"} className="rounded border border-slate-400 bg-transparent px-1 py-1 font-mono text-sm text-inherit" />
            </label>
            <button type="button" data-testid="alert-add" onClick={submitAlert} className="mt-2 w-full rounded border border-sky-600 bg-sky-500/15 px-2 py-1 font-semibold">Thêm cảnh báo</button>
            <p className="mt-1 text-[11px] text-slate-600 dark:text-slate-400">Chỉ hoạt động khi trang này đang mở. Không giao dịch gì cả.</p>
          </div>
        )}
      </div>
      <div className="relative">
        <button type="button" data-testid="overlay-menu" title="Lớp phủ" aria-expanded={overlayOpen} aria-haspopup="true" onClick={() => { setOverlayOpen(!overlayOpen); setAlertOpen(false); }} aria-label="Lớp phủ trên biểu đồ" className={`${btn} ${overlayOpen ? on : off}`}>☰<span className="hidden sm:inline">&nbsp;Lớp phủ</span></button>
        {overlayOpen && (
          <div role="group" aria-label="Lớp phủ trên biểu đồ" className="absolute right-0 top-9 z-30 w-56 space-y-1 rounded-lg border border-slate-400 bg-white p-2 text-xs shadow-lg sm:left-0 sm:right-auto dark:bg-slate-900" onKeyDown={(e) => e.key === "Escape" && setOverlayOpen(false)}>
            {OVERLAY_LABELS.map(([key, label]) => (
              <label key={key} className="flex items-center gap-2">
                <input type="checkbox" data-testid={`toggle-${key}`} checked={p.overlays[key]} onChange={(e) => p.onOverlays({ ...p.overlays, [key]: e.target.checked })} />
                {label}
              </label>
            ))}
            <label className="flex items-center gap-2">
              <input type="checkbox" data-testid="toggle-history" checked={p.history} onChange={(e) => p.onHistory(e.target.checked)} />
              Lịch sử lệnh paper
            </label>
          </div>
        )}
      </div>
      <button type="button" data-testid="shortcut-help" title="Phím tắt (?)" aria-label="Xem phím tắt" onClick={p.onHelp} className={`${btn} ${off}`}>⌨</button>
    </div>
  );
}
