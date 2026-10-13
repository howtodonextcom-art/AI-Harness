import { useEffect, useState } from "react";
import { type ForwardSummary, type State, fetchForward } from "../api/client";

const pct = (v: number | null | undefined, d = 1) => (v == null ? "—" : `${(v * 100).toFixed(d)}%`);
const num = (v: number | null | undefined, d = 2) => (v == null ? "—" : v.toFixed(d));
const utc = (iso: string | null | undefined) => (iso ? `${new Date(iso).toISOString().slice(0, 16).replace("T", " ")}Z` : "—");

function Bar({ value, max, label }: { value: number; max: number; label: string }) {
  const width = max > 0 ? Math.max(2, Math.round((value / max) * 100)) : 0;
  return (
    <div className="meter" role="img" aria-label={label}>
      <div className="meter-fill" style={{ width: `${Math.min(width, 100)}%` }} />
    </div>
  );
}

/** Forward evidence: what the engine watched and did, with the protocol's minimums. A description, never a claim. */
export function EvidencePanel({ state, revision }: { state: State | null; revision: number }) {
  const [data, setData] = useState<ForwardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const abort = new AbortController();
    const load = () =>
      fetchForward(abort.signal)
        .then((d) => {
          setData(d);
          setError(null);
        })
        .catch((e: unknown) => !abort.signal.aborted && setError(e instanceof Error ? e.message : String(e)));
    void load();
    const timer = setInterval(() => void load(), 30_000);
    return () => {
      abort.abort();
      clearInterval(timer);
    };
  }, [revision]);

  const label = state?.evidence ?? "UNVALIDATED";
  if (error) return <p role="alert">Không đọc được bằng chứng forward: {error}</p>;
  if (!data) return <p className="muted">Đang tải…</p>;
  const p = data.progress;
  const f = data.funnel;
  const maxLevel = f ? Math.max(...Object.values(f.by_readiness), 1) : 1;
  return (
    <div data-testid="evidence-panel">
      <p>
        Mức bằng chứng của hệ thống: <strong data-testid="evidence-label">{label}</strong>. Quan sát forward:{" "}
        <strong data-testid="forward-state">{data.evidence === "NO_OBSERVATIONS" ? "chưa có" : "đang tích lũy"}</strong>. Đây là{" "}
        <strong>mô tả</strong>, không phải bằng chứng; Test-H và holdout vẫn khóa, V0 ML đã bị loại tại Kiểm định.
      </p>
      <p className="small" data-testid="forward-coverage">
        Từ {utc(data.started)} đến {utc(data.last)} ({num(p.observed_days, 2)} ngày) · đã ghi {data.logged_bars}/{data.expected_bars} nến M5 · độ phủ{" "}
        <strong>{pct(p.coverage)}</strong> (tối thiểu {pct(p.min_coverage, 0)}) · {data.gaps.length} khoảng trống
        {data.gaps.length > 0 && ` (gần nhất ${utc(data.gaps[data.gaps.length - 1]?.start)}, ${data.gaps[data.gaps.length - 1]?.bars} nến)`}
      </p>
      <p className="small" data-testid="forward-progress">
        Mức tối thiểu của giao thức: lệnh đã đóng {p.closed_trades}/{p.min_closed_trades} · ngày quan sát {num(p.observed_days, 1)}/{p.min_days} · được phép kết luận:{" "}
        <strong>{p.claim_allowed ? "CÓ" : "CHƯA"}</strong>. {p.reason}.
        {p.eta_days_to_min_trades != null && ` Với tốc độ hiện tại cần thêm khoảng ${num(p.eta_days_to_min_trades, 0)} ngày.`}
      </p>
      {f && (
        <div className="table-scroll">
          <table className="paper-table" data-testid="forward-funnel">
            <caption className="muted small">Chuỗi quyết định đi được tới đâu ở mỗi nến M5 đã đóng</caption>
            <thead>
              <tr>
                <th scope="col">Mức sẵn sàng</th>
                <th scope="col">Số nến</th>
                <th scope="col">
                  <span className="sr-only">Biểu đồ</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(f.by_readiness).map(([name, count]) => (
                <tr key={name} data-level={name}>
                  <td>{name}</td>
                  <td>{count}</td>
                  <td>
                    <Bar value={count} max={maxLevel} label={`${name}: ${count} nến`} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {f && (
        <p className="small" data-testid="forward-signals">
          Hành động: {Object.entries(f.by_action).map(([a, n]) => `${a} ${n}`).join(" · ")} · tín hiệu MUA/BÁN <strong>{f.signals}</strong> nến ({f.distinct_setups} setup khác nhau).{" "}
          Lý do chặn thường gặp: {Object.entries(f.first_refusal).slice(0, 4).map(([r, n]) => `${r} ${n}`).join(", ") || "—"}.
        </p>
      )}
      {data.trades.length === 0 ? (
        <p className="small" data-testid="forward-trades">Chưa có lệnh PAPER nào đóng.</p>
      ) : (
        <ul className="small" data-testid="forward-trades">
          {data.trades.map((t) => (
            <li key={t.strategy_version}>
              Chiến lược v{t.strategy_version}: {t.closed} lệnh đóng ({t.wins} thắng, {t.losses} thua) · tổng {num(t.total_r)} R · R trung bình {num(t.mean_r)} · tỉ lệ thắng{" "}
              {pct(t.win_rate, 0)}
              {t.win_rate_ci95 && ` (Wilson 95%: ${pct(t.win_rate_ci95[0], 0)}–${pct(t.win_rate_ci95[1], 0)})`}
            </li>
          ))}
        </ul>
      )}
      <p className="small" data-testid="forward-benchmark">
        Giá vàng trong kỳ quan sát (mua-và-giữ): {data.buy_and_hold_pct == null ? "—" : `${data.buy_and_hold_pct >= 0 ? "+" : ""}${data.buy_and_hold_pct.toFixed(2)}%`} · sổ PAPER:{" "}
        {data.paper_return_pct == null ? "—" : `${data.paper_return_pct >= 0 ? "+" : ""}${data.paper_return_pct.toFixed(2)}%`}
      </p>
      <ul className="small" data-testid="forward-notes">
        {data.notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
      <p className="muted small">Giao thức đăng ký trước: {data.protocol}</p>
    </div>
  );
}
