import type { Health, State } from "../api/client";
import { ago } from "../format";

const ORDER = ["H4", "H1", "M30", "M15", "M5", "M1"] as const;

/** Each timeframe's role and verdict in the chain, with how fresh its last stored bar is. */
export function MtfStrip({ health, state }: { health: Health | null; state: State | null }) {
  return (
    <section className="mtf" aria-label="Các khung thời gian" data-testid="mtf">
      <ul>
        {ORDER.map((tf) => {
          const row = health?.store.timeframes.find((t) => t.timeframe === tf);
          const mtf = state?.mtf.find((m) => m.timeframe === tf);
          const fresh =
            row?.age_seconds === null || row === undefined
              ? "không có dữ liệu"
              : `nến đóng cách ${ago(row.age_seconds)}${row.state === "STALE" ? " · CŨ" : row.state === "MARKET_CLOSED" ? " · thị trường đóng" : ""}`;
          return (
            <li key={tf} data-testid={`mtf-${tf}`} data-verdict={mtf?.verdict ?? ""}>
              <strong>
                {tf} <span className="muted small">{mtf?.role ?? ""}</span>
              </strong>
              <span className="verdict" data-testid={`mtf-verdict-${tf}`}>
                {mtf ? mtf.verdict : "—"}
                {mtf?.detail ? ` · ${mtf.detail}` : ""}
              </span>
              <span className="muted small">{fresh}</span>
            </li>
          );
        })}
      </ul>
      <p className="muted small">
        H1 là nguồn hướng duy nhất; H4 và M1 chỉ chặn; M30 chỉ hiển thị. Độ mới tính theo lịch thị trường.
      </p>
    </section>
  );
}
