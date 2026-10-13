import type { Intelligence, M1Execution, State } from "../api/client";
import { GateChips } from "./IntelligencePanel";

/** Everything the SYSTEM says is advice. These are the words the page uses for it. */
export const RECOMMENDATION: Record<string, { icon: string; label: string; tone: string }> = {
  BUY_CANDIDATE: { icon: "▲", label: "ỨNG VIÊN MUA", tone: "buy" },
  SELL_CANDIDATE: { icon: "▼", label: "ỨNG VIÊN BÁN", tone: "sell" },
  WAIT: { icon: "⏸", label: "CHỜ", tone: "wait" },
  HOLD: { icon: "●", label: "GIỮ (PAPER)", tone: "hold" },
  EXIT_WATCH: { icon: "◐", label: "THEO DÕI THOÁT", tone: "exit" },
  UNAVAILABLE: { icon: "⚠", label: "KHÔNG KHẢ DỤNG", tone: "unavailable" },
};
const BIAS_VI = { BUY: "▲ MUA", SELL: "▼ BÁN", NEUTRAL: "— TRUNG TÍNH" } as const;
const SETUP_VI: Record<string, string> = { NONE: "CHƯA CÓ", WATCHING: "THEO DÕI", ARMED: "ARMED" };
const TRIGGER_VI: Record<string, string> = { NONE: "CHƯA CÓ", WAITING: "CHỜ XÁC NHẬN", CONFIRMED: "ĐÃ XÁC NHẬN" };
const M1_VI: Record<string, string> = {
  TOO_EARLY: "QUÁ SỚM",
  WATCH: "THEO DÕI",
  FORMING: "ĐANG HÌNH THÀNH",
  CONFIRMED: "ĐÃ XÁC NHẬN",
  EXECUTION_WINDOW: "CỬA SỔ THỰC THI",
  TOO_LATE: "QUÁ MUỘN",
  INVALIDATED: "VÔ HIỆU",
};
const QUALITY_VI: Record<string, string> = { GOOD: "TỐT", CAUTION: "THẬN TRỌNG", BAD: "XẤU" };

