"use client";

import { useEffect, useRef } from "react";
import { RR_NOT_A_SIGNAL, fibLevels, rayEnd, rrForTarget, rrGeometry, type Drawing, type Pt } from "@/lib/drawings";

/** Chart <-> data conversions the layer needs; supplied by the chart (null while it has no data). */
export interface DrawingApi {
  toX: (t: number) => number | null;
  toY: (p: number) => number | null;
  toT: (x: number) => number | null;
  toP: (y: number) => number | null;
}

interface Props {
  drawings: Drawing[];
  draft: Drawing | null;
  selectedId: string | null;
  api: DrawingApi | null;
  width: number;
  height: number;
  onSelect: (id: string | null) => void;
  onChange: (id: string, patch: Partial<Drawing>) => void;
  onDelete: (id: string) => void;
  /** a drawing / measuring / level tool is active: existing drawings must not steal its clicks */
  passive: boolean;
}

type DragMode = "a" | "b" | "body" | "tp";

const fixed = (v: number) => v.toFixed(2);
const HIT = 10;

/**
 * The trader's own drawings as an SVG layer above the chart. Everything is positioned from (time, price) on every
 * render; the chart bumps a version number whenever its view changes. Strokes (and the box of a zone) take the
 * pointer; the empty rest of the layer lets the chart pan and zoom as usual.
 */
