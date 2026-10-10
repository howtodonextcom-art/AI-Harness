"use client";

import type { DrawingApi } from "@/components/terminal/DrawingLayer";
import type { NewsEventItem, NewsView } from "@/lib/trade";
import { formatInZone, type DisplayZone } from "@/lib/time";

const BEFORE_MIN = 30; // the engine's news window: 30 minutes before ...
const AFTER_MIN = 15; // ... and 15 minutes after a high-impact event

interface Props {
  news: NewsView | undefined;
  api: DrawingApi | null;
  zone: DisplayZone;
  width: number;
  height: number;
}

const clip = (text: string, n: number) => (text.length > n ? `${text.slice(0, n - 1)}…` : text);

/**
 * Upcoming calendar events as vertical dashed lines with a short tag (red = high, amber = medium) and, for a
 * high-impact event, a faint band over the window the news guard blocks. Read-only: the server's calendar, nothing
 * the trader can edit, never a signal. Chosen over a shaded-only and an axis-flag design by a blind review.
 */
export function NewsMarkers({ news, api, zone, width, height }: Props) {
  if (!news || !api) return null;
  const items: NewsEventItem[] = [...(news.blocked_by ? [news.blocked_by] : []), ...news.next_events.filter((e) => e.time !== news.blocked_by?.time)];
  const placed: { x: number; e: NewsEventItem }[] = [];
  for (const e of items) {
    const x = api.toX(Date.parse(e.time) / 1000);
    if (x !== null && x >= 0 && x <= width) placed.push({ x, e });
  }
  if (placed.length === 0) return null;
  placed.sort((a, b) => a.x - b.x);
  let lastX = -1e9;
  let row = 0;
  return (
    <svg data-testid="news-markers" aria-hidden="true" className="pointer-events-none absolute inset-0 z-[10] h-full w-full" width={width} height={height}>
      {placed.map(({ x, e }) => {
        row = x - lastX < 120 ? (row + 1) % 3 : 0; // events close in time stagger their tags instead of overlapping
        lastX = x;
        const high = e.impact === "high";
        const color = high ? "#dc2626" : "#d97706";
        const left = api.toX(Date.parse(e.time) / 1000 - BEFORE_MIN * 60);
        const right = api.toX(Date.parse(e.time) / 1000 + AFTER_MIN * 60);
        const flip = x > width - 150; // near the right edge the tag goes to the left of the line
        const label = `${formatInZone(e.time, zone).slice(11, 16)} ${e.currency ? `${e.currency} ` : ""}${clip(e.title, 22)}`;
        return (
          <g key={`${e.time}-${e.title}`} data-testid="news-marker" data-impact={e.impact} data-title={e.title}>
            {high && left !== null && right !== null ? <rect data-testid="news-window" x={Math.min(left, right)} y={0} width={Math.abs(right - left)} height={height} fill="rgba(220,38,38,0.07)" /> : null}
            <line x1={x} x2={x} y1={0} y2={height} stroke={color} strokeWidth={high ? 1.6 : 1} strokeDasharray={high ? "5 4" : "2 4"} />
            <text x={flip ? x - 4 : x + 4} y={12 + row * 13} textAnchor={flip ? "end" : "start"} fontSize={11} fontWeight={700} fill={color} stroke="rgba(255,255,255,0.9)" strokeWidth={3} paintOrder="stroke">
              {label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
