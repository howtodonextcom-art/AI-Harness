import { useCallback, useEffect, useState } from "react";
import {
  type JournalEvent,
  type PaperPosition,
  type PaperSummary,
  type State,
  closePosition,
  fetchHumanDecisions,
  fetchJournal,
  type HumanRecord,
  openCurrentPlan,
} from "../api/client";

const usd = (v: number | null | undefined) => (v == null ? "—" : `${v < 0 ? "-" : v > 0 ? "+" : ""}$${Math.abs(v).toFixed(2)}`);
const REASON_VI: Record<string, string> = {
  STOP_LOSS: "chạm SL",
  TAKE_PROFIT: "chạm TP",
  MANUAL: "đóng tay",
  FLATTEN: "cắt do lỗ ngày",
};

function Summary({ s }: { s: PaperSummary }) {
  const g = s.governor;
  return (
    <div data-testid="paper-summary">
      <p>
        Equity <strong data-testid="paper-equity">${s.equity.toFixed(2)}</strong> (khởi đầu ${s.start_equity.toFixed(0)}, giả định) · hôm nay{" "}
        <strong>{usd(s.day_pnl_usd)}</strong> · đã chốt {usd(s.realized_pnl_usd)} · đang mở {usd(s.floating_pnl_usd)}
      </p>
      <p className="muted small">
        {s.closed_count} lệnh đã đóng ({s.wins} thắng, {s.losses} thua) · tổng {s.total_r.toFixed(2)} R. Mẫu quá nhỏ để kết luận
        bất cứ điều gì về lợi thế; đây là sổ ghi chép, không phải bằng chứng.
      </p>
      <p className="small" data-testid="governor">
        Bộ kiểm soát: {g.open_positions} lệnh mở · {g.trades_today} lệnh hôm nay · chuỗi thua {g.loss_streak} · lỗ ngày{" "}
        {g.daily_loss_pct.toFixed(2)}% / dừng {g.daily_loss_stop_pct}%
        {g.cooldown_until && ` · nghỉ tới ${new Date(g.cooldown_until).toISOString().slice(11, 16)} UTC`}
        {g.refusals.length > 0 ? ` · lệnh mới bị chặn: ${g.refusals.join(", ")}` : " · lệnh mới được phép"}
      </p>
    </div>
  );
}

