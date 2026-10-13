import { useEffect, useState } from "react";
import { type ModelDetail, fetchModel } from "../api/client";

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const mark = (passed: boolean | null) => (passed === null ? "—" : passed ? "✓ đạt" : "✗ KHÔNG đạt");

/** ML V0 (volatility / range): its status, its pre-registered evidence and its locks. Never a forecast. */
export function ModelPanel() {
  const [model, setModel] = useState<ModelDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const abort = new AbortController();
    fetchModel(abort.signal)
      .then(setModel)
      .catch((e: unknown) => !abort.signal.aborted && setError(e instanceof Error ? e.message : String(e)));
    return () => abort.abort();
  }, []);

  if (error) return <p role="alert">Không đọc được trạng thái mô hình: {error}</p>;
  if (!model) return <p className="muted">Đang tải…</p>;
  if (!model.available) {
    return (
      <p data-testid="model-panel">
        Trạng thái: <strong>{model.status}</strong>. Chưa có bản ghi mô hình. {model.display}
      </p>
    );
  }
  return (
    <div data-testid="model-panel">
      <p>
        <strong data-testid="model-status">{model.status}</strong> · {model.model_id} v{model.version} ({model.role}) · thẩm quyền{" "}
        <strong>{model.authority}</strong> · tác vụ {model.task} ({model.label_version}) · đặc tả {model.spec_version}
      </p>
      <p data-testid="model-display" className="muted small">
        {model.display}
      </p>
      <p className="small" data-testid="model-locks">
        Test-H: <strong>{model.test_h === "LOCKED" ? "KHÓA (chưa mở)" : "đã chạy 1 lần"}</strong> · Holdout:{" "}
        <strong>{model.holdout === "LOCKED" ? "KHÓA (chưa mở)" : "đã chạy 1 lần"}</strong> · họ K {model.k_family} = {model.k} (
        {model.candidates.join(" + ")})
      </p>
      <div className="table-scroll">
        <table className="paper-table" data-testid="model-stages">
          <caption className="muted small">Tiêu chí đăng ký trước (mô hình mặc định so với ATR14 một đặc trưng)</caption>
          <thead>
            <tr>
              <th scope="col">Giai đoạn</th>
              <th scope="col">Hàng</th>
              <th scope="col">Cải thiện MSE</th>
              <th scope="col">CI 95% (chênh lệch MSE)</th>
              <th scope="col">Cận dưới một phía 97,5% (hiệu chỉnh K)</th>
              <th scope="col">Độ phủ dải 80%</th>
              <th scope="col">Tiêu chí</th>
            </tr>
          </thead>
          <tbody>
            {model.stages.map((s) => (
              <tr key={s.name} data-testid={`stage-${s.name.slice(0, 3)}`}>
                <td>{s.name}</td>
                <td>{s.n.toLocaleString("vi-VN")}</td>
                <td>{pct(s.skill_vs_atr14)}</td>
                <td>
                  [{s.ci95[0].toFixed(4)}; {s.ci95[1].toFixed(4)}]
                </td>
                <td>≥ {s.lower_adjusted.toFixed(4)}</td>
                <td>{pct(s.coverage_80)}</td>
                <td>
                  <ul className="criteria">
                    {s.criteria.map((c) => (
                      <li key={c.id} data-passed={String(c.passed)}>
                        {c.label}: {c.value} {mark(c.passed)}
                      </li>
                    ))}
                  </ul>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="small" data-testid="model-notes">
        {model.notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
    </div>
  );
}
