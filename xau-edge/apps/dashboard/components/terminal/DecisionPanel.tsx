"use client";

import { useEffect, useState } from "react";
import { actionText, type ActionTone } from "@/lib/action";
import { parseDecimal } from "@/lib/chartMath";
import { BAD, GOOD, INFO, NEUTRAL, WARN, fmt, money } from "@/components/trade/ui";
import { formatInZone, type DisplayZone } from "@/lib/time";
import { fetchRisk, type PaperTrade, type RiskPlan, type TradeView } from "@/lib/trade";
import { ACTIVITY_VI, BLOCKER_VI, EXIT_REASON_VI, HERO_VI, PAPER_ACCOUNT_VI, REFUSAL_VI, STAGE_VI, humanCondition, invalidationText, trendText, waitingText } from "@/lib/vi";

interface Props {
  view: TradeView;
  serverNowMs: number;
  risk: number;
  onRisk: (r: number) => void;
  onOpenRequest: () => void;
  onCloseRequest: () => void;
  uiStale: boolean;
  busy: boolean;
  tf: string;
  onFocusTf: (tf: string) => void;
  zone: DisplayZone;
}



// ---- setup pipeline ------------------------------------------------------------------------------

function Pipeline({ view, tf, onFocusTf }: { view: TradeView; tf: string; onFocusTf: (tf: string) => void }) {
  const stages = view.why_wait?.stages ?? [];
  return (
    <div data-testid="why-wait">
      <p data-testid="stages-progress" className="mb-1 text-sm font-semibold">
        Đã đạt {stages.filter((s) => s.status === "PASS").length}/{stages.length} điều kiện
      </p>
      <ol data-testid="stages" className="space-y-0.5 text-sm" aria-label="Tiến trình setup">
        {stages.map((s) => (
          <li key={s.stage}>
            <button
              type="button"
              data-testid={`stage-${s.stage.replace(/[^A-Za-z0-9]+/g, "-")}`}
              data-timeframe={s.timeframe}
              data-status={s.status}
              aria-label={`${STAGE_VI[s.stage] ?? s.stage}: ${s.status === "PASS" ? "đạt" : s.status === "FAIL" ? "chưa đạt" : "chưa tới"}. Xem biểu đồ ${s.timeframe}`}
              onClick={() => onFocusTf(s.timeframe)}
              className={`flex w-full items-center gap-2 rounded px-1.5 py-0.5 text-left hover:bg-slate-500/10 ${tf === s.timeframe ? "bg-sky-500/10" : ""}`}
            >
              <span aria-hidden="true" className={`w-4 text-center font-bold ${s.status === "PASS" ? "text-emerald-700 dark:text-emerald-400" : s.status === "FAIL" ? "text-red-700 dark:text-red-400" : "text-slate-600 dark:text-slate-400"}`}>
                {s.status === "PASS" ? "✓" : s.status === "FAIL" ? "✗" : "○"}
              </span>
              <span className="flex-1">{STAGE_VI[s.stage] ?? s.stage}</span>
              <span className="text-xs text-slate-600 dark:text-slate-400">{s.timeframe}</span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}

function WaitContext({ view }: { view: TradeView }) {
  const h1 = view.timeframes?.find((t) => t.timeframe === "H1");
  const trend = (view.structure?.h1_trend as string | undefined) ?? h1?.state;
  const bullish = trend === "BULLISH" ? true : trend === "BEARISH" ? false : null;
  const why = view.why_wait;
  const next = waitingText(why?.waiting_for_code ?? null, bullish, { phase: view.setup?.phase ?? null, age: view.setup?.bars_since_armed ?? null });
  const d = view.decision;
  const vol = (view.structure?.volatility as string | undefined) ?? "UNKNOWN";
  const phase = view.setup?.phase;
  const blocked = (why?.blocked_by ?? []).map((c) => REFUSAL_VI[c] ?? c);
  return (
    <div className="space-y-2">
      {next && (
        <p data-testid="waiting-for" className="rounded-md bg-slate-500/10 px-2 py-1.5 text-sm">
          Đang chờ: <b>{next}</b>
          <span className="block text-xs text-slate-600 dark:text-slate-400">Mô tả trạng thái hiện tại, không phải dự báo hay khuyến nghị.</span>
        </p>
      )}
      {blocked.length > 0 && (
        <p data-testid="blocked-by" className="text-xs text-slate-600 dark:text-slate-400">
          Mã chặn: {blocked.join(" · ")}
        </p>
      )}
      <ul data-testid="wait-context" className="space-y-0.5 text-sm">
        <li>Xu hướng: <b>{trendText(trend)}</b></li>
        <li>Setup: <b>{phase && phase !== "NONE" ? `${phase === "ARMED" ? "đang hình thành" : phase === "TRIGGERED" ? "đã kích hoạt" : phase}${view.setup?.bars_since_armed != null ? ` (nến ${view.setup.bars_since_armed}/${view.setup.valid_bars})` : ""}` : "chưa có"}</b></li>
        {d && (
          <li data-testid="market-activity">
            Hoạt động: biến động <b>{ACTIVITY_VI[vol] ?? vol}</b> · tick <b>{ACTIVITY_VI[d.volume_state] ?? d.volume_state}</b> · spread <b>{ACTIVITY_VI[d.spread_state] ?? d.spread_state}</b>
          </li>
        )}
      </ul>
      {view.news?.warning && (
        <p data-testid="news-warning" className={`rounded-md border px-2 py-1 text-xs ${WARN}`}>
          Tin tức CHƯA XÁC MINH (NEWS NOT VERIFIED): chưa có lịch kinh tế, hãy tự kiểm tra.
        </p>
      )}
    </div>
  );
}

// ---- order ticket --------------------------------------------------------------------------------

function RrRuler({ rr }: { rr: number }) {
  // the bar's proportions and label are the plan's NET R/R (after spread), the same number as the ticket
  const reward = Math.max(rr, 0.2);
  return (
    <div data-testid="rr-ruler" role="img" aria-label={`Thang rủi ro/lợi nhuận sau spread: rủi ro 1R, lợi nhuận ${rr.toFixed(2)}R`} className="flex h-28 w-16 shrink-0 flex-col text-xs font-semibold">
      <div className="flex items-start justify-center rounded-t bg-emerald-500/25 px-1 text-emerald-800 dark:text-emerald-200" style={{ flexGrow: reward }}>+{rr.toFixed(2)}R</div>
      <div className="h-0.5 bg-blue-600" aria-hidden="true" />
      <div className="flex items-end justify-center rounded-b bg-red-500/25 px-1 text-red-800 dark:text-red-200" style={{ flexGrow: 1 }}>−1R</div>
    </div>
  );
}

function Ticket({ view, risk, onRisk, onOpenRequest, busy, uiStale, expiredNow }: Pick<Props, "view" | "risk" | "onRisk" | "onOpenRequest" | "busy" | "uiStale"> & { expiredNow: boolean }) {
  const plan = view.trade_plan;
  if (!plan) return null;
  const chosen = view.risk_plans?.find((p) => Math.abs(p.risk_pct - risk) < 1e-9);
  const blockers = view.entry_blockers ?? [];
  const canOpen = Boolean(view.actionable && !expiredNow && !uiStale && plan.complete && chosen?.ok);
  const buy = plan.side === "BUY";
  const cells: { k: string; v: string; id: string; strong?: boolean }[] = [
    { k: "Entry (thị trường)", v: fmt(plan.planned_entry), id: "plan-entry", strong: true },
    { k: "SL", v: fmt(plan.sl), id: "plan-sl" },
    { k: "TP", v: fmt(plan.tp1), id: "plan-tp" },
    ...(plan.tp2 !== null ? [{ k: "TP 2", v: fmt(plan.tp2), id: "plan-tp2" }] : []),
    { k: "R/R sau spread", v: fmt(plan.rr_net), id: "plan-rr" },
    { k: "Rủi ro", v: `${fmt(risk, 2)}% · ${money(chosen ? -chosen.loss_at_sl : null)}`, id: "plan-risk" },
    { k: "Lot", v: fmt(chosen?.lots, 2), id: "plan-lots", strong: true },
    { k: "Lãi nếu chạm TP", v: money(chosen?.gain_at_tp), id: "plan-tp-value" },
  ];
  return (
    <div data-testid="plan-card" className="space-y-2">
      {!plan.complete && (
        <p data-testid="plan-incomplete" className={`rounded-md border px-2 py-1 text-sm font-semibold ${WARN}`}>
          Phát hiện setup nhưng CHƯA ĐỦ KẾ HOẠCH ({plan.missing.join(", ")}): không thể mở lệnh.
        </p>
      )}
      {(expiredNow || uiStale) && (
        <p data-testid="plan-stale" role="status" className={`rounded-md border px-2 py-1 text-sm font-semibold ${WARN}`}>
          {expiredNow ? "KẾ HOẠCH ĐÃ HẾT HẠN — chỉ để tham khảo, không thể mở lệnh." : "Dữ liệu hoặc kết nối không chắc chắn — chỉ để tham khảo, không thể mở lệnh."}
        </p>
      )}
      <div className="flex items-center justify-between">
        <span data-testid="plan-side" className={`rounded px-2 py-0.5 text-sm font-black ${buy ? "bg-emerald-700 text-white" : "bg-red-700 text-white"}`}>
          {buy ? "▲ MUA (BUY)" : "▼ BÁN (SELL)"}
        </span>
        <span data-testid="plan-version" className="text-xs text-slate-600 dark:text-slate-400">chiến lược v{plan.strategy_version}</span>
      </div>
      <div className="flex gap-3">
        <div className="flex-1">
          {cells.map((c) => (
            <div key={c.id} className="flex justify-between gap-3 py-0.5 text-sm">
              <span className="text-slate-600 dark:text-slate-400">{c.k}</span>
              <span data-testid={c.id} className={`font-mono tabular-nums ${c.strong ? "font-bold" : ""}`}>{c.v}</span>
            </div>
          ))}
        </div>
        {plan.rr_net !== null && <RrRuler rr={plan.rr_net} />}
      </div>
      {plan.invalidation && <p data-testid="plan-invalidation" className="rounded-md bg-slate-500/10 px-2 py-1 text-sm">Vô hiệu khi: <b>{invalidationText(plan.invalidation)}</b></p>}
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Mức rủi ro mỗi lệnh">
        <span className="text-xs text-slate-600 dark:text-slate-400">Rủi ro:</span>
        {(view.risk_choices ?? [0.1, 0.25, 0.5]).map((r) => (
          <button key={r} type="button" data-testid={`risk-${r}`} aria-pressed={r === risk} onClick={() => onRisk(r)} className={`rounded-md border px-3 py-1 text-sm ${r === risk ? "border-sky-600 bg-sky-500/15 font-semibold" : "border-slate-400"}`}>
            {r.toFixed(2)}%
          </button>
        ))}
      </div>
      <p className="text-xs text-slate-600 dark:text-slate-400" data-testid="paper-equity">{PAPER_ACCOUNT_VI}: ${fmt(view.desk?.account.equity, 0)}</p>
      {chosen && !chosen.ok && <p className="text-sm text-red-700 dark:text-red-400">{chosen.errors.join(", ")}</p>}
      {blockers.length > 0 && (
        <ul data-testid="blockers" className="space-y-1 text-sm">
          {blockers.map((b) => (
            <li key={b.code} data-code={b.code} className={`rounded-md border px-2 py-1 ${b.code === "PAPER_STATE_ERROR" || b.code === "WRITER_LOCK" ? BAD : WARN}`}>
              {BLOCKER_VI[b.code] ?? b.message} <span className="font-mono text-xs">{b.code}</span>
            </li>
          ))}
        </ul>
      )}
      <button type="button" data-testid="take-paper" disabled={!canOpen || busy} onClick={onOpenRequest} className={`w-full rounded-md border-2 px-3 py-2.5 text-base font-black disabled:opacity-40 ${buy ? "border-emerald-700 bg-emerald-700 text-white" : "border-red-700 bg-red-700 text-white"}`}>
        Mở lệnh PAPER {buy ? "MUA" : "BÁN"}
      </button>
      <p className="text-center text-xs text-slate-600 dark:text-slate-400">Giả lập, không gửi lệnh thật tới MT5.</p>
    </div>
  );
}

// ---- open position -------------------------------------------------------------------------------

function PositionPanel({ trade, onCloseRequest, busy }: { trade: PaperTrade; onCloseRequest: () => void; busy: boolean }) {
  const pnl = trade.unrealized_pnl ?? null;
  const tone = pnl === null ? "" : pnl >= 0 ? "text-emerald-700 dark:text-emerald-400" : "text-red-700 dark:text-red-400";
  const risk = Math.abs(trade.fill_price - trade.initial_sl);
  const mfeR = trade.mfe != null && risk > 0 ? trade.mfe / risk : null;
  const maeR = trade.mae != null && risk > 0 ? trade.mae / risk : null;
  const slipped = trade.planned_entry != null && Math.abs(trade.planned_entry - trade.fill_price) > 1e-9;
  const buy = trade.side === "BUY";
  return (
    <div data-testid="paper-position" className="space-y-2">
      <div className="flex items-center justify-between">
        <span className={`rounded px-2 py-0.5 text-sm font-black ${buy ? "bg-emerald-700 text-white" : "bg-red-700 text-white"}`}>PAPER {buy ? "MUA" : "BÁN"}</span>
        <span data-testid="position-id" className="font-mono text-xs text-slate-600 dark:text-slate-400">{trade.trade_id}</span>
      </div>
      <div className="rounded-lg border border-slate-300 p-2 text-center dark:border-slate-700">
        <div className="text-xs text-slate-600 dark:text-slate-400">Lãi/lỗ tạm tính</div>
        <div data-testid="position-pnl" className={`font-mono text-3xl font-black tabular-nums ${tone}`}>{money(pnl)}</div>
        <div className="font-mono text-sm">R hiện tại: <b data-testid="position-r">{fmt(trade.unrealized_r, 2)}</b></div>
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-sm">
        <dt className="text-slate-600 dark:text-slate-400">Giá vào (khớp)</dt><dd data-testid="position-entry" className="text-right font-mono">{fmt(trade.fill_price)}</dd>
        {slipped && (<><dt className="text-slate-600 dark:text-slate-400">Giá kế hoạch</dt><dd data-testid="position-planned" className="text-right font-mono">{fmt(trade.planned_entry)}</dd></>)}
        <dt className="text-slate-600 dark:text-slate-400">Giá hiện tại</dt><dd data-testid="position-current" className="text-right font-mono">{fmt(trade.current_price)}</dd>
        <dt className="text-slate-600 dark:text-slate-400">SL / TP</dt><dd data-testid="position-levels" className="text-right font-mono">{fmt(trade.sl)} / {fmt(trade.tp)}</dd>
        <dt className="text-slate-600 dark:text-slate-400">Cách SL / TP</dt>
        <dd data-testid="position-distance" className="text-right font-mono">
          {trade.current_price != null ? `${Math.abs(trade.current_price - trade.sl).toFixed(2)} / ${Math.abs(trade.tp - trade.current_price).toFixed(2)} (${risk > 0 ? `${(Math.abs(trade.current_price - trade.sl) / risk).toFixed(2)}R` : "—"} / ${risk > 0 ? `${(Math.abs(trade.tp - trade.current_price) / risk).toFixed(2)}R` : "—"})` : "—"}
        </dd>
        <dt className="text-slate-600 dark:text-slate-400">Lot · rủi ro</dt><dd className="text-right font-mono">{fmt(trade.lots, 2)} · {money(trade.risk_amount)}</dd>
        <dt className="text-slate-600 dark:text-slate-400">Đã giữ</dt><dd data-testid="position-duration" className="text-right font-mono">{fmt(trade.duration_minutes, 0)} phút</dd>
        <dt className="text-xs text-slate-600 dark:text-slate-400">MFE / MAE (R)</dt><dd data-testid="position-excursion" className="text-right font-mono text-xs text-slate-600 dark:text-slate-400">{fmt(mfeR)} / {fmt(maeR)}</dd>
      </dl>
      <button type="button" data-testid="close-paper" disabled={busy || trade.status !== "OPEN"} onClick={onCloseRequest} className="w-full rounded-md border-2 border-slate-500 px-3 py-2 text-sm font-bold disabled:opacity-40">
        Đóng lệnh paper…
      </button>
    </div>
  );
}

// ---- calculator ----------------------------------------------------------------------------------

function Calculator({ bid }: { bid: number | null }) {
  const [open, setOpen] = useState(false);
  const [entry, setEntry] = useState("");
  const [stop, setStop] = useState("");
  const [riskPct, setRiskPct] = useState("0.25");
  const [result, setResult] = useState<RiskPlan | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const e = parseDecimal(entry);
    const s = parseDecimal(stop);
    const r = parseDecimal(riskPct);
    if (!open || !(e > 0) || !(s > 0) || !(r > 0 && r <= 0.5)) return;
    const ctl = new AbortController();
    const t = setTimeout(() => {
      fetchRisk(e, s, r, ctl.signal)
        .then((p) => {
          setResult(p);
          setError(null);
        })
        .catch(() => setError("Không tính được (API không phản hồi)."));
    }, 250);
    return () => {
      clearTimeout(t);
      ctl.abort();
    };
  }, [open, entry, stop, riskPct]);

  const valid = parseDecimal(entry) > 0 && parseDecimal(stop) > 0 && parseDecimal(riskPct) > 0 && parseDecimal(riskPct) <= 0.5;
  return (
    <details data-testid="calculator" open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)} className="rounded-lg border border-slate-300 p-2 dark:border-slate-700">
      <summary className="cursor-pointer text-sm font-semibold">Máy tính lệnh (chỉ để tính)</summary>
      <p className={`mt-1 rounded border px-2 py-0.5 text-[11px] font-semibold ${WARN}`}>CHỈ LÀ MÁY TÍNH — KHÔNG PHẢI TÍN HIỆU</p>
      <div className="mt-2 grid grid-cols-3 gap-2 text-sm">
        <label className="flex flex-col text-xs text-slate-600 dark:text-slate-400">Entry
          <input data-testid="calc-entry" inputMode="decimal" value={entry} onChange={(e) => setEntry(e.target.value)} placeholder={bid ? bid.toFixed(2) : ""} className="rounded border border-slate-400 bg-transparent px-1 py-0.5 font-mono text-sm text-inherit" />
        </label>
        <label className="flex flex-col text-xs text-slate-600 dark:text-slate-400">SL
          <input data-testid="calc-sl" inputMode="decimal" value={stop} onChange={(e) => setStop(e.target.value)} className="rounded border border-slate-400 bg-transparent px-1 py-0.5 font-mono text-sm text-inherit" />
        </label>
        <label className="flex flex-col text-xs text-slate-600 dark:text-slate-400">Rủi ro %
          <input data-testid="calc-risk" inputMode="decimal" value={riskPct} onChange={(e) => setRiskPct(e.target.value)} className="rounded border border-slate-400 bg-transparent px-1 py-0.5 font-mono text-sm text-inherit" />
        </label>
      </div>
      <div data-testid="calc-result" className="mt-2 text-sm">
        {!valid ? <span className="text-slate-600 dark:text-slate-400">Nhập entry, SL và rủi ro (≤ 0,5%).</span> : error ? <span className="text-red-700 dark:text-red-400">{error}</span> : result ? (
          result.ok ? (
            <span>Lot <b className="font-mono">{fmt(result.lots, 2)}</b> · rủi ro <b className="font-mono">{money(result.risk_amount)}</b> · lỗ nếu chạm SL <b className="font-mono">{money(-result.loss_at_sl)}</b></span>
          ) : (
            <span className="text-red-700 dark:text-red-400">{(result.errors ?? []).join(", ")}</span>
          )
        ) : <span className="text-slate-600 dark:text-slate-400">Đang tính…</span>}
      </div>
    </details>
  );
}

