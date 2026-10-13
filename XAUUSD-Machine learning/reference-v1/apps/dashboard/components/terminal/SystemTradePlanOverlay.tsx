"use client";

import type { DrawingApi } from "@/components/terminal/DrawingLayer";
import { allocateLabelSlots } from "@/lib/labelSlots";
import { ZONE_SHORT, formatInZone, type DisplayZone } from "@/lib/time";
import type { TradePlan, TradeView } from "@/lib/trade";

const GREEN = "#16a34a";
const RED = "#dc2626";
const BLUE = "#2563eb";
const AMBER = "#d97706";

const fmt = (v: number | null | undefined) => (v === null || v === undefined ? "—" : v.toFixed(2));
const clamp = (n: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, n));

interface Level {
  role: "entry" | "sl" | "tp1" | "tp2" | "now";
  price: number;
  y: number;
  label: string;
  color: string;
  dashed?: boolean;
}

interface OverlayModel {
  mode: "PLAN" | "POSITION";
  side: "BUY" | "SELL";
  entry: number;
  sl: number;
  tp1: number;
  tp2: number | null;
  now: number | null;
  rr: number | null;
  risk: number | null;
  expiresAt: string | null;
  evidence: string;
  validGeometry: boolean;
}

interface Props {
  api: DrawingApi | null;
  width: number;
  height: number;
  /** px at the top of the chart taken by the context legend: labels and the badge stay below it */
  topInset?: number;
  planLive: boolean;
  /** the Human action authorizes the open position's facts on the chart (action HOLD) */
  holdLive: boolean;
  /** the trader's display zone: the expiry label must read like the clock next to it */
  zone: DisplayZone;
  plan: TradePlan | null;
  view: TradeView | null;
  showPlan: boolean;
  showPaper: boolean;
}

function modelFromProps({ planLive, holdLive, plan, view, showPlan, showPaper }: Omit<Props, "api" | "width" | "height" | "topInset" | "zone">): OverlayModel | null {
  const position = view?.desk?.position;
  if (showPaper && holdLive && position && position.status === "OPEN") {
    const side = position.side === "SELL" ? "SELL" : "BUY";
    const entry = position.fill_price;
    const sl = position.sl;
    const tp1 = position.tp;
    const validGeometry = side === "BUY" ? sl < entry && entry < tp1 : tp1 < entry && entry < sl;
    return {
      mode: "POSITION",
      side,
      entry,
      sl,
      tp1,
      tp2: null,
      now: position.current_price ?? null,
      rr: position.unrealized_r ?? null,
      risk: position.risk_amount ?? null,
      expiresAt: position.max_hold_until ?? null,
      evidence: "PAPER · NOT A REAL-MONEY SIGNAL",
      validGeometry,
    };
  }
  if (!showPlan || !planLive || !plan || !plan.complete) return null;
  if (plan.planned_entry === null || plan.sl === null || plan.tp1 === null) return null;
  const validGeometry = plan.side === "BUY" ? plan.sl < plan.planned_entry && plan.planned_entry < plan.tp1 : plan.tp1 < plan.planned_entry && plan.planned_entry < plan.sl;
  return {
    mode: "PLAN",
    side: plan.side,
    entry: plan.planned_entry,
    sl: plan.sl,
    tp1: plan.tp1,
    tp2: plan.tp2,
    now: null,
    rr: plan.rr_net,
    risk: plan.risk_amount,
    expiresAt: plan.expires_at,
    evidence: view?.evidence?.level ? `${view.evidence.level} · PAPER · NOT A REAL-MONEY SIGNAL` : "UNVALIDATED · PAPER · NOT A REAL-MONEY SIGNAL",
    validGeometry,
  };
}