function Table({ rows, onClose, busy }: { rows: PaperPosition[]; onClose: (id: string) => void; busy: boolean }) {
  return (
    <div className="table-scroll">
      <table className="paper-table" data-testid="paper-positions">
        <caption className="muted small">Lệnh PAPER (mới nhất trước)</caption>
        <thead>
          <tr>
            <th scope="col">Mở lúc (UTC)</th>
            <th scope="col">Hướng</th>
            <th scope="col">Lot</th>
            <th scope="col">Vào</th>
            <th scope="col">SL</th>
            <th scope="col">TP</th>
            <th scope="col">Ra</th>
            <th scope="col">Lý do</th>
            <th scope="col">PnL ròng</th>
            <th scope="col">R</th>
            <th scope="col">MAE/MFE (điểm)</th>
            <th scope="col">Nguồn</th>
            <th scope="col">
              <span className="sr-only">Thao tác</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.id} data-status={p.status} data-testid={`pos-${p.id}`}>
              <td>{new Date(p.opened_at).toISOString().slice(5, 16).replace("T", " ")}</td>
              <td>{p.side === "BUY" ? "▲ MUA" : "▼ BÁN"}</td>
              <td>{p.lots}</td>
              <td>{p.entry.toFixed(2)}</td>
              <td>{p.stop_loss.toFixed(2)}</td>
              <td>{p.take_profit.toFixed(2)}</td>
              <td>{p.exit_price == null ? "đang mở" : p.exit_price.toFixed(2)}</td>
              <td>
                {p.exit_reason ? REASON_VI[p.exit_reason] : "—"}
                {p.ambiguous ? " (nến chạm cả hai, tính SL)" : ""}
              </td>
              <td>{p.status === "OPEN" ? `${usd(p.floating_pnl_usd)} (nổi)` : usd(p.net_pnl_usd)}</td>
              <td>{p.r_multiple == null ? "—" : p.r_multiple.toFixed(2)}</td>
              <td>
                {p.mae_points.toFixed(0)} / {p.mfe_points.toFixed(0)}
              </td>
              <td>{p.source === "AUTO" ? "tự động" : "thủ công"}</td>
              <td>
                {p.status === "OPEN" && (
                  <button type="button" disabled={busy} onClick={() => onClose(p.id)} data-testid="close-position">
                    Đóng ngay
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const CHOICE_VI: Record<string, string> = { ACCEPT: "CHẤP NHẬN", WAIT: "CHỜ", REJECT: "BỎ QUA" };

function HumanLog({ rows }: { rows: HumanRecord[] }) {
  return (
    <div className="table-scroll" data-testid="human-log">
      <h3>Quyết định của con người (chỉ thêm, không sửa)</h3>
      <table className="paper-table">
        <caption className="sr-only">Nhật ký quyết định của con người</caption>
        <thead>
          <tr>
            <th scope="col">Lúc (UTC)</th>
            <th scope="col">Chọn</th>
            <th scope="col">Hệ thống nói</th>
            <th scope="col">M1</th>
            <th scope="col">Entry / SL / TP</th>
            <th scope="col">R:R</th>
            <th scope="col">Lý do</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} data-testid={`human-row-${r.id}`}>
              <td>{new Date(r.timestamp).toISOString().slice(0, 19).replace("T", " ")}</td>
              <td><strong>{CHOICE_VI[r.human_choice]}</strong></td>
              <td>{r.system_recommendation} · {r.system_bias}</td>
              <td>{r.m1_execution_state ?? "—"}{r.m1_quality ? ` (${r.m1_quality})` : ""}</td>
              <td>{r.entry?.toFixed(2) ?? "—"} / {r.sl?.toFixed(2) ?? "—"} / {r.tp?.toFixed(2) ?? "—"}</td>
              <td>{r.rr?.toFixed(2) ?? "—"}</td>
              <td>{r.human_reason || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Events({ events }: { events: JournalEvent[] }) {
  return (
    <ol className="journal-list" data-testid="journal-events" aria-label="Sổ nhật ký (chỉ thêm, không sửa)">
      {events.map((e) => (
        <li key={e.seq}>
          <span className="muted">{new Date(e.ts).toISOString().slice(0, 19).replace("T", " ")}Z</span> <strong>{e.kind}</strong>{" "}
          {e.kind === "OPENED"
            ? `${String(e.detail.side)} ${String(e.detail.lots)} lot @ ${Number(e.detail.fill).toFixed(2)} (${String(e.detail.source)})`
            : `${REASON_VI[String(e.detail.reason)] ?? String(e.detail.reason)} @ ${Number(e.detail.exit_price).toFixed(2)} · ròng ${usd(Number(e.detail.net_usd))} · ${e.detail.r == null ? "—" : `${Number(e.detail.r).toFixed(2)} R`}`}
        </li>
      ))}
    </ol>
  );
}

interface Props {
  summary: PaperSummary | null;
  positions: PaperPosition[];
  state: State | null;
  revision: number;
  humanRevision: number;
  onChanged: () => void;
}

export function PaperJournal({ summary, positions, state, revision, humanRevision, onChanged }: Props) {
  const [events, setEvents] = useState<JournalEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    const abort = new AbortController();
    fetchJournal(abort.signal)
      .then((j) => setEvents(j.events))
      .catch(() => undefined);
    return () => abort.abort();
  }, [revision]);

  const [humans, setHumans] = useState<HumanRecord[]>([]);
  useEffect(() => {
    const abort = new AbortController();
    fetchHumanDecisions(abort.signal)
      .then((j) => setHumans(j.decisions))
      .catch(() => undefined);
    return () => abort.abort();
  }, [humanRevision]);

  const act = useCallback(
    async (run: () => Promise<{ message: string }>) => {
      setBusy(true);
      try {
        const r = await run();
        setMessage({ ok: true, text: r.message });
      } catch (e) {
        setMessage({ ok: false, text: e instanceof Error ? e.message : String(e) });
      } finally {
        setBusy(false);
        onChanged();
      }
    },
    [onChanged],
  );

  const canOpen = state?.action === "BUY" || state?.action === "SELL";
  return (
    <div data-testid="paper-journal">
      {summary ? <Summary s={summary} /> : <p className="muted">Đang tải sổ PAPER…</p>}
      <p className="actions">
        <button type="button" disabled={busy || !canOpen} onClick={() => void act(openCurrentPlan)} data-testid="open-current">
          Mở lệnh PAPER theo kế hoạch hiện tại
        </button>
        <span className="muted small">
          {" "}
          {canOpen ? "Kế hoạch hợp lệ." : "Chưa có kế hoạch hợp lệ (BUY/SELL) nên không mở được."} Tự động mở:{" "}
          <strong data-testid="auto-paper">{summary?.auto_paper ? "BẬT" : "TẮT"}</strong>. Không gửi lệnh tới broker.
        </span>
      </p>
      {message && (
        <p role={message.ok ? "status" : "alert"} className={message.ok ? "muted" : "error-text"} data-testid="paper-message">
          {message.text}
        </p>
      )}
      {positions.length === 0 ? (
        <p>Chưa có lệnh PAPER nào. Khi bộ máy ra BUY/SELL hợp lệ, lệnh sẽ được ghi ở đây cùng R thực, MAE/MFE và chi phí.</p>
      ) : (
        <Table rows={positions} onClose={(id) => void act(() => closePosition(id))} busy={busy} />
      )}
      {humans.length > 0 && <HumanLog rows={humans} />}
      {events.length > 0 && <Events events={events} />}
      {summary && (
        <details className="chain">
          <summary>Giả định của số liệu PAPER</summary>
          <ul>
            {summary.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