// ---- the panel: the dominant state, and the detail under it ----------------------------------------

export function expiryOf(view: TradeView, serverNowMs: number) {
  const plan = view.trade_plan ?? null;
  const expiresMs = plan?.expires_at ? Date.parse(plan.expires_at) : null;
  const expiredNow = plan !== null && (plan.expired || (expiresMs !== null && expiresMs <= serverNowMs));
  const secondsLeft = expiresMs === null ? null : Math.max(0, Math.round((expiresMs - serverNowMs) / 1000));
  return { expiredNow, secondsLeft };
}

const ACTION_STYLE: Record<ActionTone, string> = {
  buy: "border-emerald-800 bg-emerald-700 text-white",
  sell: "border-red-800 bg-red-700 text-white",
  // a WATCH is not an order: amber with a dashed border, so it is never mistaken for BUY/SELL READY
  "watch-buy": "border-dashed border-amber-700 bg-amber-500/15 text-amber-950 dark:text-amber-100",
  "watch-sell": "border-dashed border-amber-700 bg-amber-500/15 text-amber-950 dark:text-amber-100",
  hold: "border-sky-700 bg-sky-500/15 text-sky-900 dark:text-sky-100",
  exit: "border-slate-600 bg-slate-500/15 text-slate-900 dark:text-slate-100",
  wait: "border-slate-500 bg-slate-500/10 text-slate-800 dark:text-slate-200",
  error: "border-red-700 bg-red-500/15 text-red-900 dark:text-red-100",
};
const ACTION_ICON: Record<ActionTone, string> = { buy: "▲", sell: "▼", "watch-buy": "👁▲", "watch-sell": "👁▼", hold: "●", exit: "✓", wait: "⏸", error: "⚠" };

