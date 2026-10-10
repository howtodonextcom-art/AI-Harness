"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChartToolbar } from "@/components/terminal/ChartToolbar";
import { CloseConfirmModal, OpenConfirmModal, planMatches, type FrozenPlan } from "@/components/terminal/ConfirmModals";
import { DecisionBody, DecisionHero } from "@/components/terminal/DecisionPanel";
import { MarketBar } from "@/components/terminal/MarketBar";
import { Modal } from "@/components/terminal/Modal";
import { MtfStrip } from "@/components/terminal/MtfStrip";
import { TerminalChart, type ChartHandle, type Tool } from "@/components/terminal/TerminalChart";
import { Workspace } from "@/components/terminal/Workspace";
import { BAD, WARN, fmt, money } from "@/components/trade/ui";
import { fetchBars, type BarsResponse, type MarketTimeframe } from "@/lib/market";
import { DEFAULT_PREFS, crossed, loadAlerts, loadLevels, loadPrefs, newId, saveAlerts, saveLevels, savePrefs, type ManualLevel, type Prefs, type PriceAlert, type Tab } from "@/lib/prefs";
import { loadZone, saveZone, type DisplayZone } from "@/lib/time";
import {
  closePaperTrade,
  fetchDecision,
  fetchJournal,
  fetchMarkers,
  fetchSetups,
  fetchSignals,
  openPaperTrade,
  type JournalResponse,
  type MarkersResponse,
  type PaperTrade,
  type SetupHistoryResponse,
  type SignalHistoryResponse,
  type SignalMarker,
  type TradeView as TradeViewData,
} from "@/lib/trade";
import { BASE_TITLE, beep, isNewSetup, readyTitle, systemNotify } from "@/lib/notify";
import { EXIT_REASON_VI, HERO_ICON, HERO_VI, humanCondition } from "@/lib/vi";

const POLL_MS = 3000;
const STALE_UI_SECONDS = 15; // longer than one aborted poll (8 s) plus the interval, so one slow answer does not flicker the ticket

const SHORTCUTS: [string, string][] = [
  ["1", "Biểu đồ M1"],
  ["5", "Biểu đồ M5"],
  ["2", "Biểu đồ M15"],
  ["3", "Biểu đồ M30"],
  ["H", "Biểu đồ H1"],
  ["4", "Biểu đồ H4"],
  ["F", "Vừa khung nhìn"],
  ["L", "Về nến mới nhất"],
  ["W", "Bật/tắt theo nến mới"],
  ["X", "Toàn màn hình"],
  ["M", "Công cụ đo"],
  ["T", "Vẽ đường ngang"],
  ["?", "Mở bảng phím tắt"],
  ["Esc", "Thoát công cụ / toàn màn hình / đóng hộp thoại"],
];

