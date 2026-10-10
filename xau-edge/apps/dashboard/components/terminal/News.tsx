"use client";

import { BAD, Card, GOOD, NEUTRAL, WARN } from "@/components/trade/ui";
import type { NewsEventItem, NewsView } from "@/lib/trade";
import { ZONE_SHORT, formatInZone, type DisplayZone } from "@/lib/time";

/** What each canonical server state means to a trader, in plain Vietnamese. Only CLEAR is ever green. */
export const NEWS_VI: Record<string, { label: string; tone: string }> = {
  CLEAR: { label: "Chưa vào cửa sổ tin mạnh", tone: GOOD },
  BLOCKED: { label: "ĐANG trong cửa sổ tin mạnh", tone: BAD },
  UNKNOWN: { label: "Tin tức chưa xác minh", tone: WARN },
  NOT_CONFIGURED: { label: "Chưa cấu hình lịch tin", tone: WARN },
  STALE: { label: "Lịch tin đã cũ hoặc hết hạn", tone: WARN },
  ERROR: { label: "Lịch tin bị lỗi", tone: BAD },
};

/** "sau 2h15" / "2h15 trước"; the server counts the minutes, so this does not depend on the display zone. */
export function untilText(minutes: number): string {
  const abs = Math.abs(minutes);
  const body = abs >= 60 ? `${Math.floor(abs / 60)}h${String(abs % 60).padStart(2, "0")}` : `${abs} phút`;
  return minutes >= 0 ? `sau ${body}` : `${body} trước`;
}

const IMPACT_VI: Record<string, string> = { high: "MẠNH", medium: "vừa", low: "nhẹ" };

function eventLine(e: NewsEventItem): string {
  const where = e.currency ? ` ${e.currency}` : "";
  return `${e.title}${where} · ${IMPACT_VI[e.impact] ?? e.impact} · ${untilText(e.minutes_to)}`;
}

const WINDOW_BEFORE_MIN = 30; // the news guard blocks from this many minutes before a high-impact event

/** One compact line under the decision: the state, and the next event that matters. */
export function NewsStrip({ news }: { news: NewsView }) {
  const meta = NEWS_VI[news.state] ?? { label: news.state, tone: WARN };
  const next = news.blocked_by ?? news.next_events.find((e) => e.impact === "high") ?? news.next_events[0];
  // CLEAR only says "not inside the window NOW": a high-impact event within two hours turns the strip amber and says when the window opens
  const opensIn = news.state === "CLEAR" && next && next.impact === "high" ? next.minutes_to - WINDOW_BEFORE_MIN : null;
  const soon = opensIn !== null && opensIn <= 90;
  const tone = soon ? WARN : meta.tone;
  return (
    <p data-testid="news-strip" data-state={news.state} data-soon={soon ? "true" : "false"} role="status" className={`rounded-md border px-2 py-1 text-xs ${tone}`}>
      <b data-testid="news-state">TIN: {soon ? "Tin mạnh sắp tới" : meta.label}</b>
      {news.state !== "CLEAR" && news.state !== "BLOCKED" && news.detail ? <span data-testid="news-detail"> — {news.detail}. Hãy tự kiểm tra tin.</span> : null}
      {next ? <span data-testid="news-next"> · {news.blocked_by ? "Tin: " : "Tiếp theo: "}{eventLine(next)}</span> : null}
      {soon && opensIn !== null ? <span data-testid="news-opens"> · {opensIn > 0 ? `cửa sổ chặn lệnh mở sau ${untilText(opensIn).replace("sau ", "")}` : "đang sát cửa sổ chặn lệnh"}</span> : null}
    </p>
  );
}

/** System tab: where the calendar comes from, how fresh it is, what it covers and what is coming. */
export function NewsCard({ news, zone }: { news: NewsView | undefined; zone: DisplayZone }) {
  if (!news) {
    return (
      <Card title="Lịch tin tức" testId="news-card">
        <p className="text-sm text-slate-600 dark:text-slate-400">Chưa có thông tin tin tức từ máy chủ.</p>
      </Card>
    );
  }
  const meta = NEWS_VI[news.state] ?? { label: news.state, tone: NEUTRAL };
  const at = (iso: string | null) => (iso ? `${formatInZone(iso, zone).slice(5, 16)} (${ZONE_SHORT[zone]})` : "—");
  const last = news.last_update;
  return (
    <Card title="Lịch tin tức" testId="news-card">
      <p className="text-sm">
        <span data-testid="news-card-state" className={`rounded border px-1.5 py-0.5 text-xs font-bold ${meta.tone}`}>{news.state}</span>{" "}
        {meta.label}
      </p>
      {news.detail && <p data-testid="news-card-detail" className="mt-1 text-xs text-slate-600 dark:text-slate-400">{news.detail}</p>}
      <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 text-sm">
        <dt className="text-slate-600 dark:text-slate-400">Nguồn</dt><dd data-testid="news-source" className="font-mono">{news.source ?? "—"}</dd>
        <dt className="text-slate-600 dark:text-slate-400">Phủ từ</dt><dd className="font-mono">{at(news.coverage?.from ?? null)}</dd>
        <dt className="text-slate-600 dark:text-slate-400">Phủ đến</dt><dd className="font-mono">{at(news.coverage?.to ?? null)}</dd>
        <dt className="text-slate-600 dark:text-slate-400">Làm mới lần cuối</dt><dd data-testid="news-updated" className="font-mono">{at(news.last_updated_at)}</dd>
      </dl>
      {last && last.ok === false && (
        <p data-testid="news-update-failed" role="status" className={`mt-1 rounded-md border px-2 py-1 text-xs ${WARN}`}>
          Lần cập nhật gần nhất THẤT BẠI ({at(last.last_attempt_at)}): {last.error ?? "không rõ lỗi"}. Lịch cũ vẫn được giữ nguyên.
        </p>
      )}
      {news.next_events.length > 0 ? (
        <ul data-testid="news-events" className="mt-1 space-y-0.5 text-xs">
          {news.next_events.map((e) => (
            <li key={`${e.time}-${e.title}`}>{eventLine(e)}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">Không có tin vừa/mạnh trong 24 giờ tới (theo lịch hiện có).</p>
      )}
    </Card>
  );
}
