"use client";

import { ColorType, createChart, LineSeries, type UTCTimestamp } from "lightweight-charts";
import { useEffect, useRef } from "react";
import type { PatternsResponse } from "@/lib/api";

const asTime = (x: number) => (x + 1) as UTCTimestamp;

/**
 * Current pattern against the top historical analogues, all in ATR units and aligned so that the
 * end of the pattern sits at x = 0. Everything to the right of 0 is what followed each analogue:
 * it is shown for context and never feeds a model.
 */
export function AnalogueChart({ data, topN }: { data: PatternsResponse; topN: number }) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = container.current;
    if (!element || !data.available || !data.current_path || !data.window) return;
    const window_ = data.window;
    const dark = globalThis.matchMedia("(prefers-color-scheme: dark)").matches;
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
      timeScale: {
        timeVisible: false,
        tickMarkFormatter: (time: number) => String(time - 1 - window_),
      },
      rightPriceScale: { borderVisible: false },
      localization: { timeFormatter: (time: number) => `bar ${time - 1 - window_}` },
    });

    for (const match of data.matches.slice(0, topN)) {
      const end = match.pattern_path[match.pattern_path.length - 1] ?? 0;
      const points = [
        ...match.pattern_path.map((value, x) => ({ time: asTime(x), value })),
        ...match.outcome_path.slice(1).map((value, i) => ({
          time: asTime(window_ + 1 + i),
          value: end + value,
        })),
      ];
      const series = chart.addSeries(LineSeries, {
        color: dark ? "rgba(148,163,184,0.5)" : "rgba(100,116,139,0.5)",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      series.setData(points);
    }

    const now = chart.addSeries(LineSeries, {
      color: "#f59e0b",
      lineWidth: 3,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    now.setData(data.current_path.map((value, x) => ({ time: asTime(x), value })));
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [data, topN]);

  if (!data.available) {
    return <p className="text-sm text-slate-500">{data.reason ?? "No analogues available."}</p>;
  }
  return (
    <div
      ref={container}
      role="img"
      aria-label="Current pattern (amber) against the top historical analogues (grey), in ATR units"
      className="h-64 w-full"
    />
  );
}
