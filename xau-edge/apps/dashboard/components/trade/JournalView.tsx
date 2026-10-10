"use client";

import Link from "next/link";
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { fetchJournal, type JournalResponse, type PaperTrade } from "@/lib/trade";
import { ZONE_SHORT, formatInZone } from "@/lib/time";
import { ZoneSelect, useDisplayZone } from "@/lib/useZone";
import { fmt, money } from "@/components/trade/ui";
import { sourceText, viState } from "@/lib/vi";

function Stat({ k, v, testId }: { k: string; v: string; testId: string }) {
  return (
    <div className="rounded-md border border-slate-300 px-3 py-2 dark:border-slate-700">
      <div className="text-xs text-slate-600 dark:text-slate-400">{k}</div>
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
  const [zone, changeZone] = useDisplayZone("UTC");
  const [open, setOpen] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "win" | "loss" | "BUY" | "SELL">("all");

  useEffect(() => {
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
      clearTimeout(first);
      clearInterval(poll);
      ctl.abort();
    };
  }, []);

  const matches = useCallback(
    (t: PaperTrade) => filter === "all" || (filter === "win" ? (t.net_pnl ?? 0) > 0 : filter === "loss" ? t.status === "CLOSED" && (t.net_pnl ?? 0) <= 0 : t.side === filter),
    [filter],
  );
  const closedAll = useMemo(() => (data?.trades ?? []).filter((t) => t.status === "CLOSED" && matches(t)), [data, matches]);
  const stats = useMemo(() => {
    const wins = closedAll.filter((t) => (t.net_pnl ?? 0) > 0).length;
    const pnl = closedAll.reduce((a, t) => a + (t.net_pnl ?? 0), 0);
    const r = closedAll.reduce((a, t) => a + (t.r_multiple ?? 0), 0);
    const n = closedAll.length;
    return { n, wins, pnl, r, winRate: n === 0 ? null : (wins / n) * 100, avgR: n === 0 ? null : r / n };
  }, [closedAll]);
  // cumulative R in the order the trades closed
  const curve = useMemo(() => {
    const ordered = [...closedAll].sort((x, y) => Date.parse(x.closed_at ?? "") - Date.parse(y.closed_at ?? ""));
    const out: number[] = [];
    for (const t of ordered) out.push((out.length > 0 ? out[out.length - 1] : 0) + (t.r_multiple ?? 0));
    return out;
  }, [closedAll]);

  const byReason = useMemo(() => {
    const m = new Map<string, { n: number; r: number; pnl: number }>();
    for (const t of closedAll) {
      const k = t.exit_reason ?? "—";
      const cur = m.get(k) ?? { n: 0, r: 0, pnl: 0 };
      m.set(k, { n: cur.n + 1, r: cur.r + (t.r_multiple ?? 0), pnl: cur.pnl + (t.net_pnl ?? 0) });
    }
    return [...m.entries()].sort((a, b) => b[1].n - a[1].n);
  }, [closedAll]);
  const byWeek = useMemo(() => {
    const m = new Map<string, { n: number; wins: number; r: number; pnl: number }>();
    for (const t of closedAll) {
      const d = new Date(Date.parse(t.closed_at ?? ""));
      if (Number.isNaN(d.getTime())) continue;
      const monday = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() - ((d.getUTCDay() + 6) % 7)));
      const k = monday.toISOString().slice(0, 10);
      const cur = m.get(k) ?? { n: 0, wins: 0, r: 0, pnl: 0 };
      m.set(k, { n: cur.n + 1, wins: cur.wins + ((t.net_pnl ?? 0) > 0 ? 1 : 0), r: cur.r + (t.r_multiple ?? 0), pnl: cur.pnl + (t.net_pnl ?? 0) });
    }
    return [...m.entries()].sort((a, b) => (a[0] < b[0] ? 1 : -1));
  }, [closedAll]);

  const rows: PaperTrade[] = [...(data?.open && filter === "all" ? [data.open] : []), ...(data?.trades ?? []).filter(matches)];

  const exportCsv = () => {
    const head = ["trade_id", "setup_id", "side", "opened_at", "closed_at", "fill_price", "exit_price", "sl", "tp", "lots", "exit_reason", "r_multiple", "net_pnl", "mfe_r", "mae_r", "duration_minutes", "strategy_version", "code_version", "source_mode"];
    // RFC 4180 quoting, a BOM so Excel reads Vietnamese, and a leading ' on text a spreadsheet would run as a formula
    const cell = (v: unknown) => {
      let text = v === null || v === undefined ? "" : String(v);
      if (typeof v === "string" && /^[=+\-@\t\r]/.test(text)) text = `'${text}`;
      return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
    };
    const lines = rows.map((t) => head.map((k) => cell((t as unknown as Record<string, unknown>)[k === "sl" ? "initial_sl" : k])).join(","));
    const blob = new Blob(["\ufeff" + [head.join(","), ...lines].join("\r\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `paper-journal-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const replay = data !== null && data.source_mode !== "LIVE";

  return (
    <main className="mx-auto w-full max-w-6xl space-y-3 px-4 py-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-bold">Journal · lệnh PAPER (giả lập)</h1>
        <ZoneSelect zone={zone} onChange={changeZone} testId="journal-zone" />
      </div>
      {replay && (
        <div data-testid="journal-replay-banner" role="status" className="rounded-md border-2 border-amber-600 bg-amber-500/15 px-3 py-2 text-sm font-bold">
          REPLAY NGHIỆM THU ({data.source_mode.replace("_", " ")}) — KHÔNG PHẢI LIVE. Các lệnh dưới đây chạy trên dữ liệu lịch sử đã đốt, không tính vào bằng chứng forward.
        </div>
      )}
      <p data-testid="journal-note" className="text-xs text-slate-600 dark:text-slate-400">
        Mọi lệnh ở đây là mô phỏng. Chưa có bằng chứng thống kê rằng baseline này có lợi thế — số liệu nhỏ không chứng minh gì.
      </p>
      {data?.desk_fault && (
        <div data-testid="journal-desk-fault" role="alert" className="rounded-md border-2 border-red-600 bg-red-500/15 px-3 py-2 text-sm font-semibold">
          PAPER_STATE_ERROR: {data.desk_fault}. Danh sách bên dưới có thể THIẾU lệnh; nguồn đầy đủ là paper_journal.jsonl.
        </div>
      )}
      {error && <div role="alert" className="rounded-md border border-red-600 bg-red-500/15 px-3 py-2 text-sm">{error}</div>}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6">
        <Stat k="Lệnh đã đóng" v={String(stats.n)} testId="stat-n" />
        <Stat k="Thắng" v={`${stats.wins}`} testId="stat-wins" />
        <Stat k="P&L ròng (paper)" v={money(stats.pnl)} testId="stat-pnl" />
        <Stat k="Tổng R" v={fmt(stats.r)} testId="stat-r" />
        <Stat k="Tỷ lệ thắng" v={stats.winRate === null ? "—" : `${stats.winRate.toFixed(0)}%`} testId="stat-winrate" />
        <Stat k="R trung bình / lệnh" v={fmt(stats.avgR)} testId="stat-avgr" />
        <div className="col-span-2 rounded-md border border-slate-300 px-3 py-2 dark:border-slate-700">
          <div className="text-xs text-slate-600 dark:text-slate-400">Đường R tích lũy</div>
          <svg data-testid="r-curve" role="img" aria-label={`Đường R tích lũy qua ${curve.length} lệnh`} viewBox="0 0 200 40" className="mt-1 h-10 w-full">
            {curve.length >= 2 ? (
              (() => {
                const lo = Math.min(0, ...curve);
                const hi = Math.max(0, ...curve);
                const span = hi - lo || 1;
                const pts = curve.map((v, i) => `${(i / (curve.length - 1)) * 200},${38 - ((v - lo) / span) * 36}`).join(" ");
                const zero = 38 - ((0 - lo) / span) * 36;
                return (
                  <>
                    <line x1="0" x2="200" y1={zero} y2={zero} stroke="#94a3b8" strokeDasharray="3 3" />
                    <polyline points={pts} fill="none" stroke="#0369a1" strokeWidth="1.8" />
                  </>
                );
              })()
            ) : (
              <text x="4" y="24" fontSize="9" fill="#64748b">cần ít nhất 2 lệnh đã đóng</text>
            )}
          </svg>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-1 text-xs" role="group" aria-label="Lọc lệnh">
        {([["all", "Tất cả"], ["win", "Thắng"], ["loss", "Thua"], ["BUY", "MUA"], ["SELL", "BÁN"]] as [typeof filter, string][]).map(([k, label]) => (
          <button key={k} type="button" data-testid={`filter-${k}`} aria-pressed={filter === k} onClick={() => setFilter(k)} className={`rounded-md border px-2 py-1 ${filter === k ? "border-sky-600 bg-sky-500/15 font-semibold" : "border-slate-400"}`}>{label}</button>
        ))}
        <button type="button" data-testid="export-csv" onClick={exportCsv} disabled={rows.length === 0} className="ml-auto rounded-md border border-slate-400 px-2 py-1 font-semibold disabled:opacity-40">Xuất CSV</button>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <section data-testid="by-reason" className="rounded-md border border-slate-300 p-2 text-sm dark:border-slate-700">
          <h2 className="mb-1 text-xs font-semibold uppercase text-slate-600 dark:text-slate-400">Theo lý do thoát</h2>
          {byReason.length === 0 ? (
            <p className="text-slate-600 dark:text-slate-400">Chưa có lệnh đã đóng.</p>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="text-slate-600 dark:text-slate-400"><tr><th>Lý do</th><th className="text-right">Lệnh</th><th className="text-right">R</th><th className="text-right">P&L</th></tr></thead>
              <tbody>
                {byReason.map(([k, v]) => (
                  <tr key={k} className="border-t border-slate-200 dark:border-slate-800"><td>{REASON_TEXT[k] ?? k}</td><td className="text-right font-mono">{v.n}</td><td className="text-right font-mono">{fmt(v.r)}</td><td className="text-right font-mono">{money(v.pnl)}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
        <section data-testid="by-week" className="rounded-md border border-slate-300 p-2 text-sm dark:border-slate-700">
          <h2 className="mb-1 text-xs font-semibold uppercase text-slate-600 dark:text-slate-400">Theo tuần (thứ Hai, UTC)</h2>
          {byWeek.length === 0 ? (
            <p className="text-slate-600 dark:text-slate-400">Chưa có lệnh đã đóng.</p>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="text-slate-600 dark:text-slate-400"><tr><th>Tuần</th><th className="text-right">Lệnh</th><th className="text-right">Thắng</th><th className="text-right">R</th><th className="text-right">P&L</th></tr></thead>
              <tbody>
                {byWeek.map(([k, v]) => (
                  <tr key={k} className="border-t border-slate-200 dark:border-slate-800"><td className="font-mono">{k}</td><td className="text-right font-mono">{v.n}</td><td className="text-right font-mono">{v.wins}</td><td className="text-right font-mono">{fmt(v.r)}</td><td className="text-right font-mono">{money(v.pnl)}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
      <div className="overflow-x-auto">
        <table data-testid="journal-table" className="w-full text-left text-sm">
          <thead className="text-xs text-slate-600 dark:text-slate-400">
            <tr>
              <th className="pr-3">Setup</th>
              <th className="pr-3">Hướng</th>
              <th className="pr-3">Mở lúc ({ZONE_SHORT[zone]})</th>
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
                <td colSpan={14} className="py-3 text-slate-600 dark:text-slate-400">
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
                  <td className="pr-3 text-xs">v{t.strategy_version ?? "?"}<span className="block text-slate-600 dark:text-slate-400">{t.code_version ?? ""}</span></td>
                  <td className="whitespace-nowrap">
                    <Link data-testid="journal-view-on-chart" href={`/trade?focus=${encodeURIComponent(t.opened_at ?? t.created_at)}&to=${encodeURIComponent(t.closed_at ?? t.opened_at ?? t.created_at)}&tf=M5&trade=${encodeURIComponent(t.trade_id)}`} className="mr-2 text-xs underline">
                      xem trên biểu đồ
                    </Link>
                    <button type="button" data-testid="journal-detail-toggle" className="text-xs underline" onClick={() => setOpen(open === t.trade_id ? null : t.trade_id)}>
                      {open === t.trade_id ? "ẩn" : "nguồn gốc"}
                    </button>
                  </td>
                </tr>
                {open === t.trade_id && (
                  <tr>
                    <td colSpan={14} className="pb-2">
                      <dl data-testid="journal-detail" className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5 rounded-md bg-slate-500/10 p-2 text-xs sm:grid-cols-[auto_1fr_auto_1fr]">
                        <dt className="text-slate-600 dark:text-slate-400">Nguồn dữ liệu</dt><dd>{sourceText(t.source_mode)}</dd>
                        <dt className="text-slate-600 dark:text-slate-400">Chiến lược</dt><dd>v{t.strategy_version ?? "?"}</dd>
                        <dt className="text-slate-600 dark:text-slate-400">Phiên bản mã</dt><dd className="font-mono">{t.code_version ?? "—"}</dd>
                        <dt className="text-slate-600 dark:text-slate-400">Setup</dt><dd className="font-mono">{t.setup_id}</dd>
                        <dt className="text-slate-600 dark:text-slate-400">Phiên giao dịch</dt><dd>{viState(t.market?.session)}</dd>
                        <dt className="text-slate-600 dark:text-slate-400">H4 / H1 / M15 / M5</dt><dd>{[t.market?.h4, t.market?.h1, t.market?.m15, t.market?.m5].map((x) => viState(x)).join(" · ")}</dd>
                        <dt className="text-slate-600 dark:text-slate-400">Spread lúc vào</dt><dd>{String(t.market?.spread_points ?? "—")} điểm ({viState(t.market?.spread_state)})</dd>
                        <dt className="text-slate-600 dark:text-slate-400">Biến động / tick volume</dt><dd>{viState(t.market?.volatility)} / {viState(t.market?.volume_state)}</dd>
                        <dt className="text-slate-600 dark:text-slate-400">Tin tức</dt><dd>{viState(t.market?.news_state)}</dd>
                        <dt className="text-slate-600 dark:text-slate-400">Tuổi dữ liệu</dt><dd>{String(t.market?.data_age_seconds ?? "—")} s</dd>
                        {t.cancel_reason && (<><dt className="text-slate-600 dark:text-slate-400">Lý do hủy</dt><dd>{t.cancel_reason}</dd></>)}
                      </dl>
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
