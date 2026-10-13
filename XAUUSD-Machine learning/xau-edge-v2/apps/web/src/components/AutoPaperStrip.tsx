import type { PaperPosition, PaperSummary } from "../api/client";

/** AUTO PAPER is a separate research mechanism: it follows the strategy, not the human. */
export function AutoPaperStrip({ paper, positions }: { paper: PaperSummary | null; positions: PaperPosition[] }) {
  const open = positions.find((p) => p.status === "OPEN");
  return (
    <section className="card auto-paper" aria-label="AUTO PAPER: chỉ để nghiên cứu" data-testid="auto-paper-strip">
      <header className="card-head">
        <h2>AUTO PAPER: CHỈ ĐỂ NGHIÊN CỨU</h2>
        <span className="chip chip-neutral" data-testid="auto-paper-state">
          {paper ? (paper.auto_paper ? "BẬT" : "TẮT") : "—"}
        </span>
      </header>
      <p className="small">
        {open ? (
          <span data-testid="auto-paper-position">
            Đang giữ lệnh PAPER {open.side === "BUY" ? "▲ MUA" : "▼ BÁN"} {open.lots} lot ({open.source === "AUTO" ? "tự động" : "thủ công"}) · PnL nổi{" "}
            {open.floating_pnl_usd == null ? "—" : `${open.floating_pnl_usd >= 0 ? "+" : "-"}$${Math.abs(open.floating_pnl_usd).toFixed(2)}`}
          </span>
        ) : (
          <span className="muted">Không có lệnh PAPER nào đang mở.</span>
        )}
      </p>
      <p className="muted small">Độc lập với quyết định của bạn; theo tín hiệu gốc để thu bằng chứng forward.</p>
    </section>
  );
}
