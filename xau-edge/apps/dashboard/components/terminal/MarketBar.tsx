"use client";

import { Term } from "@/components/terminal/Term";
import { useEffect, useRef, useState } from "react";
import { countdownText } from "@/lib/chartMath";
import { ZONE_LABEL, clockInZone, formatInZone, type DisplayZone } from "@/lib/time";
import type { TradeView } from "@/lib/trade";
import { ageText, fmt } from "@/components/trade/ui";

interface Props {
  view: TradeView | null;
  tf: string;
  zone: DisplayZone;
  onZone: (zone: DisplayZone) => void;
  /** Milliseconds on the SERVER clock (browser clock corrected by the served_at skew). */
  serverNowMs: number;
  /** The page has not heard from the API for too long. */
  uiStale: boolean;
}

const pill = "inline-flex items-center whitespace-nowrap rounded-md border px-2 py-0.5 text-xs font-semibold";
const MUTED = "text-slate-600 dark:text-slate-400";

/** Price is split so the integer part reads at a glance and the decimals stay quiet. */
function BigPrice({ value }: { value: number }) {
  const [whole, dec = "00"] = value.toFixed(2).split(".");
  return (
    <span className="font-mono tabular-nums leading-none">
      <span className="text-3xl font-black sm:text-5xl">{whole}</span>
      <span className="text-xl font-bold sm:text-3xl">.{dec}</span>
    </span>
  );
}

