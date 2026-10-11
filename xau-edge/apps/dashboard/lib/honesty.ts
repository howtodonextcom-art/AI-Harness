/**
 * Honesty on the fold: evidence class + forward coverage vs the existing 95% gate.
 * The browser does not invent a class; it only formats server fields.
 */

import type { TradeView } from "@/lib/trade";

export const COVERAGE_GATE_PCT = 95;

/** The human evidence ladder, lowest first. BUY/SELL may show at any level; the label always goes with it. */
export const EVIDENCE_LADDER: Record<string, { label: string; gloss: string; copy: string }> = {
  UNVALIDATED: { label: "UNVALIDATED", gloss: "CHƯA KIỂM CHỨNG", copy: "Baseline vận hành. Chưa có bằng chứng kỳ vọng dương." },
  DEVELOPMENT_CANDIDATE: { label: "DEVELOPMENT CANDIDATE", gloss: "ỨNG VIÊN DEV", copy: "Mới qua Dev. Chưa qua Val, chưa phải bằng chứng." },
  VALIDATED_CANDIDATE: { label: "VALIDATED CANDIDATE", gloss: "ĐÃ QUA DEV + VAL", copy: "Đã qua Dev + Val. Chưa qua Test-H." },
  OOS_VALIDATED: { label: "OOS VALIDATED", gloss: "ĐÃ QUA TEST-H", copy: "Đã qua Test-H. Chưa qua holdout." },
  HOLDOUT_VALIDATED: { label: "HOLDOUT VALIDATED", gloss: "ĐÃ QUA HOLDOUT", copy: "Đã qua Test-H + holdout. Chưa có forward paper đủ mẫu." },
  FORWARD_PAPER_VALIDATED: { label: "FORWARD PAPER VALIDATED", gloss: "ĐÃ QUA FORWARD PAPER", copy: "Đã qua forward paper đủ mẫu. Chưa phải tiền thật." },
  DEMO_CANDIDATE: { label: "DEMO CANDIDATE", gloss: "ỨNG VIÊN DEMO", copy: "Đủ điều kiện xem xét DEMO. Không phải khuyến nghị tiền thật." },
};

export interface HonestyLine {
  /** a rung of EVIDENCE_LADDER (English term kept next to the Vietnamese gloss) */
  label: string;
  level: string;
  gloss: string;
  /** what the level means, in one sentence */
  copy: string;
  coverageText: string;
  gate: number;
  belowGate: boolean;
  consequence: string;
}

export function honestyLine(view: TradeView): HonestyLine {
  const validated = view.evidence.validated_edge === true;
  // an unknown or missing level falls to the lowest rung: the browser never raises the evidence
  const level = view.evidence.level && EVIDENCE_LADDER[view.evidence.level] ? view.evidence.level : "UNVALIDATED";
  const rung = EVIDENCE_LADDER[level];
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
    label: rung.label,
    level,
    gloss: rung.gloss,
    copy: rung.copy,
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
