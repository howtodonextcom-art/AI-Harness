/**
 * Honesty on the fold: evidence class + forward coverage vs the existing 95% gate.
 * The browser does not invent a class; it only formats server fields.
 */

import type { TradeView } from "@/lib/trade";

export const COVERAGE_GATE_PCT = 95;

export interface HonestyLine {
  /** VALIDATED / UNVALIDATED — English term kept next to the Vietnamese gloss */
  label: "VALIDATED" | "UNVALIDATED";
  gloss: string;
  coverageText: string;
  gate: number;
  belowGate: boolean;
  consequence: string;
}

export function honestyLine(view: TradeView): HonestyLine {
  const validated = view.evidence.validated_edge === true;
  const cov = view.decision_coverage;
  const pct = cov?.coverage_pct ?? view.forward_acceptance?.coverage_pct ?? null;
  const gate = cov?.threshold_pct ?? COVERAGE_GATE_PCT;
  const coverageText = pct === null || pct === undefined ? "—" : `${pct.toFixed(1)}%`;
  const belowGate = pct !== null && pct !== undefined && pct < gate;
  const consequence = validated
    ? "lợi thế đã kiểm chứng"
    : belowGate
      ? `độ phủ ${coverageText} < cổng ${gate}% — “chưa thấy setup” chưa chứng minh được gì`
      : pct === null || pct === undefined
        ? "chưa phải lợi thế đã kiểm chứng; độ phủ forward chưa đo"
        : "chưa phải lợi thế đã kiểm chứng";
  return {
    label: validated ? "VALIDATED" : "UNVALIDATED",
    gloss: validated ? "ĐÃ KIỂM CHỨNG" : "CHƯA KIỂM CHỨNG",
    coverageText,
    gate,
    belowGate,
    consequence,
  };
}

export function heroLevels(view: TradeView): { entry: number | null; sl: number | null; tp: number | null; rr: number | null } {
  const plan = view.trade_plan ?? null;
  const pos = view.desk?.position ?? null;
  return {
    entry: plan?.planned_entry ?? pos?.fill_price ?? null,
    sl: plan?.sl ?? pos?.sl ?? null,
    tp: plan?.tp1 ?? pos?.tp ?? null,
    rr: plan?.rr_net ?? null,
  };
}