export function DrawingLayer({ drawings, draft, selectedId, api, width, height, onSelect, onChange, onDelete, passive }: Props) {
  const svg = useRef<SVGSVGElement>(null);
  const drag = useRef<{ id: string; mode: DragMode; start: { x: number; y: number }; a: Pt; b: Pt; ax: number; ay: number; bx: number; by: number; drawing: Drawing } | null>(null);

  // Delete / Backspace removes the selected drawing (never while typing in a field)
  useEffect(() => {
    if (!selectedId) return;
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable)) return;
      if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        onDelete(selectedId);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedId, onDelete]);

  if (!api) return null;

  const local = (e: { clientX: number; clientY: number }) => {
    const r = svg.current?.getBoundingClientRect();
    return r ? { x: e.clientX - r.left, y: e.clientY - r.top } : null;
  };

  const begin = (e: React.PointerEvent, d: Drawing, mode: DragMode) => {
    e.stopPropagation();
    onSelect(d.id);
    const at = local(e);
    if (!at || d.locked) return;
    const ax = api.toX(d.a.t);
    const ay = api.toY(d.a.p);
    const bx = api.toX(d.b.t);
    const by = api.toY(d.b.p);
    if (ax === null || ay === null || bx === null || by === null) return;
    drag.current = { id: d.id, mode, start: at, a: d.a, b: d.b, ax, ay, bx, by, drawing: d };
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
  };

  const move = (e: React.PointerEvent) => {
    const g = drag.current;
    const at = local(e);
    if (!g || !at) return;
    const dx = at.x - g.start.x;
    const dy = at.y - g.start.y;
    const point = (x: number, y: number): Pt | null => {
      const t = api.toT(x);
      const p = api.toP(y);
      return t === null || p === null || !(p > 0) ? null : { t: Math.round(t), p: Math.round(p * 100) / 100 };
    };
    if (g.mode === "a") {
      const a = point(g.ax + dx, g.ay + dy);
      if (a) onChange(g.id, g.drawing.kind === "vline" ? { a, b: a } : { a });
    } else if (g.mode === "b") {
      const b = point(g.bx + dx, g.by + dy);
      if (b) onChange(g.id, { b });
    } else if (g.mode === "tp") {
      const p = api.toP(g.start.y + dy);
      if (p !== null) onChange(g.id, { rr: rrForTarget(g.a.p, g.b.p, p) });
    } else {
      const a = point(g.ax + dx, g.ay + dy);
      const b = point(g.bx + dx, g.by + dy);
      if (a && b) onChange(g.id, g.drawing.kind === "vline" ? { a, b: a } : { a, b });
    }
  };

  const end = (e: React.PointerEvent) => {
    drag.current = null;
    (e.currentTarget as Element).releasePointerCapture?.(e.pointerId);
  };

  const handle = (d: Drawing, mode: DragMode, x: number, y: number, key: string) =>
    d.id === selectedId && !d.locked ? (
      <circle key={key} data-testid={`drawing-handle-${mode}`} cx={x} cy={y} r={5} fill="#fff" stroke={d.color} strokeWidth={2} style={{ cursor: "grab", pointerEvents: passive ? "none" : "all" }} onPointerDown={(e) => begin(e, d, mode)} onPointerMove={move} onPointerUp={end} />
    ) : null;

  const render = (d: Drawing, preview = false) => {
    const ax = api.toX(d.a.t);
    const ay = api.toY(d.a.p);
    const bx = api.toX(d.b.t);
    const by = api.toY(d.b.p);
    if (ax === null || ay === null) return null;
    const sel = d.id === selectedId && !preview;
    const common = { stroke: d.color, strokeWidth: sel ? 2.5 : 1.5, fill: "none" as const };
    const body = (extra: React.SVGProps<SVGGElement> = {}) => ({
      "data-testid": preview ? "drawing-draft" : `drawing-${d.id}`,
      "data-kind": d.kind,
      "data-selected": sel ? "true" : "false",
      style: { pointerEvents: preview || passive ? "none" : "all", cursor: d.locked ? "pointer" : "move" } as React.CSSProperties,
      onPointerDown: preview ? undefined : (e: React.PointerEvent) => begin(e, d, "body"),
      onPointerMove: preview ? undefined : move,
      onPointerUp: preview ? undefined : end,
      ...extra,
    });
    const tag = (x: number, y: number, text: string, anchor: "start" | "end" = "start") => (
      <text x={x} y={y} fontSize={11} fontWeight={600} textAnchor={anchor} fill={d.color} stroke="rgba(255,255,255,0.85)" strokeWidth={3} paintOrder="stroke" style={{ pointerEvents: "none" }}>
        {text}
      </text>
    );
    const caption = d.label ? tag(ax + 6, ay - 6, d.label) : null;

    if (d.kind === "vline") {
      return (
        <g key={d.id} {...body()}>
          <line x1={ax} y1={0} x2={ax} y2={height} stroke="transparent" strokeWidth={HIT} />
          <line x1={ax} y1={0} x2={ax} y2={height} {...common} strokeDasharray="6 4" />
          {d.label ? tag(ax + 4, 14, d.label) : null}
          {handle(d, "a", ax, 40, `${d.id}-a`)}
        </g>
      );
    }
    if (bx === null || by === null) return null;

    if (d.kind === "trend" || d.kind === "ray") {
      const far = d.kind === "ray" ? rayEnd(ax, ay, bx, by, width) : { x: bx, y: by };
      const to = far ?? { x: bx, y: by };
      return (
        <g key={d.id} {...body()}>
          <line x1={ax} y1={ay} x2={to.x} y2={to.y} stroke="transparent" strokeWidth={HIT} />
          <line x1={ax} y1={ay} x2={to.x} y2={to.y} {...common} />
          {caption}
          {handle(d, "a", ax, ay, `${d.id}-a`)}
          {handle(d, "b", bx, by, `${d.id}-b`)}
        </g>
      );
    }
    if (d.kind === "rect") {
      const x = Math.min(ax, bx);
      const y = Math.min(ay, by);
      return (
        <g key={d.id} {...body()}>
          <rect x={x} y={y} width={Math.abs(bx - ax)} height={Math.abs(by - ay)} {...common} fill={`${d.color}22`} />
          <text x={x + 4} y={y + 13} fontSize={11} fontWeight={600} fill={d.color} stroke="rgba(255,255,255,0.85)" strokeWidth={3} paintOrder="stroke" style={{ pointerEvents: "none" }}>
            {d.label || `${fixed(Math.max(d.a.p, d.b.p))} – ${fixed(Math.min(d.a.p, d.b.p))}`}
          </text>
          {handle(d, "a", ax, ay, `${d.id}-a`)}
          {handle(d, "b", bx, by, `${d.id}-b`)}
        </g>
      );
    }
    if (d.kind === "fib") {
      const x0 = Math.min(ax, bx);
      const x1 = width;
      return (
        <g key={d.id} {...body()}>
          <line x1={ax} y1={ay} x2={bx} y2={by} {...common} strokeDasharray="3 3" strokeWidth={1} />
          {fibLevels(d.a, d.b).map((l) => {
            const y = api.toY(l.price);
            if (y === null) return null;
            return (
              <g key={l.ratio}>
                <line x1={x0} y1={y} x2={x1} y2={y} stroke="transparent" strokeWidth={HIT} />
                <line x1={x0} y1={y} x2={x1} y2={y} stroke={d.color} strokeWidth={l.ratio === 0.5 || l.ratio === 0.618 ? 1.8 : 1} strokeDasharray={l.ratio === 0 || l.ratio === 1 ? undefined : "5 4"} />
                {tag(Math.min(x0 + 4, x1 - 120), y - 3, `${l.ratio} · ${fixed(l.price)}`)}
              </g>
            );
          })}
          {caption}
          {handle(d, "a", ax, ay, `${d.id}-a`)}
          {handle(d, "b", bx, by, `${d.id}-b`)}
        </g>
      );
    }
    // rr: a manual analysis box, never a signal
    const g = rrGeometry(d);
    const tpY = api.toY(g.tp);
    const slY = api.toY(g.sl);
    const entryY = api.toY(g.entry);
    if (tpY === null || slY === null || entryY === null) return null;
    const x0 = Math.min(ax, Math.max(bx, ax + 40) - 40);
    const x1 = Math.max(bx, ax + 40);
    const isBuy = g.side === "BUY";
    return (
      <g key={d.id} {...body()}>
        <rect data-testid="rr-reward" x={x0} y={Math.min(entryY, tpY)} width={x1 - x0} height={Math.abs(tpY - entryY)} fill="rgba(22,163,74,0.18)" stroke="#16a34a" strokeWidth={sel ? 2 : 1} />
        <rect data-testid="rr-risk" x={x0} y={Math.min(entryY, slY)} width={x1 - x0} height={Math.abs(slY - entryY)} fill="rgba(220,38,38,0.18)" stroke="#dc2626" strokeWidth={sel ? 2 : 1} />
        <line x1={x0} y1={entryY} x2={x1} y2={entryY} stroke="#2563eb" strokeWidth={1.5} />
        {tag(x0 + 4, entryY - 3, `ENTRY ${fixed(g.entry)}`)}
        {tag(x0 + 4, isBuy ? slY + 12 : slY - 3, `SL ${fixed(g.sl)} (${isBuy ? "−" : "+"}${Math.round(g.riskPoints)} điểm)`)}
        {tag(x0 + 4, isBuy ? tpY - 3 : tpY + 12, `TP ${fixed(g.tp)} (${isBuy ? "+" : "−"}${Math.round(g.rewardPoints)} điểm) · R:R 1:${g.rr}`)}
        <text data-testid="rr-disclaimer" x={x0 + 4} y={Math.min(entryY, tpY, slY) - 18} fontSize={10} fontWeight={700} fill="#475569" stroke="rgba(255,255,255,0.85)" strokeWidth={3} paintOrder="stroke" style={{ pointerEvents: "none" }}>
          {RR_NOT_A_SIGNAL}
        </text>
        {handle(d, "a", x0, entryY, `${d.id}-a`)}
        {handle(d, "b", x1, slY, `${d.id}-b`)}
        {handle(d, "tp", x1, tpY, `${d.id}-tp`)}
      </g>
    );
  };

  return (
    <svg ref={svg} data-testid="drawing-layer" aria-label="Các nét vẽ của bạn trên biểu đồ (ghi chú, không ảnh hưởng quyết định)" className="absolute inset-0 z-[11] h-full w-full" style={{ pointerEvents: "none" }} width={width} height={height}>
      {drawings.map((d) => render(d))}
      {draft ? render(draft, true) : null}
    </svg>
  );
}
