"use client";

import { BAD, Card, GOOD, NEUTRAL, WARN } from "@/components/trade/ui";
import type { AgeRow, AgeState, DataAges, SystemHealthRow } from "@/lib/trade";

const AGE_NAMES: [keyof Omit<DataAges, "live" | "market_open">, string, string][] = [
  ["quote", "QUOTE AGE", "tuổi báo giá: lần tick cuối"],
  ["last_bar", "LAST BAR AGE", "tuổi nến M1 đã đóng mới nhất"],
  ["collector_heartbeat", "COLLECTOR HEARTBEAT AGE", "lần cuối collector ghi nhịp tim"],
  ["last_decision", "LAST DECISION AGE", "lần cuối bộ máy tính quyết định"],
];

const AGE_VI: Record<AgeState, { label: string; tone: string }> = {
  FRESH: { label: "MỚI", tone: GOOD },
  STALE: { label: "CŨ", tone: BAD },
  MARKET_CLOSED: { label: "THỊ TRƯỜNG ĐÓNG", tone: NEUTRAL },
  UNAVAILABLE: { label: "KHÔNG CÓ", tone: WARN },
  REPLAY: { label: "REPLAY", tone: WARN },
};

export function ageText(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds < 90) return `${Math.round(seconds)} giây`;
  if (seconds < 5400) return `${Math.round(seconds / 60)} phút`;
  if (seconds < 172800) return `${(seconds / 3600).toFixed(1)} giờ`;
  return `${Math.round(seconds / 86400)} ngày`;
}

function AgeLine({ id, name, hint, row }: { id: string; name: string; hint: string; row: AgeRow }) {
  const meta = AGE_VI[row.state];
  return (
    <li data-testid={`age-${id}`} data-state={row.state} className="flex flex-wrap items-baseline gap-x-2 text-sm">
      <span className="w-52 font-semibold" title={hint}>{name}</span>
      <span className="font-mono">{ageText(row.age_seconds)}</span>
      <span className={`rounded border px-1.5 text-xs font-bold ${meta.tone}`}>{meta.label}</span>
    </li>
  );
}

/** Four different ages, each with the server's own verdict: one blurred "stale" would hide which part is wrong. */
export function DataAgesCard({ ages }: { ages: DataAges | undefined }) {
  if (!ages) return null;
  return (
    <Card title="Tuổi dữ liệu (do máy chủ đo)" testId="data-ages-card">
      <ul className="space-y-1">
        {AGE_NAMES.map(([id, name, hint]) => (
          <AgeLine key={id} id={id} name={name} hint={hint} row={ages[id]} />
        ))}
      </ul>
      <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
        {ages.live ? (ages.market_open ? "Thị trường đang mở: tuổi quá hạn nghĩa là có thành phần đang lỗi." : "Thị trường đóng: báo giá và nến cũ là bình thường; chỉ nhịp tim collector phải còn mới.") : "Replay: không phải dữ liệu live."}
      </p>
    </Card>
  );
}

const STATE_TONE: Record<SystemHealthRow["state"], string> = { OK: GOOD, WARN: WARN, ERROR: BAD, UNKNOWN: NEUTRAL };
const STATE_VI: Record<SystemHealthRow["state"], string> = { OK: "TỐT", WARN: "CẢNH BÁO", ERROR: "LỖI", UNKNOWN: "CHƯA RÕ" };

/** One row per component the trader depends on; the dashboard row is this page itself (it is up, or you would not see it). */
export function SystemHealthCard({ rows }: { rows: SystemHealthRow[] | undefined }) {
  if (!rows) return null;
  const all: SystemHealthRow[] = [...rows, { id: "dashboard", label: "Dashboard", state: "OK", detail: "trang này đang chạy" }];
  const worst = all.some((r) => r.state === "ERROR") ? "ERROR" : all.some((r) => r.state === "WARN") ? "WARN" : all.some((r) => r.state === "UNKNOWN") ? "UNKNOWN" : "OK";
  return (
    <Card title="Sức khỏe hệ thống" testId="system-health-card">
      <p data-testid="health-overall" data-state={worst} className={`mb-1 inline-block rounded border px-1.5 py-0.5 text-xs font-bold ${STATE_TONE[worst]}`}>
        {worst === "OK" ? "Mọi thành phần tốt" : worst === "ERROR" ? "Có thành phần LỖI" : worst === "WARN" ? "Có cảnh báo" : "Có mục chưa rõ"}
      </p>
      <ul className="space-y-0.5">
        {all.map((r) => (
          <li key={r.id} data-testid={`health-${r.id}`} data-state={r.state} className="flex flex-wrap items-baseline gap-x-2 text-sm">
            <span className={`w-20 rounded border px-1 text-center text-[11px] font-bold ${STATE_TONE[r.state]}`}>{STATE_VI[r.state]}</span>
            <span className="w-44 font-semibold">{r.label}</span>
            <span className="text-xs text-slate-600 dark:text-slate-400">{r.detail}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