/** Action-first: what to do NOW in one word, why in one line, and exactly when to act. */
function ActionHero({ view, expiredNow, secondsLeft }: { view: TradeView; expiredNow: boolean; secondsLeft: number | null }) {
  const [more, setMore] = useState(false);
  const t = actionText(view, secondsLeft, expiredNow);
  const state = expiredNow && (view.hero.state === "BUY_READY" || view.hero.state === "SELL_READY") ? "EXPIRED_SETUP" : view.hero.state;
  const text = HERO_VI[state];
  const errors = view.conditions.filter((c) => c.severity === "ERROR" && c.code !== "MARKET_CLOSED");
  const solid = t.tone === "buy" || t.tone === "sell";
  const veil = solid ? "bg-black/25" : "bg-black/10 dark:bg-white/10"; // solid heroes keep white text on a darker, never lighter, panel
  const urgent = secondsLeft !== null && secondsLeft <= 60 && (t.code === "BUY" || t.code === "SELL") && !expiredNow;
  return (
    <div data-testid="hero" data-hero-state={state} data-action={t.code} data-server-label={view.hero.label} className={`rounded-lg border-2 px-4 py-2 ${ACTION_STYLE[t.tone]}`}>
      <div className="flex items-center justify-between gap-2 text-xs font-semibold uppercase">
        <span>Bạn nên làm gì bây giờ?</span>
        <span data-testid="decision" className={`rounded px-1.5 py-0.5 ${veil}`}>{text.label}</span>
      </div>
      <div className="mt-1 flex items-center gap-2">
        <span aria-hidden="true" className="text-2xl">{ACTION_ICON[t.tone]}</span>
        <span data-testid="action-word" className="text-4xl font-black leading-none">{expiredNow && (t.code === "BUY" || t.code === "SELL") ? "BỎ QUA" : t.word}</span>
      </div>
      <p data-testid="action-sub" className="mt-1 text-sm font-semibold">
        {expiredNow && (t.code === "BUY" || t.code === "SELL") ? "Kế hoạch đã hết hạn" : t.sub}
        {urgent && <span data-testid="expiry" data-urgent="true"> — sắp hết hạn</span>}
        {!urgent && secondsLeft !== null && (t.code === "BUY" || t.code === "SELL") && !expiredNow && <span data-testid="expiry" data-urgent="false" className="sr-only"> còn hiệu lực {mmss2(secondsLeft)}</span>}
      </p>
      <p data-testid="action-when" className={`mt-2 rounded-md px-2 py-1.5 text-sm ${veil} sm:line-clamp-none ${more ? "" : "line-clamp-2"}`}>
        <b>Khi nào?</b> {expiredNow && (t.code === "BUY" || t.code === "SELL") ? "Không mở được nữa; chờ setup mới." : t.when}
      </p>
      <button type="button" data-testid="action-when-toggle" aria-expanded={more} onClick={() => setMore(!more)} className="mt-0.5 text-xs font-semibold underline sm:hidden">{more ? "thu gọn" : "xem thêm"}</button>
      {(state === "UNAVAILABLE" || state === "STALE") && errors.length > 0 && (
        <ul data-testid="hero-problems" className="mt-1 space-y-0.5 text-sm">
          {errors.map((c) => (
            <li key={c.code}>{humanCondition(c.code, c.message)} <span className="font-mono text-xs">{c.code}</span></li>
          ))}
        </ul>
      )}
    </div>
  );
}