/** Top market bar: what XAUUSD is doing right now, before anything about the engine. */
export function MarketBar({ view, tf, zone, onZone, serverNowMs, uiStale }: Props) {
  const quote = view?.quote ?? null;
  const ctx = view?.market_context;
  const daily = ctx?.daily ?? null;
  const prev = useRef<number | null>(null);
  const [dir, setDir] = useState<"up" | "down" | "flat">("flat");
  const [more, setMore] = useState(false); // phone only: the day statistics and the zone selector

  useEffect(() => {
    if (!quote) return;
    const before = prev.current;
    if (before !== null && quote.bid !== before) setDir(quote.bid > before ? "up" : "down");
    prev.current = quote.bid;
  }, [quote]);

  const open = view?.market?.open ?? false;
  const status = view?.market?.status ?? "—";
  const closeIso = ctx?.bar_close?.[tf] ?? null;
  const countdown = countdownText(closeIso ? Date.parse(closeIso) : null, serverNowMs);
  const reopen = !open && ctx?.next_open ? Date.parse(ctx.next_open) : null;
  const reopenIn = countdownText(reopen, serverNowMs);
  // an old quote while the market is closed is normal (the last price); it is only an alarm while trading is open
  const stalePrice = uiStale || (open && Boolean(quote?.stale));
  const lastPrice = !open && Boolean(quote?.stale) && !uiStale;
  const live = view?.source_mode === "LIVE";
  const change = daily?.change ?? null;
  const changeTone = change === null ? "" : change >= 0 ? "text-emerald-700 dark:text-emerald-400" : "text-red-700 dark:text-red-400";
  const arrow = dir === "up" ? "▲" : dir === "down" ? "▼" : "";

  return (
    <section data-testid="market-bar" aria-label="Thanh thị trường XAUUSD" className="rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-700">
      <div className="grid gap-x-8 gap-y-1.5 lg:grid-cols-[auto_auto_1fr] lg:items-center">
        {/* price */}
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <h1 className="mr-1 text-lg font-black tracking-tight">XAUUSD</h1>
            <span data-testid="source-pill" className={`${pill} ${live ? "border-emerald-600 bg-emerald-500/15 text-emerald-800 dark:text-emerald-200" : "border-red-600 bg-red-500/15 text-red-800 dark:text-red-200"}`}>
              {view ? (live ? "LIVE" : "REPLAY · NOT LIVE") : "…"}
            </span>
            <span data-testid="market-pill" className={`${pill} ${open ? "border-emerald-600 bg-emerald-500/15 text-emerald-800 dark:text-emerald-200" : "border-slate-500 bg-slate-500/15 text-slate-700 dark:text-slate-300"}`}>
              {open ? `Thị trường MỞ${live ? "" : " (replay)"}` : status === "—" ? "…" : `Thị trường ${status === "CLOSED" ? "ĐÓNG" : status}`}
            </span>
            <span data-testid="paper-only" className={`${pill} border-amber-600 bg-amber-500/15 text-amber-800 dark:text-amber-200`}><span className="sm:hidden">PAPER</span><span className="hidden sm:inline">PAPER · không gửi lệnh thật</span></span>
          </div>
          <div className="mt-1 flex flex-wrap items-end gap-x-5 gap-y-1" data-testid="quote">
            <div className={stalePrice ? "grayscale" : ""} aria-label="Giá bid">
              <div className={`hidden text-xs font-semibold uppercase sm:block ${MUTED}`}><Term id="bid">Bid (giá bán ra)</Term></div>
              <div className="flex items-baseline gap-1.5">
                {quote ? <BigPrice value={quote.bid} /> : <span className="text-4xl font-black">—</span>}
                <span data-testid="price-dir" aria-hidden="true" className={dir === "up" ? "text-emerald-700 dark:text-emerald-400" : "text-red-700 dark:text-red-400"}>{arrow}</span>
              </div>
              <span data-testid="price-bid" className="sr-only">{quote ? fmt(quote.bid) : "—"}</span>
            </div>
            <div className={`font-mono text-sm ${stalePrice ? "grayscale" : ""}`}>
              <div><Term id="ask">Ask</Term> <b data-testid="price-ask" className="text-base">{quote ? fmt(quote.ask) : "—"}</b></div>
              <div data-testid="spread" className={MUTED}><Term id="spread">Spread</Term> {quote ? `${fmt(quote.spread_points, 0)} điểm (${fmt(quote.spread_points / 100)})` : "—"}</div>
            </div>
            {lastPrice && quote && (
              <span data-testid="price-last-close" className={`${pill} border-slate-500 bg-slate-500/15 text-slate-700 dark:text-slate-300`}>
                Giá đóng cửa gần nhất · {ageText(quote.age_seconds)} trước
              </span>
            )}
            {stalePrice && (
              <span data-testid="price-stale" role="status" className={`${pill} border-red-600 bg-red-500/15 text-red-800 dark:text-red-200`}>
                GIÁ CŨ{quote ? ` · ${ageText(quote.age_seconds)}` : ""}
              </span>
            )}
          </div>
        </div>

        {/* the day */}
        <dl data-testid="day-stats" aria-label="Thống kê trong ngày" className={`${more ? "flex" : "hidden"} flex-wrap gap-x-4 gap-y-0.5 text-sm sm:flex lg:grid lg:grid-cols-[auto_auto] lg:gap-x-4`}>
          <div className="flex gap-1.5 lg:contents">
            <dt className={MUTED}>{daily && !daily.is_current_day ? "Phiên gần nhất" : "Hôm nay"}</dt>
            <dd data-testid="day-change" className={`font-mono font-semibold tabular-nums ${changeTone}`}>
              {daily ? `${daily.change >= 0 ? "+" : ""}${fmt(daily.change)} (${daily.change_pct === null ? "—" : `${daily.change_pct >= 0 ? "+" : ""}${daily.change_pct.toFixed(2)}%`})` : "—"}
            </dd>
          </div>
          <div className="flex gap-1.5 lg:contents">
            <dt className={MUTED}>Cao / Thấp</dt>
            <dd className="font-mono tabular-nums"><span data-testid="day-high">{fmt(daily?.high)}</span> / <span data-testid="day-low">{fmt(daily?.low)}</span></dd>
          </div>
          <div className="hidden gap-1.5 sm:flex lg:contents">
            <dt className={MUTED}>Biên ngày</dt>
            <dd className="flex items-center gap-2 font-mono tabular-nums">
              <span data-testid="day-range">{fmt(daily?.range)}</span>
              {daily?.range_position !== null && daily?.range_position !== undefined && (
                <span aria-hidden="true" className="relative hidden h-1.5 w-20 rounded bg-slate-300 sm:inline-block dark:bg-slate-700">
                  <span className="absolute top-[-2px] h-2.5 w-1 rounded bg-sky-600" style={{ left: `${Math.min(100, Math.max(0, daily.range_position * 100))}%` }} />
                </span>
              )}
            </dd>
          </div>
        </dl>

        {/* the clock */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-sm lg:ml-auto lg:flex-col lg:items-end">
          <div className="flex flex-wrap items-center gap-x-3">
            <span data-testid="session" className="font-semibold">{open ? (ctx?.session.label ?? "—") : "Ngoài giờ giao dịch"}</span>
            <span data-testid="vn-clock" className="font-mono tabular-nums" title={ZONE_LABEL[zone]}>
              {serverNowMs > 0 ? clockInZone(serverNowMs, zone) : "--:--:--"}
              {!live && view ? <span className="ml-1 text-xs font-normal text-red-700 dark:text-red-300">(giờ replay)</span> : null}
            </span>
            <select aria-label="Múi giờ hiển thị" value={zone} onChange={(e) => onZone(e.target.value as DisplayZone)} className={`${more ? "block" : "hidden"} max-w-44 rounded border border-slate-400 bg-transparent px-1 py-0.5 text-xs sm:block`}>
              {(Object.keys(ZONE_LABEL) as DisplayZone[]).map((z) => (
                <option key={z} value={z}>{ZONE_LABEL[z]}</option>
              ))}
            </select>
          </div>
          <div data-testid="countdown" className={`font-mono text-xs ${MUTED}`}>
            {countdown ? <>Nến {tf} đóng sau <b className="text-sm text-inherit">{countdown}</b></> : <span>{open ? `Nến ${tf}: chờ dữ liệu` : reopen !== null ? <>Mở lại lúc <b className="text-sm text-inherit">{formatInZone(ctx?.next_open ?? null, zone).slice(5, 16)}</b> · còn <b className="text-sm text-inherit">{reopenIn}</b></> : `Nến ${tf}: thị trường đóng`}</span>}
          </div>
          <span data-testid="data-age" className={`hidden text-xs sm:inline ${MUTED}`}>dữ liệu: {ageText(view?.data_age_seconds)}</span>
          <button type="button" data-testid="market-more" aria-expanded={more} onClick={() => setMore(!more)} className="text-xs font-semibold underline sm:hidden">{more ? "Ẩn chi tiết thị trường ▴" : "Chi tiết thị trường ▾"}</button>
        </div>
      </div>
    </section>
  );
}
