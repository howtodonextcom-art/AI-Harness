"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { TradeChart, type Overlays } from "@/components/trade/TradeChart";
import { MARKET_TIMEFRAMES, fetchBars, type BarsResponse, type MarketTimeframe } from "@/lib/market";
import { formatInZone, loadZone, type DisplayZone } from "@/lib/time";
import {
  closePaperTrade,
  fetchDecision,
  fetchMarkers,
  openPaperTrade,
  type MarkersResponse,
  type PaperTrade,
  type RiskPlan,
  type TradeView as TradeViewData,
} from "@/lib/trade";

const POLL_MS = 3000;
const STALE_UI_SECONDS = 20;
const STALE_DATA_SECONDS = 180;

const GOOD = "border-emerald-600 bg-emerald-500/15 text-emerald-800 dark:text-emerald-200";
const WARN = "border-amber-600 bg-amber-500/15 text-amber-800 dark:text-amber-200";
const BAD = "border-red-600 bg-red-500/15 text-red-800 dark:text-red-200";
const NEUTRAL = "border-slate-500 bg-slate-500/15 text-slate-700 dark:text-slate-300";
const SIDE_STYLE = { BUY: GOOD, SELL: BAD, WAIT: NEUTRAL } as const;

const BLOCKER_TEXT: Record<string, string> = {
  RISK_LIMIT: "đã có lệnh đang mở hoặc tổng rủi ro vượt giới hạn",
  COOLDOWN: "đang nghỉ sau lệnh trước",
  DAILY_LIMIT: "đã chạm giới hạn lệnh/lỗ trong ngày hoặc trong phiên",
};

const fmt = (v: number | null | undefined, d = 2) => (v === null || v === undefined ? "—" : v.toFixed(d));
const money = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v >= 0 ? "" : "-"}$${Math.abs(v).toFixed(2)}`);

function ageText(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  const s = Math.max(0, Math.round(seconds));
  if (s < 90) return `${s}s`;
  if (s < 5400) return `${Math.round(s / 60)} phút`;
  return `${(s / 3600).toFixed(1)} giờ`;
}

function Pill({ label, value, tone, testId }: { label: string; value: string; tone: string; testId?: string }) {
  return (
    <span data-testid={testId} className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold ${tone}`}>
      <span className="font-normal opacity-80">{label}</span>
      {value}
    </span>
  );
}

function Card({ title, children, testId }: { title: string; children: React.ReactNode; testId?: string }) {
  return (
    <section data-testid={testId} className="rounded-lg border border-slate-300 p-3 dark:border-slate-700">
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h2>
      {children}
    </section>
  );
}

function Row({ k, v, testId }: { k: string; v: React.ReactNode; testId?: string }) {
  return (
    <div className="flex justify-between gap-3 py-0.5 text-sm">
      <span className="text-slate-500">{k}</span>
      <span data-testid={testId} className="font-mono tabular-nums">{v}</span>
    </div>
  );
}

function biasText(bias: number | null): string {
  return bias === null ? "—" : bias > 0 ? "▲" : bias < 0 ? "▼" : "•";
}

function Position({ trade, onClose, busy }: { trade: PaperTrade; onClose: () => void; busy: boolean }) {
  const pnl = trade.unrealized_pnl ?? null;
  const tone = pnl === null ? "" : pnl >= 0 ? "text-emerald-600" : "text-red-600";
  return (
    <div data-testid="paper-position" className="space-y-1">
      <div className="flex items-center gap-2">
        <Pill label="PAPER" value={`${trade.side} ${trade.status}`} tone={SIDE_STYLE[trade.side]} />
        <span className="text-xs text-slate-500">{trade.trade_id}</span>
      </div>
      <Row k="Giá vào" v={fmt(trade.fill_price)} testId="position-entry" />
      <Row k="SL / TP" v={`${fmt(trade.sl)} / ${fmt(trade.tp)}`} />
      <Row k="Lot" v={fmt(trade.lots, 2)} />
      <Row k="Giá hiện tại" v={fmt(trade.current_price)} />
      <Row k="R hiện tại" v={fmt(trade.unrealized_r, 2)} testId="position-r" />
      <Row k="Lãi/lỗ tạm tính" v={<span className={tone}>{money(pnl)}</span>} testId="position-pnl" />
      <Row k="Thời gian giữ" v={`${fmt(trade.duration_minutes, 0)} phút`} />
      <button
        type="button"
        data-testid="close-paper"
        disabled={busy || trade.status !== "OPEN"}
        onClick={onClose}
        className="mt-2 w-full rounded-md border border-red-600 px-3 py-1.5 text-sm font-semibold text-red-700 disabled:opacity-40 dark:text-red-300"
      >
        Đóng lệnh paper ngay
      </button>
    </div>
  );
}

