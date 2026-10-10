/**
 * The ONE thing the trader may do now, in words. Everything here is built from server fields
 * (hero.action, the plan, the position, the last exit, the setup phase); the browser decides nothing
 * about strategy. Two separate questions are answered separately:
 *   BIAS   - which way does the market lean? (a description, never permission)
 *   ACTION - what am I allowed to do now?    (CHỜ / MUA PAPER / BÁN PAPER / GIỮ VỊ THẾ / ĐÃ THOÁT / KHÔNG KHẢ DỤNG)
 * `whenLabel` + `whenBody` answer "when exactly would I buy / sell / exit?" without any documentation.
 */

import type { TradeView } from "@/lib/trade";
import { BLOCKER_VI, EXIT_REASON_VI, invalidationText, waitingText } from "@/lib/vi";

export type ActionTone = "buy" | "sell" | "hold" | "exit" | "wait" | "error";

export interface BiasText {
  side: "BUY" | "SELL" | null;
  /** MUA / BÁN / TRUNG TÍNH */
  word: string;
  note: string;
}

export interface ActionText {
  code: "WAIT" | "BUY" | "SELL" | "HOLD" | "EXIT" | "UNAVAILABLE";
  tone: ActionTone;
  /** the dominant instruction */
  word: string;
  /** one line: why / what is going on */
  sub: string;
  /** "MUA khi:" / "BÁN khi:" / "Khi nào?" */
  whenLabel: string;
  whenBody: string;
  /** a shorter form for a phone (same facts, fewer clauses); the full whenBody is shown from sm up */
  whenShort: string;
  /** whenLabel + whenBody as one sentence */
  when: string;
  bias: BiasText;
  /** Chưa có / Đang hình thành (nến 2/6) / Đã kích hoạt */
  setup: string;
  /** the bias and setup rows only mean something while the engine is evaluating (not closed, expired, blocked, ...) */
  showBias: boolean;
}

const money = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v >= 0 ? "+" : "-"}$${Math.abs(v).toFixed(2)}`);
const px = (v: number | null | undefined) => (v === null || v === undefined ? "—" : v.toFixed(2));
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s) % 60).padStart(2, "0")}`;

export const sideWord = (side: string | null | undefined) => (side === "BUY" ? "MUA" : side === "SELL" ? "BÁN" : "");

/** Time of day (HH:MM) of an ISO instant in UTC; callers pass a formatter for the trader's display zone. */
export function utcClock(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  return Number.isFinite(t) ? new Date(t).toISOString().slice(11, 16) : null;
}

