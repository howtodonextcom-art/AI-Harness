"use client";

import { useState } from "react";
import type { PaperTrade, TradeView } from "@/lib/trade";
import { BAD, Card, GOOD, INFO, NEUTRAL, Pill, Row, TONE_ICON, TONE_STYLE, WARN, fmt, money } from "@/components/trade/ui";

interface Props {
  view: TradeView;
  nowMs: number;
  risk: number;
  onRisk: (r: number) => void;
  onOpen: () => void;
  busy: boolean;
  uiStale: boolean;
}

/** Hero state + trade plan + the (confirmed) paper action. The state itself comes from the server. */
export function HeroPanel({ view, nowMs, risk, onRisk, onOpen, busy, uiStale }: Props) {
  const [confirming, setConfirming] = useState(false);
  const hero = view.hero;
  const plan = view.trade_plan ?? null;
  const expiresMs = plan?.expires_at ? Date.parse(plan.expires_at) : null;
  const expiredNow = plan !== null && (plan.expired || (expiresMs !== null && expiresMs <= nowMs));
  const secondsLeft = expiresMs === null ? null : Math.max(0, Math.round((expiresMs - nowMs) / 1000));
  const showExpired = expiredNow && (hero.state === "BUY_READY" || hero.state === "SELL_READY");
  const label = showExpired ? "EXPIRED SETUP" : hero.label;
  const toneKey = showExpired ? "warn" : hero.tone;
  const icon = showExpired ? TONE_ICON.EXPIRED_SETUP : (TONE_ICON[hero.state] ?? "•");
  const blockers = view.entry_blockers ?? [];
  const chosen = view.risk_plans?.find((p) => Math.abs(p.risk_pct - risk) < 1e-9);
  const canOpen = Boolean(view.actionable && !expiredNow && !uiStale && plan?.complete && chosen?.ok);
  const showPlan = plan !== null && hero.state !== "UNAVAILABLE" && hero.state !== "STALE";

  return (
    <Card title="Quyết định hiện tại" testId="decision-card">
      <div className={`rounded-lg border-2 px-4 py-3 ${TONE_STYLE[toneKey] ?? NEUTRAL}`} data-testid="hero" data-hero-state={showExpired ? "EXPIRED_SETUP" : hero.state}>
        <div className="flex flex-wrap items-center gap-3">
          <span aria-hidden="true" className="text-3xl leading-none">{icon}</span>
          <span data-testid="decision" className="text-2xl font-black leading-tight">{label}</span>
          {plan && !expiredNow && secondsLeft !== null && (
            <span data-testid="expiry" className="text-sm">
              còn hiệu lực <b>{Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, "0")}</b>
            </span>
          )}
        </div>
        <p data-testid="hero-detail" className="mt-1 text-sm">{showExpired ? "Kế hoạch đã hết hạn, không còn mở được" : hero.detail}</p>
      </div>

      {hero.state === "WAIT" || hero.state === "SETUP_ARMED" ? (
        <p data-testid="blocked-by" className="mt-2 text-sm">
          Blocked by: <b>{(view.why_wait?.blocked_by ?? []).join(", ") || "—"}</b>
        </p>
      ) : null}

      <div className="mt-2 flex flex-wrap gap-1.5">
        <Pill label="bằng chứng" value="CHƯA KIỂM CHỨNG" tone={WARN} testId="evidence-pill" />
        {view.news?.warning && <Pill label="tin tức" value="CHƯA XÁC MINH (NEWS NOT VERIFIED)" tone={WARN} testId="news-warning" />}
        {view.setup?.phase && view.setup.phase !== "NONE" && (
          <Pill label="setup" value={view.setup.phase} tone={view.setup.phase === "TRIGGERED" ? GOOD : INFO} testId="setup-phase" />
        )}
      </div>

      {view.alerts?.this_setup?.announced && (hero.state === "BUY_READY" || hero.state === "SELL_READY") && (
        <p data-testid="setup-ready-alert" className="mt-2 rounded-md border border-sky-600 bg-sky-500/10 px-2 py-1 text-xs">
          SETUP READY {hero.side}: cảnh báo đã gửi qua {view.alerts.this_setup.channel === "TELEGRAM" ? "Telegram" : "file (alerts.jsonl)"} lúc{" "}
          {view.alerts.this_setup.at.slice(11, 16)} UTC (mỗi setup một lần)
        </p>
      )}

      {showPlan && plan && (
        <div data-testid="plan-card" className="mt-3 border-t border-slate-200 pt-2 dark:border-slate-800">
          {!plan.complete && (
            <p data-testid="plan-incomplete" className={`mb-2 rounded-md border px-2 py-1 text-sm font-semibold ${WARN}`}>
              SETUP DETECTED — NOT ACTIONABLE ({plan.missing.join(", ")})
            </p>
          )}
          <Row k={`Side`} v={plan.side} testId="plan-side" />
          <Row k={`Vào lệnh (MARKET, ${plan.entry_basis})`} v={fmt(plan.planned_entry)} testId="plan-entry" />
          <Row k="Stop loss" v={fmt(plan.sl)} testId="plan-sl" />
          <Row k="Take profit" v={fmt(plan.tp1)} testId="plan-tp" />
          {plan.tp2 !== null && <Row k="Take profit 2" v={fmt(plan.tp2)} testId="plan-tp2" />}
          <Row k="R/R (sau spread)" v={fmt(plan.rr_net)} testId="plan-rr" />
          <Row k="Rủi ro" v={`${fmt(risk, 2)}% · ${money(chosen ? -chosen.loss_at_sl : null)}`} testId="plan-risk" />
          <Row k="Lot" v={fmt(chosen?.lots, 2)} testId="plan-lots" />
          <Row k="Giá trị nếu chạm TP" v={money(chosen?.gain_at_tp)} testId="plan-tp-value" />
          <Row k="Chiến lược" v={`v${plan.strategy_version}`} testId="plan-version" />
          {plan.invalidation && <p className="mt-1 text-xs text-slate-500">Vô hiệu khi: {plan.invalidation}</p>}
          <div className="mt-2 flex flex-wrap items-center gap-2" role="group" aria-label="Mức rủi ro">
            {(view.risk_choices ?? [0.1, 0.25, 0.5]).map((r) => (
              <button
                key={r}
                type="button"
                data-testid={`risk-${r}`}
                aria-pressed={r === risk}
                onClick={() => onRisk(r)}
                className={`rounded-md border px-3 py-1 text-sm ${r === risk ? "border-sky-600 bg-sky-500/15 font-semibold" : "border-slate-400"}`}
              >
                {r.toFixed(2)}%
              </button>
            ))}
          </div>
          <p className="mt-1 text-xs text-slate-500" data-testid="paper-equity">
            {view.paper_account_label}: ${fmt(view.desk?.account.equity, 0)}
          </p>
          {chosen && !chosen.ok && <p className="text-sm text-red-600">{chosen.errors.join(", ")}</p>}

          {blockers.length > 0 && (
            <ul data-testid="blockers" className="mt-2 space-y-1 text-sm">
              {blockers.map((b) => (
                <li key={b.code} data-code={b.code} className={`rounded-md border px-2 py-1 ${b.code === "PAPER_STATE_ERROR" || b.code === "WRITER_LOCK" ? BAD : WARN}`}>
                  {b.message}
                </li>
              ))}
            </ul>
          )}

          {!confirming ? (
            <button
              type="button"
              data-testid="take-paper"
              disabled={!canOpen || busy}
              onClick={() => setConfirming(true)}
              className="mt-3 w-full rounded-md border border-sky-600 bg-sky-500/15 px-3 py-2 font-semibold disabled:opacity-40"
            >
              Mở lệnh PAPER {plan.side}
            </button>
          ) : (
            <div data-testid="confirm-card" role="alertdialog" aria-label="Xác nhận lệnh paper" className="mt-3 rounded-md border-2 border-emerald-600 p-2">
              <p className="mb-1 text-sm font-bold">XÁC NHẬN LỆNH PAPER {plan.side} (giả lập, không gửi lệnh thật)</p>
              <Row k="Entry (kế hoạch)" v={fmt(plan.planned_entry)} />
              <Row k="SL / TP" v={`${fmt(plan.sl)} / ${fmt(plan.tp1)}`} />
              <Row k="Rủi ro" v={`${fmt(risk, 2)}% · ${money(chosen ? -chosen.loss_at_sl : null)}`} />
              <Row k="Lot" v={fmt(chosen?.lots, 2)} />
              <Row k="R/R" v={fmt(plan.rr_net)} />
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  data-testid="confirm-paper"
                  disabled={busy || !canOpen}
                  onClick={() => {
                    setConfirming(false);
                    onOpen();
                  }}
                  className="flex-1 rounded-md border border-emerald-600 bg-emerald-500/15 px-3 py-2 font-semibold disabled:opacity-40"
                >
                  Xác nhận mở PAPER {plan.side}
                </button>
                <button type="button" data-testid="cancel-paper" onClick={() => setConfirming(false)} className="rounded-md border border-slate-400 px-3 py-2">
                  Hủy
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

/** The open paper position: obvious numbers, a close button that is clear but not dominant. */
export function PositionCard({ trade, onClose, busy }: { trade: PaperTrade | null; onClose: () => void; busy: boolean }) {
  if (!trade) {
    return (
      <Card title="Lệnh paper đang mở" testId="position-card">
        <p className="text-sm text-slate-500">Không có lệnh paper đang mở.</p>
      </Card>
    );
  }
  const pnl = trade.unrealized_pnl ?? null;
  const tone = pnl === null ? "" : pnl >= 0 ? "text-emerald-600" : "text-red-600";
  const risk = Math.abs(trade.fill_price - trade.initial_sl);
  const mfeR = trade.mfe !== undefined && trade.mfe !== null && risk > 0 ? trade.mfe / risk : null;
  const maeR = trade.mae !== undefined && trade.mae !== null && risk > 0 ? trade.mae / risk : null;
  const slipped = trade.planned_entry !== undefined && trade.planned_entry !== null && Math.abs(trade.planned_entry - trade.fill_price) > 1e-9;
  return (
    <Card title="Lệnh paper đang mở" testId="position-card">
      <div data-testid="paper-position" className="space-y-1">
        <div className="flex items-center gap-2">
          <Pill label="PAPER" value={`${trade.side} ${trade.status}`} tone={trade.side === "BUY" ? GOOD : BAD} />
          <span data-testid="position-id" className="text-xs text-slate-500">{trade.trade_id}</span>
        </div>
        <Row k="Giá vào (khớp)" v={fmt(trade.fill_price)} testId="position-entry" />
        {slipped && <Row k="Giá kế hoạch" v={fmt(trade.planned_entry)} testId="position-planned" />}
        <Row k="Giá hiện tại" v={fmt(trade.current_price)} testId="position-current" />
        <Row k="SL / TP" v={`${fmt(trade.sl)} / ${fmt(trade.tp)}`} testId="position-levels" />
        <Row k="Lot · rủi ro" v={`${fmt(trade.lots, 2)} · ${money(trade.risk_amount)}`} />
        <Row k="R hiện tại" v={fmt(trade.unrealized_r, 2)} testId="position-r" />
        <Row k="Lãi/lỗ tạm tính" v={<span className={tone}>{money(pnl)}</span>} testId="position-pnl" />
        <Row k="MFE / MAE (R)" v={`${fmt(mfeR)} / ${fmt(maeR)}`} testId="position-excursion" />
        <Row k="Thời gian giữ" v={`${fmt(trade.duration_minutes, 0)} phút`} testId="position-duration" />
        <button
          type="button"
          data-testid="close-paper"
          disabled={busy || trade.status !== "OPEN"}
          onClick={onClose}
          className="mt-2 w-full rounded-md border border-slate-400 px-3 py-1.5 text-sm font-semibold text-slate-700 disabled:opacity-40 dark:text-slate-200"
        >
          Đóng lệnh paper ngay
        </button>
      </div>
    </Card>
  );
}
