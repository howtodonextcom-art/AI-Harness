"use client";

import { BAD, WARN, fmt, money } from "@/components/trade/ui";
import { Modal } from "@/components/terminal/Modal";
import type { PaperTrade, TradePlan } from "@/lib/trade";

/** What the trader was shown when the confirmation opened: the confirm is bound to exactly this. */
export interface FrozenPlan {
  setup_id: string;
  side: "BUY" | "SELL";
  sl: number | null;
  tp1: number | null;
  risk: number;
  entry: number | null;
  lots: number | null;
  rr: number | null;
  riskAmount: number | null;
}

/** True while the live plan is still the very one the modal was opened for. */
export function planMatches(frozen: FrozenPlan, plan: TradePlan | null, risk: number, actionable: boolean): boolean {
  return Boolean(
    plan && actionable && !plan.expired && plan.setup_id === frozen.setup_id && plan.sl === frozen.sl && plan.tp1 === frozen.tp1 && risk === frozen.risk,
  );
}

export function OpenConfirmModal({ frozen, liveEntry, valid, busy, onConfirm, onCancel }: { frozen: FrozenPlan; liveEntry: number | null; valid: boolean; busy: boolean; onConfirm: () => void; onCancel: () => void }) {
  const buy = frozen.side === "BUY";
  return (
    <Modal title={`Xác nhận mở lệnh PAPER ${buy ? "MUA" : "BÁN"}`} testId="confirm-open-modal" tone={buy ? "buy" : "sell"} onClose={onCancel}>
      <p className="mb-2 text-sm">Đây là lệnh <b>giả lập</b>: không có lệnh nào được gửi tới MT5.</p>
      {!valid && (
        <p role="alert" data-testid="confirm-invalid" className={`mb-2 rounded border px-2 py-1 text-sm font-semibold ${BAD}`}>
          Kế hoạch đã thay đổi hoặc hết hạn. Hãy xem lại kế hoạch mới trước khi mở lệnh.
        </p>
      )}
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
        <dt className="text-slate-600 dark:text-slate-400">Hướng</dt><dd className="text-right font-bold">{buy ? "MUA (BUY)" : "BÁN (SELL)"}</dd>
        <dt className="text-slate-600 dark:text-slate-400">Entry (giá thị trường hiện tại)</dt><dd data-testid="confirm-entry" className="text-right font-mono">{fmt(liveEntry ?? frozen.entry)}</dd>
        <dt className="text-slate-600 dark:text-slate-400">SL</dt><dd data-testid="confirm-sl" className="text-right font-mono">{fmt(frozen.sl)}</dd>
        <dt className="text-slate-600 dark:text-slate-400">TP</dt><dd data-testid="confirm-tp" className="text-right font-mono">{fmt(frozen.tp1)}</dd>
        <dt className="text-slate-600 dark:text-slate-400">R/R</dt><dd className="text-right font-mono">{fmt(frozen.rr)}</dd>
        <dt className="text-slate-600 dark:text-slate-400">Rủi ro</dt><dd data-testid="confirm-risk" className="text-right font-mono">{fmt(frozen.risk, 2)}% · {money(frozen.riskAmount === null ? null : -frozen.riskAmount)}</dd>
        <dt className="text-slate-600 dark:text-slate-400">Lot</dt><dd data-testid="confirm-lots" className="text-right font-mono">{fmt(frozen.lots, 2)}</dd>
      </dl>
      <p className="mt-2 text-xs text-slate-600 dark:text-slate-400">Giá khớp thực có thể lệch nhẹ so với giá hiển thị; máy chủ kiểm tra lại mọi điều kiện trước khi mở.</p>
      <div className="mt-3 flex gap-2">
        <button type="button" data-testid="confirm-paper" data-autofocus disabled={busy || !valid} onClick={onConfirm} className={`flex-1 rounded-md border-2 px-3 py-2 font-black text-white disabled:opacity-40 ${buy ? "border-emerald-700 bg-emerald-700" : "border-red-700 bg-red-700"}`}>
          XÁC NHẬN MỞ LỆNH PAPER
        </button>
        <button type="button" data-testid="cancel-paper" onClick={onCancel} className="rounded-md border-2 border-slate-400 px-3 py-2 font-semibold">
          Hủy
        </button>
      </div>
    </Modal>
  );
}

export function CloseConfirmModal({ trade, busy, unsure, onConfirm, onCancel }: { trade: PaperTrade; busy: boolean; unsure: boolean; onConfirm: () => void; onCancel: () => void }) {
  const pnl = trade.unrealized_pnl ?? null;
  return (
    <Modal title="Xác nhận đóng lệnh PAPER" testId="confirm-close-modal" onClose={onCancel}>
      <p className="mb-2 text-sm">Đóng lệnh giả lập <b>{trade.side === "BUY" ? "MUA" : "BÁN"}</b> <span className="font-mono">{trade.trade_id}</span> tại giá thực thi mới nhất.</p>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
        <dt className="text-slate-600 dark:text-slate-400">Giá thực thi (ước tính)</dt><dd data-testid="close-price" className="text-right font-mono">{fmt(trade.current_price)}</dd>
        <dt className="text-slate-600 dark:text-slate-400">Lãi/lỗ ước tính</dt><dd data-testid="close-pnl" className={`text-right font-mono font-bold ${pnl !== null && pnl < 0 ? "text-red-700 dark:text-red-400" : "text-emerald-700 dark:text-emerald-400"}`}>{money(pnl)}</dd>
        <dt className="text-slate-600 dark:text-slate-400">R ước tính</dt><dd className="text-right font-mono">{fmt(trade.unrealized_r, 2)}</dd>
        <dt className="text-slate-600 dark:text-slate-400">Mã lệnh</dt><dd className="text-right font-mono">{trade.trade_id}</dd>
      </dl>
      {unsure && (
        <p role="alert" data-testid="close-unsure" className={`mt-2 rounded border px-2 py-1 text-sm font-semibold ${BAD}`}>
          Mất kết nối hoặc dữ liệu cũ: giá ước tính ở trên có thể không còn đúng.
        </p>
      )}
      <p className={`mt-2 rounded border px-2 py-1 text-xs ${WARN}`}>Giá và lãi/lỗ cuối cùng được máy chủ đọc lại ngay lúc đóng, có thể khác ước tính.</p>
      <div className="mt-3 flex gap-2">
        <button type="button" data-testid="confirm-close" data-autofocus disabled={busy} onClick={onConfirm} className="flex-1 rounded-md border-2 border-slate-700 bg-slate-800 px-3 py-2 font-black text-white disabled:opacity-40">
          XÁC NHẬN ĐÓNG
        </button>
        <button type="button" data-testid="cancel-close" onClick={onCancel} className="rounded-md border-2 border-slate-400 px-3 py-2 font-semibold">Giữ lệnh</button>
      </div>
    </Modal>
  );
}
