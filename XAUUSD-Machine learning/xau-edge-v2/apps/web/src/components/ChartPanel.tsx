import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  LineStyle,
  type UTCTimestamp,
  createChart,
  createSeriesMarkers,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import { useEffect, useRef, useState } from "react";
import type { FormingBar, PaperPosition, Quote, State } from "../api/client";
import {
  type ChartBar,
  TIMEFRAMES,
  TIMEFRAME_SECONDS,
  type Tf,
  positionMarkers,
  toChartBar,
  wantsOlder,
  withForming,
} from "../chart/bars";
import { useBars } from "../hooks/useBars";

const UP = "#15803d";
const DOWN = "#b91c1c";
const VISIBLE_BARS = 150;

interface Handles {
  chart: IChartApi;
  candles: ISeriesApi<"Candlestick">;
  volume: ISeriesApi<"Histogram">;
  lines: IPriceLine[];
  markers: ISeriesMarkersPluginApi<Time>;
}

const candle = (b: ChartBar) => ({
  time: b.time as UTCTimestamp,
  open: b.open,
  high: b.high,
  low: b.low,
  close: b.close,
});
const volume = (b: ChartBar) => ({
  time: b.time as UTCTimestamp,
  value: b.volume,
  color: b.close >= b.open ? `${UP}66` : `${DOWN}66`,
});

interface Props {
  state: State | null;
  quote: Quote | null;
  forming: Record<string, FormingBar["bar"]>;
  dataVersion: string | null;
  positions: PaperPosition[];
}

