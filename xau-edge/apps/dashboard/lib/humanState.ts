/**
 * The ONE Human state of the desk, and what each surface may show in it.
 *
 * Why this exists: MCP QA round 3 (2026-10-11) found a screen that said CHỜ in the hero while the chart drew a
 * "MUA · R:R" badge with Entry/SL/TP and a phone bar said "SẴN SÀNG MUA". Each surface had decided for itself from
 * `hero.state` or from the mere presence of a plan. Now every surface asks this table, and the table is driven by the
 * server-authorized Human action (`hero.action`), never by the plan, the signal side or `hero.state` alone.
 *
 * Authority: a BUY/SELL surface (overlay, sticky open bar, ticket, Entry/SL/TP in the hero) exists only when
 * `action.code` is BUY or SELL with stage READY, the plan is complete, nothing is stale or expired. A setup that
 * is READY but blocked is WAIT_BLOCKED: no permission look anywhere; its numbers live in a clearly labelled,
 * folded "reference only" block.
 */
import type { TradeView } from "@/lib/trade";

export type HumanStateId =
  | "UNAVAILABLE"
  | "MARKET_CLOSED"
  | "WAIT_NO_SETUP"
  | "WAIT_NO_TRIGGER"
  | "WAIT_BLOCKED"
  | "BUY_READY"
  | "SELL_READY"
  | "HOLD"
  | "EXIT"
  | "EXPIRED"
  | "INVALIDATED";

export interface HumanSurface {
  id: HumanStateId;
  /** the Human action word's code */
  action: "WAIT" | "BUY" | "SELL" | "HOLD" | "EXIT" | "UNAVAILABLE";
  /** the system plan overlay on the chart: PLAN (a ready BUY/SELL), POSITION (the open trade's facts) or nothing */
  overlay: "PLAN" | "POSITION" | null;
  /** the phone's sticky bar: open a trade, close the trade, or no bar */
  stickyBar: "OPEN" | "CLOSE" | null;
  /** the full ticket (the plan with the "Mở lệnh" button) */
  ticket: boolean;
  /** the folded, labelled "SETUP BỊ CHẶN — chỉ tham khảo" block */
  referencePlan: boolean;
  /** which numbers the hero's Entry/SL/TP row shows: the plan, the open position's actual facts, or none */
  heroLevels: "PLAN" | "FILL" | null;
  /** plan price lines on the chart */
  planLines: boolean;
}

const NONE: Omit<HumanSurface, "id" | "action"> = { overlay: null, stickyBar: null, ticket: false, referencePlan: false, heroLevels: null, planLines: false };

/** Everything a surface may show, per state. This table is the contract (and is tested). */
export const SURFACES: Record<HumanStateId, Omit<HumanSurface, "id" | "action">> = {
  UNAVAILABLE: NONE,
  MARKET_CLOSED: NONE,
  WAIT_NO_SETUP: NONE,
  WAIT_NO_TRIGGER: NONE,
  WAIT_BLOCKED: { ...NONE, referencePlan: true },
  BUY_READY: { overlay: "PLAN", stickyBar: "OPEN", ticket: true, referencePlan: false, heroLevels: "PLAN", planLines: true },
  SELL_READY: { overlay: "PLAN", stickyBar: "OPEN", ticket: true, referencePlan: false, heroLevels: "PLAN", planLines: true },
  HOLD: { overlay: "POSITION", stickyBar: "CLOSE", ticket: false, referencePlan: false, heroLevels: "FILL", planLines: false },
  EXIT: NONE,
  EXPIRED: NONE,
  INVALIDATED: NONE,
};

export interface HumanInputs {
  /** the plan's server-clock expiry has passed */
  expiredNow: boolean;
  /** no connection, or data stopped arriving */
  offline: boolean;
}

/** The Human state, from the server-authorized action first; the plan and `hero.state` only add context. */
export function humanState(view: TradeView, { expiredNow, offline }: HumanInputs): HumanStateId {
  const a = view.hero.action;
  if (offline || a.code === "UNAVAILABLE") return "UNAVAILABLE";
  if (a.code === "HOLD") return "HOLD";
  if (a.code === "EXIT") return "EXIT";
  if (view.hero.state === "MARKET_CLOSED" || a.stage === "CLOSED") return "MARKET_CLOSED";
  if (a.code === "BUY" || a.code === "SELL") {
    if (expiredNow) return "EXPIRED";
    const complete = Boolean(view.trade_plan?.complete);
    if (a.stage !== "READY" || !complete) return "WAIT_NO_SETUP"; // never a permission look without a complete READY plan
    return a.code === "BUY" ? "BUY_READY" : "SELL_READY";
  }
  if (a.stage === "BLOCKED") return expiredNow ? "EXPIRED" : "WAIT_BLOCKED";
  if (a.stage === "EXPIRED" || expiredNow) return "EXPIRED";
  if (a.stage === "INVALIDATED") return "INVALIDATED";
  if (a.stage === "ARMED" || a.missing === "TRIGGER") return "WAIT_NO_TRIGGER";
  return "WAIT_NO_SETUP";
}

export function humanSurface(view: TradeView, inputs: HumanInputs): HumanSurface {
  const id = humanState(view, inputs);
  const action = id === "BUY_READY" ? "BUY" : id === "SELL_READY" ? "SELL" : id === "HOLD" ? "HOLD" : id === "EXIT" ? "EXIT" : id === "UNAVAILABLE" ? "UNAVAILABLE" : "WAIT";
  return { id, action, ...SURFACES[id] };
}