const mmss2 = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

/** The state that dominates the decision area (always first, also on a phone). */
export function DecisionHero({ view, serverNowMs }: { view: TradeView; serverNowMs: number }) {
  const { expiredNow, secondsLeft } = expiryOf(view, serverNowMs);
  return <ActionHero view={view} expiredNow={expiredNow} secondsLeft={secondsLeft} />;
}

/** Ticket, position, or the wait context: what the trader can read or do about the state. */
export function DecisionBody({ view, serverNowMs, risk, onRisk, onOpenRequest, onCloseRequest, uiStale, busy, tf, onFocusTf, zone }: Props) {
  const { expiredNow } = expiryOf(view, serverNowMs);
  const plan = view.trade_plan ?? null;
  const state = view.hero.state;
  const showTicket = (state === "BUY_READY" || state === "SELL_READY") && plan !== null;
  const showPosition = state === "POSITION_OPEN" && view.desk?.position;
  const waiting = state === "WAIT" || state === "SETUP_ARMED" || state === "NOT_ACTIONABLE";
  return (
    <section data-testid="decision-card" className="space-y-3">
      {showPosition && view.desk?.position ? <PositionPanel trade={view.desk.position} onCloseRequest={onCloseRequest} busy={busy} /> : null}
      {showTicket && <Ticket view={view} risk={risk} onRisk={onRisk} onOpenRequest={onOpenRequest} busy={busy} uiStale={uiStale} expiredNow={expiredNow} />}
      {waiting && <Pipeline view={view} tf={tf} onFocusTf={onFocusTf} />}
      {waiting && <WaitContext view={view} />}
      {state !== "POSITION_OPEN" && <LastExit view={view} />}
      <AlertChannelNotice view={view} />
      {state === "MARKET_CLOSED" && <ClosedInfo view={view} zone={zone} />}
      <AccountStrip view={view} />
      {!showTicket && !showPosition && <Calculator bid={view.quote?.bid ?? null} />}
    </section>
  );
}

