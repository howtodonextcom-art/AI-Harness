/**
 * The ONE thing to do now, in words. Everything here is built from server fields (hero.action, the
 * plan, the position, the last exit, the setup phase); the browser decides nothing about strategy.
 * `when` answers "when exactly would I buy / sell / exit?" without any documentation.
 */

import type { TradeView } from "@/lib/trade";
import { BLOCKER_VI, EXIT_REASON_VI, humanCondition, invalidationText, trendText, waitingText } from "@/lib/vi";

export type ActionTone = "buy" | "sell" | "watch-buy" | "watch-sell" | "hold" | "exit" | "wait" | "error";

export interface ActionText {
  code: string;
  tone: ActionTone;
  word: string;
  sub: string;
  when: string;
}

const money = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v >= 0 ? "+" : "-"}$${Math.abs(v).toFixed(2)}`);
const px = (v: number | null | undefined) => (v === null || v === undefined ? "—" : v.toFixed(2));
const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s) % 60).padStart(2, "0")}`;

export function actionText(view: TradeView, secondsLeft: number | null, expiredNow: boolean): ActionText {
  const a = view.hero.action;
  const plan = view.trade_plan ?? null;
  const side = a.side;
  const sideVi = side === "BUY" ? "mua" : side === "SELL" ? "bán" : "";
  const SIDE = side === "BUY" ? "MUA" : side === "SELL" ? "BÁN" : "";

  if (a.code === "UNAVAILABLE") {
    const err = view.conditions.find((c) => c.severity === "ERROR" && c.code !== "MARKET_CLOSED");
    if (a.stage === "API_DOWN") return { code: a.code, tone: "error", word: "KHÔNG KHẢ DỤNG", sub: "Mất kết nối API: những gì thấy trên màn hình có thể đã cũ.", when: "Đừng vào lệnh lúc này. Đây không phải trạng thái chờ bình thường: đợi kết nối trở lại." };
    return { code: a.code, tone: "error", word: "KHÔNG KHẢ DỤNG", sub: err ? humanCondition(err.code, err.message) : "Hệ thống chưa cho quyết định đáng tin.", when: "Đừng vào lệnh lúc này. Đây không phải trạng thái chờ bình thường: hãy kiểm tra hệ thống." };
  }
  if (a.code === "HOLD") {
    const pos = view.desk?.position ?? null;
    const thesis = a.thesis === "INTACT" ? "luận điểm còn vững (H1 vẫn cùng hướng)" : a.thesis === "WEAK" ? "luận điểm đang YẾU (H1 đã đổi hướng)" : "chưa đánh giá được luận điểm";
    return {
      code: a.code,
      tone: "hold",
      word: "GIỮ LỆNH",
      sub: pos ? `${SIDE} từ ${px(pos.fill_price)} · ${money(pos.unrealized_pnl)} (${px(pos.unrealized_r)}R)` : `Đang có lệnh ${sideVi}`,
      when: pos ? `Chưa cần làm gì. Bàn tự thoát khi chạm SL ${px(pos.sl)} (-1R) hoặc TP ${px(pos.tp)}, hoặc khi hết thời gian giữ. Hiện ${thesis}.` : "Chưa cần làm gì: bàn tự thoát khi chạm SL, TP hoặc hết thời gian giữ.",
    };
  }
  if (a.code === "EXIT") {
    const x = view.desk?.last_exit ?? null;
    return {
      code: a.code,
      tone: "exit",
      word: "ĐÃ THOÁT",
      sub: x ? `${EXIT_REASON_VI[x.exit_reason ?? ""] ?? x.exit_reason} · ${money(x.net_pnl)} · ${px(x.r_multiple)}R` : "Lệnh paper vừa đóng",
      when: "Lệnh đã đóng, không cần làm gì thêm. Xem lại ở tab Hoạt động hoặc Journal; bộ máy tiếp tục chờ setup kế tiếp.",
    };
  }
  if (a.code === "BUY" || a.code === "SELL") {
    return {
      code: a.code,
      tone: side === "BUY" ? "buy" : "sell",
      word: SIDE,
      sub: secondsLeft !== null ? `Sẵn sàng · còn hiệu lực ${mmss(secondsLeft)}` : "Sẵn sàng",
      when: `${side === "BUY" ? "Mua" : "Bán"} ngay ở khoảng ${px(plan?.planned_entry)} nếu bạn theo kế hoạch (SL ${px(plan?.sl)}, TP ${px(plan?.tp1)}). Hết hạn thì bỏ qua${plan?.invalidation ? `; kế hoạch vô hiệu khi ${invalidationText(plan.invalidation)}` : ""}.`,
    };
  }
  if (a.code === "WATCH_BUY" || a.code === "WATCH_SELL") {
    const tone: ActionTone = side === "BUY" ? "watch-buy" : "watch-sell";
    if (a.stage === "ARMED") {
      const n = view.setup?.bars_since_armed ?? null;
      const left = n === null ? null : Math.max(0, view.setup!.valid_bars - n);
      return {
        code: a.code,
        tone,
        word: `THEO DÕI ${SIDE}`,
        sub: `Setup đã hình thành${n === null ? "" : ` (nến ${n}/${view.setup!.valid_bars})`} · chờ nến M5 kích hoạt`,
        when: `Chưa ${sideVi}. ${side === "BUY" ? "Mua" : "Bán"} khi nến M5 kế tiếp đóng kích hoạt ${side === "BUY" ? "tăng" : "giảm"}${left === null ? "" : ` (còn ${left} nến M5 trước khi setup hết hạn)`}; lúc đó trạng thái chuyển thành SẴN SÀNG ${SIDE}.`,
      };
    }
    return {
      code: a.code,
      tone,
      word: `THEO DÕI ${SIDE}`,
      sub: `${trendText(side === "BUY" ? "BULLISH" : "BEARISH")} · chờ nhịp pullback M15`,
      when: `Chưa ${sideVi}. ${side === "BUY" ? "Mua" : "Bán"} khi: (1) M15 có nhịp pullback tạo setup, (2) nến M5 đóng kích hoạt ${side === "BUY" ? "tăng" : "giảm"}, (3) kế hoạch hợp lệ. Khi đủ, trạng thái chuyển thành SẴN SÀNG ${SIDE}.`,
    };
  }
  // WAIT
  const bull = view.structure?.h1_trend === "BULLISH" ? true : view.structure?.h1_trend === "BEARISH" ? false : null;
  const next = waitingText(view.why_wait?.waiting_for_code ?? null, bull, { phase: view.setup?.phase ?? null, age: view.setup?.bars_since_armed ?? null });
  let sub = next ? `Đang chờ: ${next}` : "Chưa có kế hoạch";
  if (a.stage === "BLOCKED" && a.blocked_by) sub = `${SIDE ? `Có setup ${sideVi} nhưng ` : ""}không mở được: ${BLOCKER_VI[a.blocked_by.code] ?? a.blocked_by.message}`;
  else if (a.stage === "CLOSED") sub = "Thị trường đóng cửa";
  else if (a.stage === "EXPIRED" || expiredNow) sub = "Kế hoạch trước đã hết hạn, không còn mở được";
  else if (a.stage === "INVALIDATED") sub = "Setup vừa bị vô hiệu: bộ máy chờ setup mới";
  else if (a.stage === "INCOMPLETE") sub = "Có setup nhưng kế hoạch chưa đầy đủ";
  return { code: "WAIT", tone: "wait", word: "CHỜ", sub, when: a.stage === "BLOCKED" ? "Đừng mở lệnh cho setup này. Bàn sẽ tự cập nhật khi lý do chặn hết hoặc có setup mới." : a.stage === "CLOSED" ? "Chưa làm gì. Bộ máy tự tính lại khi thị trường mở cửa." : "Chưa làm gì. Chờ là trạng thái bình thường: bộ máy rất ít khi có kế hoạch." };
}
