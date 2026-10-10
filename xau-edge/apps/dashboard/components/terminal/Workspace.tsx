"use client";

import { useMemo, useState } from "react";
import { AccountCard, AlertCard, DemoLockCard, ForwardCard, FunnelCard, StrategyCard, SystemStatus } from "@/components/terminal/SystemCards";
import { Card, NEUTRAL, Pill, Row, fmt, money } from "@/components/trade/ui";
import type { ManualLevel, PriceAlert, Tab } from "@/lib/prefs";
import { formatInZone, type DisplayZone } from "@/lib/time";
import type { JournalResponse, PaperTrade, SignalHistoryResponse, SignalMarker, TradeView } from "@/lib/trade";
import { ACTIVITY_VI, EXIT_REASON_VI, REFUSAL_VI, STAGE_VI } from "@/lib/vi";

const TABS: [Tab, string][] = [
  ["overview", "Tổng quan"],
  ["why", "Lý do"],
  ["position", "Vị thế"],
  ["activity", "Hoạt động"],
  ["system", "Hệ thống"],
];

interface Props {
  tab: Tab;
  onTab: (t: Tab) => void;
  view: TradeView | null;
  mode: string;
  journal: JournalResponse | null;
  signals: SignalHistoryResponse | null;
  zone: DisplayZone;
  tf: string;
  onFocusTf: (tf: string) => void;
  onFocusPaper: (t: PaperTrade) => void;
  onFocusSignal: (s: SignalMarker) => void;
  levels: ManualLevel[];
  onRemoveLevel: (id: string) => void;
  alerts: PriceAlert[];
  onRemoveAlert: (id: string) => void;
}

type Kind = "signal" | "trade" | "alert";
interface Item {
  key: string;
  at: string;
  kind: Kind;
  text: string;
  detail?: string;
  tone: string;
  onClick?: () => void;
}

function Meter({ k, v, tone }: { k: string; v: string; tone: string }) {
  return (
    <div className="rounded-md border border-slate-300 px-2 py-1 text-center dark:border-slate-700">
      <div className="text-[11px] text-slate-600 dark:text-slate-400">{k}</div>
      <div className={`text-sm font-bold ${tone}`}>{v}</div>
    </div>
  );
}

const meterTone = (v: string) => (v === "HIGH" || v === "SHOCK" || v === "WIDE" ? "text-red-700 dark:text-red-400" : v === "ELEVATED" ? "text-amber-600" : "text-emerald-700 dark:text-emerald-300");