function LastExit({ view }: { view: TradeView }) {
  const x = view.desk?.last_exit;
  if (!x) return null;
  return (
    <section data-testid="last-exit" aria-label="Lệnh paper đóng gần nhất" className="rounded-lg border border-slate-300 p-2 text-sm dark:border-slate-700">
      <div className="mb-0.5 text-xs font-semibold uppercase text-slate-600 dark:text-slate-400">Lệnh đóng gần nhất</div>
      <div className="flex flex-wrap items-baseline gap-x-3">
        <b>{x.side === "BUY" ? "MUA" : "BÁN"}</b>
        <span>{EXIT_REASON_VI[x.exit_reason ?? ""] ?? x.exit_reason}</span>
        <span className={`font-mono font-bold ${(x.net_pnl ?? 0) >= 0 ? "text-emerald-700 dark:text-emerald-400" : "text-red-700 dark:text-red-400"}`}>{money(x.net_pnl)} · {fmt(x.r_multiple, 2)}R</span>
        <span className="text-xs text-slate-600 dark:text-slate-400">{fmt(x.duration_minutes, 0)} phút</span>
      </div>
    </section>
  );
}

/** Off-browser alerts are the channel that works when the page is closed: say whether it is on. */
function AlertChannelNotice({ view }: { view: TradeView }) {
  const a = view.alerts;
  if (view.source_mode !== "LIVE" || !a || a.telegram_configured) return null;
  return (
    <p data-testid="alert-channel-notice" className={`rounded-md border px-2 py-1 text-xs ${WARN}`}>
      Cảnh báo khi đóng trình duyệt: <b>CHƯA BẬT</b> (Telegram chưa cấu hình, hiện chỉ ghi file). Thông báo trong trình duyệt chỉ hoạt động khi trang đang mở.
    </p>
  );
}

