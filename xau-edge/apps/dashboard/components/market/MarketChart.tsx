"use client";

import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { MarketBar } from "@/lib/market";
import { shiftedSeconds, type DisplayZone } from "@/lib/time";

interface Handles {
  chart: IChartApi;
  candles: ISeriesApi<"Candlestick">;
  volume: ISeriesApi<"Histogram">;
  spread: ISeriesApi<"Line">;
}


/**
 * Candlesticks (price pane), TICK volume (second pane) and the bar spread in points (third pane).
 * The chart is created once per timeframe; polling only replaces the data. A still-forming bar is
 * drawn hollow/translucent so it cannot be mistaken for a closed one. Times are shown in the chosen display zone (default UTC).
 */
export function MarketChart({ bars, timeframe, zone = "UTC" }: { bars: MarketBar[]; timeframe: string; zone?: DisplayZone }) {
  const container = useRef<HTMLDivElement>(null);
  const handles = useRef<Handles | null>(null);
  const fitted = useRef<string | null>(null);

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const chart = createChart(element, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: dark ? "#cbd5e1" : "#334155",
      },
      grid: {
        vertLines: { color: dark ? "#1e293b" : "#e2e8f0" },
        horzLines: { color: dark ? "#1e293b" : "#e2e8f0" },
      },
      timeScale: { timeVisible: true, secondsVisible: false },
    });
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: "#16a34a",
      downColor: "#dc2626",
      wickUpColor: "#16a34a",
      wickDownColor: "#dc2626",
      borderVisible: false,
    });
    const volume = chart.addSeries(
      HistogramSeries,
      { priceFormat: { type: "volume" }, priceLineVisible: false, title: "Tick volume" },
      1,
    );
    const spread = chart.addSeries(
      LineSeries,
      { color: "#d97706", lineWidth: 1, priceLineVisible: false, title: "Spread (points)" },
      2,
    );
    handles.current = { chart, candles, volume, spread };
    fitted.current = null;
    return () => {
      chart.remove();
      handles.current = null;
    };
  }, [timeframe]);

  useEffect(() => {
    const h = handles.current;
    if (!h) return;
    const toTime = (iso: string) => shiftedSeconds(iso, zone) as UTCTimestamp;
    h.candles.setData(
      bars.map((b) => {
        const up = b.close >= b.open;
        const base = up ? "#16a34a" : "#dc2626";
        return b.is_closed
          ? { time: toTime(b.time), open: b.open, high: b.high, low: b.low, close: b.close }
          : {
              time: toTime(b.time),
              open: b.open,
              high: b.high,
              low: b.low,
              close: b.close,
              color: `${base}55`,
              borderColor: base,
              wickColor: base,
            };
      }),
    );
    h.volume.setData(
      bars.map((b) => ({
        time: toTime(b.time),
        value: b.tick_volume,
        color: b.is_closed ? (b.close >= b.open ? "#16a34a99" : "#dc262699") : "#64748b66",
      })),
    );
    h.spread.setData(bars.map((b) => ({ time: toTime(b.time), value: b.spread })));
    if (fitted.current !== timeframe && bars.length > 0) {
      h.chart.timeScale().fitContent();
      fitted.current = timeframe;
    }
  }, [bars, timeframe, zone]);

  return (
    <div
      ref={container}
      role="img"
      aria-label={`Biểu đồ nến ${timeframe} của XAUUSD với tick volume và spread`}
      data-testid="market-chart"
      className="h-[28rem] w-full lg:h-[34rem]"
    />
  );
}
