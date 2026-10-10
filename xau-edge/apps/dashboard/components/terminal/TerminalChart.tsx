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
import { ZONE_LABEL, shiftedSeconds, formatInZone, type DisplayZone } from "@/lib/time";
import type { MarkersResponse, PaperMarker, SetupHistoryRow, SignalMarker, TradePlan, TradeView } from "@/lib/trade";
import { EXIT_REASON_VI, SIDE_VI } from "@/lib/vi";

export type Tool = "none" | "line" | "measure";

export interface ChartHandle {
  fit: () => void;
  latest: () => void;
}

export interface MarkerDetail {
  key: string;
  kind: "BUY" | "SELL" | "PAPER_ENTRY" | "EXIT" | "SETUP";
  /** ISO time of the chart bar the marker is drawn on. */
  barTime: string;
  lines: string[];
  signal?: SignalMarker;
  trade?: PaperMarker;
  setup?: SetupHistoryRow;
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
  /** how each setup the engine armed ended (server history): drawn as a small SETUP marker */
  setups?: SetupHistoryRow[] | null;
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

const LABEL_PX = 46; // two labelled markers of the same side closer than this would overlap: the better-ranked one keeps its label
const AXIS_PX = 16; // a price-axis label is about this tall: two lines closer than this would stack their labels
const EXIT_SHORT: Record<string, string> = { TAKE_PROFIT: "TP", STOP_LOSS: "SL", TIME_EXIT: "HẾT GIỜ", MANUAL_CLOSE: "TAY", CLOSURE_CLOSE: "ĐÓNG CỬA", INVALIDATED: "VÔ HIỆU" };
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
  { bars, timeframe, zone, overlays, view, markers, history, planLive, plan, focus, follow, onFollowChange, levels, alerts, setups, tool, onAddLevel, onToolDone },
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
  const applied = useRef<{ last: number; zone: DisplayZone } | null>(null);
  const fitted = useRef<string | null>(null);
  const followRef = useRef(follow);
  const toolRef = useRef(tool);
  const interacting = useRef(false);
  const hasOverlay = useRef(false);
  const [readout, setReadout] = useState<number | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  // Esc closes the marker popover from anywhere (it does not take focus), and only that: a second Esc leaves fullscreen
  useEffect(() => {
    if (selected === null) return;
    const onEsc = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.stopImmediatePropagation();
      setSelected(null);
    };
    window.addEventListener("keydown", onEsc, true);
    return () => window.removeEventListener("keydown", onEsc, true);
  }, [selected]);
  const [atLatest, setAtLatest] = useState(true);
  const [measure, setMeasure] = useState<Measure>({ a: null, b: null, fixed: false });
  const [, setTick] = useState(0);

  useEffect(() => {
    followRef.current = follow;
    handles.current?.chart.timeScale().applyOptions({ shiftVisibleRangeOnNewBar: follow });
  }, [follow]);
  useEffect(() => {
    hasOverlay.current = measure.a !== null; // the ruler is the only thing positioned from the visible range
  }, [measure.a]);
  useEffect(() => {
    toolRef.current = tool;
    if (tool !== "measure") setMeasure({ a: null, b: null, fixed: false });
  }, [tool]);

  useImperativeHandle(ref, () => ({
    fit: () => handles.current?.chart.timeScale().fitContent(),
    latest: () => {
      interacting.current = false; // a jump to now is not the trader's scroll: follow must stay ON
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
  const { chartMarkers, markerPrio, details } = useMemo(() => {
    // prio: who keeps the label when two labelled markers of the same side sit closer than a label is wide (lower wins)
    const meta: { m: SeriesMarker<Time>; prio: number }[] = [];
    const list = { push: (m: SeriesMarker<Time>, prio = 5) => void meta.push({ m, prio }) };
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
        list.push({ time: at.time as UTCTimestamp, position: buy ? "belowBar" : "aboveBar", shape: buy ? "arrowUp" : "arrowDown", color: buy ? GREEN : RED, text: SIDE_VI[s.side] }, 2);
        out.push({
          key: `sig-${s.setup_id}`,
          kind: s.side,
          barTime: at.barIso,
          signal: s,
          lines: [
            `Tín hiệu ${s.side === "BUY" ? "MUA" : "BÁN"} tại ${fmt(s.price ?? s.entry)} · SL ${fmt(s.sl)} · TP ${fmt(s.tp1)} · RR ${fmt(s.rr)}${s.taken ? " · đã mở paper" : ""} · v${s.strategy_version} · ${s.source_mode === "LIVE" ? "LIVE" : "REPLAY"}`,
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
          list.push({ time: entry.time as UTCTimestamp, position: t.side === "BUY" ? "belowBar" : "aboveBar", shape: "circle", color: BLUE, text: "" }); // the circle is enough; a label collides with the signal arrow
          out.push({ key: `in-${t.trade_id}`, kind: "PAPER_ENTRY", barTime: entry.barIso, trade: t, lines: [`Mở lệnh PAPER ${t.side === "BUY" ? "MUA" : "BÁN"} tại ${fmt(t.entry_price)}`] });
        }
        const exit = t.status === "CLOSED" ? byTime(t.exit_time, "containing") : null;
        if (exit) {
          list.push({ time: exit.time as UTCTimestamp, position: t.side === "BUY" ? "aboveBar" : "belowBar", shape: "square", color: (t.net_pnl ?? 0) >= 0 ? GREEN : RED, text: EXIT_SHORT[t.exit_reason ?? ""] ?? "THOÁT" }, 1);
          out.push({
            key: `out-${t.trade_id}`,
            kind: "EXIT",
            barTime: exit.barIso,
            trade: t,
            lines: [`Thoát lệnh (${EXIT_REASON_VI[t.exit_reason ?? ""] ?? t.exit_reason}) tại ${fmt(t.exit_price)} · P&L ${fmt(t.net_pnl)} · ${fmt(t.r_multiple)}R · ${fmt(t.duration_minutes, 0)} phút${t.strategy_version ? ` · v${t.strategy_version}` : ""}`],
          });
        }
      }
    }
    if (setups && overlays.signals) {
      for (const r of setups.slice(0, 12)) {
        const at = byTime(r.armed_at, "containing");
        if (!at) continue;
        const buy = r.side === "BUY";
        const how = r.outcome === "INVALIDATED" ? "bị vô hiệu" : r.outcome === "EXPIRED" ? "hết hiệu lực" : r.outcome === "TRIGGERED" ? "đã kích hoạt" : "đang hình thành";
        list.push({ time: at.time as UTCTimestamp, position: buy ? "belowBar" : "aboveBar", shape: "circle", color: GREY, text: "SETUP" }, 3);
        out.push({ key: `setup-${r.armed_at}`, kind: "SETUP", barTime: at.barIso, setup: r, lines: [`SETUP ${r.side === "BUY" ? "MUA" : r.side === "SELL" ? "BÁN" : ""} ${how}`] });
      }
    }
    meta.sort((a, b) => (a.m.time as number) - (b.m.time as number));
    return { chartMarkers: meta.map((x) => x.m), markerPrio: meta.map((x) => x.prio), details: out };
  }, [markers, overlays.signals, overlays.paper, history, times, zone, tfSeconds, setups]);

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
      // a click on (or within a finger's width of) a bar that carries markers opens their details
      const x = param.point?.x;
      let hit = time === null ? undefined : detailsRef.current.find((d) => d.time === time);
      if (!hit && x !== undefined) {
        let best = 14; // px
        for (const d of detailsRef.current) {
          const mx = chart.timeScale().timeToCoordinate(d.time as never);
          if (mx !== null && Math.abs(mx - x) <= best) {
            best = Math.abs(mx - x);
            hit = d;
          }
        }
      }
      setSelected(hit ? hit.detail.key : null);
    });
    const onRange = () => {
      const logical = chart.timeScale().getVisibleLogicalRange();
      if (logical) element.dataset.range = `${logical.from.toFixed(1)}:${logical.to.toFixed(1)}`; // observable, no re-render
      const pos = chart.timeScale().scrollPosition();
      const latest = pos > -1.5;
      setAtLatest(latest);
      // only the trader's own scroll/zoom turns follow off (never a programmatic fit or jump), and the chart never snaps back
      if (!latest && followRef.current && interacting.current) onFollowChangeRef.current(false);
      if (hasOverlay.current) setTick((n) => n + 1);
      schedule.current();
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
    const onMove = (e: PointerEvent) => e.buttons > 0 && touch(2500);
    element.addEventListener("pointermove", onMove);
    element.addEventListener("wheel", onWheel, { passive: true });
    const onScheme = (e: MediaQueryListEvent) => chart.applyOptions(palette(e.matches));
    scheme.addEventListener("change", onScheme);
    return () => {
      scheme.removeEventListener("change", onScheme);
      clearTimeout(quiet);
      element.removeEventListener("pointerdown", onDown);
      element.removeEventListener("wheel", onWheel);
      element.removeEventListener("pointermove", onMove);
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
    // incremental: continue from the last bar already drawn. A sliding 400-bar window (the oldest bar
    // drops off, a new one arrives) therefore only appends, and the trader's zoom and pan stay put.
    const prev = applied.current;
    const at = prev ? barIndexAt(times, prev.last) : -1;
    // a different display zone re-times EVERY bar, so it is never an incremental update
    if (prev && prev.zone === zone && at >= 0 && times[at] === prev.last) {
      for (let i = at; i < series.length; i++) {
        h.candles.update(candlePoint(series[i]));
        h.volume.update(volumePoint(series[i]));
      }
    } else {
      h.candles.setData(series.map(candlePoint));
      h.volume.setData(series.map(volumePoint));
    }
    applied.current = { last: times[times.length - 1], zone };
    container.current?.setAttribute("data-bars", String(h.candles.data().length)); // observable (tests, support)
    const last = series[series.length - 1].bar;
    h.candles.applyOptions({ priceLineColor: last.close >= last.open ? GREEN : RED });
    if (fitted.current !== timeframe) {
      h.chart.timeScale().fitContent();
      h.chart.timeScale().scrollToRealTime();
      fitted.current = timeframe;
    }
  }, [series, times, timeframe, zone]);

  // Label collisions: markers and axis labels are re-ranked whenever the view changes (zoom, pan, new bar, new line).
  // The shapes and the lines always stay; only the TEXT of a lower-ranked neighbour is dropped, and everything stays in the legend / details.
  const chartMarkersRef = useRef<{ list: SeriesMarker<Time>[]; prio: number[] }>({ list: [], prio: [] });
  const lastCloseRef = useRef<number | null>(null);
  const lineStateRef = useRef<boolean[]>([]);
  const lastLabelRef = useRef<boolean | null>(null);
  const declutter = useRef<() => void>(() => {});
  const schedule = useRef<() => void>(() => {});
  const rafId = useRef(0);
  useEffect(() => {
    lastCloseRef.current = series.length ? series[series.length - 1].bar.close : null;
  }, [series]);
  useEffect(() => {
    declutter.current = () => {
      const h = handles.current;
      const el = container.current;
      if (!h || !el) return;
      const ts = h.chart.timeScale();
      const { list, prio } = chartMarkersRef.current;
      const order = list.map((_, i) => i).sort((a, b) => prio[a] - prio[b] || a - b);
      const kept: { x: number; pos: string }[] = [];
      const blank = new Set<number>();
      for (const i of order) {
        const m = list[i];
        if (!m.text) continue;
        const x = ts.timeToCoordinate(m.time);
        if (x === null) continue;
        if (kept.some((k) => k.pos === m.position && Math.abs(k.x - x) < LABEL_PX)) blank.add(i);
        else kept.push({ x, pos: m.position });
      }
      const sig = `${list.length}:${[...blank].join(",")}`;
      if (sig !== el.dataset.markerSig) {
        el.dataset.markerSig = sig;
        h.plugin.setMarkers(list.map((m, i) => (blank.has(i) ? { ...m, text: "" } : m)));
      }
      el.dataset.hiddenMarkerLabels = String(blank.size);
      // price-axis labels, best first: the plan (ENTRY/SL/TP) and the paper position, then the last price, then NOW/TP2, the
      // trader's levels, alerts, structure. A label that would stack on a better one is dropped (the line stays, the legend lists it).
      const specs = lineSpecsRef.current;
      const rank = (id: string) => (["ENTRY", "SL", "TP1", "PAPER ENTRY", "PAPER SL", "PAPER TP"].includes(id) ? 1 : id === "LAST" ? 1.5 : id === "NOW" || id === "TP2" ? 2 : id.startsWith("level-") ? 3 : id.startsWith("alert-") ? 4 : 5);
      const lastY = lastCloseRef.current === null ? null : h.candles.priceToCoordinate(lastCloseRef.current);
      const items: { i: number; id: string; y: number }[] = specs.flatMap((l, i) => {
        const y = h.candles.priceToCoordinate(l.price);
        return y === null ? [] : [{ i, id: l.id, y }];
      });
      if (lastY !== null) items.push({ i: -1, id: "LAST", y: lastY });
      items.sort((x, y) => rank(x.id) - rank(y.id) || x.i - y.i);
      const taken: number[] = [];
      let hiddenAxis = 0;
      for (const it of items) {
        const clash = taken.some((t) => Math.abs(t - it.y) < AXIS_PX);
        if (clash) hiddenAxis++;
        else taken.push(it.y);
        if (it.id === "LAST") {
          if (lastLabelRef.current !== !clash) {
            lastLabelRef.current = !clash;
            h.candles.applyOptions({ lastValueVisible: !clash });
          }
        } else if (h.lines[it.i] && lineStateRef.current[it.i] !== !clash) {
          lineStateRef.current[it.i] = !clash;
          const l = specs[it.i];
          h.lines[it.i].applyOptions({ axisLabelVisible: !clash, title: clash ? "" : `${l.title} ${l.price.toFixed(2)}` });
        }
      }
      el.dataset.hiddenAxisLabels = String(hiddenAxis);
    };
    schedule.current = () => {
      if (rafId.current) return;
      rafId.current = requestAnimationFrame(() => {
        rafId.current = 0;
        declutter.current();
      });
    };
  }, [series]);
  useEffect(() => {
    chartMarkersRef.current = { list: chartMarkers, prio: markerPrio };
    const el = container.current;
    if (el) el.dataset.markerSig = ""; // new marker set: apply it
    schedule.current();
  }, [chartMarkers, markerPrio]);
  useEffect(() => {
    const id = setInterval(() => schedule.current(), 1500); // the price scale autoscales with every new bar
    return () => clearInterval(id);
  }, []);

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

  const lineKey = useMemo(() => lineSpecs.map((l) => `${l.id}|${l.title}|${l.price}|${l.color}|${l.style}|${l.width}`).join(";"), [lineSpecs]);
  const lineSpecsRef = useRef(lineSpecs);
  useEffect(() => {
    lineSpecsRef.current = lineSpecs;
  }, [lineSpecs]);
  useEffect(() => {
    const h = handles.current;
    if (!h) return;
    const lineSpecs = lineSpecsRef.current;
    for (const line of h.lines) h.candles.removePriceLine(line);
    extraPrices.current = lineSpecs.filter((l) => !l.id.startsWith("level-") && !l.id.startsWith("alert-")).map((l) => l.price);
    h.candles.priceScale().applyOptions({ autoScale: true });
    h.lines = lineSpecs.map((l) => h.candles.createPriceLine({ price: l.price, color: l.color, lineWidth: l.width, lineStyle: l.style, axisLabelVisible: true, title: `${l.title} ${l.price.toFixed(2)}` }));
    lineStateRef.current = [];
    lastLabelRef.current = null; // a new chart (timeframe change) starts with every label on
    schedule.current();
  }, [lineKey, timeframe]);

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

  // journal / history -> chart: a ONE-SHOT request, applied when asked (or once its bars have loaded),
  // never again on a later poll, so the trader can pan away afterwards
  const pendingFocus = useRef<{ from: string; to: string } | null>(null);
  useEffect(() => {
    pendingFocus.current = focus;
  }, [focus]);
  useEffect(() => {
    const h = handles.current;
    const want = pendingFocus.current;
    if (!h || !want || times.length === 0) return;
    const from = shiftedSeconds(want.from, zone);
    const to = shiftedSeconds(want.to, zone);
    if (!Number.isFinite(from) || !Number.isFinite(to)) {
      pendingFocus.current = null;
      return;
    }
    pendingFocus.current = null;
    try {
      h.chart.timeScale().setVisibleRange({ from: (from - 40 * tfSeconds) as UTCTimestamp, to: (to + 40 * tfSeconds) as UTCTimestamp });
    } catch {
      /* the period is outside the loaded bars: keep the current view */
    }
  }, [focus, times, zone, tfSeconds]);

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
    <div className="relative isolate flex min-h-0 min-w-0 flex-1 flex-col">
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
          <span className={`hidden sm:inline ${shown.change >= 0 ? "text-emerald-700 dark:text-emerald-400" : "text-red-700 dark:text-red-400"}`}>
            {shown.change >= 0 ? "+" : ""}{fmt(shown.change)} ({shown.pct === null ? "—" : `${shown.pct >= 0 ? "+" : ""}${shown.pct.toFixed(2)}%`})
          </span>
          <span className="hidden text-slate-600 sm:inline dark:text-slate-400">biên {fmt(shown.range)}</span>
          <span className="hidden text-slate-600 sm:inline dark:text-slate-400">vol {shown.bar.tick_volume}</span>
        </div>
      )}

      {!atLatest && (
        <button type="button" data-testid="go-latest" onClick={() => { interacting.current = false; /* a jump to now is not the trader's scroll: follow must stay ON */ handles.current?.chart.timeScale().scrollToRealTime(); onFollowChange(true); }} className="absolute bottom-9 right-16 z-10 rounded-md border border-sky-600 bg-sky-500/90 px-2 py-1 text-xs font-semibold text-white shadow">
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
        <div data-testid="marker-popover" role="dialog" aria-label="Chi tiết tín hiệu trên biểu đồ" className="absolute right-2 top-8 z-20 w-72 max-w-[calc(100%-1rem)] rounded-lg border border-slate-400 bg-white p-3 text-xs shadow-lg dark:bg-slate-900" onKeyDown={(e) => e.key === "Escape" && setSelected(null)}>
          <div className="mb-1 flex items-center justify-between">
            <b className="text-sm">
              {selectedDetail.kind === "BUY" ? "▲ Tín hiệu MUA" : selectedDetail.kind === "SELL" ? "▼ Tín hiệu BÁN" : selectedDetail.kind === "EXIT" ? "■ Thoát lệnh paper" : selectedDetail.kind === "SETUP" ? "● Setup đã hình thành" : "● Mở lệnh paper"}
            </b>
            <button type="button" aria-label="Đóng chi tiết" onClick={() => setSelected(null)} className="rounded px-1.5 hover:bg-slate-500/20">✕</button>
          </div>
          <p data-testid="popover-zone" className="mb-1 text-[11px] text-slate-600 dark:text-slate-400">Giờ hiển thị: {ZONE_LABEL[zone]}</p>
          {selectedDetail.signal && (
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 font-mono">
              <dt className="text-slate-600 dark:text-slate-400">Thời điểm</dt><dd>{formatInZone(selectedDetail.signal.at, zone)}</dd>
              <dt className="text-slate-600 dark:text-slate-400">Hướng</dt><dd>{selectedDetail.signal.side === "BUY" ? "MUA" : "BÁN"}</dd>
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
              <dt className="text-slate-600 dark:text-slate-400">Hướng</dt><dd>{selectedDetail.trade.side === "BUY" ? "MUA" : "BÁN"}</dd>
              <dt className="text-slate-600 dark:text-slate-400">Vào</dt><dd>{fmt(selectedDetail.trade.entry_price)} · {formatInZone(selectedDetail.trade.entry_time, zone)}</dd>
              {selectedDetail.trade.status === "CLOSED" && (
                <>
                  <dt className="text-slate-600 dark:text-slate-400">Thoát</dt><dd>{fmt(selectedDetail.trade.exit_price)} · {EXIT_REASON_VI[selectedDetail.trade.exit_reason ?? ""] ?? selectedDetail.trade.exit_reason}</dd>
                  <dt className="text-slate-600 dark:text-slate-400">Giờ thoát</dt><dd data-testid="popover-exit-time">{formatInZone(selectedDetail.trade.exit_time, zone)}</dd>
                  <dt className="text-slate-600 dark:text-slate-400">P&L</dt><dd>{fmt(selectedDetail.trade.net_pnl)} · {fmt(selectedDetail.trade.r_multiple)}R</dd>
                </>
              )}
              <dt className="text-slate-600 dark:text-slate-400">SL / TP</dt><dd>{fmt(selectedDetail.trade.sl)} / {fmt(selectedDetail.trade.tp)}</dd>
              <dt className="text-slate-600 dark:text-slate-400">Chiến lược</dt><dd>v{selectedDetail.trade.strategy_version ?? "?"}</dd>
            </dl>
          )}
          {selectedDetail.setup && (
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 font-mono">
              <dt className="text-slate-600 dark:text-slate-400">Hướng</dt><dd>{selectedDetail.setup.side === "BUY" ? "MUA" : selectedDetail.setup.side === "SELL" ? "BÁN" : "—"}</dd>
              <dt className="text-slate-600 dark:text-slate-400">Hình thành</dt><dd>{formatInZone(selectedDetail.setup.armed_at, zone)}</dd>
              <dt className="text-slate-600 dark:text-slate-400">Kết quả</dt><dd>{selectedDetail.setup.outcome === "INVALIDATED" ? "bị vô hiệu" : selectedDetail.setup.outcome === "EXPIRED" ? "hết hiệu lực" : selectedDetail.setup.outcome === "TRIGGERED" ? "đã kích hoạt" : "đang hình thành"}</dd>
              <dt className="text-slate-600 dark:text-slate-400">Có lệnh vào?</dt><dd>{selectedDetail.setup.actionable ? "có tín hiệu vào lệnh" : "không"}</dd>
              <dt className="text-slate-600 dark:text-slate-400">Chiến lược</dt><dd>v{selectedDetail.setup.strategy_version ?? "?"}</dd>
            </dl>
          )}
        </div>
      )}

      <ul data-testid="chart-legend" aria-label="Các đường trên biểu đồ" className="pointer-events-none absolute left-2 top-12 z-10 flex max-w-[70%] sm:top-6 flex-wrap gap-x-3 gap-y-0 text-[11px] font-semibold">
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