/** While the market is closed the right column is not empty: what happened last and what comes next. */
function ClosedInfo({ view, zone }: { view: TradeView; zone: DisplayZone }) {
  const d = view.market_context?.daily ?? null;
  const t = view.desk?.today;
  return (
    <div data-testid="closed-info" className="space-y-2 rounded-lg border border-slate-300 p-3 text-sm dark:border-slate-700">
      <p>Bộ máy quyết định tạm dừng và tự tính lại khi thị trường mở cửa; giá và biểu đồ là dữ liệu cuối cùng.</p>
      {view.market_context?.next_open && <p data-testid="reopen-at">Thị trường mở lại lúc <b className="font-mono">{formatInZone(view.market_context.next_open, zone).slice(0, 16)}</b>.</p>}
      {d && (
        <p>
          Phiên giao dịch gần nhất: {d.change >= 0 ? "tăng" : "giảm"} <b className="font-mono">{fmt(Math.abs(d.change))}</b> ({d.change_pct === null ? "—" : `${d.change_pct >= 0 ? "+" : ""}${d.change_pct.toFixed(2)}%`}), biên <b className="font-mono">{fmt(d.range)}</b>, đóng cửa tại <b className="font-mono">{fmt(d.last)}</b>.
        </p>
      )}
      <p>Bàn PAPER: {String(t?.paper_trades ?? 0)} lệnh trong ngày · P&L {money(t?.net_pnl as number | null)}.</p>
    </div>
  );
}