function Row({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
  return (
    <div className="row" data-testid={id}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function M1Line({ m1 }: { m1: M1Execution }) {
  if (!m1.applicable || !m1.state) {
    return (
      <span className="muted" data-testid="m1-state" data-state="N/A">
        chưa áp dụng · {m1.reason}
      </span>
    );
  }
  return (
    <span data-testid="m1-state" data-state={m1.state} data-quality={m1.quality ?? ""}>
      <strong>{M1_VI[m1.state]}</strong> <span className="muted small">({m1.state})</span> · chất lượng{" "}
      <strong data-testid="m1-quality">{m1.quality ? QUALITY_VI[m1.quality] : "—"}</strong>
    </span>
  );
}

const money = (v: number | null | undefined, d = 2) => (v == null ? "—" : v.toFixed(d));

/** The SYSTEM layer: measurements and an advisory recommendation. It decides nothing. */
export function SystemPanel({ state, intel = null }: { state: State | null; intel?: Intelligence | null }) {
  if (!state) {
    return (
      <section className="card system" aria-busy="true" aria-label="Hệ thống">
        <p className="muted">Đang tải…</p>
      </section>
    );
  }
  const sys = state.system;
  const rec = sys?.recommendation ?? (state.action === "UNAVAILABLE" ? "UNAVAILABLE" : "WAIT");
  const view = RECOMMENDATION[rec] ?? RECOMMENDATION.WAIT!;
  const candidate = rec === "BUY_CANDIDATE" || rec === "SELL_CANDIDATE";
  const plan = state.plan;
  return (
    <section className="card system" aria-label="Hệ thống: khuyến nghị tham khảo" data-testid="system-panel">
      <header className="card-head">
        <h2>Hệ thống</h2>
        <span className="muted small">khuyến nghị tham khảo, không phải lệnh</span>
      </header>
      <div className={`action tone-${view.tone}`} role="status" aria-label={`Hệ thống: ${view.label}`} data-testid="recommendation" data-code={rec}>
        <span className="action-icon" aria-hidden="true">{view.icon}</span>
        <span className="action-label">{view.label}</span>
      </div>
      {(candidate || !intel) && (
        <p className="headline" data-testid="headline">
          {sys?.reasons[0] ?? state.headline}
        </p>
      )}
      <dl className="rows">
        <Row id="blocker" label="Thị trường chặn">
          {!candidate && intel?.authorization.chain_blocker ? (
            <span data-testid="why-market" data-chain={intel.authorization.chain_verdict}>
              {intel.authorization.chain_blocker.text}
              {intel.authorization.next_condition && (
                <span className="muted small"> · cần: {intel.authorization.next_condition}</span>
              )}
            </span>
          ) : (
            (sys?.blocker_text ?? state.blocker ?? (candidate ? "— không có" : "—"))
          )}
        </Row>
        <Row id="secondary" label="Cổng / tài khoản">
          {intel && !candidate ? (
            <span data-testid="why-gates">
              <GateChips gates={intel.authorization.gates} none="cổng: không chặn" />{" "}
              <GateChips gates={intel.authorization.system_hold} none="tài khoản: không giữ" prefix="TK: " />
            </span>
          ) : sys && sys.secondary_text.length > 0 ? (
            sys.secondary_text.join(" · ")
          ) : (
            "—"
          )}
        </Row>
        <Row id="sys-bias" label="Thiên hướng">
          <strong>{BIAS_VI[sys?.bias ?? state.bias]}</strong> <span className="muted small">(H4/H1)</span>
        </Row>
        <Row id="sys-setup" label="Setup (M15)">
          {SETUP_VI[sys?.setup_state ?? "NONE"]}
        </Row>
        <Row id="sys-trigger" label="M5 trigger">
          {TRIGGER_VI[sys?.trigger_state ?? "NONE"]}
        </Row>
        <Row id="sys-m1" label="M1 thực thi">
          {sys ? <M1Line m1={sys.m1} /> : <span className="muted">—</span>}
        </Row>
        <Row id="plan" label="Entry / SL / TP">
          {plan && candidate ? (
            <span>
              {plan.side} {plan.entry.toFixed(2)} / SL {plan.stop_loss.toFixed(2)} / TP {plan.take_profit_1.toFixed(2)}
              {plan.take_profit_2 != null && <> / TP2 {plan.take_profit_2.toFixed(2)}</>}
            </span>
          ) : (
            <span className="muted">— chưa có kế hoạch để cân nhắc</span>
          )}
        </Row>
        <Row id="rr" label="R:R ròng">
          {plan && candidate ? plan.net_rr.toFixed(2) : <span className="muted">—</span>}
        </Row>
        <Row id="risk" label="Rủi ro / lot">
          {state.risk && candidate ? (
            <span>
              {state.risk.risk_pct}% · {state.risk.lots ?? "—"} lot · ${money(state.risk.risk_amount)}
            </span>
          ) : (
            <span className="muted">—</span>
          )}
        </Row>
        <Row id="cost" label="Chi phí">
          {state.risk && candidate ? (
            <span>
              {state.risk.cost_usd == null ? "chưa tính được" : `$${state.risk.cost_usd.toFixed(2)}/vòng`} ·{" "}
              {state.risk.cost_status === "ASSUMED" ? "GIẢ ĐỊNH" : state.risk.cost_status}
            </span>
          ) : (
            <span className="muted">— chưa tính (chi phí không xác minh thì không coi là 0)</span>
          )}
        </Row>
        <Row id="expiry" label="Hạn / vô hiệu">
          {candidate && state.expires_at ? (
            <span>
              tới {new Date(state.expires_at).toISOString().slice(11, 16)} UTC · vô hiệu khi H1 đảo chiều hoặc giá đóng ngoài SL
            </span>
          ) : (
            <span className="muted">—</span>
          )}
        </Row>
        <Row id="sys-evidence" label="Bằng chứng">
          <strong>{state.evidence}</strong> <span className="muted small">· chiến lược v{state.strategy_version ?? "—"}, chưa kiểm chứng</span>
        </Row>
        <Row id="strategy-says" label="Chiến lược nói">
          <span data-testid="strategy-action">{sys?.strategy_action ?? state.action}</span>{" "}
          <span className="muted small">(đầu ra tất định gốc, không bị lớp M1 hay con người ghi đè)</span>
        </Row>
      </dl>
      {state.warnings.length > 0 && (
        <ul className="warnings" data-testid="warnings" aria-label="Cảnh báo">
          {state.warnings.map((w) => (
            <li key={w}>⚠ {w}</li>
          ))}
        </ul>
      )}
      <details className="chain" data-testid="chain">
        <summary>Vì sao ({(sys?.reasons.length ?? 0) + state.chain.length} dòng)</summary>
        <ol>
          {(sys?.reasons ?? []).map((r) => (
            <li key={`s-${r}`}>{r}</li>
          ))}
          {state.chain.map((c) => (
            <li key={`c-${c}`} className="muted">
              {c}
            </li>
          ))}
        </ol>
      </details>
      <p className="codes" data-testid="reason-codes">
        Mã: {state.reason_codes.join(", ")}
      </p>
    </section>
  );
}
