"use client";

import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineStyle,
  createChart,
  createSeriesMarkers,
  type AutoscaleInfo,
  type IChartApi,
  type IPriceLine,
  type IPrimitivePaneRenderer,
  type IPrimitivePaneView,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type ISeriesPrimitive,
  type SeriesAttachedParameter,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import { TF_SECONDS, barIndexAt, signalBarIndex } from "@/lib/chartMath";
import type { MarketBar } from "@/lib/market";
import type { ManualLevel, Overlays, PriceAlert } from "@/lib/prefs";
import { SESSION_COLORS, SESSION_NAMES, sessionRuns } from "@/lib/sessions";
import { shiftedSeconds, formatInZone, type DisplayZone } from "@/lib/time";
import type { MarkersResponse, PaperMarker, SignalMarker, TradePlan, TradeView } from "@/lib/trade";
import { EXIT_REASON_VI, SIDE_VI } from "@/lib/vi";

export type Tool = "none" | "line" | "measure";

export interface ChartHandle {
  fit: () => void;
  latest: () => void;
}

export interface MarkerDetail {
  key: string;
  kind: "BUY" | "SELL" | "PAPER_ENTRY" | "EXIT";
  /** ISO time of the chart bar the marker is drawn on. */
  barTime: string;
  lines: string[];
  signal?: SignalMarker;
  trade?: PaperMarker;
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
  plan: TradePlan | null;
  focus: { from: string; to: string } | null;
  follow: boolean;
  onFollowChange: (follow: boolean) => void;
  levels: ManualLevel[];
  alerts: PriceAlert[];
  tool: Tool;
  onAddLevel: (price: number) => void;
  onToolDone: () => void;
}

const GREEN = "#16a34a";
const RED = "#dc2626";
const BLUE = "#2563eb";
const GREY = "#64748b";
const AMBER = "#d97706";
const PURPLE = "#7c3aed";

const fmt = (v: number | null | undefined, d = 2) => (v === null || v === undefined ? "—" : v.toFixed(d));

// ---- session bands drawn behind the candles (a series primitive) --------------------------------

interface BandRun {
  from: number;
  to: number;
  color: string;
}

interface BitmapScope {
  context: CanvasRenderingContext2D;
  horizontalPixelRatio: number;
  verticalPixelRatio: number;
  bitmapSize: { width: number; height: number };
}
interface DrawTarget {
  useBitmapCoordinateSpace: (cb: (scope: BitmapScope) => void) => void;
}

class SessionPrimitive implements ISeriesPrimitive<Time> {
  runs: BandRun[] = [];
  chart: IChartApi | null = null;
  private request: (() => void) | null = null;

  attached(param: SeriesAttachedParameter<Time>) {
    this.chart = param.chart as IChartApi;
    this.request = param.requestUpdate;
  }
  detached() {
    this.chart = null;
    this.request = null;
  }
  setRuns(runs: BandRun[]) {
    this.runs = runs;
    this.request?.();
  }
  updateAllViews() {}
  paneViews(): readonly IPrimitivePaneView[] {
    return [{ zOrder: () => "bottom", renderer: () => new SessionRenderer(this) }];
  }
}

class SessionRenderer implements IPrimitivePaneRenderer {
  constructor(private readonly src: SessionPrimitive) {}
  draw(target: DrawTarget) {
    const { runs, chart } = this.src;
    if (!chart || runs.length === 0) return;
    target.useBitmapCoordinateSpace(({ context, horizontalPixelRatio: hr, bitmapSize }) => {
      for (const run of runs) {
        const x0 = chart.timeScale().timeToCoordinate(run.from as UTCTimestamp);
        const x1 = chart.timeScale().timeToCoordinate(run.to as UTCTimestamp);
        if (x0 === null || x1 === null) continue;
        context.fillStyle = run.color;
        context.fillRect(Math.max(0, x0 * hr), 0, Math.max(0, (x1 - x0) * hr), bitmapSize.height);
      }
    });
  }
}

interface Measure {
  a: { time: number; price: number } | null;
  b: { time: number; price: number } | null;
  fixed: boolean;
}

