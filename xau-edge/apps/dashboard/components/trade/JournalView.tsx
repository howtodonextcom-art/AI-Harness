"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { fetchJournal, type JournalResponse, type PaperTrade } from "@/lib/trade";
import { formatInZone, loadZone, type DisplayZone } from "@/lib/time";
import { fmt, money } from "@/components/trade/ui";

function Stat({ k, v, testId }: { k: string; v: string; testId: string }) {
  return (
    <div className="rounded-md border border-slate-300 px-3 py-2 dark:border-slate-700">
      <div className="text-xs text-slate-500">{k}</div>
      <div data-testid={testId} className="font-mono text-lg">{v}</div>
    </div>
  );
}

const REASON_TEXT: Record<string, string> = {
  STOP_LOSS: "Chạm SL",
  TAKE_PROFIT: "Chạm TP",
  TIME_EXIT: "Hết thời gian giữ",
  MANUAL_CLOSE: "Đóng tay",
  CLOSURE_CLOSE: "Đóng trước giờ thị trường nghỉ",
  INVALIDATED: "Setup bị vô hiệu",
};

/** The paper trade journal: every simulated trade with its plan, result and provenance (no real orders). */
export function JournalView() {
  const [data, setData] = useState<JournalResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [zone, setZone] = useState<DisplayZone>("UTC");
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setZone(loadZone()), 0);
    const ctl = new AbortController();
    const run = () =>
      fetchJournal(ctl.signal)
        .then((d) => {
          setData(d);
          setError(null);
        })
        .catch(() => setError("Không kết nối được API /trade/journal — chưa có dữ liệu để hiển thị (không có nghĩa là chưa có lệnh)"));
    const first = setTimeout(run, 0);
    const poll = setInterval(run, 5000);
    return () => {
      clearTimeout(t);
      clearTimeout(first);
      clearInterval(poll);
      ctl.abort();
    };
  }, []);

  const stats = useMemo(() => {
    const closed = (data?.trades ?? []).filter((t) => t.status === "CLOSED");
    const wins = closed.filter((t) => (t.net_pnl ?? 0) > 0).length;
    const pnl = closed.reduce((a, t) => a + (t.net_pnl ?? 0), 0);
    const r = closed.reduce((a, t) => a + (t.r_multiple ?? 0), 0);
    return { n: closed.length, wins, pnl, r };
  }, [data]);

  const rows: PaperTrade[] = [...(data?.open ? [data.open] : []), ...(data?.trades ?? [])];
  const replay = data !== null && data.source_mode !== "LIVE";

  return (
    <main className="mx-auto w-full max-w-6xl space-y-3 px-4 py-4">
      <h1 className="text-xl font-bold">Journal · lệnh PAPER (giả lập)</h1>
      {replay && (
        <div data-testid="journal-replay-banner" role="status" className="rounded-md border-2 border-amber-600 bg-amber-500/15 px-3 py-2 text-sm font-bold">
          {data.source_mode.replace("_", " ")} — KHÔNG PHẢI LIVE. Các lệnh dưới đây chạy trên dữ liệu lịch sử đã đốt, không tính vào bằng chứng forward.
        </div>
      )}
      <p data-testid="journal-note" className="text-xs text-slate-500">
        Mọi lệnh ở đây là mô phỏng. Chưa có bằng chứng thống kê rằng baseline này có lợi thế — số liệu nhỏ không chứng minh gì.
      </p>
      {data?.desk_fault && (
        <div data-testid="journal-desk-fault" role="alert" className="rounded-md border-2 border-red-600 bg-red-500/15 px-3 py-2 text-sm font-semibold">
          PAPER_STATE_ERROR: {data.desk_fault}. Danh sách bên dưới có thể THIẾU lệnh; nguồn đầy đủ là paper_journal.jsonl.
        </div>
      )}
      {error && <div role="alert" className="rounded-md border border-red-600 bg-red-500/15 px-3 py-2 text-sm">{error}</div>}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat k="Lệnh đã đóng" v={String(stats.n)} testId="stat-n" />
        <Stat k="Thắng" v={`${stats.wins}`} testId="stat-wins" />
        <Stat k="P&L ròng (paper)" v={money(stats.pnl)} testId="stat-pnl" />
        <Stat k="Tổng R" v={fmt(stats.r)} testId="stat-r" />
      </div>
      <div className="overflow-x-auto">
        <table data-testid="journal-table" className="w-full text-left text-sm">
          <thead className="text-xs text-slate-500">
            <tr>
              <th className="pr-3">Setup</th>
              <th className="pr-3">Hướng</th>
              <th className="pr-3">Mở lúc</th>
              <th className="pr-3">Vào</th>
              <th className="pr-3">Thoát</th>
              <th className="pr-3">SL / TP</th>
              <th className="pr-3">Lot</th>
              <th className="pr-3">Lý do thoát</th>
              <th className="pr-3">R</th>
              <th className="pr-3">P&L</th>
              <th className="pr-3">MFE / MAE (R)</th>
              <th className="pr-3">Phút</th>
              <th className="pr-3">Bản</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={14} className="py-3 text-slate-500">
                  {error ? "Không tải được journal." : "Chưa có lệnh paper nào. Khi bạn mở một lệnh từ trang Trade, nó sẽ hiện ở đây."}
                </td>
              </tr>
            )}
            {rows.map((t) => (
              <Fragment key={t.trade_id}>
                <tr data-testid="journal-row" data-status={t.status} className="border-t border-slate-200 dark:border-slate-800">
                  <td className="pr-3 font-mono text-xs">{t.setup_id.slice(0, 8)}</td>
                  <td className="pr-3 font-semibold">{t.side}</td>
                  <td className="pr-3">{formatInZone(t.opened_at ?? t.created_at, zone)}</td>
                  <td className="pr-3 font-mono">{fmt(t.fill_price)}</td>
                  <td className="pr-3 font-mono">{fmt(t.exit_price)}</td>
                  <td className="pr-3 font-mono">{fmt(t.initial_sl)} / {fmt(t.tp)}</td>
                  <td className="pr-3 font-mono">{fmt(t.lots, 2)}</td>
                  <td className="pr-3">{t.status === "CLOSED" ? (REASON_TEXT[t.exit_reason ?? ""] ?? t.exit_reason ?? "—") : t.status}</td>
                  <td className="pr-3 font-mono">{fmt(t.r_multiple)}</td>
                  <td className="pr-3 font-mono">{money(t.net_pnl)}</td>
                  <td className="pr-3 font-mono">{fmt(t.mfe_r)} / {fmt(t.mae_r)}</td>
                  <td className="pr-3 font-mono">{fmt(t.duration_minutes, 0)}</td>
                  <td className="pr-3 text-xs">v{t.strategy_version ?? "?"}<span className="block text-slate-500">{t.code_version ?? ""}</span></td>
                  <td>
                    <button type="button" data-testid="journal-detail-toggle" className="text-xs underline" onClick={() => setOpen(open === t.trade_id ? null : t.trade_id)}>
                      {open === t.trade_id ? "ẩn" : "nguồn gốc"}
                    </button>
                  </td>
                </tr>
                {open === t.trade_id && (
                  <tr>
                    <td colSpan={14} className="pb-2">
                      <pre data-testid="journal-detail" className="max-h-64 overflow-auto rounded-md bg-slate-500/10 p-2 text-xs">
                        {JSON.stringify(
                          { source_mode: t.source_mode, strategy_version: t.strategy_version, code_version: t.code_version, market: t.market, decision: t.decision, setup_id: t.setup_id, cancel_reason: t.cancel_reason },
                          null,
                          2,
                        )}
                      </pre>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
