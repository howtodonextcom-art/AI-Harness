"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { HeroPanel, PositionCard } from "@/components/trade/HeroPanel";
import { AlertCard, ConditionsPanel, ForwardCard, FunnelCard, PaperHistory, SignalHistory, StrategyCard, WhyPanel } from "@/components/trade/InfoPanels";
import { StatusStrip } from "@/components/trade/StatusStrip";
import { TradeChart, type Overlays } from "@/components/trade/TradeChart";
import { BAD, Card, NEUTRAL, Pill, Row, WARN, ageText, biasText, fmt, money } from "@/components/trade/ui";
import { MARKET_TIMEFRAMES, fetchBars, type BarsResponse, type MarketTimeframe } from "@/lib/market";
import { formatInZone, loadZone, type DisplayZone } from "@/lib/time";
import {
  closePaperTrade,
  fetchDecision,
  fetchJournal,
  fetchMarkers,
  fetchSignals,
  openPaperTrade,
  type JournalResponse,
  type MarkersResponse,
  type PaperTrade,
  type SignalHistoryResponse,
  type SignalMarker,
  type TradeView as TradeViewData,
} from "@/lib/trade";

const POLL_MS = 3000;
const STALE_UI_SECONDS = 20;

const TOGGLES: [keyof Overlays, string][] = [
  ["signals", "Signals"],
  ["plan", "Trade Plan"],
  ["paper", "Paper Trades"],
  ["structure", "Structure"],
  ["volume", "Volume"],
];

