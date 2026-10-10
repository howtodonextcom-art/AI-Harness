"use client";

import { BAD, Card, GOOD, INFO, NEUTRAL, Pill, Row, WARN, fmt, money } from "@/components/trade/ui";
import type { AlertsSummary, Funnel, StatusStrip as StatusStripData, StrategyInfo, TradeView } from "@/lib/trade";
import { ZONE_SHORT, formatInZone, type DisplayZone } from "@/lib/time";
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

/** The state words and fixed sentences the server sends (English), in plain Vietnamese; the raw word stays as a suffix. */
const STATE_VI: Record<string, string> = {
  GOOD: "TỐT", RUNNING: "ĐANG CHẠY", READY: "SẴN SÀNG", ACTIVE: "ĐANG DÙNG", LOCKED: "ĐÃ KHÓA", READ_ONLY: "CHỈ ĐỌC",
  CLOSED: "ĐÓNG", STALE: "CŨ", ERROR: "LỖI", UNAVAILABLE: "KHÔNG KHẢ DỤNG", DEGRADED: "SUY GIẢM", UNVALIDATED: "CHƯA KIỂM CHỨNG",
};
const DETAIL_VI: Record<string, string> = {
  "the market is closed": "Thị trường đang đóng cửa",
  "bars and quote are fresh": "Nến và báo giá còn mới",
  "decisions are being computed": "Bộ máy đang tính quyết định",
  "paper state verified against its journal": "Trạng thái bàn PAPER đã khớp nhật ký",
  "paper only; the desk never sends an order": "Chỉ PAPER: bàn không bao giờ gửi lệnh thật",
  UNVALIDATED_OPERATIONAL_BASELINE: "Baseline vận hành, chưa phải lợi thế đã kiểm chứng",
};

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
          const raw = key === "strategy" && item.label ? item.label : item.state;
          const state = STATE_VI[raw] ? `${STATE_VI[raw]} · ${raw}` : raw;
          const detail = key === "forward" ? (FORWARD_VI[item.state] ?? item.detail) : key === "strategy" ? "" : (DETAIL_VI[item.detail] ?? item.detail);
          return (
            <li key={key} data-testid={`status-${key}`} className="flex flex-wrap items-center gap-2">
              <span className="w-full text-slate-600 sm:w-40 dark:text-slate-400">{name}</span>
              <span className="min-w-0 max-w-full [&>*]:max-w-full [&>*]:whitespace-normal [&>*]:break-words"><Pill value={state} tone={CHIP_TONE[item.state] ?? NEUTRAL} /></span>
              <span title={item.detail} className="min-w-0 flex-1 text-xs text-slate-600 dark:text-slate-400">{detail}</span>
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
      {f.evidence_complete === false && (
        <p data-testid="forward-incomplete" role="status" className={`mt-1 rounded-md border px-2 py-1 text-xs font-semibold ${WARN}`}>
          BẰNG CHỨNG FORWARD CHƯA ĐỦ: mới ghi được {f.coverage_pct?.toFixed(1) ?? "?"}% số quyết định đáng ra phải có, nên “chưa thấy setup” chưa chứng minh được gì.
        </p>
      )}
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

/** Telemetry coverage lives in System, never on the trading surface. */
export function CoverageCard({ view, zone }: { view: TradeView; zone: DisplayZone }) {
  const c = view.decision_coverage;
  if (c === undefined) return null;
  if (c === null) {
    return (
      <Card title="Độ phủ quyết định" testId="coverage-card">
        <p className="text-sm text-slate-600 dark:text-slate-400">Chưa có dữ liệu quyết định để tính độ phủ (hoặc đây là replay).</p>
      </Card>
    );
  }
  const fmtTime = (iso: string) => formatInZone(iso, zone).slice(5, 16);
  return (
    <Card title="Độ phủ quyết định" testId="coverage-card">
      <p data-testid="coverage-pct" className="text-sm">
        <b className={c.complete ? "" : "text-red-700 dark:text-red-400"}>{c.coverage_pct.toFixed(1)}%</b>{" "}
        <span className="text-slate-600 dark:text-slate-400">(ngưỡng {c.threshold_pct}% để bằng chứng forward được tin)</span>
      </p>
      <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 text-sm">
        <dt className="text-slate-600 dark:text-slate-400">Cần có</dt><dd data-testid="coverage-expected" className="font-mono">{c.expected_m1_decisions}</dd>
        <dt className="text-slate-600 dark:text-slate-400">Đã ghi</dt><dd data-testid="coverage-recorded" className="font-mono">{c.recorded_m1_decisions}</dd>
        <dt className="text-slate-600 dark:text-slate-400">Thiếu</dt><dd data-testid="coverage-missing" className="font-mono">{c.missing}</dd>
        <dt className="text-slate-600 dark:text-slate-400">Trùng / trễ</dt><dd className="font-mono">{c.duplicate_rows} / {c.late_rows}</dd>
      </dl>
      {c.missing_intervals.length > 0 && (
        <details data-testid="coverage-gaps" className="mt-1 text-xs">
          <summary className="cursor-pointer font-semibold">{c.missing_intervals.length} khoảng thiếu (giờ {ZONE_SHORT[zone]})</summary>
          <ul className="mt-1 space-y-0.5 font-mono">
            {c.missing_intervals.slice(0, 8).map((g) => (
              <li key={g.from}>{fmtTime(g.from)} → {fmtTime(g.to)} · {g.minutes} phút</li>
            ))}
          </ul>
          <p className="mt-1 text-slate-600 dark:text-slate-400">Một khoảng thiếu thường là tiến trình API/bộ máy không chạy (khởi động lại): bộ máy chỉ ghi nến M1 mới nó thấy, không ghi bù.</p>
        </details>
      )}
      <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">Mỗi nến M1 đã đóng trong lúc thị trường mở là một quyết định phải có; nến collector không giao thì không tính.</p>
    </Card>
  );
}