const TOGGLES: [keyof Overlays, string][] = [
  ["signals", "Signals"],
  ["plan", "Trade Plan"],
  ["paper", "Paper Trades"],
  ["structure", "Structure"],
  ["volume", "Volume"],
];

/** The one page for a disciplined PAPER trading decision on live FTMO data (no real orders). */
export function TradeView() {
  const [view, setView] = useState<TradeViewData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastOk, setLastOk] = useState<number | null>(null);
  const [now, setNow] = useState(0);
  const [risk, setRisk] = useState(0.25);
  const [zone, setZone] = useState<DisplayZone>("UTC");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: string; text: string } | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [tf, setTf] = useState<MarketTimeframe>("M5");
  const [bars, setBars] = useState<BarsResponse | null>(null);
  const [markers, setMarkers] = useState<MarkersResponse | null>(null);
  const [history, setHistory] = useState(false);
  const [overlays, setOverlays] = useState<Overlays>({ signals: true, plan: true, paper: true, structure: false, volume: true });
  const inFlight = useRef(false);

  useEffect(() => {
    const t = setTimeout(() => setZone(loadZone()), 0);
    return () => clearTimeout(t);
  }, []);

  const load = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 8000);
    try {
      const data = await fetchDecision(ctl.signal);
      setView(data);
      setError(null);
      setLastOk(Date.now());
      setNow(Date.now());
    } catch {
      setError("Không kết nối được API /trade/decision — quyết định bên dưới có thể đã cũ");
    } finally {
      clearTimeout(timer);
      inFlight.current = false;
    }
  }, []);

  useEffect(() => {
    const first = setTimeout(load, 0);
    const poll = setInterval(load, POLL_MS);
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      clearTimeout(first);
      clearInterval(poll);
      clearInterval(tick);
    };
  }, [load]);

  useEffect(() => {
    let alive = true;
    const run = async () => {
      try {
        const b = await fetchBars(tf, 400, true);
        if (alive) setBars(b);
      } catch {
        /* the stale banner (decision API) already tells the owner; the chart keeps its last data */
      }
    };
    const first = setTimeout(() => void run(), 0);
    const id = setInterval(() => void run(), 3000);
    return () => {
      alive = false;
      clearTimeout(first);
      clearInterval(id);
    };
  }, [tf]);

  useEffect(() => {
    let alive = true;
    const run = async () => {
      try {
        const m = await fetchMarkers();
        if (alive) setMarkers(m);
      } catch {
        /* markers are secondary */
      }
    };
    const first = setTimeout(() => void run(), 0);
    const id = setInterval(() => void run(), 5000);
    return () => {
      alive = false;
      clearTimeout(first);
      clearInterval(id);
    };
  }, []);

  const uiStale = lastOk === null || (now - lastOk) / 1000 > STALE_UI_SECONDS;
  const dataStale = Boolean(view?.market?.open) && ((view?.data_age_seconds ?? 0) > STALE_DATA_SECONDS || Boolean(view?.quote?.stale));
  const anyStale = uiStale || dataStale;
  const decision = view?.decision;
  const side = decision?.decision ?? "WAIT";
  const expiresMs = decision?.signal_expiry ? Date.parse(decision.signal_expiry) : null;
  const secondsLeft = expiresMs === null ? null : Math.max(0, Math.round((expiresMs - now) / 1000));
  const expired = Boolean(decision?.expired) || (secondsLeft !== null && secondsLeft <= 0 && side !== "WAIT");
  const plan: RiskPlan | undefined = view?.risk_plans?.find((p) => Math.abs(p.risk_pct - risk) < 1e-9);
  const blockers = view?.desk?.blockers ?? [];
  const canOpen = Boolean(view?.actionable && view?.desk?.can_open && !expired && !anyStale && plan?.ok);
  const planLive = side !== "WAIT" && !expired && !anyStale;

  const take = async () => {
    if (!decision || !decision.setup_id) return;
    setBusy(true);
    setConfirming(false);
    const res = await openPaperTrade(decision.setup_id, risk);
    setMessage(
      res.ok
        ? { tone: GOOD, text: `Đã mở lệnh PAPER ${res.data.side} ${fmt(res.data.lots, 2)} lot @ ${fmt(res.data.fill_price)}` }
        : { tone: BAD, text: `Không mở được: ${res.error.message} (${res.error.code})` },
    );
    setBusy(false);
    void load();
  };

  const closeNow = async () => {
    const trade = view?.desk?.position;
    if (!trade) return;
    setBusy(true);
    const res = await closePaperTrade(trade.trade_id);
    setMessage(
      res.ok
        ? { tone: GOOD, text: `Đã đóng lệnh paper: ${money(res.data.net_pnl ?? null)} (${fmt(res.data.r_multiple ?? null, 2)}R)` }
        : { tone: BAD, text: `Không đóng được: ${res.error.message} (${res.error.code})` },
    );
    setBusy(false);
    void load();
  };

  const blockedBy = view?.why_wait?.blocked_by ?? decision?.refusal_reasons ?? [];

  return (
    <main className="mx-auto w-full max-w-7xl space-y-3 px-3 py-3 sm:px-4">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-bold">XAUUSD · FTMO DEMO</h1>
        <Pill label="" value="PAPER ONLY — không gửi lệnh thật" tone={WARN} testId="paper-only" />
        {view?.market && (
          <Pill label="thị trường" value={view.market.open ? "MỞ" : view.market.status} tone={view.market.open ? GOOD : NEUTRAL} testId="market-pill" />
        )}
        {view?.quote && (
          <span data-testid="quote" className="font-mono text-sm">
            {fmt(view.quote.bid)} / {fmt(view.quote.ask)} · spread {fmt(view.quote.spread_points, 0)} điểm
          </span>
        )}
        <span data-testid="data-age" className="text-xs text-slate-500">
          dữ liệu: {ageText(view?.data_age_seconds)} · cập nhật {view ? formatInZone(view.generated_at, zone) : "—"} ({zone})
          {view?.setup?.strategy_version ? ` · baseline v${view.setup.strategy_version}` : ""}
        </span>
      </header>

      {(error || uiStale) && (
        <div role="alert" data-testid="stale-banner" className={`rounded-md border px-3 py-2 text-sm ${BAD}`}>
          {error ?? "Đang chờ dữ liệu"} — không được vào lệnh khi dữ liệu cũ.
        </div>
      )}
      {dataStale && (
        <div role="alert" data-testid="data-stale-banner" className={`rounded-md border px-3 py-2 text-sm ${BAD}`}>
          Dữ liệu thị trường đã cũ ({ageText(view?.data_age_seconds)}) hoặc quote cũ — không có kế hoạch nào được coi là hợp lệ.
        </div>
      )}
      {view && !view.available && (
        <div role="alert" className={`rounded-md border px-3 py-2 text-sm ${WARN}`}>
          Engine chưa có quyết định: {view.problems.join("; ")}
        </div>
      )}
      {view?.problems?.map((p) => (
        <div key={p} data-testid="problem" className={`rounded-md border px-3 py-1.5 text-sm ${WARN}`}>
          {p}
        </div>
      ))}
      {view?.auto_paper && (
        <div role="status" data-testid="auto-paper-banner" className={`rounded-md border px-3 py-1.5 text-sm ${WARN}`}>
          AUTO_PAPER đang BẬT: lệnh PAPER sẽ tự mở khi có quyết định hành động (chỉ bàn paper, không bao giờ gửi lệnh tới MT5).
        </div>
      )}
      {message && (
        <div role="status" data-testid="action-message" className={`rounded-md border px-3 py-2 text-sm ${message.tone}`}>
          {message.text}
        </div>
      )}

      <div className="grid gap-3 lg:grid-cols-3">
        {/* 1. LIVE CHART */}
        <section data-testid="chart-card" className={`min-w-0 space-y-2 lg:col-span-2 ${anyStale ? "opacity-60" : ""}`}>
          <div className="flex flex-wrap items-center gap-2">
            <div role="group" aria-label="Khung thời gian biểu đồ" className="flex gap-1">
              {MARKET_TIMEFRAMES.map((t) => (
                <button
                  key={t}
                  type="button"
                  data-testid={`chart-tf-${t}`}
                  aria-pressed={t === tf}
                  onClick={() => setTf(t)}
                  className={`rounded-md border px-2 py-1 text-xs ${t === tf ? "border-sky-600 bg-sky-500/15 font-semibold" : "border-slate-400"}`}
                >
                  {t}
                </button>
              ))}
            </div>
            <div role="group" aria-label="Lớp phủ" className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
              {TOGGLES.map(([key, label]) => (
                <label key={key} className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    data-testid={`toggle-${key}`}
                    checked={overlays[key]}
                    onChange={(e) => setOverlays({ ...overlays, [key]: e.target.checked })}
                  />
                  {label}
                </label>
              ))}
              <label className="flex items-center gap-1">
                <input type="checkbox" data-testid="toggle-history" checked={history} onChange={(e) => setHistory(e.target.checked)} />
                Paper trade history
              </label>
            </div>
          </div>
          {/* chart-side multi-timeframe matrix: TF / ROLE / STATE; click = switch the chart */}
          <div data-testid="matrix" className="grid grid-cols-2 gap-1 text-xs sm:grid-cols-3 lg:grid-cols-6">
            {(view?.timeframes ?? []).map((r) => (
              <button
                key={r.timeframe}
                type="button"
                data-testid={`matrix-${r.timeframe}`}
                onClick={() => setTf(r.timeframe as MarketTimeframe)}
                className="rounded-md border border-slate-300 px-2 py-1 text-left hover:bg-slate-500/10 dark:border-slate-700"
                title={`Hiển thị biểu đồ ${r.timeframe}`}
              >
                <div className="font-semibold">{r.timeframe} <span className="font-normal text-slate-500">{r.role.split(" ")[0]}</span></div>
                <div className="truncate">{r.state}</div>
              </button>
            ))}
          </div>
          <TradeChart
            bars={bars?.bars ?? []}
            timeframe={tf}
            zone={zone}
            overlays={overlays}
            view={view}
            markers={markers}
            history={history}
            planLive={planLive}
          />
          <p data-testid="volume-line" className="text-xs text-slate-500">
            Tick volume M1 (không phải volume sàn): {view?.volume?.state ?? "—"} · tương đối {fmt(view?.volume?.m1_relative)} · percentile{" "}
            {view?.volume?.m1_percentile === null || view?.volume?.m1_percentile === undefined ? "—" : `${(view.volume.m1_percentile * 100).toFixed(0)}%`} · z {fmt(view?.volume?.m1_zscore)}
          </p>
        </section>

        {/* 2-4. DECISION, PLAN, POSITION */}
        <div className="min-w-0 space-y-3">
          <Card title="Quyết định hiện tại" testId="decision-card">
            <div className="flex flex-wrap items-center gap-3">
              <span data-testid="decision" className={`rounded-lg border-2 px-5 py-2 text-3xl font-black ${SIDE_STYLE[side]}`}>
                {side !== "WAIT" && (expired || dataStale) ? `${side} (${expired ? "hết hạn" : "dữ liệu cũ"})` : side}
              </span>
              {side !== "WAIT" && !expired && secondsLeft !== null && (
                <span data-testid="expiry" className="text-sm">
                  còn hiệu lực <b>{Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, "0")}</b>
                </span>
              )}
            </div>
            {side === "WAIT" && view?.available && (
              <p data-testid="blocked-by" className="mt-2 text-sm">
                Blocked by: <b>{blockedBy.join(", ") || "—"}</b>
              </p>
            )}
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Pill label="bằng chứng" value="CHƯA KIỂM CHỨNG" tone={WARN} testId="evidence-pill" />
              {view?.news?.warning && <Pill label="tin tức" value="CHƯA XÁC MINH (NEWS NOT VERIFIED)" tone={WARN} testId="news-warning" />}
              {view?.setup?.phase && view.setup.phase !== "NONE" && (
                <Pill label="setup" value={view.setup.phase} tone={view.setup.phase === "TRIGGERED" ? GOOD : NEUTRAL} testId="setup-phase" />
              )}
            </div>

            {side !== "WAIT" && decision && (
              <div data-testid="plan-card" className="mt-3 border-t border-slate-200 pt-2 dark:border-slate-800">
                <Row k="Vào lệnh (MARKET)" v={fmt(decision.entry_price)} testId="plan-entry" />
                <Row k="Stop loss" v={fmt(decision.stop_loss)} testId="plan-sl" />
                <Row k="Take profit" v={fmt(decision.take_profit)} testId="plan-tp" />
                <Row k="R/R (sau phí)" v={fmt(decision.risk_reward)} testId="plan-rr" />
                <Row k="Mô hình stop" v={decision.stop_model ?? "—"} />
                {decision.invalidation && <p className="mt-1 text-xs text-slate-500">Vô hiệu khi: {decision.invalidation}</p>}
                <div className="mt-2 flex flex-wrap items-center gap-2" role="group" aria-label="Mức rủi ro">
                  {(view?.risk_choices ?? [0.1, 0.25, 0.5]).map((r) => (
                    <button
                      key={r}
                      type="button"
                      data-testid={`risk-${r}`}
                      aria-pressed={r === risk}
                      onClick={() => setRisk(r)}
                      className={`rounded-md border px-3 py-1 text-sm ${r === risk ? "border-sky-600 bg-sky-500/15 font-semibold" : "border-slate-400"}`}
                    >
                      {r.toFixed(2)}%
                    </button>
                  ))}
                </div>
                {plan ? (
                  <div className="mt-1" data-testid="risk-plan">
                    <Row k="Lot" v={fmt(plan.lots, 2)} testId="plan-lots" />
                    <Row k="Rủi ro nếu chạm SL" v={money(-plan.loss_at_sl)} />
                    <Row k="Lãi nếu chạm TP" v={money(plan.gain_at_tp)} />
                    <p className="text-xs text-slate-500">vốn paper giả lập ${fmt(view?.desk?.account.equity, 0)}</p>
                    {plan.errors.length > 0 && <p className="text-sm text-red-600">{plan.errors.join(", ")}</p>}
                  </div>
                ) : (
                  <p className="mt-1 text-sm text-slate-500">Chưa tính được lot (thiếu thông số hợp đồng của broker).</p>
                )}
                {blockers.length > 0 && (
                  <p data-testid="blockers" className="mt-2 text-sm text-amber-700 dark:text-amber-300">
                    Không thể mở lệnh: {blockers.map((b) => BLOCKER_TEXT[b] ?? b).join("; ")}
                  </p>
                )}
                {!confirming ? (
                  <button
                    type="button"
                    data-testid="take-paper"
                    disabled={!canOpen || busy}
                    onClick={() => setConfirming(true)}
                    className="mt-3 w-full rounded-md border border-sky-600 bg-sky-500/15 px-3 py-2 font-semibold disabled:opacity-40"
                  >
                    Mở lệnh PAPER {side}
                  </button>
                ) : (
                  <div className="mt-3 flex gap-2" role="alertdialog" aria-label="Xác nhận lệnh paper">
                    <button type="button" data-testid="confirm-paper" onClick={take} disabled={busy} className="flex-1 rounded-md border border-emerald-600 bg-emerald-500/15 px-3 py-2 font-semibold">
                      Xác nhận: {side} {fmt(plan?.lots, 2)} lot (PAPER)
                    </button>
                    <button type="button" onClick={() => setConfirming(false)} className="rounded-md border border-slate-400 px-3 py-2">
                      Hủy
                    </button>
                  </div>
                )}
              </div>
            )}
          </Card>

          <Card title="Lệnh paper đang mở" testId="position-card">
            {view?.desk?.position ? (
              <Position trade={view.desk.position} onClose={closeNow} busy={busy} />
            ) : (
              <p className="text-sm text-slate-500">Không có lệnh paper đang mở.</p>
            )}
          </Card>

          <details data-testid="why-wait" className="rounded-lg border border-slate-300 p-3 dark:border-slate-700" open={side === "WAIT"}>
            <summary className="cursor-pointer text-sm font-semibold uppercase tracking-wide text-slate-500">
              {side === "WAIT" ? "Why WAIT?" : "Chuỗi điều kiện"}
            </summary>
            <ul className="mt-2 space-y-0.5 text-sm" data-testid="stages">
              {(view?.why_wait?.stages ?? []).map((s) => (
                <li key={s.stage} data-testid={`stage-${s.stage.replace(/[^A-Za-z0-9]+/g, "-")}`} className="flex justify-between">
                  <span>{s.stage}</span>
                  <span className={s.status === "PASS" ? "text-emerald-600" : s.status === "FAIL" ? "font-semibold text-red-600" : "text-slate-400"}>
                    {s.status === "NOT_REACHED" ? "—" : s.status}
                  </span>
                </li>
              ))}
            </ul>
            {view?.why_wait?.waiting_for && side === "WAIT" && (
              <p data-testid="waiting-for" className="mt-2 rounded-md bg-slate-500/10 px-2 py-1 text-sm">
                Waiting for: <b>{view.why_wait.waiting_for}</b>
                <span className="block text-xs text-slate-500">Trạng thái giải thích, không phải dự báo hay khuyến nghị.</span>
              </p>
            )}
          </details>
        </div>
      </div>

      {view?.available && (
        <>
          {/* 5-6. MULTI-TF STATE and REASONS */}
          <div className="grid gap-3 lg:grid-cols-3">
            <div className="min-w-0 lg:col-span-2">
              <Card title="Khung thời gian" testId="timeframes">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="text-xs text-slate-500">
                      <tr>
                        <th className="pr-3">TF</th>
                        <th className="pr-3">Vai trò</th>
                        <th className="pr-3">Trạng thái</th>
                        <th className="pr-3">Hướng</th>
                        <th className="pr-3">Tick vol (tương đối)</th>
                        <th>Dữ liệu</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(view.timeframes ?? []).map((r) => (
                        <tr key={r.timeframe} data-testid={`tf-${r.timeframe}`} className="border-t border-slate-200 dark:border-slate-800">
                          <td className="pr-3 font-semibold">{r.timeframe}</td>
                          <td className="pr-3 text-xs text-slate-500">{r.role}</td>
                          <td className="pr-3">{r.state}</td>
                          <td className="pr-3">{biasText(r.bias)}</td>
                          <td className="pr-3 font-mono">{fmt(r.relative_tick_volume, 2)}</td>
                          <td className={r.freshness === "FRESH" ? "text-emerald-600" : "text-red-600"}>{r.freshness}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>
            <Card title="Lý do" testId="reasons-card">
              <ul data-testid="explanation" className="list-disc space-y-0.5 pl-5 text-sm">
                {(view.explanation ?? []).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              {(decision?.warnings ?? []).length > 0 && (
                <ul className="mt-1 list-disc pl-5 text-xs text-amber-700 dark:text-amber-300">
                  {decision?.warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              )}
              <p data-testid="evidence-text" className="mt-2 text-xs text-slate-500">{view.evidence.label} {view.evidence.research}</p>
            </Card>
          </div>

          {/* 8. ADVANCED DIAGNOSTICS */}
          <details data-testid="advanced" className="rounded-lg border border-slate-300 p-3 dark:border-slate-700">
            <summary className="cursor-pointer text-sm font-semibold uppercase tracking-wide text-slate-500">Chẩn đoán nâng cao</summary>
            <div className="mt-3 grid gap-3 lg:grid-cols-3">
              <Card title="Volume (tick volume)" testId="volume-card">
                <p data-testid="volume-note" className="mb-1 text-xs text-slate-500">{view.volume?.note}</p>
                <Row k="Trạng thái M1" v={view.volume?.state ?? "—"} />
                <Row k="Z-score" v={fmt(view.volume?.m1_zscore)} />
                <Row k="Tương đối" v={fmt(view.volume?.m1_relative)} />
                <Row k="Gia tốc" v={fmt(view.volume?.m1_acceleration)} />
              </Card>
              <Card title="Cấu trúc & mức giá" testId="structure-card">
                <Row k="Kháng cự gần" v={fmt(view.structure?.nearest_resistance as number | null)} />
                <Row k="Hỗ trợ gần" v={fmt(view.structure?.nearest_support as number | null)} />
                <Row k="PDH / PDL" v={`${fmt(view.structure?.pdh as number | null)} / ${fmt(view.structure?.pdl as number | null)}`} />
                <Row k="Biến động" v={String(view.structure?.volatility ?? "—")} />
                <Row k="Phiên" v={String(view.structure?.session ?? "—")} />
                <Row k="BOS / CHOCH" v={`${view.structure?.bos ?? "—"} / ${view.structure?.choch ?? "—"}`} />
              </Card>
              <Card title="Tài khoản paper & hôm nay" testId="account-card">
                <p className="mb-1 text-xs text-slate-500">Vốn giả lập — không phải số dư FTMO.</p>
                <Row k="Equity" v={money(view.desk?.account.equity)} />
                <Row k="Số lệnh hôm nay" v={String(view.desk?.today.paper_trades ?? 0)} />
                <Row k="Thắng / Thua" v={`${view.desk?.today.wins ?? 0} / ${view.desk?.today.losses ?? 0}`} />
                <Row k="P&L ròng" v={money(view.desk?.today.net_pnl as number | null)} />
                <Row k="Tổng R" v={fmt(view.desk?.today.net_r as number | null)} />
              </Card>
              {view.telemetry && (
                <Card title="Phễu quyết định hôm nay" testId="telemetry-card">
                  <Row k="BUY / SELL / WAIT" v={`${view.telemetry.buy} / ${view.telemetry.sell} / ${view.telemetry.wait}`} />
                  <Row k="Setup khác nhau" v={String(view.telemetry.distinct_setups)} />
                  <Row k="Lý do chặn phổ biến" v={view.telemetry.most_common_blocker ?? "—"} />
                  {view.telemetry.setup_phases && (
                    <Row k="Giai đoạn setup" v={Object.entries(view.telemetry.setup_phases).map(([k, n]) => `${k}:${n}`).join(" ")} />
                  )}
                </Card>
              )}
              <Card title="Khóa thực thi DEMO" testId="demo-lock">
                <Pill label="" value={view.demo.status === "LOCKED" ? "ĐANG KHÓA" : "MỞ KHÓA THEO CẤU HÌNH"} tone={view.demo.status === "LOCKED" ? BAD : WARN} />
                <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs">
                  {view.demo.reasons.map((r) => (
                    <li key={r.code}>
                      <b>{r.code}</b>: {r.why}
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-xs text-slate-500">Bàn paper không bao giờ gửi lệnh tới MT5. {view.demo.how_to_unlock}</p>
              </Card>
            </div>
          </details>
        </>
      )}
    </main>
  );
}