/** The paper account at a glance: equity, floating and today's result, and how close the daily loss limit is. */
function AccountStrip({ view }: { view: TradeView }) {
  const a = view.desk?.account;
  const t = view.desk?.today;
  const l = view.desk?.limits;
  if (!a) return null;
  const floating = a.equity - a.balance;
  const used = l && l.daily_loss_stop_pct > 0 ? Math.min(100, (Math.max(0, l.daily_loss_pct) / l.daily_loss_stop_pct) * 100) : 0;
  return (
    <section data-testid="account-strip" aria-label="Tài khoản PAPER" className="rounded-lg border border-slate-300 p-2 text-sm dark:border-slate-700">
      <div className="mb-1 flex items-center justify-between">
        <b>Tài khoản PAPER</b>
        <span className="text-xs text-slate-600 dark:text-slate-400">vốn giả lập</span>
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-0.5">
        <dt className="text-slate-600 dark:text-slate-400">Equity</dt><dd data-testid="acct-equity" className="text-right font-mono">{money(a.equity)}</dd>
        <dt className="text-slate-600 dark:text-slate-400">Đang chạy</dt><dd data-testid="acct-floating" className={`text-right font-mono ${floating < 0 ? "text-red-700 dark:text-red-400" : ""}`}>{money(floating)}</dd>
        <dt className="text-slate-600 dark:text-slate-400">Hôm nay</dt><dd data-testid="acct-today" className="text-right font-mono">{money(t?.net_pnl as number | null)} · {fmt(t?.net_r as number | null)}R</dd>
        <dt className="text-slate-600 dark:text-slate-400">Số lệnh hôm nay</dt><dd className="text-right font-mono">{String(t?.paper_trades ?? 0)}{l ? ` / ${l.max_trades_per_day}` : ""}</dd>
      </dl>
      {l && (
        <div className="mt-1" data-testid="acct-limit">
          <div className="flex justify-between text-xs text-slate-600 dark:text-slate-400"><span>Lỗ trong ngày</span><span className="font-mono">{l.daily_loss_pct.toFixed(2)}% / giới hạn {l.daily_loss_stop_pct}%</span></div>
          <div role="progressbar" aria-label="Mức lỗ trong ngày so với giới hạn" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(used)} className="mt-0.5 h-1.5 w-full rounded bg-slate-300 dark:bg-slate-700">
            <div className={`h-1.5 rounded ${used >= 80 ? "bg-red-600" : used >= 50 ? "bg-amber-500" : "bg-emerald-600"}`} style={{ width: `${used}%` }} />
          </div>
        </div>
      )}
    </section>
  );
}
