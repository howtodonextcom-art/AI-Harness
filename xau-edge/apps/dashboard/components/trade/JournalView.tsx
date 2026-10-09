"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { fetchJournal, type JournalResponse, type PaperTrade } from "@/lib/trade";
import { formatInZone, loadZone, type DisplayZone } from "@/lib/time";

const fmt = (v: number | null | undefined, d = 2) => (v === null || v === undefined ? "—" : v.toFixed(d));
const money = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v >= 0 ? "" : "-"}$${Math.abs(v).toFixed(2)}`);

function Stat({ k, v, testId }: { k: string; v: string; testId: string }) {
  return (
    <div className="rounded-md border border-slate-300 px-3 py-2 dark:border-slate-700">
      <div className="text-xs text-slate-500">{k}</div>
      <div data-testid={testId} className="font-mono text-lg">{v}</div>
    </div>
  );
}

/** The paper trade journal: every simulated trade with its decision snapshot (no real orders). */
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
        .catch(() => setError("Không kết nối được API /trade/journal"));
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

  return (
    <main className="mx-auto w-full max-w-6xl space-y-3 px-4 py-4">
      <h1 className="text-xl font-bold">Journal · lệnh PAPER (giả lập)</h1>
      <p data-testid="journal-note" className="text-xs text-slate-500">
        Mọi lệnh ở đây là mô phỏng trên dữ liệu FTMO demo. Chưa có bằng chứng thống kê rằng baseline này có lợi thế — số liệu nhỏ không chứng minh gì.
      </p>
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
              <th className="pr-3">Mở lúc</th>
              <th className="pr-3">Hướng</th>
              <th className="pr-3">Vào</th>
              <th className="pr-3">SL / TP</th>
              <th className="pr-3">Lot</th>
              <th className="pr-3">Thoát</th>
              <th className="pr-3">R</th>
              <th className="pr-3">P&L</th>
              <th className="pr-3">MFE / MAE (R)</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={10} className="py-3 text-slate-500">Chưa có lệnh paper nào.</td>
              </tr>
            )}
            {rows.map((t) => (
              <Fragment key={t.trade_id}>
                <tr data-testid="journal-row" className="border-t border-slate-200 dark:border-slate-800">
                  <td className="pr-3">{formatInZone(t.opened_at ?? t.created_at, zone)}</td>
                  <td className="pr-3 font-semibold">{t.side}</td>
                  <td className="pr-3 font-mono">{fmt(t.fill_price)}</td>
                  <td className="pr-3 font-mono">{fmt(t.initial_sl)} / {fmt(t.tp)}</td>
                  <td className="pr-3 font-mono">{fmt(t.lots, 2)}</td>
                  <td className="pr-3">{t.status === "CLOSED" ? (t.exit_reason ?? "—") : t.status}</td>
                  <td className="pr-3 font-mono">{fmt(t.r_multiple)}</td>
                  <td className="pr-3 font-mono">{money(t.net_pnl)}</td>
                  <td className="pr-3 font-mono">{fmt(t.mfe_r)} / {fmt(t.mae_r)}</td>
                  <td>
                    <button type="button" className="text-xs underline" onClick={() => setOpen(open === t.trade_id ? null : t.trade_id)}>
                      {open === t.trade_id ? "ẩn" : "chi tiết"}
                    </button>
                  </td>
                </tr>
                {open === t.trade_id && (
                  <tr>
                    <td colSpan={10} className="pb-2">
                      <pre data-testid="journal-detail" className="max-h-64 overflow-auto rounded-md bg-slate-500/10 p-2 text-xs">
                        {JSON.stringify({ market: t.market, decision: t.decision, setup_id: t.setup_id, cancel_reason: t.cancel_reason }, null, 2)}
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
