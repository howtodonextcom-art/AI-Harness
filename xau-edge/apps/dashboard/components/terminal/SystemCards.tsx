"use client";

import { BAD, Card, GOOD, INFO, NEUTRAL, Pill, Row, WARN, fmt, money } from "@/components/trade/ui";
import type { AlertsSummary, Funnel, StatusStrip as StatusStripData, StrategyInfo, TradeView } from "@/lib/trade";
import { PAPER_ACCOUNT_VI, REFUSAL_VI } from "@/lib/vi";

const CHIP_TONE: Record<string, string> = {
  GOOD: GOOD, RUNNING: GOOD, READY: GOOD, ACTIVE: INFO, LOCKED: INFO,
  F0: WARN, UNVALIDATED: WARN, CLOSED: NEUTRAL, STALE: BAD, ERROR: BAD, UNAVAILABLE: BAD, DEGRADED: WARN,
};

const NAMES: [keyof StatusStripData, string][] = [
  ["data", "Dữ liệu"],
  ["trading_core", "Lõi giao dịch"],
  ["strategy", "Chiến lược"],
  ["paper_desk", "Bàn PAPER"],
  ["forward", "Forward acceptance"],
  ["demo", "DEMO"],
  ["edge", "Edge (lợi thế)"],
];

const FORWARD_VI: Record<string, string> = {
  F0: "chưa thấy setup LIVE nào",
  F1: "đã thấy setup LIVE",
  F2: "đã mở lệnh paper trên setup LIVE",
  F3: "đã hoàn tất ít nhất 1 lệnh paper LIVE đúng quy trình",
  F4: "nhiều lệnh paper LIVE, không lỗi đúng đắn",
};