/** The paper-trading cockpit: chart first, then the decision, plan, why, position and alerts. */
export function TradeView() {
  const [view, setView] = useState<TradeViewData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastOk, setLastOk] = useState<number | null>(null);
  const [now, setNow] = useState(0);
  const [skew, setSkew] = useState(0);
  const [risk, setRisk] = useState(0.25);
  const [zone, setZone] = useState<DisplayZone>("UTC");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: string; text: string } | null>(null);
  const [tf, setTf] = useState<MarketTimeframe>("M5");
  const [bars, setBars] = useState<BarsResponse | null>(null);
  const [barsError, setBarsError] = useState(false);
  const [markers, setMarkers] = useState<MarkersResponse | null>(null);
  const [signals, setSignals] = useState<SignalHistoryResponse | null>(null);
  const [journal, setJournal] = useState<JournalResponse | null>(null);
  const [history, setHistory] = useState(false);
  const [focus, setFocus] = useState<{ from: string; to: string } | null>(null);
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
      // expiry is judged on the SERVER clock (served_at), never the browser clock: a skewed PC clock
      // (or a replay) must not turn a live setup into an expired one, or the reverse
      const served = data.served_at ? Date.parse(data.served_at) : NaN;
      setSkew(Number.isFinite(served) ? served - Date.now() : 0);
    } catch {
      setError("API /trade/decision không phản hồi");
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
        if (alive) {
          setBars(b);
          setBarsError(b.bars.length === 0);
        }
      } catch {
        if (alive) setBarsError(true);
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

  // markers, signal history and journal; reloaded right after a paper action so the owner sees it at once
  const loadSide = useCallback(async () => {
    const [m, s, j] = await Promise.allSettled([fetchMarkers(), fetchSignals(), fetchJournal()]);
    if (m.status === "fulfilled") setMarkers(m.value);
    if (s.status === "fulfilled") setSignals(s.value);
    if (j.status === "fulfilled") setJournal(j.value);
  }, []);

  useEffect(() => {
    const first = setTimeout(() => void loadSide(), 0);
    const id = setInterval(() => void loadSide(), 6000);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, [loadSide]);

  const uiStale = lastOk === null || (now - lastOk) / 1000 > STALE_UI_SECONDS;
  const hero = view?.hero;
  const plan = view?.trade_plan ?? null;
  const expiresMs = plan?.expires_at ? Date.parse(plan.expires_at) : null;
  const serverNow = now + skew;
  const expiredNow = plan !== null && (plan.expired || (expiresMs !== null && expiresMs <= serverNow));
  const planLive = !uiStale && !expiredNow && Boolean(plan?.complete) && (hero?.state === "BUY_READY" || hero?.state === "SELL_READY");
  const untrusted = hero?.state === "UNAVAILABLE" || hero?.state === "STALE";
  const dim = uiStale || untrusted;

  const focusTf = (target: string) => {
    if ((MARKET_TIMEFRAMES as readonly string[]).includes(target)) setTf(target as MarketTimeframe);
  };
  const focusPaper = (t: PaperTrade) => {
    setTf("M5");
    setFocus({ from: t.opened_at ?? t.created_at, to: t.closed_at ?? new Date().toISOString() });
  };
  const focusSignal = (s: SignalMarker) => {
    setTf("M5");
    setFocus({ from: s.bar_time, to: s.bar_time });
  };

  const take = async () => {
    if (!plan) return;
    setBusy(true);
    const res = await openPaperTrade(plan.setup_id, risk);
    setMessage(
      res.ok
        ? {
            tone: "border-emerald-600 bg-emerald-500/15",
            text: `Đã mở lệnh PAPER ${res.data.side} ${fmt(res.data.lots, 2)} lot: kế hoạch ${fmt(res.data.planned_entry ?? null)}, khớp ${fmt(res.data.fill_price)}`,
          }
        : { tone: BAD, text: `Không mở được: ${res.error.message} (${res.error.code})` },
    );
    setBusy(false);
    void load();
    void loadSide();
  };

  const closeNow = async () => {
    const trade = view?.desk?.position;
    if (!trade) return;
    setBusy(true);
    const res = await closePaperTrade(trade.trade_id);
    setMessage(
      res.ok
        ? { tone: "border-emerald-600 bg-emerald-500/15", text: `Đã đóng lệnh paper: ${money(res.data.net_pnl ?? null)} (${fmt(res.data.r_multiple ?? null, 2)}R), lý do ${res.data.exit_reason}` }
        : { tone: BAD, text: `Không đóng được: ${res.error.message} (${res.error.code})` },
    );
    setBusy(false);
    void load();
    void loadSide();
  };

  const closed = (journal?.trades ?? []).filter((t) => t.status === "CLOSED");
  const mode = view?.source_mode ?? "LIVE";

  return (
    <main className="mx-auto w-full max-w-7xl space-y-3 px-3 py-3 sm:px-4">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-bold">XAUUSD · FTMO DEMO</h1>
        <Pill value="PAPER ONLY — không gửi lệnh thật" tone={WARN} testId="paper-only" />
        {view?.market && <Pill label="thị trường" value={view.market.open ? "MỞ" : view.market.status} tone={view.market.open ? "border-emerald-600 bg-emerald-500/15 text-emerald-800 dark:text-emerald-200" : NEUTRAL} testId="market-pill" />}
        {view?.quote && (
          <span data-testid="quote" className="font-mono text-sm">
            {fmt(view.quote.bid)} / {fmt(view.quote.ask)} · spread {fmt(view.quote.spread_points, 0)} điểm
          </span>
        )}
        <span data-testid="data-age" className="text-xs text-slate-500">
          dữ liệu: {ageText(view?.data_age_seconds)} · cập nhật {view ? formatInZone(view.generated_at, zone) : "—"} ({zone})
        </span>
        <Link href="/journal" className="ml-auto rounded-md border border-slate-400 px-2 py-1 text-xs">Journal →</Link>
      </header>

      <StatusStrip strip={view?.status_strip} mode={view?.source_mode} />

      {mode !== "LIVE" && (
        <div role="alert" data-testid="replay-banner" className={`rounded-md border-2 px-3 py-2 text-sm font-semibold ${BAD}`}>
          {mode.replace("_", " ")} — NOT LIVE. Dữ liệu đã đốt phát lại qua đúng đường quyết định; không phải thị trường sống.
        </div>
      )}
      {(error || uiStale) && (
        <div role="alert" data-testid="api-down-banner" className={`rounded-md border px-3 py-2 text-sm ${BAD}`}>
          <b>API UNAVAILABLE</b>: {error ?? "đang chờ dữ liệu"}. Quyết định hiển thị (nếu có) có thể đã cũ, đây KHÔNG phải WAIT; không được vào lệnh.
        </div>
      )}
      {view && <ConditionsPanel conditions={view.conditions} />}
      {barsError && (
        <div role="alert" data-testid="chart-unavailable" className={`rounded-md border px-3 py-2 text-sm ${WARN}`}>
          <b>CHART DATA UNAVAILABLE</b>: không tải được nến {tf}. Biểu đồ đang hiển thị dữ liệu cuối cùng (nếu có).
        </div>
      )}
      {message && (
        <div role="status" data-testid="action-message" className={`rounded-md border px-3 py-2 text-sm ${message.tone}`}>
          {message.text}
        </div>
      )}
      {view?.auto_paper && (
        <div role="status" data-testid="auto-paper-banner" className={`rounded-md border px-3 py-1.5 text-sm ${WARN}`}>
          AUTO_PAPER đang BẬT: lệnh PAPER tự mở khi có quyết định hành động (chỉ bàn paper, không bao giờ gửi lệnh tới MT5).
        </div>
      )}
      {!view && !error && <p data-testid="loading" className="text-sm text-slate-500">Đang tải quyết định…</p>}

      <div className="grid gap-3 lg:grid-cols-3">
        {/* 1. LIVE CHART */}
        <section data-testid="chart-card" className={`min-w-0 space-y-2 lg:col-span-2 ${dim ? "opacity-60" : ""}`}>
          <div className="flex flex-wrap items-center gap-2">
            <div role="group" aria-label="Khung thời gian biểu đồ" className="flex gap-1">
              {MARKET_TIMEFRAMES.map((t) => (
                <button key={t} type="button" data-testid={`chart-tf-${t}`} aria-pressed={t === tf} onClick={() => setTf(t)} className={`rounded-md border px-2 py-1 text-xs ${t === tf ? "border-sky-600 bg-sky-500/15 font-semibold" : "border-slate-400"}`}>
                  {t}
                </button>
              ))}
            </div>
            <div role="group" aria-label="Lớp phủ" className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
              {TOGGLES.map(([key, label]) => (
                <label key={key} className="flex items-center gap-1">
                  <input type="checkbox" data-testid={`toggle-${key}`} checked={overlays[key]} onChange={(e) => setOverlays({ ...overlays, [key]: e.target.checked })} />
                  {label}
                </label>
              ))}
              <label className="flex items-center gap-1">
                <input type="checkbox" data-testid="toggle-history" checked={history} onChange={(e) => setHistory(e.target.checked)} />
                Paper trade history
              </label>
            </div>
          </div>
          {/* chart-side multi-timeframe matrix: TF / ROLE / STATE; a click switches the chart */}
          <div data-testid="matrix" className="grid grid-cols-2 gap-1 text-xs sm:grid-cols-3 lg:grid-cols-6">
            {(view?.timeframes ?? []).map((r) => (
              <button key={r.timeframe} type="button" data-testid={`matrix-${r.timeframe}`} onClick={() => focusTf(r.timeframe)} className="rounded-md border border-slate-300 px-2 py-1 text-left hover:bg-slate-500/10 dark:border-slate-700" title={`Hiển thị biểu đồ ${r.timeframe}`}>
                <div className="font-semibold">{r.timeframe} <span className="font-normal text-slate-500">{r.role.split(" ")[0]}</span></div>
                <div className="truncate">{r.state}</div>
              </button>
            ))}
          </div>
          <TradeChart bars={bars?.bars ?? []} timeframe={tf} zone={zone} overlays={overlays} view={view} markers={markers} history={history} planLive={planLive} focus={focus} plan={plan} />
          <p data-testid="volume-line" className="text-xs text-slate-500">
            Tick volume M1 (không phải volume sàn): {view?.volume?.state ?? "—"} · tương đối {fmt(view?.volume?.m1_relative)} · percentile{" "}
            {view?.volume?.m1_percentile === null || view?.volume?.m1_percentile === undefined ? "—" : `${(view.volume.m1_percentile * 100).toFixed(0)}%`} · z {fmt(view?.volume?.m1_zscore)}
          </p>
        </section>

        {/* 2-5. DECISION, PLAN, POSITION, WHY */}
        <div className="min-w-0 space-y-3">
          {view && <HeroPanel view={view} nowMs={serverNow} risk={risk} onRisk={setRisk} onOpen={take} busy={busy} uiStale={uiStale} />}
          {view && <PositionCard trade={view.desk?.position ?? null} onClose={closeNow} busy={busy} />}
          {view && <WhyPanel why={view.why_wait} side={view.hero.state === "SETUP_ARMED" ? "SETUP_ARMED" : view.decision?.decision ?? "WAIT"} onFocus={focusTf} current={tf} />}
        </div>
      </div>

      {view?.available && (
        <>
          <div className="grid gap-3 lg:grid-cols-3">
            <div className="min-w-0 lg:col-span-2">
              <Card title="Khung thời gian" testId="timeframes">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="text-xs text-slate-500">
                      <tr><th className="pr-3">TF</th><th className="pr-3">Vai trò</th><th className="pr-3">Trạng thái</th><th className="pr-3">Hướng</th><th className="pr-3">Tick vol (tương đối)</th><th>Dữ liệu</th></tr>
                    </thead>
                    <tbody>
                      {(view.timeframes ?? []).map((r) => (
                        <tr key={r.timeframe} data-testid={`tf-${r.timeframe}`} tabIndex={0} onClick={() => focusTf(r.timeframe)} onKeyDown={(e) => e.key === "Enter" && focusTf(r.timeframe)} className="cursor-pointer border-t border-slate-200 hover:bg-slate-500/10 dark:border-slate-800">
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
                {(view.explanation ?? []).map((line) => (<li key={line}>{line}</li>))}
              </ul>
              {(view.decision?.warnings ?? []).length > 0 && (
                <ul className="mt-1 list-disc pl-5 text-xs text-amber-700 dark:text-amber-300">
                  {view.decision?.warnings.map((w) => (<li key={w}>{w}</li>))}
                </ul>
              )}
              <p data-testid="evidence-text" className="mt-2 text-xs text-slate-500">{view.evidence.label} {view.evidence.research}</p>
            </Card>
          </div>

          <div className="grid gap-3 lg:grid-cols-3">
            <AlertCard alerts={view.alerts} mode={mode} />
            <PaperHistory trades={closed} onFocus={focusPaper} />
            <SignalHistory signals={signals?.signals ?? []} mode={signals?.source_mode ?? mode} onFocus={focusSignal} />
          </div>

          <div className="grid gap-3 lg:grid-cols-3">
            <FunnelCard funnel={view.funnel} />
            <StrategyCard strategy={view.strategy} />
            <ForwardCard view={view} />
          </div>

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
              <Card title="PAPER ACCOUNT & hôm nay" testId="account-card">
                <p className="mb-1 text-xs text-slate-500">{view.paper_account_label}</p>
                <Row k="PAPER equity" v={money(view.desk?.account.equity)} />
                <Row k="Số lệnh hôm nay" v={String(view.desk?.today.paper_trades ?? 0)} />
                <Row k="Thắng / Thua" v={`${view.desk?.today.wins ?? 0} / ${view.desk?.today.losses ?? 0}`} />
                <Row k="P&L ròng" v={money(view.desk?.today.net_pnl as number | null)} />
                <Row k="Tổng R" v={fmt(view.desk?.today.net_r as number | null)} />
                <Row k="Chính sách đóng thị trường" v={view.desk?.closure_policy ?? "—"} />
              </Card>
              <Card title="Khóa thực thi DEMO" testId="demo-lock">
                <Pill value={view.demo.status === "LOCKED" ? "ĐANG KHÓA" : "MỞ KHÓA THEO CẤU HÌNH"} tone={view.demo.status === "LOCKED" ? "border-sky-600 bg-sky-500/15 text-sky-800 dark:text-sky-200" : WARN} />
                <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs">
                  {view.demo.reasons.map((r) => (<li key={r.code}><b>{r.code}</b>: {r.why}</li>))}
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
