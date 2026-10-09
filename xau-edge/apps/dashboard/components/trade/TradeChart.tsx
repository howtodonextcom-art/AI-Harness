"use client";

import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineStyle,
  createChart,
  createSeriesMarkers,
  type AutoscaleInfo,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";
import type { MarketBar } from "@/lib/market";
import { shiftedSeconds, type DisplayZone } from "@/lib/time";
import type { MarkersResponse, PaperTrade, TradeView } from "@/lib/trade";

export interface Overlays {
  signals: boolean;
  plan: boolean;
  paper: boolean;
  structure: boolean;
  volume: boolean;
}

interface Props {
  bars: MarketBar[];
  timeframe: string;
  zone: DisplayZone;
  overlays: Overlays;
  view: TradeView | null;
  markers: MarkersResponse | null;
  history: boolean;
  /** False when the decision must not be drawn as a live plan (stale data, expired, WAIT). */
  planLive: boolean;
}

const GREEN = "#16a34a";
const RED = "#dc2626";
const BLUE = "#2563eb";
const GREY = "#64748b";
const AMBER = "#d97706";

function barIndexAt(times: number[], seconds: number): number {
  let lo = 0;
  let hi = times.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (times[mid] <= seconds) {
      found = mid;
      lo = mid + 1;
    } else hi = mid - 1;
  }
  return found;
}

const fmt = (v: number | null | undefined, d = 2) => (v === null || v === undefined ? "—" : v.toFixed(d));

/**
 * Candles + tick volume with overlays that come ONLY from server objects: the current decision's
 * entry/SL/TP, the paper position, logged decisions (BUY/SELL markers) and closed paper trades
 * (EXIT markers). Nothing is inferred in the browser.
 */
