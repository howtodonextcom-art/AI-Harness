"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { MarketChart } from "@/components/market/MarketChart";
import {
  MARKET_TIMEFRAMES,
  fetchBars,
  fetchMatrix,
  fetchQuality,
  fetchQuote,
  fetchStatus,
  type BarsResponse,
  type MarketStatusResponse,
  type MarketTimeframe,
  type MatrixResponse,
  type QualityResponse,
  type QuoteResponse,
} from "@/lib/market";
import { formatInZone, ZONE_LABEL, type DisplayZone } from "@/lib/time";
import { useDisplayZone } from "@/lib/useZone";

const GOOD = "border-emerald-600 bg-emerald-500/15 text-emerald-800 dark:text-emerald-200";
const WARN = "border-amber-600 bg-amber-500/15 text-amber-800 dark:text-amber-200";
const BAD = "border-red-600 bg-red-500/15 text-red-800 dark:text-red-200";
const NEUTRAL = "border-slate-500 bg-slate-500/15 text-slate-700 dark:text-slate-300";

const STATE_STYLE: Record<string, string> = {
  CONNECTED: GOOD, RUNNING: GOOD, FRESH: GOOD, OPEN: GOOD, GOOD,
  STALE: BAD, STOPPED: BAD, DISCONNECTED: BAD, UNAVAILABLE: BAD,
  DEGRADED: WARN, ROLLOVER: NEUTRAL, CLOSED: NEUTRAL, MARKET_CLOSED: NEUTRAL, UNKNOWN: NEUTRAL,
} as unknown as Record<string, string>;

const STATE_TEXT: Record<string, string> = {
  CONNECTED: "ĐÃ KẾT NỐI", DISCONNECTED: "MẤT KẾT NỐI", RUNNING: "ĐANG CHẠY", STOPPED: "ĐÃ DỪNG",
  STALE: "CŨ", FRESH: "MỚI", OPEN: "MỞ", CLOSED: "ĐÓNG (cuối tuần)", ROLLOVER: "NGHỈ GIỮA NGÀY",
  MARKET_CLOSED: "THỊ TRƯỜNG ĐÓNG", UNKNOWN: "KHÔNG RÕ", UNAVAILABLE: "CHƯA CÓ", MAINTENANCE: "BẢO TRÌ",
};

const fmt = (value: number | null | undefined, digits = 2) =>
  value === null || value === undefined ? "—" : value.toFixed(digits);

function age(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  const s = Math.max(0, Math.round(seconds));
  if (s < 90) return `${s}s`;
  if (s < 5400) return `${Math.round(s / 60)} phút`;
  if (s < 172800) return `${(s / 3600).toFixed(1)} giờ`;
  return `${(s / 86400).toFixed(1)} ngày`;
}