/** The PAPER trading terminal: price and market first, then the chart and the decision to act on. */
export function TerminalView() {
  const [view, setView] = useState<TradeViewData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastOk, setLastOk] = useState<number | null>(null);
  const [now, setNow] = useState(0);
  const [skew, setSkew] = useState(0);
  const [prefs, setPrefsState] = useState<Prefs>(DEFAULT_PREFS);
  const [hydrated, setHydrated] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: string; text: string } | null>(null);
  const [bars, setBars] = useState<BarsResponse | null>(null);
  const [barsError, setBarsError] = useState(false);
  const [markers, setMarkers] = useState<MarkersResponse | null>(null);
  const [signals, setSignals] = useState<SignalHistoryResponse | null>(null);
  const [setups, setSetups] = useState<SetupHistoryResponse | null>(null);
  const [journal, setJournal] = useState<JournalResponse | null>(null);
  const [focus, setFocus] = useState<{ from: string; to: string } | null>(null);
  const [tool, setTool] = useState<Tool>("none");
  const [levels, setLevels] = useState<ManualLevel[]>([]);
  const [alerts, setAlerts] = useState<PriceAlert[]>([]);
  const [fullscreen, setFullscreen] = useState(false);
  const [openFrozen, setOpenFrozen] = useState<FrozenPlan | null>(null);
  const [closing, setClosing] = useState(false);
  const [help, setHelp] = useState(false);
  const chart = useRef<ChartHandle>(null);
  const inFlight = useRef(false);
  const decisionSeq = useRef(0);
  const sideSeq = useRef(0);
  const alertsRef = useRef<PriceAlert[]>([]);
  const prevBid = useRef<number | null>(null);

  const setPrefs = useCallback((patch: Partial<Prefs>) => setPrefsState((p) => ({ ...p, ...patch })), []);

  // ---- hydrate local preferences, annotations, journal->chart deep link ------------------------
  useEffect(() => {
    const t = setTimeout(() => {
      const loaded = loadPrefs();
      const zone = loadZone(loaded.zone);
      const params = new URLSearchParams(window.location.search);
      const from = params.get("focus");
      const link = from && Number.isFinite(Date.parse(from)) && Number.isFinite(Date.parse(params.get("to") ?? from)) ? { from, to: params.get("to") ?? from } : null;
      const linkTf = params.get("tf");
      setPrefsState({ ...loaded, zone, ...(linkTf && ["M1", "M5", "M15", "M30", "H1", "H4"].includes(linkTf) ? { tf: linkTf } : {}), ...(link ? { history: true, tab: "position" as Tab } : {}) });
      setLevels(loadLevels());
      const stored = loadAlerts();
      alertsRef.current = stored;
      setAlerts(stored);
      if (link) setFocus(link);
      setHydrated(true);
    }, 0);
    return () => clearTimeout(t);
  }, []);
  useEffect(() => {
    if (hydrated) savePrefs(prefs);
  }, [prefs, hydrated]);
  useEffect(() => {
    const onStorage = () => {
      const stored = loadAlerts();
      alertsRef.current = stored;
      setAlerts(stored);
      setLevels(loadLevels());
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);
  useEffect(() => {
    if (hydrated) saveLevels(levels);
  }, [levels, hydrated]);

  // ---- the decision (every 3 s) -----------------------------------------------------------------
  const fireAlerts = useCallback((bid: number) => {
    const fired: PriceAlert[] = [];
    const next = alertsRef.current.map((a) => {
      if (crossed(a, prevBid.current, bid)) {
        const done = { ...a, firedAt: new Date().toISOString() };
        fired.push(done);
        return done;
      }
      return a;
    });
    prevBid.current = bid;
    if (fired.length === 0) return;
    alertsRef.current = next;
    setAlerts(next);
    saveAlerts(next);
    const text = fired.map((a) => `XAUUSD ${a.direction === "UP" ? "vượt" : "xuống dưới"} ${a.price.toFixed(2)}`).join(" · ");
    setMessage({ tone: "border-amber-600 bg-amber-500/15", text: `🔔 Cảnh báo giá: ${text}` });
    try {
      if ("Notification" in window && Notification.permission === "granted") new Notification("XAU EDGE — cảnh báo giá", { body: text });
    } catch {
      /* notifications unavailable: the on-page message is enough */
    }
  }, []);

  const load = useCallback(async (force = false) => {
    if (inFlight.current && !force) return;
    const seq = ++decisionSeq.current; // only the newest request may change what is shown
    inFlight.current = true;
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), 8000);
    try {
      const data = await fetchDecision(ctl.signal);
      if (seq !== decisionSeq.current) return;
      setView(data);
      setError(null);
      setLastOk(Date.now());
      setNow(Date.now());
      // expiry and every countdown run on the SERVER clock (served_at), never the browser clock
      const served = data.served_at ? Date.parse(data.served_at) : Date.parse(data.generated_at);
      setSkew(Number.isFinite(served) ? served - Date.now() : 0);
      if (data.quote && !data.quote.stale && data.source_mode === "LIVE") fireAlerts(data.quote.bid); // never on replay prices
    } catch {
      if (seq === decisionSeq.current) setError("API /trade/decision không phản hồi");
    } finally {
      clearTimeout(timer);
      if (seq === decisionSeq.current) inFlight.current = false;
    }
  }, [fireAlerts]);

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

  // ---- candles of the selected timeframe -------------------------------------------------------
  const tf = prefs.tf as MarketTimeframe;
  useEffect(() => {
    let alive = true;
    let seq = 0;
    const run = async () => {
      const mine = ++seq;
      try {
        const b = await fetchBars(tf, 400, true);
        if (alive && mine === seq && b.timeframe === tf) {
          setBars(b);
          setBarsError(b.bars.length === 0);
        } else if (alive && mine === seq) setBarsError(true);
      } catch {
        if (alive) setBarsError(true);
      }
    };
    const first = setTimeout(() => void run(), 0);
    const id = setInterval(() => void run(), POLL_MS);
    return () => {
      alive = false;
      clearTimeout(first);
      clearInterval(id);
    };
  }, [tf]);

  // markers, signal history and journal; reloaded right after a paper action
  const loadSide = useCallback(async () => {
    const seq = ++sideSeq.current;
    const [m, s, j, u] = await Promise.allSettled([fetchMarkers(), fetchSignals(), fetchJournal(), fetchSetups()]);
    if (seq !== sideSeq.current) return;
    if (m.status === "fulfilled") setMarkers(m.value);
    if (s.status === "fulfilled") setSignals(s.value);
    if (j.status === "fulfilled") setJournal(j.value);
    if (u.status === "fulfilled") setSetups(u.value);
  }, []);
  useEffect(() => {
    const first = setTimeout(() => void loadSide(), 0);
    const id = setInterval(() => void loadSide(), 6000);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, [loadSide]);

  // a trade opened or closed (possibly by the engine itself): refresh markers/journal at once instead of at the next 6 s poll
  const exitedId = view?.desk?.last_exit?.trade_id ?? null;
  const openId = view?.desk?.position?.trade_id ?? null;
  useEffect(() => {
    if (exitedId === null && openId === null) return;
    const t = setTimeout(() => void loadSide(), 0);
    return () => clearTimeout(t);
  }, [exitedId, openId, loadSide]);

  // a success message is a receipt, not a status: it goes away by itself (errors stay until dismissed)
  useEffect(() => {
    if (!message || message.tone === BAD) return;
    const t = setTimeout(() => setMessage(null), 12_000);
    return () => clearTimeout(t);
  }, [message]);

  // ---- derived ---------------------------------------------------------------------------------
  const uiStale = lastOk === null || (now - lastOk) / 1000 > STALE_UI_SECONDS;
  const serverNow = now + skew;
  const hero = view?.hero;
  const plan = view?.trade_plan ?? null;
  const expiresMs = plan?.expires_at ? Date.parse(plan.expires_at) : null;
  const expiredNow = plan !== null && (plan.expired || (expiresMs !== null && expiresMs <= serverNow));
  const planLive = !uiStale && !error && !expiredNow && Boolean(plan?.complete) && (hero?.state === "BUY_READY" || hero?.state === "SELL_READY");
  const untrusted = hero?.state === "UNAVAILABLE" || hero?.state === "STALE";
  const dim = uiStale || untrusted;
  const mode = view?.source_mode ?? "LIVE";
  const position = view?.desk?.position ?? null;
  const chosen = view?.risk_plans?.find((p) => Math.abs(p.risk_pct - prefs.risk) < 1e-9);

  const frozenValid = useMemo(() => (openFrozen ? planMatches(openFrozen, plan, prefs.risk, Boolean(view?.actionable && !uiStale && !error && !expiredNow)) : false), [openFrozen, plan, prefs.risk, view?.actionable, uiStale, error, expiredNow]);

  // ---- actions ---------------------------------------------------------------------------------
  const requestOpen = () => {
    if (!plan || plan.side === undefined) return;
    setOpenFrozen({ setup_id: plan.setup_id, side: plan.side, sl: plan.sl, tp1: plan.tp1, risk: prefs.risk, entry: plan.planned_entry, lots: chosen?.lots ?? null, rr: plan.rr_net, riskAmount: chosen?.risk_amount ?? null, tp2: plan.tp2 });
  };
  const confirmOpen = async () => {
    const frozen = openFrozen;
    if (!frozen) return;
    setOpenFrozen(null);
    setBusy(true);
    const res = await openPaperTrade(frozen.setup_id, frozen.risk);
    setMessage(
      res.ok
        ? { tone: "border-emerald-600 bg-emerald-500/15", text: `Đã mở lệnh PAPER ${res.data.side === "BUY" ? "MUA" : "BÁN"} ${fmt(res.data.lots, 2)} lot: kế hoạch ${fmt(res.data.planned_entry ?? null)}, khớp ${fmt(res.data.fill_price)}` }
        : { tone: BAD, text: `Không mở được lệnh PAPER: ${res.error.message} (${res.error.code})` },
    );
    await Promise.all([load(true), loadSide()]);
    setBusy(false);
  };
  const confirmClose = async () => {
    if (!position) return;
    setClosing(false);
    setBusy(true);
    const res = await closePaperTrade(position.trade_id);
    setMessage(
      res.ok
        ? { tone: "border-emerald-600 bg-emerald-500/15", text: `Đã đóng lệnh paper: ${money(res.data.net_pnl ?? null)} (${fmt(res.data.r_multiple ?? null, 2)}R) — ${EXIT_REASON_VI[res.data.exit_reason ?? ""] ?? res.data.exit_reason}` }
        : { tone: BAD, text: `Không đóng được lệnh: ${res.error.message} (${res.error.code})` },
    );
    await Promise.all([load(true), loadSide()]);
    setBusy(false);
  };

  const focusTf = useCallback((target: string) => setPrefs({ tf: target }), [setPrefs]);
  const focusPaper = useCallback((t: PaperTrade) => {
    setPrefs({ history: true });
    setFocus({ from: t.opened_at ?? t.created_at, to: t.closed_at ?? new Date().toISOString() });
  }, [setPrefs]);
  const focusSignal = useCallback((s: SignalMarker) => setFocus({ from: s.at, to: s.at }), []);

  const addLevel = useCallback((price: number) => setLevels((l) => [...l, { id: newId(), price, label: "Đường" }].slice(-20)), []);
  const addAlert = useCallback((price: number) => {
    const bid = view?.quote?.bid ?? null;
    const alert: PriceAlert = { id: newId(), price, direction: bid !== null && price < bid ? "DOWN" : "UP", createdAt: new Date().toISOString(), firedAt: null };
    const next = [...alertsRef.current, alert].slice(-30);
    alertsRef.current = next;
    setAlerts(next);
    saveAlerts(next);
    try {
      if ("Notification" in window && Notification.permission === "default") void Notification.requestPermission();
    } catch {
      /* optional */
    }
  }, [view?.quote?.bid]);
  const removeAlert = useCallback((id: string) => {
    const next = alertsRef.current.filter((a) => a.id !== id);
    alertsRef.current = next;
    setAlerts(next);
    saveAlerts(next);
  }, []);

  const changeZone = (zone: DisplayZone) => {
    saveZone(zone);
    setPrefs({ zone });
  };

  // ---- a setup became ready: tab title, notification, optional beep (LIVE only, once per setup) -------
  const seenSetups = useRef<Set<string>>(new Set());
  const readySide = view?.source_mode === "LIVE" && !uiStale && !error && !expiredNow && (hero?.state === "BUY_READY" || hero?.state === "SELL_READY") ? plan?.side ?? null : null;
  const readyId = readySide ? plan?.setup_id ?? null : null;
  const readyEntry = plan?.planned_entry ?? null;
  useEffect(() => {
    if (!prefs.notify || !readySide || !readyId) {
      document.title = BASE_TITLE;
      return;
    }
    document.title = readyTitle(readySide, readyEntry);
    if (isNewSetup(seenSetups.current, readyId)) {
      systemNotify("XAU EDGE — setup sẵn sàng", readyTitle(readySide, readyEntry));
      if (prefs.sound) beep();
    }
    return () => {
      document.title = BASE_TITLE;
    };
  }, [prefs.notify, prefs.sound, readySide, readyId, readyEntry]);

  // ---- keyboard: safe shortcuts only (never an order) ------------------------------------------
  const modalOpen = openFrozen !== null || closing || help;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const el = e.target as HTMLElement | null;
      const typing = el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
      if (e.key === "Escape") {
        if (modalOpen || typing) return;
        if (tool !== "none") setTool("none");
        else if (fullscreen) setFullscreen(false);
        return;
      }
      if (typing || modalOpen || !prefs.shortcuts) return;
      const k = e.key.toLowerCase();
      const map: Record<string, string> = { "1": "M1", "5": "M5", "2": "M15", "3": "M30", h: "H1", "4": "H4" };
      if (map[k]) setPrefs({ tf: map[k] });
      else if (k === "f") chart.current?.fit();
      else if (k === "l") chart.current?.latest();
      else if (k === "w") setPrefs({ follow: !prefs.follow });
      else if (k === "x") setFullscreen((v) => !v);
      else if (k === "m") setTool((t) => (t === "measure" ? "none" : "measure"));
      else if (k === "t") setTool((t) => (t === "line" ? "none" : "line"));
      else if (e.key === "?") setHelp(true);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [modalOpen, tool, fullscreen, prefs.follow, prefs.shortcuts, setPrefs]);

  // ---- conditions that need attention are banners with a human sentence first -------------------
  const banners = (view?.conditions ?? []).filter((c) => (c.severity === "ERROR" || c.severity === "WARN") && c.code !== "MARKET_CLOSED" && c.code !== "NEWS_UNKNOWN");

  // no connection (or data that stopped arriving): never keep a green BUY on screen, whatever the last view said
  const heroView = view && (error || uiStale) ? { ...view, hero: { ...view.hero, action: { ...view.hero.action, code: "UNAVAILABLE" as const, stage: "API_DOWN" } } } : view;
  const heroNode = heroView && <DecisionHero view={heroView} serverNowMs={serverNow} />;
  const bodyNode = view && (
    <DecisionBody
      view={view}
      serverNowMs={serverNow}
      risk={prefs.risk}
      onRisk={(r) => setPrefs({ risk: r })}
      onOpenRequest={requestOpen}
      onCloseRequest={() => setClosing(true)}
      uiStale={uiStale || Boolean(error)}
      busy={busy}
      tf={prefs.tf}
      onFocusTf={focusTf}
      zone={prefs.zone}
    />
  );
  const ready = hero?.state === "BUY_READY" || hero?.state === "SELL_READY";
  const canOpen = Boolean(view?.actionable && !uiStale && !error && !expiredNow && plan?.complete && chosen?.ok);
  const showActionBar = Boolean(view && ((ready && !expiredNow) || hero?.state === "POSITION_OPEN"));

  const chartBlock = (
    <section
      data-testid="chart-card"
      aria-label="Biểu đồ"
      style={fullscreen ? undefined : { gridArea: "chart" }}
      className={fullscreen ? "fixed inset-0 z-40 flex flex-col gap-1 bg-white p-2 dark:bg-slate-950" : "relative flex min-w-0 flex-col gap-1"}
    >
      <ChartToolbar
        tf={prefs.tf}
        onTf={focusTf}
        overlays={prefs.overlays}
        onOverlays={(o) => setPrefs({ overlays: o })}
        history={prefs.history}
        onHistory={(v) => setPrefs({ history: v })}
        follow={prefs.follow}
        onFollow={(v) => setPrefs({ follow: v })}
        fullscreen={fullscreen}
        onFullscreen={setFullscreen}
        tool={tool}
        onTool={setTool}
        onFit={() => chart.current?.fit()}
        onLatest={() => chart.current?.latest()}
        onAlert={addAlert}
        bid={view?.quote?.bid ?? null}
        alertCount={alerts.filter((a) => !a.firedAt).length}
        onHelp={() => setHelp(true)}
      />
      <div className={`relative flex min-h-0 ${fullscreen ? "flex-1" : "h-[min(28rem,62vh)] sm:h-[28rem] lg:h-[min(38rem,calc(100vh-14rem))]"}`}>
        {dim && <div data-testid="chart-veil" aria-hidden="true" className="pointer-events-none absolute inset-0 z-[5] bg-white/60 dark:bg-slate-950/60" />}
        {hydrated && <TerminalChart
          ref={chart}
          bars={bars && bars.timeframe === prefs.tf ? bars.bars : []}
          timeframe={prefs.tf}
          zone={prefs.zone}
          overlays={prefs.overlays}
          view={view}
          markers={markers && markers.source_mode === mode ? markers : null}
          history={prefs.history}
          planLive={planLive}
          plan={plan}
          focus={focus}
          follow={prefs.follow}
          onFollowChange={(v) => setPrefs({ follow: v })}
          levels={levels}
          alerts={alerts}
          tool={tool}
          onAddLevel={addLevel}
          onToolDone={() => setTool("none")}
        />}
      </div>
      {fullscreen && view && (
        <div data-testid="fullscreen-summary" className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border border-slate-400 px-3 py-1.5 text-sm">
          <b>{HERO_ICON[view.hero.state]} {HERO_VI[view.hero.state].label}</b>
          {planLive && plan && <span className="font-mono">Entry {fmt(plan.planned_entry)} · SL {fmt(plan.sl)} · TP {fmt(plan.tp1)} · R/R {fmt(plan.rr_net)}</span>}
          {position && <span className="font-mono">{position.side} {fmt(position.fill_price)} · P&L {money(position.unrealized_pnl)} · {fmt(position.unrealized_r, 2)}R</span>}
          <span className="font-mono text-slate-600 dark:text-slate-400">{view.quote ? `${fmt(view.quote.bid)} / ${fmt(view.quote.ask)}` : ""}</span>
          {ready && !expiredNow && <button type="button" data-testid="fs-open" disabled={!canOpen || busy} onClick={requestOpen} className="rounded border-2 border-slate-600 px-2 py-0.5 text-xs font-bold disabled:opacity-40">Mở lệnh…</button>}
          {hero?.state === "POSITION_OPEN" && <button type="button" data-testid="fs-close" disabled={busy} onClick={() => setClosing(true)} className="rounded border-2 border-slate-600 px-2 py-0.5 text-xs font-bold disabled:opacity-40">Đóng lệnh…</button>}
          <button type="button" onClick={() => setFullscreen(false)} className="ml-auto rounded border border-slate-400 px-2 py-0.5 text-xs font-semibold">⤡ Thu nhỏ (Esc)</button>
        </div>
      )}
    </section>
  );

  return (
    <main className={`mx-auto w-full max-w-[1800px] space-y-2 px-2 py-2 sm:px-3 ${showActionBar ? "pb-20 lg:pb-2" : ""}`}>
      <div inert={modalOpen} className="space-y-2">
      <MarketBar view={view} tf={prefs.tf} zone={prefs.zone} onZone={changeZone} serverNowMs={serverNow} uiStale={uiStale} />

      {mode !== "LIVE" && (
        <div role="alert" data-testid="replay-banner" className={`rounded-md border-2 px-3 py-1 text-xs font-semibold ${BAD}`}>
          {mode.replace("_", " ")} — KHÔNG PHẢI LIVE: dữ liệu lịch sử đã đốt phát lại qua đúng đường quyết định, không phải thị trường sống.
        </div>
      )}
      {(error || uiStale) && (
        <div role="alert" data-testid="api-down-banner" className={`rounded-md border px-3 py-1.5 text-sm ${BAD}`}>
          <b>Không kết nối được API.</b> {error ?? "Đang chờ dữ liệu."} Những gì hiển thị có thể đã cũ, đây KHÔNG phải trạng thái CHỜ; không được vào lệnh. <span className="font-mono text-xs">API_UNAVAILABLE</span>
        </div>
      )}
      {banners.length > 0 && (
        <ul data-testid="conditions" className="space-y-1">
          {banners.map((c) => (
            <li key={c.code} data-code={c.code} data-severity={c.severity}>
              <div role={c.severity === "ERROR" ? "alert" : undefined} className={`rounded-md border px-3 py-1 text-sm ${c.severity === "ERROR" ? BAD : WARN}`}>
                {humanCondition(c.code, c.message)} <span className="font-mono text-xs">{c.code}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
      {barsError && (
        <div role="alert" data-testid="chart-unavailable" className={`rounded-md border px-3 py-1.5 text-sm ${WARN}`}>
          <b>Không tải được dữ liệu biểu đồ {prefs.tf}.</b> Đang hiển thị dữ liệu cuối cùng (nếu có). <span className="font-mono text-xs">CHART_DATA_UNAVAILABLE</span>
        </div>
      )}
      {message && (
        <div role="status" data-testid="action-message" className={`flex items-start justify-between gap-2 rounded-md border px-3 py-1.5 text-sm ${message.tone}`}>
          <span>{message.text}</span>
          <button type="button" aria-label="Đóng thông báo" onClick={() => setMessage(null)} className="rounded px-1.5 hover:bg-slate-500/20">✕</button>
        </div>
      )}
      {view?.auto_paper && (
        <div role="status" data-testid="auto-paper-banner" className={`rounded-md border px-3 py-1 text-sm ${WARN}`}>
          AUTO_PAPER đang BẬT: lệnh PAPER tự mở khi có quyết định hành động (chỉ bàn paper, không bao giờ gửi lệnh tới MT5).
        </div>
      )}
      {!view && !error && <p data-testid="loading" className="text-sm text-slate-600 dark:text-slate-400">Đang tải quyết định…</p>}

      {/* phone: one column in the order price -> decision -> chart -> plan; desktop: chart column | decision column,
          independent of each other so a tall decision never pushes the multi-timeframe strip down */}
      <div data-testid="terminal-grid" className="grid items-start gap-2 [grid-template-areas:'hero'_'chart'_'mtf'_'body'] lg:grid-cols-[minmax(0,1fr)_23rem] lg:[grid-template-areas:'left_side']">
        <div className="contents lg:flex lg:min-w-0 lg:flex-col lg:gap-2 lg:[grid-area:left]">
          {chartBlock}
          <div style={{ gridArea: "mtf" }} className="min-w-0">
            <MtfStrip rows={view?.timeframes ?? []} tf={prefs.tf} onFocus={focusTf} />
          </div>
        </div>
        <div className="contents lg:flex lg:min-w-0 lg:flex-col lg:gap-2 lg:[grid-area:side]">
          <div style={{ gridArea: "hero" }} className="min-w-0">{heroNode}</div>
          <div style={{ gridArea: "body" }} className="min-w-0">{bodyNode}</div>
        </div>
      </div>

      <Workspace
        tab={prefs.tab}
        onTab={(t) => setPrefs({ tab: t })}
        view={view}
        mode={mode}
        journal={journal}
        signals={signals}
        setups={setups && setups.source_mode === mode ? setups : null}
        zone={prefs.zone}
        tf={prefs.tf}
        onFocusTf={focusTf}
        onFocusPaper={focusPaper}
        onFocusSignal={focusSignal}
        levels={levels}
        onRemoveLevel={(id) => setLevels((l) => l.filter((x) => x.id !== id))}
        alerts={alerts}
        onRemoveAlert={removeAlert}
        notify={prefs.notify}
        sound={prefs.sound}
        onNotify={(v) => {
          setPrefs({ notify: v });
          try {
            if (v && "Notification" in window && Notification.permission === "default") void Notification.requestPermission();
          } catch {
            /* optional */
          }
        }}
        onSound={(v) => setPrefs({ sound: v })}
      />

      </div>
      {showActionBar && view && (
        <div data-testid="mobile-action-bar" inert={modalOpen} style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }} className="fixed inset-x-0 bottom-0 z-30 flex items-center gap-3 border-t-2 border-slate-400 bg-white px-3 py-2 shadow-[0_-4px_12px_rgba(0,0,0,0.15)] lg:hidden dark:bg-slate-900">
          {hero?.state === "POSITION_OPEN" && position ? (
            <>
              <div className="min-w-0 flex-1 text-sm">
                <b>{HERO_ICON.POSITION_OPEN} {position.side === "BUY" ? "MUA" : "BÁN"} paper</b>
                <div className="font-mono text-xs">{money(position.unrealized_pnl)} · {fmt(position.unrealized_r, 2)}R</div>
              </div>
              <button type="button" data-testid="action-bar-close" disabled={busy} onClick={() => setClosing(true)} className="rounded-md border-2 border-slate-600 px-4 py-2 text-sm font-black">Đóng lệnh…</button>
            </>
          ) : (
            <>
              <div className="min-w-0 flex-1 text-sm">
                <b>{hero ? HERO_ICON[hero.state] : ""} {hero ? HERO_VI[hero.state].label : ""}</b>
                <div className="truncate font-mono text-xs">SL {fmt(plan?.sl)} · TP {fmt(plan?.tp1)} · R/R {fmt(plan?.rr_net)}</div>
              </div>
              <button type="button" data-testid="action-bar-open" disabled={!canOpen || busy} onClick={requestOpen} className={`rounded-md border-2 px-4 py-2 text-sm font-black text-white disabled:opacity-40 ${hero?.state === "BUY_READY" ? "border-emerald-700 bg-emerald-700" : "border-red-700 bg-red-700"}`}>
                Mở lệnh…
              </button>
            </>
          )}
        </div>
      )}
      {openFrozen && (
        <OpenConfirmModal frozen={openFrozen} liveEntry={plan?.planned_entry ?? null} maxDriftR={view?.desk?.limits.max_entry_drift_r ?? 0.25} valid={frozenValid} busy={busy} onConfirm={() => void confirmOpen()} onCancel={() => setOpenFrozen(null)} />
      )}
      {closing && position && <CloseConfirmModal trade={position} busy={busy} unsure={uiStale || Boolean(error)} onConfirm={() => void confirmClose()} onCancel={() => setClosing(false)} />}
      {help && (
        <Modal title="Phím tắt" testId="shortcut-modal" onClose={() => setHelp(false)}>
          <dl className="grid grid-cols-[3rem_1fr] gap-y-1 text-sm">
            {SHORTCUTS.map(([k, v]) => (
              <div key={k} className="contents">
                <dt><kbd className="rounded border border-slate-400 px-1.5 font-mono text-xs">{k}</kbd></dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
          <label className="mt-2 flex items-center gap-2 text-sm">
            <input type="checkbox" data-testid="shortcuts-enabled" checked={prefs.shortcuts} onChange={(e) => setPrefs({ shortcuts: e.target.checked })} />
            Bật phím tắt một phím
          </label>
          <p className="mt-2 text-xs text-slate-600 dark:text-slate-400">Không có phím tắt nào mở hay đóng lệnh.</p>
          <button type="button" data-autofocus onClick={() => setHelp(false)} className="mt-3 w-full rounded-md border-2 border-slate-400 px-3 py-1.5 font-semibold">Đóng</button>
        </Modal>
      )}
    </main>
  );
}
