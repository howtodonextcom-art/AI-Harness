"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { MarketChart } from "@/components/market/MarketChart";
import {
  MARKET_TIMEFRAMES,
  fetchBars,
  fetchMatrix,
  fetchQuote,
  fetchStatus,
  type BarsResponse,
  type MarketStatusResponse,
  type MarketTimeframe,
  type MatrixResponse,
  type QuoteResponse,
} from "@/lib/market";

const HEALTH_STYLE: Record<string, string> = {
  GOOD: "border-emerald-600 bg-emerald-500/15 text-emerald-800 dark:text-emerald-200",
  DEGRADED: "border-amber-600 bg-amber-500/15 text-amber-800 dark:text-amber-200",
  STALE: "border-orange-600 bg-orange-500/15 text-orange-800 dark:text-orange-200",
  DISCONNECTED: "border-red-600 bg-red-500/15 text-red-800 dark:text-red-200",
  UNKNOWN: "border-slate-500 bg-slate-500/15 text-slate-700 dark:text-slate-300",
};

const HEALTH_LABEL: Record<string, string> = {
  GOOD: "TỐT",
  DEGRADED: "SUY GIẢM",
  STALE: "CŨ (STALE)",
  DISCONNECTED: "MẤT KẾT NỐI",
  UNKNOWN: "KHÔNG RÕ",
};

const MARKET_LABEL: Record<string, string> = {
  OPEN: "Thị trường mở",
  CLOSED: "Thị trường đóng (cuối tuần)",
  ROLLOVER: "Nghỉ giữa ngày (rollover)",
  MAINTENANCE: "Bảo trì",
  UNKNOWN: "Không rõ phiên",
};

const fmt = (value: number | null | undefined, digits = 2) =>
  value === null || value === undefined ? "—" : value.toFixed(digits);

function age(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  const s = Math.max(0, Math.round(seconds));
  if (s < 90) return `${s}s`;
  if (s < 5400) return `${Math.round(s / 60)} phút`;
  return `${(s / 3600).toFixed(1)} giờ`;
}

function Badge({ text, className }: { text: string; className: string }) {
  return <span className={`rounded-md border px-2 py-0.5 text-xs font-semibold ${className}`}>{text}</span>;
}