function Pill({ label, state, testId }: { label: string; state: string; testId?: string }) {
  return (
    <span
      data-testid={testId}
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold ${STATE_STYLE[state] ?? NEUTRAL}`}
    >
      <span className="font-normal opacity-80">{label}</span>
      {STATE_TEXT[state] ?? state}
    </span>
  );
}

/** Live FTMO MT5 market view: component status, quote, candles + tick volume + spread, data quality. */
export function MarketView() {
  const [tf, setTf] = useState<MarketTimeframe>("M15");
  const [forming, setForming] = useState(true);
  const [zone, changeZone] = useDisplayZone("UTC");
  const [bars, setBars] = useState<BarsResponse | null>(null);
  const [quote, setQuote] = useState<QuoteResponse | null>(null);
  const [status, setStatus] = useState<MarketStatusResponse | null>(null);
  const [matrix, setMatrix] = useState<MatrixResponse | null>(null);
  const [quality, setQuality] = useState<QualityResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);


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
        setLoaded(true);
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

  useEffect(() => {
    let alive = true;
    const run = async () => {
      try {
        const q = await fetchQuality();
        if (alive) setQuality(q);
      } catch {
        /* the quality panel is secondary: the main error banner already covers an API outage */
      }
    };
    const first = setTimeout(() => void run(), 0);
    const id = setInterval(() => void run(), 15000);
    return () => {
      alive = false;
      clearTimeout(first);
      clearInterval(id);
    };
  }, []);

  const components = status?.components;
  const quoteState = quote ? (quote.state ?? "UNAVAILABLE") : "UNKNOWN";
  const recovery = status?.recovery_action;
  const freshness = status?.freshness ?? {};

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6">
      <header className="flex flex-wrap items-center gap-3">
        <Link href="/" className="rounded-md border border-slate-400 px-3 py-1 text-sm">
          ← Dashboard chính
        </Link>
        <h1 className="text-xl font-bold">XAUUSD · FTMO MT5</h1>
        <label className="ml-auto flex items-center gap-2 text-sm">
          Múi giờ hiển thị
          <select
            value={zone}
            onChange={(e) => changeZone(e.target.value as DisplayZone)}
            className="rounded-md border border-slate-400 bg-transparent px-2 py-1"
            data-testid="zone-select"
          >
            {(Object.keys(ZONE_LABEL) as DisplayZone[]).map((z) => (
              <option key={z} value={z}>
                {ZONE_LABEL[z]}
              </option>
            ))}
          </select>
        </label>
      </header>

      <section aria-label="Trạng thái thành phần" className="flex flex-wrap gap-2" data-testid="components">
        <Pill label="MT5 " state={components?.terminal ?? "UNKNOWN"} testId="pill-terminal" />
        <Pill label="Collector " state={components?.collector ?? "UNKNOWN"} testId="pill-collector" />
        <Pill label="API " state={components ? components.api : error ? "DISCONNECTED" : "UNKNOWN"} testId="pill-api" />
        <Pill label="Thị trường " state={components?.market ?? quote?.market_status ?? "UNKNOWN"} testId="pill-market" />
        <Pill label="Báo giá " state={components?.quote ?? quoteState} testId="pill-quote" />
        <Pill label="Nến " state={components?.bars ?? "UNKNOWN"} testId="pill-bars" />
      </section>

      <p className="text-xs text-slate-600 dark:text-slate-400" data-testid="source-note">
        Nguồn: terminal FTMO MetaTrader 5 (tài khoản DEMO, chỉ đọc dữ liệu thị trường). Khối lượng là{" "}
        <strong>tick volume</strong> (số lần giá đổi), không phải khối lượng thật. Giờ hiển thị: {ZONE_LABEL[zone]}.
      </p>

      {error ? (
        <p role="alert" className="rounded-md border border-red-600 bg-red-500/10 p-2 text-sm">
          Không đọc được API ({error}). Nếu API không chạy: <code>scripts/start_market_stack.ps1</code>.
        </p>
      ) : null}
      {recovery ? (
        <p role="status" className="rounded-md border border-amber-600 bg-amber-500/10 p-2 text-sm" data-testid="recovery">
          Cách khắc phục: {recovery}
        </p>
      ) : null}

      <section aria-label="Báo giá" className="rounded-lg border border-slate-300 p-3 dark:border-slate-700">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
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
        </div>
        <p className="mt-2 text-xs text-slate-600 dark:text-slate-400" data-testid="quote-detail">
          Tick cuối: <span className="font-mono">{formatInZone(quote?.last_tick_time ?? quote?.timestamp, zone)}</span>
          {quote?.reason ? ` · ${quote.reason}` : ""}
        </p>
      </section>

      {status?.warnings && status.warnings.length > 0 ? (
        <ul className="rounded-md border border-amber-600 bg-amber-500/10 p-2 text-xs" data-testid="warnings">
          {status.warnings.map((w) => (
            <li key={w}>⚠ {w}</li>
          ))}
        </ul>
      ) : null}

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
        {!loaded ? (
          <p className="p-6 text-sm text-slate-600 dark:text-slate-400" data-testid="loading">
            Đang tải dữ liệu…
          </p>
        ) : bars && bars.bars.length > 0 ? (
          <MarketChart bars={bars.bars} timeframe={tf} zone={zone} />
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
            <caption className="sr-only">Nến đóng gần nhất và độ mới theo từng khung</caption>
            <thead>
              <tr className="border-b border-slate-300 dark:border-slate-700">
                <th scope="col" className="py-1 pr-3">Khung</th>
                <th scope="col" className="py-1 pr-3">Nến đóng gần nhất (mở lúc)</th>
                <th scope="col" className="py-1 pr-3">Đóng lúc</th>
                <th scope="col" className="py-1 pr-3">Cách đây</th>
                <th scope="col" className="py-1">Trạng thái</th>
              </tr>
            </thead>
            <tbody>
              {(matrix?.timeframes ?? []).map((row) => (
                <tr key={row.timeframe} className="border-b border-slate-200 dark:border-slate-800">
                  <td className="py-1 pr-3 font-mono">{row.timeframe}</td>
                  <td className="py-1 pr-3 font-mono">{formatInZone(row.last_closed_bar_open, zone)}</td>
                  <td className="py-1 pr-3 font-mono">{formatInZone(row.last_close_time, zone)}</td>
                  <td className="py-1 pr-3">{age(row.age_seconds)}</td>
                  <td className="py-1">
                    <Pill label="" state={freshness[row.timeframe] ?? "UNKNOWN"} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <details className="rounded-lg border border-slate-300 p-3 dark:border-slate-700" data-testid="quality">
        <summary className="cursor-pointer text-base font-semibold">
          Chất lượng dữ liệu
          {quality ? ` · collector ${quality.collector_health}` : ""}
        </summary>
        {quality ? (
          <div className="mt-3 flex flex-col gap-3 text-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left" data-testid="depth">
                <caption className="sr-only">Độ sâu lịch sử theo khung</caption>
                <thead>
                  <tr className="border-b border-slate-300 dark:border-slate-700">
                    <th scope="col" className="py-1 pr-3">Khung</th>
                    <th scope="col" className="py-1 pr-3">Nến sớm nhất</th>
                    <th scope="col" className="py-1 pr-3">Nến mới nhất</th>
                    <th scope="col" className="py-1 pr-3">Số nến</th>
                    <th scope="col" className="py-1">Độ mới</th>
                  </tr>
                </thead>
                <tbody>
                  {quality.history_depth.map((d) => (
                    <tr key={d.timeframe} className="border-b border-slate-200 dark:border-slate-800">
                      <td className="py-1 pr-3 font-mono">{d.timeframe}</td>
                      <td className="py-1 pr-3 font-mono">{formatInZone(d.earliest, zone)}</td>
                      <td className="py-1 pr-3 font-mono">{formatInZone(d.latest, zone)}</td>
                      <td className="py-1 pr-3 font-mono">{d.rows ?? "—"}</td>
                      <td className="py-1">{STATE_TEXT[d.freshness] ?? d.freshness}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p data-testid="tick-store">
              Kho tick:{" "}
              {quality.tick_store.enabled
                ? `phủ đến ${formatInZone(quality.tick_store.covered_until, zone)}, chậm ${age(quality.tick_store.lag_seconds)}`
                : "chưa bật"}
            </p>
            <p data-testid="disk">
              Ổ đĩa: {quality.disk.level ?? "—"}
              {quality.disk.free_gb !== undefined ? ` · trống ${quality.disk.free_gb} GB` : ""}
              {quality.disk.estimated_days_remaining ? ` · ước tính còn ${quality.disk.estimated_days_remaining} ngày` : ""}
            </p>
            <p data-testid="integrity">
              Toàn vẹn kho nến:{" "}
              {quality.ledger_integrity
                ? quality.ledger_integrity.ok
                  ? "đã kiểm tra, sạch"
                  : "CÓ VẤN ĐỀ (chạy scripts/verify_market_ledger.py)"
                : "chưa có báo cáo kiểm tra (chạy scripts/verify_market_ledger.py)"}
            </p>
            <div>
              <div className="font-semibold">Sự kiện gần đây (thay đổi nến, khoảng trống)</div>
              {quality.recent_events.length === 0 ? (
                <p>Không có.</p>
              ) : (
                <ul className="font-mono text-xs">
                  {quality.recent_events.map((e, i) => (
                    <li key={`${e.at}-${i}`}>
                      {formatInZone(e.at, zone)} · {e.kind}
                      {e.timeframe ? ` · ${e.timeframe}` : ""}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        ) : (
          <p className="mt-2 text-sm">Chưa tải được dữ liệu chất lượng.</p>
        )}
      </details>
    </main>
  );
}