export function TradeChart({ bars, timeframe, zone, overlays, view, markers, history, planLive }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const handles = useRef<{
    chart: IChartApi;
    candles: ISeriesApi<"Candlestick">;
    volume: ISeriesApi<"Histogram">;
    plugin: ISeriesMarkersPluginApi<Time>;
    lines: IPriceLine[];
  } | null>(null);
  const fitted = useRef<string | null>(null);
  const [hover, setHover] = useState<string[]>([]);

  const times = useMemo(() => bars.map((b) => shiftedSeconds(b.time, zone)), [bars, zone]);

  // marker texts by bar time (for the hover tooltip) and the markers themselves
  const { chartMarkers, notes, markerList } = useMemo(() => {
    const list: SeriesMarker<Time>[] = [];
    const byTime = new Map<number, string[]>();
    const items: { key: string; kind: string; barTime: string; note: string }[] = [];
    const add = (iso: string | null, kind: string, build: (time: number) => SeriesMarker<Time>, note: string) => {
      if (!iso || times.length === 0) return;
      const seconds = shiftedSeconds(iso, zone);
      const idx = barIndexAt(times, seconds);
      if (idx < 0 || seconds > times[times.length - 1] + 7 * 86400) return;
      const time = times[idx];
      list.push(build(time));
      items.push({ key: `${kind}-${items.length}-${time}`, kind, barTime: new Date((time - (shiftedSeconds(iso, zone) - Date.parse(iso) / 1000)) * 1000).toISOString(), note });
      byTime.set(time, [...(byTime.get(time) ?? []), note]);
    };
    if (markers && overlays.signals) {
      for (const s of markers.signals) {
        add(
          s.bar_time,
          s.side === "BUY" ? "BUY" : "SELL",
          (time) => ({
            time: time as UTCTimestamp,
            position: s.side === "BUY" ? "belowBar" : "aboveBar",
            shape: s.side === "BUY" ? "arrowUp" : "arrowDown",
            color: s.side === "BUY" ? GREEN : RED,
            text: s.side,
          }),
          `${s.side} signal @ ${fmt(s.entry)} · SL ${fmt(s.sl)} · TP ${fmt(s.tp1)} · RR ${fmt(s.rr)}${s.taken ? " · taken (paper)" : ""} · v${s.strategy_version}`,
        );
      }
    }
    if (markers && overlays.paper) {
      const trades = history ? markers.paper_trades : markers.paper_trades.filter((t) => t.status === "OPEN").concat(markers.paper_trades.filter((t) => t.status === "CLOSED").slice(-1));
      for (const t of trades) {
        add(
          t.entry_time,
          "PAPER_ENTRY",
          (time) => ({
            time: time as UTCTimestamp,
            position: t.side === "BUY" ? "belowBar" : "aboveBar",
            shape: "circle",
            color: BLUE,
            text: `PAPER ${t.side}`,
          }),
          `PAPER ${t.side} opened @ ${fmt(t.entry_price)}`,
        );
        if (t.status === "CLOSED") {
          add(
            t.exit_time,
            "EXIT",
            (time) => ({
              time: time as UTCTimestamp,
              position: t.side === "BUY" ? "aboveBar" : "belowBar",
              shape: "square",
              color: (t.net_pnl ?? 0) >= 0 ? GREEN : RED,
              text: `EXIT ${t.exit_reason ?? ""}`,
            }),
            `EXIT ${t.exit_reason} @ ${fmt(t.exit_price)} · P&L ${fmt(t.net_pnl)} · ${fmt(t.r_multiple)}R · ${fmt(t.duration_minutes, 0)} min`,
          );
        }
      }
    }
    list.sort((a, b) => (a.time as number) - (b.time as number));
    return { chartMarkers: list, notes: byTime, markerList: items };
  }, [markers, overlays.signals, overlays.paper, history, times, zone]);

  const extraPrices = useRef<number[]>([]);
  const notesRef = useRef(notes);
  useEffect(() => {
    notesRef.current = notes;
  }, [notes]);

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const chart = createChart(element, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: dark ? "#cbd5e1" : "#334155",
        panes: { separatorColor: dark ? "#334155" : "#cbd5e1" },
      },
      grid: {
        vertLines: { color: dark ? "#1e293b" : "#e2e8f0" },
        horzLines: { color: dark ? "#1e293b" : "#e2e8f0" },
      },
      timeScale: { timeVisible: true, secondsVisible: false },
    });
    const candles = chart.addSeries(CandlestickSeries, {
      // plan / position lines must stay visible: widen the auto-scaled range to contain them
      autoscaleInfoProvider: (original: () => AutoscaleInfo | null) => {
        const base = original();
        const extra = extraPrices.current;
        if (!base || !base.priceRange || extra.length === 0) return base;
        return {
          ...base,
          priceRange: {
            minValue: Math.min(base.priceRange.minValue, ...extra),
            maxValue: Math.max(base.priceRange.maxValue, ...extra),
          },
        };
      },
      upColor: GREEN,
      downColor: RED,
      wickUpColor: GREEN,
      wickDownColor: RED,
      borderVisible: false,
    });
    const volume = chart.addSeries(
      HistogramSeries,
      { priceFormat: { type: "volume" }, priceLineVisible: false, title: "Tick volume" },
      1,
    );
    chart.panes()[1]?.setHeight(90);
    const plugin = createSeriesMarkers(candles, []);
    handles.current = { chart, candles, volume, plugin, lines: [] };
    fitted.current = null;
    chart.subscribeCrosshairMove((param) => {
      const t = typeof param.time === "number" ? param.time : null;
      setHover(t === null ? [] : (notesRef.current.get(t) ?? []));
    });
    return () => {
      chart.remove();
      handles.current = null;
    };
  }, [timeframe]);

  useEffect(() => {
    const h = handles.current;
    if (!h) return;
    h.candles.setData(
      bars.map((b, i) => {
        const base = b.close >= b.open ? GREEN : RED;
        const time = times[i] as UTCTimestamp;
        return b.is_closed
          ? { time, open: b.open, high: b.high, low: b.low, close: b.close }
          : { time, open: b.open, high: b.high, low: b.low, close: b.close, color: `${base}55`, borderColor: base, wickColor: base };
      }),
    );
    h.volume.setData(
      bars.map((b, i) => ({
        time: times[i] as UTCTimestamp,
        value: b.tick_volume,
        color: b.is_closed ? (b.close >= b.open ? `${GREEN}99` : `${RED}99`) : `${GREY}66`,
      })),
    );
    if (fitted.current !== timeframe && bars.length > 0) {
      h.chart.timeScale().fitContent();
      fitted.current = timeframe;
    }
  }, [bars, times, timeframe]);

  useEffect(() => {
    handles.current?.plugin.setMarkers(chartMarkers);
  }, [chartMarkers, bars]);

  useEffect(() => {
    handles.current?.volume.applyOptions({ visible: overlays.volume });
  }, [overlays.volume, timeframe]);

  // price lines: plan, paper position, structure (all from the server view)
  const lineSpecs = useMemo(() => {
    const out: { title: string; price: number; color: string; style: LineStyle; width: 1 | 2 }[] = [];
    const add = (price: number | null | undefined, title: string, color: string, style: LineStyle = LineStyle.Dashed, width: 1 | 2 = 1) => {
      if (price === null || price === undefined || !Number.isFinite(price)) return;
      out.push({ title, price, color, style, width });
    };
    const decision = view?.decision;
    if (overlays.plan && planLive && decision && decision.decision !== "WAIT") {
      add(decision.entry_price, "ENTRY", BLUE, LineStyle.Solid, 2);
      add(decision.stop_loss, "SL", RED);
      add(decision.take_profit, "TP1", GREEN);
      add(decision.take_profit_2 ?? null, "TP2", GREEN, LineStyle.Dotted);
    }
    const position: PaperTrade | null | undefined = view?.desk?.position;
    if (overlays.paper && position && position.status === "OPEN") {
      add(position.fill_price, "PAPER ENTRY", BLUE, LineStyle.Solid, 2);
      add(position.sl, "PAPER SL", RED, LineStyle.Solid);
      add(position.tp, "PAPER TP", GREEN, LineStyle.Solid);
      add(position.current_price, "NOW", AMBER, LineStyle.Dotted);
    }
    if (overlays.structure && view?.structure) {
      const st = view.structure;
      add(st.nearest_resistance as number | null, "RES", GREY, LineStyle.Dotted);
      add(st.nearest_support as number | null, "SUP", GREY, LineStyle.Dotted);
      add(st.pdh as number | null, "PDH", "#7c3aed", LineStyle.SparseDotted);
      add(st.pdl as number | null, "PDL", "#7c3aed", LineStyle.SparseDotted);
    }
    return out;
  }, [view, overlays.plan, overlays.paper, overlays.structure, planLive]);

  useEffect(() => {
    const h = handles.current;
    if (!h) return;
    for (const line of h.lines) h.candles.removePriceLine(line);
    extraPrices.current = lineSpecs.map((l) => l.price);
    h.candles.priceScale().applyOptions({ autoScale: true });
    h.lines = lineSpecs.map((l) =>
      h.candles.createPriceLine({ price: l.price, color: l.color, lineWidth: l.width, lineStyle: l.style, axisLabelVisible: true, title: `${l.title} ${l.price.toFixed(2)}` }),
    );
  }, [lineSpecs, timeframe]);

  return (
    <div className="relative min-w-0">
      <div
        ref={container}
        role="img"
        aria-label={`Biểu đồ nến ${timeframe} của XAUUSD với tín hiệu, kế hoạch lệnh và lệnh paper`}
        data-testid="trade-chart"
        className="h-[22rem] w-full sm:h-[26rem] lg:h-[32rem]"
      />
      <ul data-testid="chart-legend" className="mt-1 flex flex-wrap gap-x-3 text-xs">
        {lineSpecs.map((l) => (
          <li key={l.title} data-testid={`line-${l.title.replace(/ /g, "-")}`} style={{ color: l.color }}>
            {l.title} {l.price.toFixed(2)}
          </li>
        ))}
      </ul>
      <ul data-testid="chart-markers" className="sr-only">
        {markerList.map((m) => (
          <li key={m.key} data-kind={m.kind} data-bar-time={m.barTime}>
            {m.note}
          </li>
        ))}
      </ul>
      {hover.length > 0 && (
        <div data-testid="marker-tooltip" className="pointer-events-none absolute right-2 top-2 max-w-xs rounded-md border border-slate-400 bg-white/95 p-2 text-xs shadow dark:bg-slate-900/95">
          {hover.map((line) => (
            <div key={line}>{line}</div>
          ))}
        </div>
      )}
    </div>
  );
}