function Overview({ view, levels, onRemoveLevel, alerts, onRemoveAlert }: Pick<Props, "view" | "levels" | "onRemoveLevel" | "alerts" | "onRemoveAlert">) {
  const d = view?.decision;
  const vol = (view?.structure?.volatility as string | undefined) ?? "UNKNOWN";
  const st = view?.structure;
  const daily = view?.market_context?.daily ?? null;
  return (
    <div className="grid gap-3 lg:grid-cols-3">
      <Card title="Hoạt động thị trường" testId="activity-card">
        <div className="grid grid-cols-3 gap-2">
          <Meter k="Biến động" v={ACTIVITY_VI[vol] ?? vol} tone={meterTone(vol)} />
          <Meter k="Tick volume" v={ACTIVITY_VI[d?.volume_state ?? "UNKNOWN"] ?? "—"} tone={meterTone(d?.volume_state ?? "")} />
          <Meter k="Spread" v={ACTIVITY_VI[d?.spread_state ?? "UNKNOWN"] ?? "—"} tone={meterTone(d?.spread_state ?? "")} />
        </div>
        <p data-testid="volume-note" className="mt-2 text-xs text-slate-600 dark:text-slate-400">Volume là tick volume (số lần giá đổi), không phải khối lượng sàn.</p>
        {view?.news?.warning && <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">Tin tức chưa được xác minh (không có lịch kinh tế).</p>}
      </Card>
      <Card title="Mức giá" testId="levels-card">
        <Row k="Kháng cự gần (M15)" v={fmt(st?.nearest_resistance as number | null)} />
        <Row k="Hỗ trợ gần (M15)" v={fmt(st?.nearest_support as number | null)} />
        <Row k="PDH / PDL (hôm qua)" v={`${fmt(st?.pdh as number | null)} / ${fmt(st?.pdl as number | null)}`} />
        <Row k="Mở cửa ngày" v={fmt(daily?.open)} />
        <Row k="Cao / thấp ngày" v={`${fmt(daily?.high)} / ${fmt(daily?.low)}`} />
      </Card>
      <Card title="Công cụ của tôi" testId="tools-card">
        <p className="text-xs text-slate-600 dark:text-slate-400">Đường ngang và cảnh báo giá chỉ là ghi chú của bạn: không ảnh hưởng quyết định hay giao dịch.</p>
        <ul data-testid="my-alerts" className="mt-1 space-y-0.5 text-sm">
          {alerts.length === 0 && <li className="text-slate-600 dark:text-slate-400">Chưa có cảnh báo giá.</li>}
          {alerts.map((a) => (
            <li key={a.id} className="flex items-center justify-between gap-2">
              <span className={a.firedAt ? "text-slate-600 dark:text-slate-400 line-through" : ""}>🔔 {a.direction === "UP" ? "↑ vượt" : "↓ xuống"} <b className="font-mono">{a.price.toFixed(2)}</b>{a.firedAt ? " (đã báo)" : ""}</span>
              <button type="button" aria-label={`Xóa cảnh báo ${a.price.toFixed(2)}`} onClick={() => onRemoveAlert(a.id)} className="rounded px-1.5 text-xs hover:bg-slate-500/20">✕</button>
            </li>
          ))}
        </ul>
        <ul data-testid="my-levels" className="mt-1 space-y-0.5 text-sm">
          {levels.length === 0 && <li className="text-slate-600 dark:text-slate-400">Chưa có đường ngang.</li>}
          {levels.map((l) => (
            <li key={l.id} className="flex items-center justify-between gap-2">
              <span>— {l.label || "Đường"} <b className="font-mono">{l.price.toFixed(2)}</b></span>
              <button type="button" aria-label={`Xóa đường ${l.price.toFixed(2)}`} onClick={() => onRemoveLevel(l.id)} className="rounded px-1.5 text-xs hover:bg-slate-500/20">✕</button>
            </li>
          ))}
        </ul>
      </Card>
      <div className="lg:col-span-3">
        <p data-testid="evidence-text" className="text-xs text-slate-600 dark:text-slate-400">{view?.evidence.label} {view?.evidence.research}</p>
      </div>
    </div>
  );
}

function Why({ view, onFocusTf }: { view: TradeView | null; onFocusTf: (tf: string) => void }) {
  if (!view?.available) return <p className="text-sm text-slate-600 dark:text-slate-400">Chưa có quyết định để giải thích.</p>;
  const blocked = (view.why_wait?.blocked_by ?? []).map((c) => REFUSAL_VI[c] ?? c);
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <Card title="Từng tầng điều kiện" testId="reasons-card">
        <ul className="space-y-0.5 text-sm">
          {(view.why_wait?.stages ?? []).map((s) => (
            <li key={s.stage}>
              <button type="button" onClick={() => onFocusTf(s.timeframe)} className="flex w-full items-center justify-between gap-2 rounded px-1 text-left hover:bg-slate-500/10">
                <span>{STAGE_VI[s.stage] ?? s.stage} <span className="text-xs text-slate-600 dark:text-slate-400">({s.timeframe})</span></span>
                <span className={s.status === "PASS" ? "text-emerald-700 dark:text-emerald-400" : s.status === "FAIL" ? "font-semibold text-red-700 dark:text-red-400" : "text-slate-600 dark:text-slate-400"}>{s.status === "PASS" ? "đạt" : s.status === "FAIL" ? "chưa đạt" : "—"}</span>
              </button>
            </li>
          ))}
        </ul>
        {blocked.length > 0 && <p className="mt-2 text-sm">Đang bị chặn bởi: <b>{blocked.join(" · ")}</b></p>}
      </Card>
      <Card title="Chi tiết kỹ thuật (từ máy chủ, tiếng Anh)" testId="explanation-card">
        <ul data-testid="explanation" className="list-disc space-y-0.5 pl-5 text-sm">
          {(view.explanation ?? []).map((line) => (<li key={line}>{line}</li>))}
        </ul>
        {(view.decision?.warnings ?? []).length > 0 && (
          <ul className="mt-1 list-disc pl-5 text-xs text-amber-700 dark:text-amber-300">
            {view.decision?.warnings.map((w) => (<li key={w}>{w}</li>))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function PositionTab({ view, journal, zone, onFocusPaper }: Pick<Props, "view" | "journal" | "zone" | "onFocusPaper">) {
  const open = view?.desk?.position ?? null;
  const closed = (journal?.trades ?? []).filter((t) => t.status === "CLOSED");
  return (
    <div className="grid gap-3 lg:grid-cols-3">
      <Card title="Lệnh paper đang mở" testId="position-card">
        {open ? (
          <>
            <Row k="Hướng" v={open.side} />
            <Row k="Mở lúc" v={formatInZone(open.opened_at, zone)} />
            <Row k="Giá vào / hiện tại" v={`${fmt(open.fill_price)} / ${fmt(open.current_price)}`} />
            <Row k="P&L · R" v={`${money(open.unrealized_pnl)} · ${fmt(open.unrealized_r)}R`} />
          </>
        ) : (
          <p className="text-sm text-slate-600 dark:text-slate-400">Không có lệnh paper đang mở.</p>
        )}
      </Card>
      <div className="lg:col-span-2">
        <Card title="Lệnh paper đã đóng" testId="paper-history">
          {closed.length === 0 ? (
            <p className="text-sm text-slate-600 dark:text-slate-400">Chưa có lệnh paper nào.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="text-slate-600 dark:text-slate-400">
                  <tr><th className="pr-2">Hướng</th><th className="pr-2">Vào</th><th className="pr-2">Thoát</th><th className="pr-2">Lý do</th><th className="pr-2">P&L</th><th className="pr-2">R</th><th className="pr-2">Phút</th><th>Bản</th></tr>
                </thead>
                <tbody>
                  {closed.slice(0, 10).map((t) => (
                    <tr key={t.trade_id} data-testid="paper-history-row" tabIndex={0} onClick={() => onFocusPaper(t)} onKeyDown={(e) => e.key === "Enter" && onFocusPaper(t)} className="cursor-pointer border-t border-slate-200 hover:bg-slate-500/10 dark:border-slate-800">
                      <td className="pr-2 font-semibold">{t.side}</td>
                      <td className="pr-2 font-mono">{fmt(t.fill_price)}</td>
                      <td className="pr-2 font-mono">{fmt(t.exit_price)}</td>
                      <td className="pr-2">{t.exit_reason ?? t.status}</td>
                      <td className="pr-2 font-mono">{money(t.net_pnl)}</td>
                      <td className="pr-2 font-mono">{fmt(t.r_multiple)}</td>
                      <td className="pr-2 font-mono">{fmt(t.duration_minutes, 0)}</td>
                      <td>v{t.strategy_version ?? "?"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <a href="/journal" className="mt-2 inline-block text-xs underline">Mở Journal đầy đủ →</a>
        </Card>
      </div>
    </div>
  );
}

function Activity({ view, journal, signals, zone, mode, onFocusPaper, onFocusSignal, alerts }: Pick<Props, "view" | "journal" | "signals" | "zone" | "mode" | "onFocusPaper" | "onFocusSignal" | "alerts">) {
  const [filter, setFilter] = useState<"all" | Kind>("all");
  const items = useMemo(() => {
    const out: Item[] = [];
    for (const s of signals?.signals ?? []) {
      out.push({
        key: `sig-${s.setup_id}`,
        at: s.at,
        kind: "signal",
        tone: s.side === "BUY" ? "text-emerald-700 dark:text-emerald-300" : "text-red-700 dark:text-red-300",
        text: `Tín hiệu ${s.side === "BUY" ? "MUA ▲" : "BÁN ▼"} @ ${fmt(s.entry)} · SL ${fmt(s.sl)} · TP ${fmt(s.tp1)}`,
        detail: `${s.taken ? "đã mở paper" : "không mở paper"} · v${s.strategy_version}`,
        onClick: () => onFocusSignal(s),
      });
    }
    for (const t of [...(journal?.open ? [journal.open] : []), ...(journal?.trades ?? [])]) {
      if (t.status === "CANCELLED") continue;
      out.push({ key: `open-${t.trade_id}`, at: t.opened_at ?? t.created_at, kind: "trade", tone: "text-sky-700 dark:text-sky-300", text: `Mở lệnh paper ${t.side === "BUY" ? "MUA" : "BÁN"} @ ${fmt(t.fill_price)} · ${fmt(t.lots, 2)} lot`, detail: `v${t.strategy_version ?? "?"}`, onClick: () => onFocusPaper(t) });
      if (t.status === "CLOSED" && t.closed_at) {
        out.push({ key: `close-${t.trade_id}`, at: t.closed_at, kind: "trade", tone: (t.net_pnl ?? 0) >= 0 ? "text-emerald-700 dark:text-emerald-300" : "text-red-700 dark:text-red-300", text: `Thoát lệnh paper: ${EXIT_REASON_VI[t.exit_reason ?? ""] ?? t.exit_reason} @ ${fmt(t.exit_price)}`, detail: `${money(t.net_pnl)} · ${fmt(t.r_multiple)}R · ${fmt(t.duration_minutes, 0)} phút`, onClick: () => onFocusPaper(t) });
      }
    }
    const a = view?.alerts;
    if (a?.last) out.push({ key: "alert-last", at: a.last.announced_at, kind: "alert", tone: "text-amber-700 dark:text-amber-300", text: `Đã báo setup ${a.last.side} (${a.delivery === "TELEGRAM" ? "Telegram" : "file"})`, detail: a.last.setup_id.slice(0, 8) });
    if (a?.last_invalidation?.at) out.push({ key: "alert-inval", at: a.last_invalidation.at, kind: "alert", tone: "text-amber-700 dark:text-amber-300", text: `Setup ${a.last_invalidation.side} bị vô hiệu`, detail: a.last_invalidation.setup_id.slice(0, 8) });
    for (const p of alerts.filter((x) => x.firedAt)) out.push({ key: `price-${p.id}`, at: p.firedAt as string, kind: "alert", tone: "text-amber-700 dark:text-amber-300", text: `Cảnh báo giá: bid ${p.direction === "UP" ? "vượt" : "xuống"} ${p.price.toFixed(2)}` });
    return out.sort((x, y) => Date.parse(y.at) - Date.parse(x.at));
  }, [signals, journal, view, alerts, onFocusPaper, onFocusSignal]);
  const shown = items.filter((i) => filter === "all" || i.kind === filter).slice(0, 40);
  return (
    <Card title={`Hoạt động gần đây${mode === "LIVE" ? "" : ` (${mode.replace("_", " ")} — không phải live)`}`} testId="activity-feed">
      <div role="group" aria-label="Lọc hoạt động" className="mb-2 flex gap-1 text-xs">
        {([["all", "Tất cả"], ["signal", "Tín hiệu"], ["trade", "Lệnh paper"], ["alert", "Cảnh báo"]] as [typeof filter, string][]).map(([k, label]) => (
          <button key={k} type="button" aria-pressed={filter === k} onClick={() => setFilter(k)} className={`rounded-md border px-2 py-0.5 ${filter === k ? "border-sky-600 bg-sky-500/15 font-semibold" : "border-slate-400"}`}>{label}</button>
        ))}
      </div>
      {shown.length === 0 ? (
        <p className="text-sm text-slate-600 dark:text-slate-400">Chưa có hoạt động nào.</p>
      ) : (
        <ul className="divide-y divide-slate-200 text-sm dark:divide-slate-800">
          {shown.map((i) => (
            <li key={i.key} data-testid="activity-row" data-kind={i.kind}>
              <button type="button" disabled={!i.onClick} onClick={i.onClick} className="flex w-full flex-wrap items-baseline gap-x-3 px-1 py-1 text-left enabled:hover:bg-slate-500/10">
                <span className="w-32 shrink-0 font-mono text-xs text-slate-600 dark:text-slate-400">{formatInZone(i.at, zone).slice(5, 16)}</span>
                <span className={`font-semibold ${i.tone}`}>{i.text}</span>
                {i.detail && <span className="text-xs text-slate-600 dark:text-slate-400">{i.detail}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function System({ view, mode }: { view: TradeView | null; mode: string }) {
  if (!view) return <p className="text-sm text-slate-600 dark:text-slate-400">Chưa có dữ liệu hệ thống.</p>;
  return (
    <div className="space-y-3">
      <SystemStatus strip={view.status_strip} />
      <div className="grid gap-3 lg:grid-cols-3">
        <StrategyCard strategy={view.strategy} />
        <ForwardCard view={view} />
        <FunnelCard funnel={view.funnel} />
        <AlertCard alerts={view.alerts} mode={mode} />
        <AccountCard view={view} />
        <DemoLockCard view={view} />
      </div>
      <div className="flex flex-wrap gap-2 text-xs text-slate-600 dark:text-slate-400">
        <Pill label="nguồn" value={view.source_mode} tone={NEUTRAL} />
        <Pill label="phiên bản mã" value={view.strategy.active_version} tone={NEUTRAL} />
      </div>
    </div>
  );
}

/** The secondary workspace under the chart. Engineering detail lives here, not above the price. */
export function Workspace(props: Props) {
  const { tab, onTab } = props;
  return (
    <section data-testid="workspace" aria-label="Không gian làm việc" className="rounded-lg border border-slate-300 dark:border-slate-700">
      <div role="tablist" aria-label="Mục thông tin" className="flex gap-1 overflow-x-auto border-b border-slate-300 px-2 pt-2 dark:border-slate-700">
        {TABS.map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            id={`tab-${id}`}
            aria-selected={tab === id}
            aria-controls={`panel-${id}`}
            tabIndex={tab === id ? 0 : -1}
            data-testid={`tab-${id}`}
            onClick={() => onTab(id)}
            onKeyDown={(e) => {
              const i = TABS.findIndex(([t]) => t === tab);
              if (e.key === "ArrowRight") onTab(TABS[(i + 1) % TABS.length][0]);
              if (e.key === "ArrowLeft") onTab(TABS[(i + TABS.length - 1) % TABS.length][0]);
            }}
            className={`whitespace-nowrap rounded-t-md border border-b-0 px-3 py-1.5 text-sm ${tab === id ? "border-slate-400 bg-slate-500/10 font-bold" : "border-transparent text-slate-600 dark:text-slate-400 hover:text-inherit"}`}
          >
            {label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="p-3">
        {tab === "overview" && <Overview view={props.view} levels={props.levels} onRemoveLevel={props.onRemoveLevel} alerts={props.alerts} onRemoveAlert={props.onRemoveAlert} />}
        {tab === "why" && <Why view={props.view} onFocusTf={props.onFocusTf} />}
        {tab === "position" && <PositionTab view={props.view} journal={props.journal} zone={props.zone} onFocusPaper={props.onFocusPaper} />}
        {tab === "activity" && <Activity view={props.view} journal={props.journal} signals={props.signals} zone={props.zone} mode={props.mode} onFocusPaper={props.onFocusPaper} onFocusSignal={props.onFocusSignal} alerts={props.alerts} />}
        {tab === "system" && <System view={props.view} mode={props.mode} />}
      </div>
    </section>
  );
}
