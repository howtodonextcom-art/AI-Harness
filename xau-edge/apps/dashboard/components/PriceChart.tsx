"use client";

import { CandlestickSeries, ColorType, createChart, type UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { Bar } from "@/lib/api";

export function PriceChart({ bars }: { bars: Bar[] }) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = container.current;
    if (!element || bars.length === 0) return;
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
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#16a34a",
      downColor: "#dc2626",
      wickUpColor: "#16a34a",
      wickDownColor: "#dc2626",
      borderVisible: false,
    });
    series.setData(
      bars.map((b) => ({
        time: (Date.parse(b.timestamp) / 1000) as UTCTimestamp,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      })),
    );
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [bars]);

  return (
    <div
      ref={container}
      role="img"
      aria-label="M15 candlestick chart of the last 200 bars"
      className="h-64 w-full lg:h-72"
    />
  );
}
