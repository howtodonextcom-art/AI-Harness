import type { IntelGate, IntelScenario, IntelStep, Intelligence } from "../api/client";

const STATUS_VI: Record<string, string> = {
  WATCH: "THEO DÕI",
  CONTEXT: "BỐI CẢNH",
  INACTIVE: "KHÔNG HOẠT ĐỘNG",
  BLOCKED: "THẬN TRỌNG",
};
const STEP_MARK: Record<string, string> = { PASS: "✓", FAIL: "✗", NOT_REACHED: "·", NOT_APPLICABLE: "–" };
const DIR_VI: Record<string, string> = { UP: "▲", DOWN: "▼", NONE: "" };
const PHASE_VI: Record<string, string> = {
  COMPRESSION: "nén",
  NORMAL: "bình thường",
  EXPANSION: "mở rộng",
  UNKNOWN: "—",
};

const hhmm = (iso: string | null | undefined) => (iso ? new Date(iso).toISOString().slice(11, 16) : "—");

/** Safety gates or governor holds as small chips ("none" text when there is nothing). */
export function GateChips({
  gates,
  none,
  prefix = "",
}: {
  gates: readonly IntelGate[];
  none: string;
  prefix?: string;
}) {
  if (gates.length === 0) return <span className="muted small">{none}</span>;
  return (
    <span className="gate-chips">
      {gates.map((g) => (
        <span key={g.code} className="chip chip-warn" data-code={g.code} title={g.code}>
          {prefix}
          {g.text}
        </span>
      ))}
    </span>
  );
}

function Scenario({ s }: { s: IntelScenario }) {
  return (
    <li className={`scenario st-${s.status.toLowerCase()}`} data-testid={`scenario-${s.key}`} data-status={s.status}>
      <div className="scenario-head">
        <strong>
          {DIR_VI[s.direction]} {s.title}
        </strong>
        <span className="chip small">{STATUS_VI[s.status] ?? s.status}</span>
      </div>
      {s.status !== "INACTIVE" && <div className="muted small">{s.why.join(" · ")}</div>}
      {s.status !== "INACTIVE" && (
        <div className="small">
          <span className="muted">xác nhận:</span> {s.confirm} · <span className="muted">vô hiệu:</span> {s.invalidate}
        </div>
      )}
    </li>
  );
}

function Step({ s }: { s: IntelStep }) {
  return (
    <li data-testid={`step-${s.key}`} data-status={s.status} className={`step step-${s.status.toLowerCase()}`}>
      <span className="step-mark" aria-hidden="true">
        {STEP_MARK[s.status]}
      </span>
      <span className="step-label">{s.label}</span>
      <span className="muted small step-obs" title={`${s.observed} (cần: ${s.required})`}>
        {s.observed}
      </span>
    </li>
  );
}

/** What the market shows, the scenarios to watch, and the strategy's authorization: three layers. */
export function IntelligencePanel({ intel }: { intel: Intelligence | null }) {
  if (!intel) {
    return (
      <section className="card intel" aria-busy="true" aria-label="Thị trường">
        <p className="muted">Đang tải mô tả thị trường…</p>
      </section>
    );
  }
  const a = intel.authorization;
  const stale = intel.quote_age_s != null && intel.quote_age_s > 5;
  return (
    <section className="card intel" aria-label="Thị trường đang nói gì" data-testid="intel-panel">
      <header className="card-head">
        <h2>Thị trường đang nói gì</h2>
        <span className="muted small" data-testid="intel-fresh">
          quyết định dựa trên nến đã đóng · M5 đóng lúc {hhmm(intel.last_closed_m5)} UTC · giá cách{" "}
          <strong className={stale ? "error-text" : ""}>
            {intel.quote_age_s == null ? "—" : `${intel.quote_age_s.toFixed(1)}s`}
          </strong>
          {" · "}chỉ mô tả, không có quyền đặt lệnh
        </span>
      </header>
      <p className="headline" data-testid="intel-summary">
        {intel.summary}
      </p>
      <div className="intel-grid">
        <div data-testid="intel-observation">
          <h3>Quan sát</h3>
          <table className="paper-table small">
            <tbody>
              {intel.timeframes.map((t) => (
                <tr key={t.timeframe} data-testid={`intel-tf-${t.timeframe}`}>
                  <th scope="row">{t.timeframe}</th>
                  <td>{t.available ? (t.regime ?? "—") : "thiếu dữ liệu"}</td>
                  <td>{PHASE_VI[t.volatility_phase]}</td>
                  <td className="muted">{t.role}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h3>Mức quan trọng</h3>
          <ul className="levels small" data-testid="intel-levels">
            {intel.levels.slice(0, 6).map((l, i) => (
              <li key={`${l.role}-${l.price}-${i}`} className={l.confirmed ? "" : "muted"}>
                {l.price.toFixed(2)} · {l.label}
                {l.confirmed ? "" : " (chưa xác nhận)"}
                {l.distance_atr != null && (
                  <span className="muted">
                    {" "}
                    · {l.distance_atr >= 0 ? "+" : ""}
                    {l.distance_atr.toFixed(2)} ATR
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
        <div data-testid="intel-scenarios">
          <h3>Kịch bản cần theo dõi</h3>
          <ul className="scenarios">
            {intel.scenarios.map((s) => (
              <Scenario key={s.key} s={s} />
            ))}
          </ul>
        </div>
        <div data-testid="intel-funnel">
          <h3>
            Chiến lược v{a.strategy_version} <span className="muted small">({a.evidence}, ứng viên V2 không hoạt động; lý do thị trường là chẩn đoán giả định tắt cổng)</span>
          </h3>
          <p className="small" data-testid="intel-explanation">
            {a.explanation}
          </p>
          <ol className="funnel">
            {a.funnel.map((s) => (
              <Step key={s.key} s={s} />
            ))}
          </ol>
        </div>
      </div>
      <div className="intel-foot">
        <details open data-testid="intel-changes">
          <summary>Vừa thay đổi ({intel.changes.length})</summary>
          <ul className="small">
            {intel.changes.slice(0, 6).map((c, i) => (
              <li key={`${c.at}-${i}`}>
                <span className="muted">{hhmm(c.at)}</span> {c.text}
              </li>
            ))}
          </ul>
        </details>
        <details data-testid="intel-events">
          <summary>Sự kiện nến và cấu trúc ({intel.events.length}), thời điểm BIẾT sau khi nến đóng</summary>
          <ul className="small">
            {intel.events.slice(0, 10).map((e, i) => (
              <li key={`${e.timeframe}-${e.kind}-${e.known_at}-${i}`}>
                <span className="muted">{hhmm(e.known_at)}</span> {e.timeframe} · {e.text}
                {e.level != null && <span className="muted"> · mức {e.level.toFixed(2)}</span>}
              </li>
            ))}
          </ul>
        </details>
      </div>
    </section>
  );
}