/**
 * Candles + tick volume. Every overlay comes from a server object (the decision's plan, the paper
 * position, logged signals, closed trades) or from the trader's own annotations (levels, alerts,
 * the ruler). Nothing here derives a signal.
 */
export const TerminalChart = forwardRef<ChartHandle, Props>(function TerminalChart(
  { bars, timeframe, zone, overlays, view, markers, history, planLive, plan, focus, follow, onFollowChange, levels, alerts, tool, onAddLevel, onToolDone },
  ref,
) {
  const container = useRef<HTMLDivElement>(null);
  const handles = useRef<{
    chart: IChartApi;
    candles: ISeriesApi<"Candlestick">;
    volume: ISeriesApi<"Histogram">;
    plugin: ISeriesMarkersPluginApi<Time>;
    bands: SessionPrimitive;
    lines: IPriceLine[];
  } | null>(null);
  const applied = useRef<{ first: number; count: number } | null>(null);
  const fitted = useRef<string | null>(null);
  const followRef = useRef(follow);
  const toolRef = useRef(tool);
  const interacting = useRef(false);
  const [readout, setReadout] = useState<number | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [atLatest, setAtLatest] = useState(true);
  const [measure, setMeasure] = useState<Measure>({ a: null, b: null, fixed: false });
  const [, setTick] = useState(0);

  useEffect(() => {
    followRef.current = follow;
    handles.current?.chart.timeScale().applyOptions({ shiftVisibleRangeOnNewBar: follow });
  }, [follow]);
  useEffect(() => {
    toolRef.current = tool;
    if (tool !== "measure") setMeasure({ a: null, b: null, fixed: false });
  }, [tool]);

  useImperativeHandle(ref, () => ({
    fit: () => handles.current?.chart.timeScale().fitContent(),
    latest: () => {
      handles.current?.chart.timeScale().scrollToRealTime();
      onFollowChange(true);
    },
  }));

  // lightweight-charts needs strictly increasing times: a DST fall-back in the display zone can
  // repeat an hour, so repeated times are dropped (never crash)
  const series = useMemo(() => {
    const out: { bar: MarketBar; time: number }[] = [];
    let last = -Infinity;
    for (const bar of bars) {
      const time = shiftedSeconds(bar.time, zone);
      if (time > last) {
        out.push({ bar, time });
        last = time;
      }
    }
    return out;
  }, [bars, zone]);
  const times = useMemo(() => series.map((s) => s.time), [series]);
  const tfSeconds = TF_SECONDS[timeframe] ?? 300;

  // ---- markers: placed from the signal's own timestamp (see signalBarIndex) --------------------
  const { chartMarkers, details } = useMemo(() => {
    const list: SeriesMarker<Time>[] = [];
    const out: MarkerDetail[] = [];
    const byTime = (iso: string | null | undefined, mode: "signal" | "containing") => {
      if (!iso || times.length === 0) return null;
      const seconds = shiftedSeconds(iso, zone);
      const idx = mode === "signal" ? signalBarIndex(times, seconds, tfSeconds) : barIndexAt(times, seconds);
      if (idx < 0 || seconds > times[times.length - 1] + 7 * 86400) return null;
      const time = times[idx];
      const offset = shiftedSeconds(iso, zone) - Date.parse(iso) / 1000;
      return { time, barIso: new Date((time - offset) * 1000).toISOString() };
    };
    if (markers && overlays.signals) {
      for (const s of markers.signals) {
        const at = byTime(s.at ?? s.bar_time, "signal");
        if (!at) continue;
        const buy = s.side === "BUY";
        list.push({ time: at.time as UTCTimestamp, position: buy ? "belowBar" : "aboveBar", shape: buy ? "arrowUp" : "arrowDown", color: buy ? GREEN : RED, text: SIDE_VI[s.side] });
        out.push({
          key: `sig-${s.setup_id}`,
          kind: s.side,
          barTime: at.barIso,
          signal: s,
          lines: [
            `${s.side} signal @ ${fmt(s.price ?? s.entry)} · SL ${fmt(s.sl)} · TP ${fmt(s.tp1)} · RR ${fmt(s.rr)}${s.taken ? " · taken (paper)" : ""} · v${s.strategy_version} · ${s.source_mode}`,
          ],
        });
      }
    }
    if (markers && overlays.paper) {
      const closed = markers.paper_trades.filter((t) => t.status === "CLOSED");
      const trades = history ? markers.paper_trades : markers.paper_trades.filter((t) => t.status === "OPEN").concat(closed.slice(-1));
      for (const t of trades) {
        const entry = byTime(t.entry_time, "containing");
        if (entry) {
          list.push({ time: entry.time as UTCTimestamp, position: t.side === "BUY" ? "belowBar" : "aboveBar", shape: "circle", color: BLUE, text: `PAPER ${SIDE_VI[t.side]}` });
          out.push({ key: `in-${t.trade_id}`, kind: "PAPER_ENTRY", barTime: entry.barIso, trade: t, lines: [`PAPER ${t.side} opened @ ${fmt(t.entry_price)}`] });
        }
        const exit = t.status === "CLOSED" ? byTime(t.exit_time, "containing") : null;
        if (exit) {
          list.push({ time: exit.time as UTCTimestamp, position: t.side === "BUY" ? "aboveBar" : "belowBar", shape: "square", color: (t.net_pnl ?? 0) >= 0 ? GREEN : RED, text: `THOÁT ${EXIT_REASON_VI[t.exit_reason ?? ""] ?? t.exit_reason ?? ""}` });
          out.push({
            key: `out-${t.trade_id}`,
            kind: "EXIT",
            barTime: exit.barIso,
            trade: t,
            lines: [`EXIT ${t.exit_reason} @ ${fmt(t.exit_price)} · P&L ${fmt(t.net_pnl)} · ${fmt(t.r_multiple)}R · ${fmt(t.duration_minutes, 0)} min${t.strategy_version ? ` · v${t.strategy_version}` : ""}`],
          });
        }
      }
    }
    list.sort((a, b) => (a.time as number) - (b.time as number));
    return { chartMarkers: list, details: out };
  }, [markers, overlays.signals, overlays.paper, history, times, zone, tfSeconds]);

  const detailsRef = useRef<{ time: number; detail: MarkerDetail }[]>([]);
  useEffect(() => {
    detailsRef.current = details.map((d) => ({ time: shiftedSeconds(d.barTime, zone), detail: d }));
  }, [details, zone]);

  const extraPrices = useRef<number[]>([]);

  // ---- create the chart (again only when the timeframe changes) --------------------------------
  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const scheme = window.matchMedia("(prefers-color-scheme: dark)");
    const palette = (dark: boolean) => ({
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: dark ? "#cbd5e1" : "#334155",
        panes: { separatorColor: dark ? "#334155" : "#cbd5e1" },
      },
      grid: { vertLines: { color: dark ? "#1e293b" : "#e2e8f0" }, horzLines: { color: dark ? "#1e293b" : "#e2e8f0" } },
    });
    const chart = createChart(element, {
      autoSize: true,
      ...palette(scheme.matches),
      crosshair: { mode: CrosshairMode.Normal },
      timeScale: { timeVisible: true, secondsVisible: false, shiftVisibleRangeOnNewBar: followRef.current, rightOffset: 10 },
    });
    const candles = chart.addSeries(CandlestickSeries, {
      autoscaleInfoProvider: (original: () => AutoscaleInfo | null) => {
        const base = original();
        const extra = extraPrices.current;
        if (!base || !base.priceRange || extra.length === 0) return base;
        return { ...base, priceRange: { minValue: Math.min(base.priceRange.minValue, ...extra), maxValue: Math.max(base.priceRange.maxValue, ...extra) } };
      },
      upColor: GREEN,
      downColor: RED,
      wickUpColor: GREEN,
      wickDownColor: RED,
      borderVisible: false,
      priceLineVisible: true,
      priceLineStyle: LineStyle.Dotted,
      priceLineWidth: 1,
      lastValueVisible: true,
    });
    const volume = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceLineVisible: false, lastValueVisible: false }, 1);
    chart.panes()[1]?.setHeight(80);
    const plugin = createSeriesMarkers(candles, []);
    const bands = new SessionPrimitive();
    candles.attachPrimitive(bands);
    handles.current = { chart, candles, volume, plugin, bands, lines: [] };
    fitted.current = null;
    applied.current = null;

    chart.subscribeCrosshairMove((param) => {
      setReadout(typeof param.time === "number" ? param.time : null);
      if (toolRef.current === "measure" && param.point && typeof param.time === "number") {
        const price = candles.coordinateToPrice(param.point.y);
        if (price !== null) setMeasure((m) => (m.a && !m.fixed ? { ...m, b: { time: param.time as number, price } } : m));
      }
    });
    chart.subscribeClick((param) => {
      const time = typeof param.time === "number" ? param.time : null;
      if (toolRef.current === "line" && param.point) {
        const price = candles.coordinateToPrice(param.point.y);
        if (price !== null) {
          onAddLevelRef.current(Math.round(price * 100) / 100);
          onToolDoneRef.current();
        }
        return;
      }
      if (toolRef.current === "measure" && param.point && time !== null) {
        const price = candles.coordinateToPrice(param.point.y);
        if (price === null) return;
        setMeasure((m) => (!m.a || m.fixed ? { a: { time, price }, b: null, fixed: false } : { ...m, b: { time, price }, fixed: true }));
        return;
      }
      if (time === null) {
        setSelected(null);
        return;
      }
      // a click on a bar that carries markers opens their details (hover alone is not enough)
      const hit = detailsRef.current.find((d) => d.time === time);
      setSelected(hit ? hit.detail.key : null);
    });
    const onRange = () => {
      const pos = chart.timeScale().scrollPosition();
      const latest = pos > -1.5;
      setAtLatest(latest);
      // only the trader's own scroll/zoom turns follow off (never a programmatic fit or jump), and the chart never snaps back
      if (!latest && followRef.current && interacting.current) onFollowChangeRef.current(false);
      setTick((n) => n + 1);
    };
    chart.timeScale().subscribeVisibleLogicalRangeChange(onRange);
    let quiet: ReturnType<typeof setTimeout> | undefined;
    const touch = (ms: number) => {
      interacting.current = true;
      clearTimeout(quiet);
      quiet = setTimeout(() => {
        interacting.current = false;
      }, ms);
    };
    const onDown = () => touch(2500); // covers the kinetic scroll after a drag
    const onWheel = () => touch(1200);
    element.addEventListener("pointerdown", onDown);
    element.addEventListener("pointermove", (e) => e.buttons > 0 && touch(2500));
    element.addEventListener("wheel", onWheel, { passive: true });
    const onScheme = (e: MediaQueryListEvent) => chart.applyOptions(palette(e.matches));
    scheme.addEventListener("change", onScheme);
    return () => {
      scheme.removeEventListener("change", onScheme);
      clearTimeout(quiet);
      element.removeEventListener("pointerdown", onDown);
      element.removeEventListener("wheel", onWheel);
      chart.remove();
      handles.current = null;
    };
  }, [timeframe]);

  // the handlers above are created once per chart; they always call the latest props
  const onAddLevelRef = useRef(onAddLevel);
  const onToolDoneRef = useRef(onToolDone);
  const onFollowChangeRef = useRef(onFollowChange);
  useEffect(() => {
    onAddLevelRef.current = onAddLevel;
    onToolDoneRef.current = onToolDone;
    onFollowChangeRef.current = onFollowChange;
  }, [onAddLevel, onToolDone, onFollowChange]);

  // ---- data: incremental updates keep the trader's zoom and scroll position --------------------
  useEffect(() => {
    const h = handles.current;
    if (!h || series.length === 0) return;
    const candlePoint = ({ bar: b, time: t }: { bar: MarketBar; time: number }) => {
      const base = b.close >= b.open ? GREEN : RED;
      const time = t as UTCTimestamp;
      return b.is_closed
        ? { time, open: b.open, high: b.high, low: b.low, close: b.close }
        : { time, open: b.open, high: b.high, low: b.low, close: b.close, color: `${base}55`, borderColor: base, wickColor: base };
    };
    const volumePoint = ({ bar: b, time: t }: { bar: MarketBar; time: number }) => ({
      time: t as UTCTimestamp,
      value: b.tick_volume,
      color: b.is_closed ? (b.close >= b.open ? `${GREEN}99` : `${RED}99`) : `${GREY}66`,
    });
    const prev = applied.current;
    const first = series[0].time;
    if (prev && prev.first === first && series.length >= prev.count) {
      for (let i = prev.count - 1; i < series.length; i++) {
        h.candles.update(candlePoint(series[i]));
        h.volume.update(volumePoint(series[i]));
      }
    } else {
      h.candles.setData(series.map(candlePoint));
      h.volume.setData(series.map(volumePoint));
    }
    applied.current = { first, count: series.length };
    const last = series[series.length - 1].bar;
    h.candles.applyOptions({ priceLineColor: last.close >= last.open ? GREEN : RED });
    if (fitted.current !== timeframe) {
      h.chart.timeScale().fitContent();
      h.chart.timeScale().scrollToRealTime();
      fitted.current = timeframe;
    }
  }, [series, timeframe]);

  useEffect(() => {
    handles.current?.plugin.setMarkers(chartMarkers);
  }, [chartMarkers]);

  useEffect(() => {
    handles.current?.volume.applyOptions({ visible: overlays.volume });
  }, [overlays.volume, timeframe]);

  // ---- price lines: plan, position, structure, the trader's levels and alerts ------------------
  const lineSpecs = useMemo(() => {
    const out: { id: string; title: string; price: number; color: string; style: LineStyle; width: 1 | 2 }[] = [];
    const add = (price: number | null | undefined, title: string, color: string, style: LineStyle = LineStyle.Dashed, width: 1 | 2 = 1, id = title) => {
      if (price === null || price === undefined || !Number.isFinite(price)) return;
      out.push({ id, title, price, color, style, width });
    };
    if (overlays.plan && planLive && plan && plan.complete) {
      add(plan.planned_entry, "ENTRY", BLUE, LineStyle.Solid, 2); // solid
      add(plan.sl, "SL", RED, LineStyle.Dashed, 2); // dashed
      add(plan.tp1, "TP1", GREEN, LineStyle.Dotted, 2); // dotted
      add(plan.tp2, "TP2", GREEN, LineStyle.SparseDotted, 1);
    }
    const position = view?.desk?.position;
    if (overlays.paper && position && position.status === "OPEN") {
      add(position.fill_price, "PAPER ENTRY", BLUE, LineStyle.Solid, 2);
      add(position.sl, "PAPER SL", RED, LineStyle.Dashed);
      add(position.tp, "PAPER TP", GREEN, LineStyle.Dotted);
      add(position.current_price, "NOW", AMBER, LineStyle.Dotted);
    }
    if (overlays.structure && view?.structure) {
      const st = view.structure;
      add(st.nearest_resistance as number | null, "M15 RES", GREY, LineStyle.Dotted);
      add(st.nearest_support as number | null, "M15 SUP", GREY, LineStyle.Dotted);
      add(st.pdh as number | null, "PDH", PURPLE, LineStyle.SparseDotted);
      add(st.pdl as number | null, "PDL", PURPLE, LineStyle.SparseDotted);
    }
    for (const l of levels) add(l.price, l.label || "ĐƯỜNG", "#0891b2", LineStyle.LargeDashed, 1, `level-${l.id}`);
    for (const a of alerts) if (a.firedAt === null) add(a.price, `CẢNH BÁO ${a.direction === "UP" ? "↑" : "↓"}`, AMBER, LineStyle.LargeDashed, 1, `alert-${a.id}`);
    return out;
  }, [view, plan, overlays.plan, overlays.paper, overlays.structure, planLive, levels, alerts]);

  useEffect(() => {
    const h = handles.current;
    if (!h) return;
    for (const line of h.lines) h.candles.removePriceLine(line);
    extraPrices.current = lineSpecs.filter((l) => !l.id.startsWith("level-") && !l.id.startsWith("alert-")).map((l) => l.price);
    h.candles.priceScale().applyOptions({ autoScale: true });
    h.lines = lineSpecs.map((l) => h.candles.createPriceLine({ price: l.price, color: l.color, lineWidth: l.width, lineStyle: l.style, axisLabelVisible: true, title: `${l.title} ${l.price.toFixed(2)}` }));
  }, [lineSpecs, timeframe]);

  // trading sessions (DST-correct, see lib/sessions.ts): shaded runs of bars behind the candles
  useEffect(() => {
    const h = handles.current;
    if (!h) return;
    if (!overlays.sessions || series.length === 0) {
      h.bands.setRuns([]);
      return;
    }
    const opens = series.map((x) => Date.parse(x.bar.time));
    const runs = sessionRuns(opens).map(([i0, i1, session]) => ({
      from: times[i0],
      to: i1 < times.length ? times[i1] : times[times.length - 1] + tfSeconds,
      color: SESSION_COLORS[session],
    }));
    h.bands.setRuns(runs);
  }, [overlays.sessions, series, times, tfSeconds, timeframe]);

  // journal / history -> chart
  useEffect(() => {
    const h = handles.current;
    if (!h || !focus || times.length === 0) return;
    const from = shiftedSeconds(focus.from, zone);
    const to = shiftedSeconds(focus.to, zone);
    try {
      h.chart.timeScale().setVisibleRange({ from: (from - 40 * tfSeconds) as UTCTimestamp, to: (to + 40 * tfSeconds) as UTCTimestamp });
    } catch {
      /* the period is outside the loaded bars: keep the current view */
    }
  }, [focus, zone, times, tfSeconds]);

  // ---- OHLC readout: the hovered bar, or the latest one ----------------------------------------
  const shown = useMemo(() => {
    if (series.length === 0) return null;
    const idx = readout === null ? series.length - 1 : barIndexAt(times, readout);
    const item = series[Math.max(0, idx)];
    if (!item) return null;
    const b = item.bar;
    return { bar: b, change: b.close - b.open, pct: b.open === 0 ? null : ((b.close - b.open) / b.open) * 100, range: b.high - b.low };
  }, [readout, series, times]);

  const selectedDetail = details.find((d) => d.key === selected) ?? null;
  const coords = (point: { time: number; price: number } | null) => {
    const h = handles.current;
    if (!h || !point) return null;
    const x = h.chart.timeScale().timeToCoordinate(point.time as UTCTimestamp);
    const y = h.candles.priceToCoordinate(point.price);
    return x === null || y === null ? null : { x, y };
  };
  const a = coords(measure.a);
  const b = coords(measure.b);
  const delta = measure.a && measure.b ? measure.b.price - measure.a.price : null;
  const bars_between = measure.a && measure.b ? Math.round(Math.abs(measure.b.time - measure.a.time) / tfSeconds) : null;

  return (
    <div className="relative flex min-h-0 min-w-0 flex-1 flex-col">
      <div
        ref={container}
        role="group"
        aria-label={`Biểu đồ nến ${timeframe} của XAUUSD với tín hiệu, kế hoạch lệnh và lệnh paper`}
        data-testid="trade-chart"
        data-tool={tool}
        className={`min-h-[16rem] w-full flex-1 ${tool === "none" ? "" : "cursor-crosshair"}`}
      />

      {shown && (
        <div data-testid="ohlc-readout" aria-live="off" className="pointer-events-none absolute left-2 top-1 z-10 flex flex-wrap items-center gap-x-3 rounded bg-white/80 px-2 py-0.5 font-mono text-[11px] tabular-nums dark:bg-slate-900/80">
          <span className="text-slate-600 dark:text-slate-400">{formatInZone(shown.bar.time, zone).slice(5, 16)}</span>
          <span>O <b>{fmt(shown.bar.open)}</b></span>
          <span>H <b>{fmt(shown.bar.high)}</b></span>
          <span>L <b>{fmt(shown.bar.low)}</b></span>
          <span>C <b>{fmt(shown.bar.close)}</b></span>
          <span className={shown.change >= 0 ? "text-emerald-700 dark:text-emerald-400" : "text-red-700 dark:text-red-400"}>
            {shown.change >= 0 ? "+" : ""}{fmt(shown.change)} ({shown.pct === null ? "—" : `${shown.pct >= 0 ? "+" : ""}${shown.pct.toFixed(2)}%`})
          </span>
          <span className="text-slate-600 dark:text-slate-400">biên {fmt(shown.range)}</span>
          <span className="text-slate-600 dark:text-slate-400">vol {shown.bar.tick_volume}</span>
        </div>
      )}

      {!atLatest && (
        <button type="button" data-testid="go-latest" onClick={() => { handles.current?.chart.timeScale().scrollToRealTime(); onFollowChange(true); }} className="absolute bottom-9 right-16 z-10 rounded-md border border-sky-600 bg-sky-500/90 px-2 py-1 text-xs font-semibold text-white shadow">
          ⇥ Về hiện tại
        </button>
      )}

      {tool === "measure" && (
        <div data-testid="measure-hint" className="pointer-events-none absolute right-2 top-1 z-10 rounded bg-slate-900/80 px-2 py-0.5 text-[11px] text-white">
          {measure.a && !measure.fixed ? "Bấm điểm thứ hai" : "Bấm điểm đầu tiên để đo"}
        </div>
      )}
      {(a || b) && (
        <svg className="pointer-events-none absolute inset-0 z-10 h-full w-full" aria-hidden="true">
          {a && b && <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#0ea5e9" strokeWidth={1.5} strokeDasharray="4 3" />}
          {a && <circle cx={a.x} cy={a.y} r={3.5} fill="#0ea5e9" />}
          {b && <circle cx={b.x} cy={b.y} r={3.5} fill="#0ea5e9" />}
        </svg>
      )}
      {delta !== null && b && (
        <div data-testid="measure-readout" className="pointer-events-none absolute z-20 rounded border border-sky-600 bg-white/95 px-2 py-1 font-mono text-[11px] shadow dark:bg-slate-900/95" style={{ left: Math.min(b.x + 8, 9999), top: Math.max(b.y - 38, 4) }}>
          Δ {delta >= 0 ? "+" : ""}{delta.toFixed(2)} · {Math.abs(Math.round(delta / 0.01))} điểm · {measure.a ? ((delta / measure.a.price) * 100).toFixed(2) : "—"}% · {bars_between} nến ({bars_between === null ? "—" : Math.round((bars_between * tfSeconds) / 60)} phút)
        </div>
      )}

      {selectedDetail && (
        <div data-testid="marker-popover" role="dialog" aria-label="Chi tiết tín hiệu trên biểu đồ" className="absolute right-2 top-8 z-20 w-72 rounded-lg border border-slate-400 bg-white p-3 text-xs shadow-lg dark:bg-slate-900" onKeyDown={(e) => e.key === "Escape" && setSelected(null)}>
          <div className="mb-1 flex items-center justify-between">
            <b className="text-sm">
              {selectedDetail.kind === "BUY" ? "▲ Tín hiệu MUA" : selectedDetail.kind === "SELL" ? "▼ Tín hiệu BÁN" : selectedDetail.kind === "EXIT" ? "■ Thoát lệnh paper" : "● Mở lệnh paper"}
            </b>
            <button type="button" aria-label="Đóng chi tiết" onClick={() => setSelected(null)} className="rounded px-1.5 hover:bg-slate-500/20">✕</button>
          </div>
          {selectedDetail.signal && (
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 font-mono">
              <dt className="text-slate-600 dark:text-slate-400">Thời điểm</dt><dd>{formatInZone(selectedDetail.signal.at, zone)}</dd>
              <dt className="text-slate-600 dark:text-slate-400">Entry</dt><dd>{fmt(selectedDetail.signal.entry)}</dd>
              <dt className="text-slate-600 dark:text-slate-400">SL</dt><dd>{fmt(selectedDetail.signal.sl)}</dd>
              <dt className="text-slate-600 dark:text-slate-400">TP</dt><dd>{fmt(selectedDetail.signal.tp1)}</dd>
              <dt className="text-slate-600 dark:text-slate-400">RR</dt><dd>{fmt(selectedDetail.signal.rr)}</dd>
              <dt className="text-slate-600 dark:text-slate-400">Chiến lược</dt><dd>v{selectedDetail.signal.strategy_version}</dd>
              <dt className="text-slate-600 dark:text-slate-400">Nguồn</dt><dd>{selectedDetail.signal.source_mode === "LIVE" ? "LIVE" : "REPLAY (không phải live)"}</dd>
              <dt className="text-slate-600 dark:text-slate-400">Đã mở paper?</dt><dd>{selectedDetail.signal.taken ? "có" : "không"}</dd>
            </dl>
          )}
          {selectedDetail.trade && (
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 font-mono">
              <dt className="text-slate-600 dark:text-slate-400">Hướng</dt><dd>{selectedDetail.trade.side}</dd>
              <dt className="text-slate-600 dark:text-slate-400">Vào</dt><dd>{fmt(selectedDetail.trade.entry_price)} · {formatInZone(selectedDetail.trade.entry_time, zone)}</dd>
              {selectedDetail.trade.status === "CLOSED" && (
                <>
                  <dt className="text-slate-600 dark:text-slate-400">Thoát</dt><dd>{fmt(selectedDetail.trade.exit_price)} · {EXIT_REASON_VI[selectedDetail.trade.exit_reason ?? ""] ?? selectedDetail.trade.exit_reason}</dd>
                  <dt className="text-slate-600 dark:text-slate-400">P&L</dt><dd>{fmt(selectedDetail.trade.net_pnl)} · {fmt(selectedDetail.trade.r_multiple)}R</dd>
                </>
              )}
              <dt className="text-slate-600 dark:text-slate-400">SL / TP</dt><dd>{fmt(selectedDetail.trade.sl)} / {fmt(selectedDetail.trade.tp)}</dd>
              <dt className="text-slate-600 dark:text-slate-400">Chiến lược</dt><dd>v{selectedDetail.trade.strategy_version ?? "?"}</dd>
            </dl>
          )}
        </div>
      )}

      <ul data-testid="chart-legend" aria-label="Các đường trên biểu đồ" className="pointer-events-none absolute left-2 top-6 z-10 flex max-w-[70%] flex-wrap gap-x-3 gap-y-0 text-[11px] font-semibold">
        {lineSpecs.map((l) => (
          <li key={l.id} data-testid={`line-${l.title.replace(/ /g, "-")}`} style={{ color: l.color }} className="rounded bg-white/70 px-1 dark:bg-slate-900/70">
            {l.title} {l.price.toFixed(2)}
          </li>
        ))}
      </ul>
      {overlays.sessions && (
        <ul data-testid="session-legend" aria-label="Chú giải phiên giao dịch" className="pointer-events-none absolute bottom-1 left-2 z-10 flex gap-2 text-[11px]">
          {(["ASIA", "LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"] as const).map((k) => (
            <li key={k} className="rounded px-1 text-slate-700 dark:text-slate-200" style={{ background: SESSION_COLORS[k].replace(/[\d.]+\)$/, "0.35)") }}>{SESSION_NAMES[k]}</li>
          ))}
        </ul>
      )}
      <ul data-testid="chart-markers" aria-label="Tín hiệu và lệnh trên biểu đồ" className="sr-only focus-within:not-sr-only focus-within:absolute focus-within:bottom-10 focus-within:left-2 focus-within:z-20 focus-within:max-w-[85%] focus-within:space-y-1 focus-within:rounded-lg focus-within:border focus-within:border-slate-400 focus-within:bg-white focus-within:p-2 focus-within:text-xs focus-within:shadow-lg dark:focus-within:bg-slate-900">
        {details.map((m) => (
          <li key={m.key} data-kind={m.kind} data-bar-time={m.barTime}>
            {m.lines.join(" ")}{" "}
            <button type="button" onClick={() => setSelected(m.key)}>Xem chi tiết</button>
          </li>
        ))}
      </ul>
    </div>
  );
});