/** Candles + tick volume for one timeframe, history on demand to the start of the store. */
export function ChartPanel({ state, quote, forming, dataVersion, positions }: Props) {
  const [tf, setTf] = useState<Tf>("M15");
  const history = useBars(tf, dataVersion);
  const host = useRef<HTMLDivElement>(null);
  const handles = useRef<Handles | null>(null);
  const shown = useRef({ first: 0, last: 0, generation: -1 });
  const latest = useRef({ history, tf });
  latest.current = { history, tf };

  // the chart object lives for the life of the panel
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const chart = createChart(el, {
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "#ffffff" }, textColor: "#131820", fontSize: 12 },
      grid: { vertLines: { color: "#e2e8f0" }, horzLines: { color: "#e2e8f0" } },
      rightPriceScale: { borderColor: "#cbd5e1" },
      timeScale: { borderColor: "#cbd5e1", timeVisible: true, secondsVisible: false, rightOffset: 4 },
    });
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: UP,
      downColor: DOWN,
      borderUpColor: UP,
      borderDownColor: DOWN,
      wickUpColor: UP,
      wickDownColor: DOWN,
    });
    const vol = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "vol" });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      const { history: h } = latest.current;
      if (range && wantsOlder(range.from, { hasMore: h.hasMoreBefore, loading: h.loading, loaded: h.bars.length })) {
        h.loadOlder();
      }
    });
    handles.current = { chart, candles, volume: vol, lines: [], markers: createSeriesMarkers(candles, []) };
    return () => {
      chart.remove();
      handles.current = null;
      shown.current = { first: 0, last: 0, generation: -1 };
    };
  }, []);

  // data: new timeframe -> refit; older page -> keep the view; new bar -> update the tail
  const formingBar = forming[tf];
  useEffect(() => {
    const h = handles.current;
    if (!h) return;
    const data = withForming(history.bars, formingBar ? toChartBar(formingBar) : null);
    const prev = shown.current;
    const first = data[0]?.time ?? 0;
    if (history.generation !== prev.generation || data.length === 0) {
      h.candles.setData(data.map(candle));
      h.volume.setData(data.map(volume));
      if (data.length > 0) {
        h.chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, data.length - VISIBLE_BARS), to: data.length + 4 });
      }
    } else if (first !== prev.first) {
      const view = h.chart.timeScale().getVisibleRange();
      h.candles.setData(data.map(candle));
      h.volume.setData(data.map(volume));
      if (view) h.chart.timeScale().setVisibleRange(view);
    } else {
      // series.update only accepts the last bar or newer ones: never an older bar
      for (const b of data.filter((x) => x.time >= prev.last)) {
        h.candles.update(candle(b));
        h.volume.update(volume(b));
      }
    }
    shown.current = { first, last: data.at(-1)?.time ?? 0, generation: history.generation };
  }, [history.bars, history.generation, formingBar]);

  // paper entries and exits as markers on the bars they happened in (this timeframe)
  useEffect(() => {
    const h = handles.current;
    if (!h) return;
    const marks = positionMarkers(positions, TIMEFRAME_SECONDS[tf]);
    h.markers.setMarkers(
      marks.map(
        (m): SeriesMarker<Time> => ({
          time: m.time as UTCTimestamp,
          position: m.position,
          shape: m.shape,
          color: m.color,
          text: m.text,
        }),
      ),
    );
  }, [positions, tf, history.generation]);

  // the plan (or, while holding, the open paper position) as price lines
  const plan = state?.plan ?? null;
  useEffect(() => {
    const h = handles.current;
    if (!h) return;
    for (const line of h.lines) h.candles.removePriceLine(line);
    h.lines = [];
    if (!plan) return;
    const add = (price: number, title: string, color: string, dashed = false) =>
      h.lines.push(
        h.candles.createPriceLine({
          price,
          title,
          color,
          lineWidth: 2,
          lineStyle: dashed ? LineStyle.Dashed : LineStyle.Solid,
          axisLabelVisible: true,
        }),
      );
    add(plan.entry, `Entry ${plan.side}`, "#1d4ed8");
    add(plan.stop_loss, "SL", DOWN);
    add(plan.take_profit_1, "TP1", UP);
    if (plan.take_profit_2 != null) add(plan.take_profit_2, "TP2", UP, true);
  }, [plan]);

  const bias = state?.bias ?? "NEUTRAL";
  const biasText = bias === "BUY" ? "▲ nghiêng MUA" : bias === "SELL" ? "▼ nghiêng BÁN" : "— trung tính";
  return (
    <section className="chart" aria-label="Biểu đồ" data-testid="chart-panel">
      <div className="chart-head">
        <h2>XAUUSD</h2>
        <div role="group" aria-label="Khung thời gian" className="tf-switch">
          {TIMEFRAMES.map((t) => (
            <button key={t} type="button" aria-pressed={t === tf} data-testid={`tf-${t}`} onClick={() => setTf(t)}>
              {t}
            </button>
          ))}
        </div>
        <p className="bias-strip" data-testid="chart-bias">
          Thiên hướng: <strong>{biasText}</strong>
          {state && <> · mức {state.readiness_level}/6</>}
          {quote?.bid != null && quote.ask != null && (
            <span data-testid="chart-quote">
              {" "}
              · bid {quote.bid.toFixed(2)} / ask {quote.ask.toFixed(2)}
            </span>
          )}
        </p>
      </div>
      <div className="chart-host" ref={host} data-testid="chart-host" />
      <p
        className="muted small chart-meta"
        data-testid="chart-meta"
        data-tf={tf}
        data-count={history.bars.length}
        data-oldest={history.bars[0] ? new Date(history.bars[0].time * 1000).toISOString() : ""}
        data-has-more={String(history.hasMoreBefore)}
        data-loading={String(history.loading)}
        aria-live="polite"
      >
        {history.error ? (
          <span role="alert" data-testid="chart-error">
            Không tải được nến: {history.error}
          </span>
        ) : history.loading && history.bars.length === 0 ? (
          "Đang tải nến…"
        ) : (
          <>
            {history.bars.length} nến {tf} (giờ UTC)
            {history.hasMoreBefore ? " · kéo sang trái để xem nến cũ hơn" : " · đã tới nến cũ nhất trong kho"}
            {history.loading && " · đang tải thêm…"}
          </>
        )}
      </p>
    </section>
  );
}
