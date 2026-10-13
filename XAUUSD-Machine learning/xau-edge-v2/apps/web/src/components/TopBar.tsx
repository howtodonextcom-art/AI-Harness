import type { Live } from "../hooks/useLive";
import { ago } from "../format";

const MARKET_VI: Record<string, string> = { OPEN: "MỞ", CLOSED: "ĐÓNG", ROLLOVER: "NGHỈ GIỮA NGÀY", UNKNOWN: "KHÔNG RÕ" };

const EVIDENCE_VI: Record<string, string> = {
  UNVALIDATED: "CHƯA KIỂM CHỨNG",
  RESEARCH: "NGHIÊN CỨU",
  SHADOW: "BÓNG (không thẩm quyền)",
  OOS_VALIDATED: "ĐÃ QUA NGOÀI MẪU",
  FORWARD_VALIDATED: "ĐÃ QUA FORWARD",
};

function dataChip(live: Live): { text: string; tone: "ok" | "warn" | "bad" } {
  if (!live.health) return { text: "Dữ liệu: đang tải", tone: "warn" };
  const store = live.health.store;
  if (!store.reachable) return { text: "Dữ liệu: không đọc được kho", tone: "bad" };
  const m1 = store.timeframes.find((t) => t.timeframe === "M1");
  if (!m1 || m1.age_seconds === null) return { text: "Dữ liệu: không có nến M1", tone: "bad" };
  const age = ago(m1.age_seconds);
  if (m1.state === "STALE") return { text: `Nến M1 CŨ: đóng cách ${age} (thị trường ${MARKET_VI[store.market_status]})`, tone: "warn" };
  if (m1.state === "MARKET_CLOSED") return { text: `Thị trường ${MARKET_VI[store.market_status]} · nến M1 cuối cách ${age}`, tone: "ok" };
  return { text: `Nến M1 đóng cách đây ${age}`, tone: "ok" };
}

export function TopBar({ live }: { live: Live }) {
  const data = dataChip(live);
  const evidence = live.state?.evidence ?? "UNVALIDATED";
  const model = live.state?.model.status ?? "NOT_DEPLOYED";
  const wsText =
    live.ws === "open"
      ? "Kết nối live"
      : live.ws === "connecting"
        ? "Đang kết nối"
        : `Mất kết nối, thử lại lần ${live.retries}`;
  return (
    <header className="topbar" role="banner">
      <div className="brand">
        <strong>XAU EDGE</strong> <span className="sym">XAUUSD</span>
      </div>
      <ul className="chips" aria-label="Trạng thái hệ thống">
        <li className="chip chip-paper" data-testid="mode">
          <span aria-hidden="true">◧</span> PAPER · không gửi lệnh thật
        </li>
        <li className="chip chip-evidence" data-testid="evidence" data-level={evidence}>
          <span aria-hidden="true">⚑</span> {evidence} · {EVIDENCE_VI[evidence] ?? evidence}
        </li>
        <li className={`chip chip-${data.tone}`} data-testid="data-chip">
          <span aria-hidden="true">{data.tone === "ok" ? "●" : "▲"}</span> {data.text}
        </li>
        {live.paper && (
          <li
            className={`chip chip-${live.paper.day_pnl_usd < 0 ? "warn" : "neutral"}`}
            data-testid="paper-chip"
            data-auto={String(live.paper.auto_paper)}
          >
            <span aria-hidden="true">◈</span> Sổ PAPER ${live.paper.equity.toFixed(0)} · hôm nay{" "}
            {live.paper.day_pnl_usd >= 0 ? "+" : "-"}${Math.abs(live.paper.day_pnl_usd).toFixed(2)} · tự động{" "}
            {live.paper.auto_paper ? "BẬT" : "TẮT"}
          </li>
        )}
        <li className="chip chip-neutral" data-testid="model-chip">
          <span aria-hidden="true">◇</span> Mô hình: {model} · không thẩm quyền
        </li>
        <li
          className={`chip chip-${live.ws === "open" ? "ok" : "warn"}`}
          data-testid="ws-status"
          data-state={live.ws}
        >
          <span aria-hidden="true">{live.ws === "open" ? "●" : "○"}</span> {wsText}
        </li>
      </ul>
    </header>
  );
}