/** Live FTMO MT5 market view: quote header, candles + tick volume + spread, multi-timeframe matrix. */
export function MarketView() {
  const [tf, setTf] = useState<MarketTimeframe>("M15");
  const [forming, setForming] = useState(true);
  const [bars, setBars] = useState<BarsResponse | null>(null);
  const [quote, setQuote] = useState<QuoteResponse | null>(null);
  const [status, setStatus] = useState<MarketStatusResponse | null>(null);
  const [matrix, setMatrix] = useState<MatrixResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadQuote = useCallback(async () => {
    try {
      setQuote(await fetchQuote());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "không đọc được API");
    }
  }, []);

  useEffect(() => {
    const first = setTimeout(() => void loadQuote(), 0);
    const id = setInterval(() => void loadQuote(), 1000);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, [loadQuote]);

  useEffect(() => {
    let alive = true;
    const run = async () => {
      try {
        const [b, s, m] = await Promise.all([fetchBars(tf, 500, forming), fetchStatus(), fetchMatrix()]);
        if (!alive) return;
        setBars(b);
        setStatus(s);
        setMatrix(m);
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : "không đọc được API");
      }
    };
    const first = setTimeout(() => void run(), 0);
    const id = setInterval(() => void run(), 3000);
    return () => {
      alive = false;
      clearTimeout(first);
      clearInterval(id);
    };
  }, [tf, forming]);

  const health = status?.health ?? "UNKNOWN";
  const marketState = quote?.market_status ?? status?.market_status ?? "UNKNOWN";
  const stale = quote?.stale ?? true;

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6">
      <header className="flex flex-wrap items-center gap-3">
        <Link href="/" className="rounded-md border border-slate-400 px-3 py-1 text-sm">
          ← Dashboard chính
        </Link>
        <h1 className="text-xl font-bold">XAUUSD · FTMO MT5</h1>
        <Badge text={`Dữ liệu: ${HEALTH_LABEL[health] ?? health}`} className={HEALTH_STYLE[health] ?? HEALTH_STYLE.UNKNOWN} />
        <Badge
          text={MARKET_LABEL[marketState] ?? marketState}
          className={marketState === "OPEN" ? HEALTH_STYLE.GOOD : HEALTH_STYLE.UNKNOWN}
        />
        {stale && quote?.available ? <Badge text="BÁO GIÁ CŨ" className={HEALTH_STYLE.STALE} /> : null}
      </header>

      <p className="text-xs text-slate-600 dark:text-slate-400" data-testid="source-note">
        Nguồn: terminal FTMO MetaTrader 5 (tài khoản DEMO, chỉ đọc dữ liệu thị trường). Khối lượng là{" "}
        <strong>tick volume</strong> (số lần giá đổi), không phải khối lượng thật. Giờ hiển thị: UTC.
      </p>

      {error ? (
        <p role="alert" className="rounded-md border border-red-600 bg-red-500/10 p-2 text-sm">
          Lỗi API: {error}
        </p>
      ) : null}
      {status && !status.collector_running ? (
        <p role="status" className="rounded-md border border-amber-600 bg-amber-500/10 p-2 text-sm">
          Collector không chạy (hoặc trạng thái đã cũ). Chạy <code>scripts/run_market_collector.py</code> để có dữ liệu mới.
        </p>
      ) : null}

      <section aria-label="Báo giá" className="grid grid-cols-2 gap-3 rounded-lg border border-slate-300 p-3 sm:grid-cols-5 dark:border-slate-700">
        {[
          ["Bid", fmt(quote?.bid)],
          ["Ask", fmt(quote?.ask)],
          ["Mid", fmt(quote?.mid)],
          ["Spread (điểm)", fmt(quote?.spread_points, 0)],
          ["Tuổi tick", age(quote?.age_seconds)],
        ].map(([label, value]) => (
          <div key={label}>
            <div className="text-xs text-slate-600 dark:text-slate-400">{label}</div>
            <div className="font-mono text-lg font-semibold" data-testid={`quote-${label}`}>
              {value}
            </div>
          </div>
        ))}
      </section>

      <section aria-label="Khung thời gian" className="flex flex-wrap items-center gap-2">
        {MARKET_TIMEFRAMES.map((t) => (
          <button
            key={t}
            type="button"
            aria-pressed={t === tf}
            onClick={() => setTf(t)}
            className={`rounded-md border px-3 py-1 text-sm ${
              t === tf ? "border-sky-600 bg-sky-500/15 font-semibold" : "border-slate-400"
            }`}
          >
            {t}
          </button>
        ))}
        <label className="ml-2 flex items-center gap-1 text-sm">
          <input type="checkbox" checked={forming} onChange={(e) => setForming(e.target.checked)} />
          Hiện nến đang hình thành
        </label>
      </section>

      <section aria-label="Biểu đồ" className="rounded-lg border border-slate-300 p-2 dark:border-slate-700">
        {bars && bars.bars.length > 0 ? (
          <MarketChart bars={bars.bars} timeframe={tf} />
        ) : (
          <p className="p-6 text-sm text-slate-600 dark:text-slate-400" data-testid="no-bars">
            Chưa có nến {tf} trong kho dữ liệu. Chạy <code>scripts/backfill_mt5.py</code> rồi collector.
          </p>
        )}
        <p className="px-2 pt-1 text-xs text-slate-600 dark:text-slate-400">
          Nến mờ viền đậm = đang hình thành (chưa đóng, không dùng cho nghiên cứu). Các nến còn lại đã đóng.
        </p>
      </section>

      <section aria-label="Ma trận khung thời gian">
        <h2 className="mb-1 text-base font-semibold">Độ mới của từng khung (nến đã đóng)</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm" data-testid="matrix">
            <thead>
              <tr className="border-b border-slate-300 dark:border-slate-700">
                <th className="py-1 pr-3">Khung</th>
                <th className="py-1 pr-3">Nến đóng gần nhất (mở lúc)</th>
                <th className="py-1 pr-3">Đóng lúc</th>
                <th className="py-1">Cách đây</th>
              </tr>
            </thead>
            <tbody>
              {(matrix?.timeframes ?? []).map((row) => (
                <tr key={row.timeframe} className="border-b border-slate-200 dark:border-slate-800">
                  <td className="py-1 pr-3 font-mono">{row.timeframe}</td>
                  <td className="py-1 pr-3 font-mono">{row.last_closed_bar_open ?? "—"}</td>
                  <td className="py-1 pr-3 font-mono">{row.last_close_time ?? "—"}</td>
                  <td className="py-1">{age(row.age_seconds)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
