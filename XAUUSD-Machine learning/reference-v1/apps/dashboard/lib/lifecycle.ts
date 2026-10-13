/**
 * The signal lifecycle as the trader reads it: Thiên hướng -> Setup -> Trigger -> Sẵn sàng -> Mở PAPER -> Giữ -> Thoát,
 * and "what happened last" for the long stretches where the action is only CHỜ. Everything comes from server facts
 * (hero.action, setup history rows, paper journal, last exit); nothing here decides anything.
 */

import { sideWord } from "@/lib/action";
import type { JournalResponse, SetupHistoryRow, TradeView } from "@/lib/trade";
import { EXIT_REASON_VI } from "@/lib/vi";

export type StepStatus = "done" | "current" | "pending";
export interface Step {
  key: "BIAS" | "SETUP" | "TRIGGER" | "READY" | "OPENED" | "HOLD" | "EXIT";
  label: string;
  status: StepStatus;
  /** ISO instant when the server recorded it, if known */
  at: string | null;
}

const LABEL: Record<Step["key"], string> = {
  BIAS: "Thiên hướng",
  SETUP: "Setup",
  TRIGGER: "Trigger",
  READY: "Sẵn sàng",
  OPENED: "Mở PAPER",
  HOLD: "Giữ",
  EXIT: "Thoát",
};
const ORDER: Step["key"][] = ["BIAS", "SETUP", "TRIGGER", "READY", "OPENED", "HOLD", "EXIT"];

/** null when the lifecycle is not meaningful right now (closed market, error, blocked or dead setup). */
export function lifecycleSteps(view: TradeView, setups: SetupHistoryRow[] | null): Step[] | null {
  const a = view.hero.action;
  let current: Step["key"] | null = null;
  if (a.code === "EXIT") current = "EXIT";
  else if (a.code === "HOLD") current = "HOLD";
  else if (a.code === "BUY" || a.code === "SELL") current = "READY";
  else if (a.code === "WAIT" && a.stage === "ARMED") current = "TRIGGER";
  else if (a.code === "WAIT" && a.stage === "WATCHING") current = "SETUP";
  else if (a.code === "WAIT" && a.stage === "WAITING") current = "BIAS";
  if (current === null) return null;
  const at = (k: Step["key"]): string | null => {
    if (k === "SETUP") return setups?.find((r) => r.outcome === "ARMED" || r.outcome === "TRIGGERED")?.armed_at ?? null;
    if (k === "OPENED") return view.desk?.position?.opened_at ?? null;
    if (k === "EXIT") return view.desk?.last_exit?.closed_at ?? null;
    return null;
  };
  const idx = ORDER.indexOf(current);
  return ORDER.map((key, i) => ({
    key,
    label: LABEL[key],
    status: i < idx ? "done" : i === idx ? (key === "EXIT" ? "done" : "current") : "pending",
    at: i <= idx ? at(key) : null,
  }));
}

/**
 * "Lần gần nhất": the newest lifecycle fact the server logged, in one sentence. `fmt` formats an ISO instant in the trader's zone.
 * A signal that the trader did not take is said plainly ("không mở PAPER") only when the journal proves no paper trade was opened then.
 */
export function lastEventText(view: TradeView, setups: SetupHistoryRow[] | null, journal: JournalResponse | null, fmt: (iso: string) => string): string | null {
  const cands: { at: string; text: string }[] = [];
  const x = view.desk?.last_exit;
  if (x?.closed_at) {
    cands.push({ at: x.closed_at, text: `Lệnh ${sideWord(x.side)} PAPER đã đóng (${EXIT_REASON_VI[x.exit_reason ?? ""] ?? x.exit_reason ?? "?"}) lúc ${fmt(x.closed_at)}` });
  }
  const opened = (journal?.trades ?? []).map((t) => (t.opened_at ? Date.parse(t.opened_at) : NaN)).filter(Number.isFinite);
  for (const r of setups ?? []) {
    const side = sideWord(r.side);
    const label = side ? `Setup ${side}` : "Setup";
    if (r.outcome === "INVALIDATED") cands.push({ at: r.last_seen, text: `${label} bị vô hiệu lúc ${fmt(r.last_seen)}` });
    else if (r.outcome === "EXPIRED") cands.push({ at: r.last_seen, text: `${label} hết hiệu lực lúc ${fmt(r.last_seen)}` });
    else if (r.outcome === "TRIGGERED" && r.actionable) {
      const t0 = Date.parse(r.first_seen);
      const t1 = Date.parse(r.last_seen) + 10 * 60_000;
      const taken = opened.some((o) => o >= t0 && o <= t1);
      cands.push({ at: r.last_seen, text: `Tín hiệu ${side || ""} lúc ${fmt(r.first_seen)}${taken ? ", đã mở PAPER" : ", không mở PAPER"}`.replace("  ", " ") });
    } else if (r.outcome === "TRIGGERED") cands.push({ at: r.last_seen, text: `${label} đã kích hoạt lúc ${fmt(r.last_seen)} nhưng không đủ điều kiện để vào lệnh` });
  }
  if (cands.length === 0) return null;
  cands.sort((p, q) => Date.parse(q.at) - Date.parse(p.at));
  return cands[0].text;
}