/** Engineering status in one table: it lives in the System tab, not above the price. */
export function SystemStatus({ strip }: { strip: StatusStripData | undefined }) {
  if (!strip) return null;
  return (
    <Card title="Trạng thái hệ thống" testId="status-strip">
      <ul className="space-y-1 text-sm">
        {NAMES.map(([key, name]) => {
          const item = strip[key] as { state: string; detail: string; label?: string };
          const state = key === "strategy" && item.label ? item.label : item.state;
          return (
            <li key={key} data-testid={`status-${key}`} className="flex flex-wrap items-center gap-2">
              <span className="w-40 text-slate-600 dark:text-slate-400">{name}</span>
              <Pill value={state} tone={CHIP_TONE[item.state] ?? NEUTRAL} />
              <span className="min-w-0 flex-1 text-xs text-slate-600 dark:text-slate-400">{item.detail}</span>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

export function AlertCard({ alerts, mode }: { alerts: AlertsSummary | null | undefined; mode: string }) {
  if (!alerts) {
    return (
      <Card title="Cảnh báo setup" testId="alert-card">
        <p className="text-sm text-slate-600 dark:text-slate-400">Không có kênh cảnh báo ({mode === "LIVE" ? "tiến trình chỉ-đọc" : "không áp dụng cho replay"}).</p>
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
      <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">Không bao giờ hiện token hay chat id. Telegram là tùy chọn.</p>
    </Card>
  );
}

export function FunnelCard({ funnel }: { funnel: Funnel | undefined }) {
  if (!funnel) return null;
  const refusals = Object.entries(funnel.refusals).filter(([, n]) => n > 0).sort((a, b) => b[1] - a[1]);
  return (
    <Card title="Phễu hôm nay (telemetry máy chủ)" testId="funnel-card">
      <div className="grid grid-cols-2 gap-x-4 text-sm">
        <Row k="Quyết định" v={String(funnel.decisions)} testId="funnel-decisions" />
        <Row k="Setup hình thành" v={String(funnel.armed_setups)} testId="funnel-armed" />
        <Row k="Đã kích hoạt" v={String(funnel.triggered_setups)} testId="funnel-triggered" />
        <Row k="Hết hạn / hủy" v={`${funnel.expired_setups} / ${funnel.invalidated_setups}`} testId="funnel-expired" />
        <Row k="BUY khả dụng" v={String(funnel.actionable_buy)} testId="funnel-buy" />
        <Row k="SELL khả dụng" v={String(funnel.actionable_sell)} testId="funnel-sell" />
        <Row k="Paper mở" v={String(funnel.paper_opens)} testId="funnel-opens" />
        <Row k="Paper thoát" v={String(funnel.paper_exits)} testId="funnel-exits" />
      </div>
      <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">Lý do chặn hàng đầu:</p>
      <ul data-testid="funnel-refusals" className="text-xs">
        {refusals.length === 0 && <li>—</li>}
        {refusals.slice(0, 5).map(([group, n]) => (
          <li key={group} className="flex justify-between"><span>{REFUSAL_VI[group] ?? group}</span><span className="font-mono">{n}</span></li>
        ))}
      </ul>
    </Card>
  );
}

export function StrategyCard({ strategy }: { strategy: StrategyInfo | undefined }) {
  if (!strategy) return null;
  return (
    <Card title="Chiến lược" testId="strategy-card">
      <p data-testid="strategy-active" className="text-sm font-semibold">Đang chạy: {strategy.label}</p>
      <p className="text-xs text-slate-600 dark:text-slate-400">Bằng chứng: {strategy.evidence}</p>
      <ul className="mt-1 text-sm" data-testid="strategy-installed">
        {strategy.installed.map((v) => (
          <li key={v.version} data-version={v.version} className="flex items-center justify-between gap-2">
            <span>v{v.version} <span className="text-xs text-slate-600 dark:text-slate-400">{v.note}</span></span>
            <Pill value={v.status === "ACTIVE" ? "ĐANG CHẠY" : "ĐÃ CÀI · KHÔNG CHẠY"} tone={v.status === "ACTIVE" ? GOOD : NEUTRAL} />
          </li>
        ))}
      </ul>
      <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">Phiên bản không chạy chỉ được cài đặt, không ảnh hưởng quyết định.</p>
    </Card>
  );
}

export function ForwardCard({ view }: { view: TradeView }) {
  const f = view.forward_acceptance;
  return (
    <Card title="Forward paper acceptance" testId="forward-card">
      <p data-testid="forward-level" className="text-sm"><b>{f.level}</b> — {FORWARD_VI[f.level] ?? f.text}</p>
      <ul className="mt-1 text-xs text-slate-600 dark:text-slate-400">
        {Object.entries(f.counts).map(([k, n]) => (
          <li key={k}>{k.replaceAll("_", " ")}: {n}</li>
        ))}
      </ul>
      <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">F0 chưa thấy setup live · F1 đã thấy · F2 đã mở paper · F3 hoàn tất 1 lệnh · F4 nhiều lệnh, không lỗi đúng đắn. Replay không nâng được mức này.</p>
    </Card>
  );
}

export function DemoLockCard({ view }: { view: TradeView }) {
  return (
    <Card title="Khóa thực thi DEMO" testId="demo-lock">
      <Pill value={view.demo.status === "LOCKED" ? "ĐANG KHÓA" : "MỞ KHÓA THEO CẤU HÌNH"} tone={view.demo.status === "LOCKED" ? INFO : WARN} />
      <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs">
        {view.demo.reasons.map((r) => (<li key={r.code}><b>{r.code}</b>: {r.why}</li>))}
      </ul>
      <p className="mt-2 text-xs text-slate-600 dark:text-slate-400">Bàn paper không bao giờ gửi lệnh tới MT5. {view.demo.how_to_unlock}</p>
    </Card>
  );
}

export function AccountCard({ view }: { view: TradeView }) {
  return (
    <Card title="Tài khoản PAPER & hôm nay" testId="account-card">
      <p className="mb-1 text-xs text-slate-600 dark:text-slate-400">{PAPER_ACCOUNT_VI}</p>
      <Row k="PAPER equity" v={money(view.desk?.account.equity)} />
      <Row k="Số lệnh hôm nay" v={String(view.desk?.today.paper_trades ?? 0)} testId="today-trades" />
      <Row k="Thắng / Thua" v={`${view.desk?.today.wins ?? 0} / ${view.desk?.today.losses ?? 0}`} />
      <Row k="P&L ròng" v={money(view.desk?.today.net_pnl as number | null)} />
      <Row k="Tổng R" v={fmt(view.desk?.today.net_r as number | null)} />
      <Row k="Chính sách đóng thị trường" v={view.desk?.closure_policy ?? "—"} />
    </Card>
  );
}