export function actionText(view: TradeView, secondsLeft: number | null, expiredNow: boolean, clock: (iso: string | null | undefined) => string | null = utcClock): ActionText {
  const a = view.hero.action;
  const plan = view.trade_plan ?? null;
  const side = a.side;
  const SIDE = sideWord(side);
  const bias: BiasText = a.bias
    ? { side: a.bias, word: sideWord(a.bias), note: "thiên hướng theo xu hướng H1, chưa phải tín hiệu vào lệnh" }
    : { side: null, word: "TRUNG TÍNH", note: "chưa có hướng ưu tiên rõ ràng" };
  const phase = view.setup?.phase ?? null;
  const n = view.setup?.bars_since_armed ?? null;
  const validBars = view.setup?.valid_bars ?? null;
  const setup =
    a.code === "BUY" || a.code === "SELL" || a.code === "HOLD" || a.code === "EXIT"
      ? "Đã kích hoạt"
      : phase === "ARMED"
        ? `Đã hình thành, chờ trigger M5${n !== null && validBars !== null ? ` (còn ${Math.max(0, validBars - n)} nến M5)` : ""}`
        : "Chưa có";
  const make = (code: ActionText["code"], tone: ActionTone, word: string, sub: string, whenLabel: string, whenBody: string, whenShort?: string): ActionText => ({
    code,
    tone,
    word,
    sub,
    whenLabel,
    whenBody,
    whenShort: whenShort ?? whenBody,
    when: `${whenLabel} ${whenBody}`.trim(),
    bias,
    setup,
    showBias: a.code === "WAIT" && ["WAITING", "WATCHING", "ARMED"].includes(a.stage),
  });

  if (a.code === "UNAVAILABLE") {
    const err = view.conditions.find((c) => c.severity === "ERROR" && c.code !== "MARKET_CLOSED");
    if (a.stage === "API_DOWN") {
      return make("UNAVAILABLE", "error", "KHÔNG KHẢ DỤNG", "Mất kết nối API: những gì thấy trên màn hình có thể đã cũ.", "Khi nào?", "Đừng vào lệnh lúc này. Đây không phải trạng thái chờ bình thường: đợi kết nối trở lại.");
    }
    return make("UNAVAILABLE", "error", "KHÔNG KHẢ DỤNG", err ? "Hệ thống chưa cho quyết định đáng tin (lý do bên dưới)." : "Hệ thống chưa cho quyết định đáng tin.", "Khi nào?", "Đừng vào lệnh lúc này. Đây không phải trạng thái chờ bình thường: hãy kiểm tra hệ thống.");
  }

  if (a.code === "HOLD") {
    const pos = view.desk?.position ?? null;
    const thesis = a.thesis === "INTACT" ? "luận điểm còn vững (H1 vẫn cùng hướng)" : a.thesis === "WEAK" ? "luận điểm đang YẾU (H1 đã đổi hướng)" : "chưa đánh giá được luận điểm";
    const latest = clock(pos?.max_hold_until);
    const sub = pos ? `${SIDE} từ ${px(pos.fill_price)} · ${money(pos.unrealized_pnl)} (${px(pos.unrealized_r)}R)` : `Đang có lệnh ${SIDE.toLowerCase()}`;
    const body = pos
      ? `Bàn tự thoát khi chạm SL ${px(pos.sl)} (-1R) hoặc TP ${px(pos.tp)}${latest ? `, hoặc muộn nhất lúc ${latest} (hết thời gian giữ)` : ", hoặc khi hết thời gian giữ"}. Hiện ${thesis}.`
      : "Bàn tự thoát khi chạm SL, TP hoặc hết thời gian giữ.";
    const short = pos ? `Tự thoát khi chạm SL ${px(pos.sl)} hoặc TP ${px(pos.tp)}${latest ? `, muộn nhất lúc ${latest}` : ""}. ${a.thesis === "INTACT" ? "Luận điểm còn vững." : a.thesis === "WEAK" ? "Luận điểm đang YẾU." : ""}`.trim() : body;
    return make("HOLD", "hold", "GIỮ VỊ THẾ", sub, "Chưa chạm điều kiện thoát nào.", body, short);
  }

  if (a.code === "EXIT") {
    const x = view.desk?.last_exit ?? null;
    const reason = x ? (EXIT_REASON_VI[x.exit_reason ?? ""] ?? x.exit_reason ?? "") : "";
    return make(
      "EXIT",
      "exit",
      "ĐÃ THOÁT",
      x ? `${reason} · ${money(x.net_pnl)} · ${px(x.r_multiple)}R${x.duration_minutes != null ? ` · ${Math.round(x.duration_minutes)} phút` : ""}` : "Lệnh paper vừa đóng",
      "Đã thoát vì",
      `${reason ? reason.charAt(0).toLowerCase() + reason.slice(1) : "lệnh đã đóng"}. Không cần làm gì thêm: xem lại ở tab Hoạt động hoặc Journal; bộ máy tiếp tục chờ setup kế tiếp.`,
    );
  }

  if (a.code === "BUY" || a.code === "SELL") {
    const sub = secondsLeft !== null ? `Sẵn sàng · còn hiệu lực ${mmss(secondsLeft)}` : "Sẵn sàng";
    const body = `${SIDE === "MUA" ? "Mua" : "Bán"} ngay ở khoảng ${px(plan?.planned_entry)} nếu bạn theo kế hoạch (SL ${px(plan?.sl)}, TP ${px(plan?.tp1)}). Hết hạn thì bỏ qua${plan?.invalidation ? `; kế hoạch vô hiệu khi ${invalidationText(plan.invalidation)}` : ""}.`;
    const short = `${SIDE === "MUA" ? "Mua" : "Bán"} ngay ở khoảng ${px(plan?.planned_entry)} (SL ${px(plan?.sl)}, TP ${px(plan?.tp1)}). Hết hạn thì bỏ qua.`;
    return make(a.code, side === "BUY" ? "buy" : "sell", `${SIDE} PAPER`, sub, `Tín hiệu ${SIDE} đã xác nhận.`, body, short);
  }

  // ---- WAIT: the engine must not trade; the bias says where the market leans, `missing` what is still absent
  const bull = view.structure?.h1_trend === "BULLISH" ? true : view.structure?.h1_trend === "BEARISH" ? false : null;
  const next = waitingText(view.why_wait?.waiting_for_code ?? null, bull, { phase, age: n });
  const dir = bias.side === "BUY" ? "tăng" : "giảm";
  const verb = sideWord(bias.side);

  if (a.stage === "BLOCKED" && a.blocked_by) {
    const why = BLOCKER_VI[a.blocked_by.code] ?? a.blocked_by.message;
    return make("WAIT", "wait", "CHỜ", `${SIDE ? `Có setup ${SIDE.toLowerCase()} nhưng ` : ""}không mở được: ${why}`, "Khi nào?", "Đừng mở lệnh cho setup này. Bàn sẽ tự cập nhật khi lý do chặn hết hoặc có setup mới.");
  }
  if (a.stage === "CLOSED") return make("WAIT", "wait", "CHỜ", "Thị trường đóng cửa", "Khi nào?", "Chưa làm gì. Bộ máy tự tính lại khi thị trường mở cửa.");
  if (a.stage === "EXPIRED" || expiredNow) return make("WAIT", "wait", "CHỜ", "Setup đã hết hiệu lực, không còn mở được", "Khi nào?", "Chưa làm gì. Chờ setup mới.");
  if (a.stage === "INVALIDATED") return make("WAIT", "wait", "CHỜ", "Setup vừa bị vô hiệu", "Khi nào?", "Chưa làm gì: không có lệnh nào để thoát. Xem \"Điều kiện vào lệnh\" bên dưới để biết điều kiện nào đang không đạt; bộ máy chờ setup mới.");
  if (a.stage === "INCOMPLETE") return make("WAIT", "wait", "CHỜ", "Có setup nhưng kế hoạch chưa đầy đủ, chưa được vào lệnh", "Khi nào?", "Chưa làm gì. Chờ kế hoạch đầy đủ hoặc setup mới.");

  if (bias.side && a.missing === "TRIGGER") {
    const left = n === null || validBars === null ? null : Math.max(0, validBars - n);
    return make("WAIT", "wait", "CHỜ", `Setup đã hình thành, chưa có trigger — chưa được vào lệnh`, `Chỉ ${verb} khi:`, `nến M5 kế tiếp đóng xác nhận trigger ${dir}${left === null ? "" : ` (còn ${left} nến M5 trước khi setup hết hạn)`}; lúc đó hành động chuyển thành ${verb} PAPER.`);
  }
  if (bias.side) {
    return make("WAIT", "wait", "CHỜ", "Chưa có tín hiệu vào lệnh", `Chỉ ${verb} khi:`, `M15 có nhịp pullback tạo setup, rồi nến M5 đóng xác nhận trigger ${dir}; lúc đó hành động chuyển thành ${verb} PAPER.`);
  }
  return make("WAIT", "wait", "CHỜ", next ? `Chưa có hướng ưu tiên · đang chờ: ${next}` : "Chưa có hướng ưu tiên", "Khi nào?", "Chưa làm gì. Chờ là trạng thái bình thường: bộ máy rất ít khi có kế hoạch.");
}
