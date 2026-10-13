import { useState } from "react";
import { type HumanChoice, type State, postHuman } from "../api/client";

const CHOICE_VI: Record<string, string> = { ACCEPT: "CHẤP NHẬN", WAIT: "CHỜ", REJECT: "BỎ QUA" };

interface Props {
  state: State | null;
  onChanged: () => void;
}

/** The HUMAN layer: the person is the final authority. Choosing records the choice; it sends no order. */
export function HumanPanel({ state, onChanged }: Props) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const rec = state?.system?.recommendation;
  const candidate = (rec === "BUY_CANDIDATE" || rec === "SELL_CANDIDATE") && !!state?.setup_id;
  const last = state?.human ?? null;

  const choose = async (choice: HumanChoice) => {
    if (!state?.setup_id) return;
    setBusy(true);
    try {
      const r = await postHuman(choice, state.setup_id, reason);
      setMessage({ ok: true, text: r.message });
      setReason("");
    } catch (e) {
      setMessage({ ok: false, text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
      onChanged();
    }
  };

  const why = !state
    ? "đang tải"
    : candidate
      ? ""
      : rec === "HOLD" || rec === "EXIT_WATCH"
        ? "đang có lệnh PAPER, không có ứng viên mới"
        : "chưa có ứng viên để quyết định";
  return (
    <section className="card human" aria-label="Quyết định của bạn" data-testid="human-panel">
      <header className="card-head">
        <h2>Quyết định của bạn</h2>
        <span className="muted small">người quyết định cuối cùng</span>
      </header>
      <div className="human-actions" role="group" aria-label="Chọn quyết định">
        <button type="button" className="h-accept" disabled={!candidate || busy} onClick={() => void choose("ACCEPT")} data-testid="human-accept">
          CHẤP NHẬN
        </button>
        <button type="button" className="h-wait" disabled={!candidate || busy} onClick={() => void choose("WAIT")} data-testid="human-wait">
          CHỜ
        </button>
        <button type="button" className="h-reject" disabled={!candidate || busy} onClick={() => void choose("REJECT")} data-testid="human-reject">
          BỎ QUA
        </button>
      </div>
      <label className="human-reason">
        <span className="sr-only">Lý do (tùy chọn)</span>
        <input
          type="text"
          maxLength={500}
          value={reason}
          disabled={!candidate || busy}
          onChange={(e) => setReason(e.target.value)}
          data-testid="human-reason"
          placeholder="Lý do (tùy chọn)"
        />
      </label>
      {!candidate && (
        <p className="muted small" data-testid="human-disabled-why">
          {why}
        </p>
      )}
      {last && (
        <p className="small" data-testid="human-last" data-choice={last.human_choice}>
          Lựa chọn gần nhất của bạn cho ứng viên này: <strong>{CHOICE_VI[last.human_choice]}</strong> lúc{" "}
          {new Date(last.timestamp).toISOString().slice(11, 19)} UTC{last.human_reason ? ` · “${last.human_reason}”` : ""}
        </p>
      )}
      {message && (
        <p role={message.ok ? "status" : "alert"} className={message.ok ? "small" : "small error-text"} data-testid="human-message">
          {message.text}
        </p>
      )}
      <p className="muted small" data-testid="human-note">
        CHẤP NHẬN chỉ ghi nhật ký. Không gửi lệnh tới broker; bạn tự thực hiện thủ công.
      </p>
    </section>
  );
}