export function SystemTradePlanOverlay(props: Props) {
  const model = modelFromProps(props);
  const { api, width, height, topInset = 0, zone } = props;
  if (!model || !api) return null;
  const w = Math.max(1, width);
  const h = Math.max(1, height);

  const toLevel = (role: Level["role"], price: number | null, label: string, color: string, dashed = false): Level | null => {
    if (price === null || !Number.isFinite(price)) return null;
    const y = api.toY(price);
    return y === null ? null : { role, price, y, label, color, dashed };
  };
  const levels = [
    toLevel("entry", model.entry, `${model.mode === "POSITION" ? "ACTUAL FILL" : `${model.side} ENTRY`} ${fmt(model.entry)}`, BLUE),
    toLevel("sl", model.sl, `${model.mode === "POSITION" ? "CURRENT SL" : "SL"} ${fmt(model.sl)}`, RED, true),
    toLevel("tp1", model.tp1, `${model.mode === "POSITION" ? "ACTIVE TP" : "TP1"} ${fmt(model.tp1)}`, GREEN, true),
    toLevel("tp2", model.tp2, `TP2 · THAM KHẢO ${fmt(model.tp2)}`, GREEN, true),
    toLevel("now", model.now, `NOW ${fmt(model.now)}`, AMBER, true),
  ].filter((x): x is Level => x !== null);
  const entry = levels.find((l) => l.role === "entry");
  const sl = levels.find((l) => l.role === "sl");
  const tp1 = levels.find((l) => l.role === "tp1");
  if (!entry || !sl || !tp1) return null;

  const x0 = 0;
  const x1 = w;
  const zoneStart = Math.max(0, w * 0.08);
  const zoneWidth = Math.max(120, w * 0.72);
  const labelX = clamp(10, 6, Math.max(6, w - 180));
  const PRIORITY: Record<Level["role"], number> = { entry: 0, sl: 1, tp1: 2, now: 3, tp2: 4 };
  const slots = allocateLabelSlots(levels.map((l) => ({ id: l.role, y: l.y - 5, priority: PRIORITY[l.role] })), Math.min(Math.max(14, topInset + 12), Math.max(14, h - 24)), h - 8, 16, 40);
  const sorted = [...levels].filter((l) => slots.has(l.role)).sort((a, b) => a.y - b.y);
  // the badge (44 px + the expiry line) goes to the first band that no plan label touches: a level label always wins
  const BADGE_H = 66;
  const labelYs = [...slots.values()];
  const badgeTop = (() => {
    const firstTop = Math.max(40, topInset + 6);
    const lastTop = Math.max(firstTop, h - BADGE_H - 4);
    for (let top = firstTop; top <= lastTop; top += 8) {
      if (labelYs.every((ly) => ly < top - 6 || ly > top + BADGE_H + 4)) return top;
    }
    return clamp(Math.min(entry.y, sl.y, tp1.y) - 52, 4, Math.max(4, h - 54)); // no free band: the old placement
  })();
  const action = model.mode === "POSITION" ? "GIỮ" : model.side === "BUY" ? "MUA" : "BÁN";
  const rrText = model.mode === "POSITION" ? (model.rr === null ? "R hiện tại —" : `R hiện tại ${model.rr.toFixed(2)}`) : model.rr === null ? "R:R —" : `R:R 1:${model.rr.toFixed(2)}`;

  return (
    <svg
      data-testid="system-plan-overlay"
      data-mode={model.mode}
      data-side={model.side}
      data-valid-geometry={model.validGeometry ? "true" : "false"}
      aria-label="System trade plan overlay, read-only visualization of the backend decision"
      className="pointer-events-none absolute inset-0 z-[12] h-full w-full"
      width={w}
      height={h}
    >
      <rect data-testid="system-reward-zone" x={zoneStart} y={Math.min(entry.y, tp1.y)} width={zoneWidth} height={Math.max(1, Math.abs(tp1.y - entry.y))} fill="rgba(22,163,74,0.13)" />
      <rect data-testid="system-risk-zone" x={zoneStart} y={Math.min(entry.y, sl.y)} width={zoneWidth} height={Math.max(1, Math.abs(sl.y - entry.y))} fill="rgba(220,38,38,0.13)" />
      {levels.map((l) => (
        <g key={l.role} data-testid={`system-line-${l.role}`} data-role={l.role} data-price={l.price} data-y={l.y} data-reprice={api.toP(l.y) ?? undefined}>
          <line x1={x0} y1={l.y} x2={x1} y2={l.y} stroke={l.color} strokeWidth={l.role === "tp2" || l.role === "now" ? 1 : 1.7} strokeDasharray={l.dashed ? "7 5" : undefined} opacity={l.role === "tp2" ? 0.72 : 0.95} />
        </g>
      ))}
      {sorted.map((l) => (
        <text key={`${l.role}-label`} x={labelX} y={slots.get(l.role)} fill={l.color} fontSize={11} fontWeight={800} stroke="rgba(255,255,255,0.9)" strokeWidth={3} paintOrder="stroke">
          {l.label}
        </text>
      ))}
      <g data-testid="system-action-badge">
        <rect x={8} y={badgeTop} width={Math.min(w - 16, 286)} height={44} rx={6} fill={model.side === "BUY" ? "rgba(22,101,52,0.92)" : "rgba(153,27,27,0.92)"} stroke={model.validGeometry ? "rgba(255,255,255,0.7)" : "#f59e0b"} />
        <text x={18} y={badgeTop + 17} fill="#fff" fontSize={13} fontWeight={900}>
          {action} · {rrText}
        </text>
        <text x={18} y={badgeTop + 34} fill="#fff" fontSize={10} fontWeight={800}>
          {model.evidence}
        </text>
      </g>
      {!model.validGeometry && (
        <text x={18} y={clamp(badgeTop + 62, 20, h - 8)} fill="#f59e0b" fontSize={11} fontWeight={900} stroke="rgba(15,23,42,0.9)" strokeWidth={3} paintOrder="stroke">
          GEOMETRY INCONSISTENCY: backend levels not in expected order
        </text>
      )}
      {model.expiresAt && (
        <text x={18} y={clamp(badgeTop + 58, 20, h - 8)} fill="#475569" fontSize={10} fontWeight={800} stroke="rgba(255,255,255,0.86)" strokeWidth={3} paintOrder="stroke">
          {model.mode === "POSITION" ? "TIME EXIT" : "EXPIRES"} {formatInZone(model.expiresAt, zone).slice(11, 16)} {ZONE_SHORT[zone]}
        </text>
      )}
    </svg>
  );
}
