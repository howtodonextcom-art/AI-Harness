"use client";

import type { AlertsSummary, Condition, Funnel, PaperTrade, SignalMarker, StrategyInfo, TradeView, WhyWait } from "@/lib/trade";
import { BAD, Card, GOOD, INFO, NEUTRAL, Pill, Row, WARN, fmt, money } from "@/components/trade/ui";

/** Why WAIT? Each row is a button: it switches the chart to the timeframe that shows the stage. */
export function WhyPanel({ why, side, onFocus, current }: { why: WhyWait | undefined; side: string; onFocus: (tf: string) => void; current: string }) {
  return (
    <details data-testid="why-wait" className="rounded-lg border border-slate-300 p-3 dark:border-slate-700" open={side === "WAIT" || side === "SETUP_ARMED"}>
      <summary className="cursor-pointer text-sm font-semibold uppercase tracking-wide text-slate-500">
        {side === "WAIT" || side === "SETUP_ARMED" ? "Why WAIT?" : "Chuỗi điều kiện"}
      </summary>
      <ul className="mt-2 space-y-0.5 text-sm" data-testid="stages">
        {(why?.stages ?? []).map((s) => (
          <li key={s.stage}>
            <button
              type="button"
              data-testid={`stage-${s.stage.replace(/[^A-Za-z0-9]+/g, "-")}`}
              data-timeframe={s.timeframe}
              aria-label={`${s.stage}: ${s.status}. Xem biểu đồ ${s.timeframe}`}
              onClick={() => onFocus(s.timeframe)}
              className={`flex w-full items-center justify-between rounded px-1 py-0.5 text-left hover:bg-slate-500/10 ${current === s.timeframe ? "bg-sky-500/10" : ""}`}
            >
              <span>{s.stage} <span className="text-xs text-slate-400">({s.timeframe})</span></span>
              <span className={s.status === "PASS" ? "text-emerald-600" : s.status === "FAIL" ? "font-semibold text-red-600" : "text-slate-400"}>
                {s.status === "NOT_REACHED" ? "—" : s.status}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {why?.waiting_for && side === "WAIT" && (
        <p data-testid="waiting-for" className="mt-2 rounded-md bg-slate-500/10 px-2 py-1 text-sm">
          Waiting for: <b>{why.waiting_for}</b>
          <span className="block text-xs text-slate-500">Trạng thái giải thích, không phải dự báo hay khuyến nghị.</span>
        </p>
      )}
    </details>
  );
}

/** Infrastructure and safety conditions with severity: never a plain WAIT for a failure. */
export function ConditionsPanel({ conditions }: { conditions: Condition[] }) {
  const shown = conditions.filter((c) => c.code !== "MARKET_CLOSED");
  if (shown.length === 0) return null;
  return (
    <ul data-testid="conditions" className="space-y-1">
      {shown.map((c) => (
        <li
          key={c.code}
          data-code={c.code}
          data-severity={c.severity}
          role={c.severity === "ERROR" ? "alert" : undefined}
          className={`rounded-md border px-3 py-1.5 text-sm ${c.severity === "ERROR" ? BAD : c.severity === "WARN" ? WARN : NEUTRAL}`}
        >
          <b>{c.code.replaceAll("_", " ")}</b>: {c.message}
        </li>
      ))}
    </ul>
  );
}

export function AlertCard({ alerts, mode }: { alerts: AlertsSummary | null | undefined; mode: string }) {
  if (!alerts) {
    return (
      <Card title="Cảnh báo" testId="alert-card">
        <p className="text-sm text-slate-500">Không có kênh cảnh báo ({mode === "LIVE" ? "tiến trình chỉ-đọc" : "không áp dụng cho replay"}).</p>
      </Card>
    );
  }
  return (
    <Card title="Cảnh báo setup" testId="alert-card">
      <Row k="Setup đã báo hôm nay" v={String(alerts.announced_today)} testId="alerts-today" />
      <Row k="Cảnh báo setup cuối" v={alerts.last ? `${alerts.last.side} ${alerts.last.announced_at.slice(11, 16)} UTC` : "—"} testId="alerts-last" />
      <Row k="Hủy hiệu lực cuối" v={alerts.last_invalidation ? `${alerts.last_invalidation.side} ${(alerts.last_invalidation.at ?? "").slice(11, 16)} UTC` : "—"} testId="alerts-invalidated" />
      <div className="mt-1 flex flex-wrap gap-1.5">
        <Pill label="Telegram" value={alerts.telegram_configured ? "ĐÃ CẤU HÌNH" : "CHƯA CẤU HÌNH"} tone={alerts.telegram_configured ? GOOD : NEUTRAL} testId="alerts-telegram" />
        <Pill label="File dự phòng" value={alerts.file_fallback_active ? "ĐANG DÙNG" : "KHÔNG DÙNG"} tone={alerts.file_fallback_active ? INFO : NEUTRAL} testId="alerts-file" />
      </div>
      <p className="mt-1 text-xs text-slate-500">Không bao giờ hiện token hay chat id. Telegram là tùy chọn.</p>
    </Card>
  );
}

export function FunnelCard({ funnel }: { funnel: Funnel | undefined }) {
  if (!funnel) return null;
  const refusals = Object.entries(funnel.refusals).filter(([, n]) => n > 0).sort((a, b) => b[1] - a[1]);
  return (
    <Card title="Phễu hôm nay (từ telemetry server)" testId="funnel-card">
      <div className="grid grid-cols-2 gap-x-4 text-sm">
        <Row k="Quyết định" v={String(funnel.decisions)} testId="funnel-decisions" />
        <Row k="Setup armed" v={String(funnel.armed_setups)} testId="funnel-armed" />
        <Row k="Triggered" v={String(funnel.triggered_setups)} testId="funnel-triggered" />
        <Row k="Hết hạn / hủy" v={`${funnel.expired_setups} / ${funnel.invalidated_setups}`} testId="funnel-expired" />
        <Row k="BUY khả dụng" v={String(funnel.actionable_buy)} testId="funnel-buy" />
        <Row k="SELL khả dụng" v={String(funnel.actionable_sell)} testId="funnel-sell" />
        <Row k="Paper mở" v={String(funnel.paper_opens)} testId="funnel-opens" />
        <Row k="Paper thoát" v={String(funnel.paper_exits)} testId="funnel-exits" />
      </div>
      <p className="mt-1 text-xs text-slate-500">Lý do chặn hàng đầu:</p>
      <ul data-testid="funnel-refusals" className="text-xs">
        {refusals.length === 0 && <li>—</li>}
        {refusals.slice(0, 5).map(([group, n]) => (
          <li key={group} className="flex justify-between"><span>{group}</span><span className="font-mono">{n}</span></li>
        ))}
      </ul>
    </Card>
  );
}

export function StrategyCard({ strategy }: { strategy: StrategyInfo | undefined }) {
  if (!strategy) return null;
  return (
    <Card title="Chiến lược" testId="strategy-card">
      <p data-testid="strategy-active" className="text-sm font-semibold">ACTIVE BASELINE: {strategy.label}</p>
      <p className="text-xs text-slate-500">Bằng chứng: {strategy.evidence}</p>
      <ul className="mt-1 text-sm" data-testid="strategy-installed">
        {strategy.installed.map((v) => (
          <li key={v.version} data-version={v.version} className="flex items-center justify-between gap-2">
            <span>v{v.version} <span className="text-xs text-slate-500">{v.note}</span></span>
            <Pill value={v.status === "ACTIVE" ? "ACTIVE" : "AVAILABLE / INACTIVE"} tone={v.status === "ACTIVE" ? GOOD : NEUTRAL} />
          </li>
        ))}
      </ul>
      <p className="mt-1 text-xs text-slate-500">Phiên bản không ACTIVE chỉ được cài đặt, không chạy.</p>
    </Card>
  );
}

export function PaperHistory({ trades, onFocus }: { trades: PaperTrade[]; onFocus: (t: PaperTrade) => void }) {
  return (
    <Card title="Lệnh paper gần đây" testId="paper-history">
      {trades.length === 0 ? (
        <p className="text-sm text-slate-500">Chưa có lệnh paper nào.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-slate-500">
              <tr><th className="pr-2">Side</th><th className="pr-2">Vào</th><th className="pr-2">Thoát</th><th className="pr-2">Lý do</th><th className="pr-2">P&L</th><th className="pr-2">R</th><th className="pr-2">Phút</th><th>Bản</th></tr>
            </thead>
            <tbody>
              {trades.slice(0, 8).map((t) => (
                <tr key={t.trade_id} data-testid="paper-history-row" tabIndex={0} onClick={() => onFocus(t)} onKeyDown={(e) => e.key === "Enter" && onFocus(t)} className="cursor-pointer border-t border-slate-200 hover:bg-slate-500/10 dark:border-slate-800">
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
    </Card>
  );
}

export function SignalHistory({ signals, mode, onFocus }: { signals: SignalMarker[]; mode: string; onFocus: (s: SignalMarker) => void }) {
  return (
    <Card title={`Tín hiệu ${mode === "LIVE" ? "LIVE" : mode.replace("_", " ")} gần đây`} testId="signal-history">
      {signals.length === 0 ? (
        <p className="text-sm text-slate-500">Chưa có tín hiệu hành động nào được ghi.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-slate-500">
              <tr><th className="pr-2">Thời điểm (UTC)</th><th className="pr-2">Side</th><th className="pr-2">Entry</th><th className="pr-2">SL</th><th className="pr-2">TP</th><th className="pr-2">Đã mở?</th><th>Bản</th></tr>
            </thead>
            <tbody>
              {signals.slice(0, 8).map((s) => (
                <tr key={s.setup_id} data-testid="signal-history-row" tabIndex={0} onClick={() => onFocus(s)} onKeyDown={(e) => e.key === "Enter" && onFocus(s)} className="cursor-pointer border-t border-slate-200 hover:bg-slate-500/10 dark:border-slate-800">
                  <td className="pr-2">{s.bar_time.slice(5, 16).replace("T", " ")}</td>
                  <td className="pr-2 font-semibold">{s.side}</td>
                  <td className="pr-2 font-mono">{fmt(s.entry)}</td>
                  <td className="pr-2 font-mono">{fmt(s.sl)}</td>
                  <td className="pr-2 font-mono">{fmt(s.tp1)}</td>
                  <td className="pr-2">{s.taken ? "có (paper)" : "không"}</td>
                  <td>v{s.strategy_version}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export function ForwardCard({ view }: { view: TradeView }) {
  const f = view.forward_acceptance;
  return (
    <Card title="Forward paper acceptance" testId="forward-card">
      <p data-testid="forward-level" className="text-sm"><b>{f.level}</b> — {f.text}</p>
      <ul className="mt-1 text-xs text-slate-500">
        {Object.entries(f.counts).map(([k, n]) => (
          <li key={k}>{k.replaceAll("_", " ")}: {n}</li>
        ))}
      </ul>
      <p className="mt-1 text-xs text-slate-500">F0 chưa thấy setup live · F1 đã thấy · F2 đã mở paper · F3 đã hoàn tất 1 lệnh · F4 nhiều lệnh, không lỗi đúng đắn. Replay không nâng được mức này.</p>
    </Card>
  );
}
