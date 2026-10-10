/**
 * User-facing language for the trading terminal. Rule: a human sentence first, the technical code
 * second (`humanCondition`). Trader-standard words stay as they are: BUY, SELL, SL, TP, RR, PAPER.
 */

import type { HeroState } from "@/lib/trade";

export const HERO_VI: Record<HeroState, { label: string; hint: string }> = {
  WAIT: { label: "CHỜ", hint: "Chưa có kế hoạch giao dịch. Chờ là trạng thái bình thường." },
  SETUP_ARMED: { label: "SETUP ĐANG HÌNH THÀNH", hint: "Có setup đang tạo ra, chưa kích hoạt." },
  BUY_READY: { label: "SẴN SÀNG MUA", hint: "Kế hoạch BUY đầy đủ và còn hiệu lực." },
  SELL_READY: { label: "SẴN SÀNG BÁN", hint: "Kế hoạch SELL đầy đủ và còn hiệu lực." },
  POSITION_OPEN: { label: "ĐANG CÓ VỊ THẾ PAPER", hint: "Lệnh paper đang chạy." },
  EXITED: { label: "VỪA THOÁT LỆNH", hint: "Lệnh paper gần nhất đã đóng." },
  EXPIRED_SETUP: { label: "HẾT HẠN", hint: "Kế hoạch đã hết hiệu lực, không còn mở được." },
  NOT_ACTIONABLE: { label: "CHƯA ĐỦ KẾ HOẠCH", hint: "Phát hiện setup nhưng kế hoạch chưa đầy đủ." },
  STALE: { label: "DỮ LIỆU CŨ", hint: "Không tin được dữ liệu. Đây KHÔNG phải trạng thái chờ." },
  UNAVAILABLE: { label: "KHÔNG THỂ TÍNH", hint: "Hệ thống không tính được quyết định. Đây KHÔNG phải trạng thái chờ." },
  MARKET_CLOSED: { label: "THỊ TRƯỜNG ĐÓNG CỬA", hint: "Không có quyết định khi thị trường nghỉ." },
};

export const HERO_ICON: Record<HeroState, string> = {
  WAIT: "⏸",
  SETUP_ARMED: "◔",
  BUY_READY: "▲",
  SELL_READY: "▼",
  POSITION_OPEN: "●",
  EXITED: "✓",
  EXPIRED_SETUP: "⏱",
  NOT_ACTIONABLE: "⚠",
  STALE: "⌛",
  UNAVAILABLE: "⚠",
  MARKET_CLOSED: "☾",
};

/** Human message for an infrastructure/safety condition code (the code itself is shown after it). */
export const CONDITION_VI: Record<string, string> = {
  DATA_STALE: "Dữ liệu giá đã quá cũ. Không thể mở lệnh PAPER.",
  QUOTE_STALE: "Báo giá đã quá cũ. Không thể mở lệnh PAPER.",
  COLLECTOR_STALE: "Bộ thu dữ liệu không còn cập nhật.",
  MT5_DISCONNECTED: "MT5 đang mất kết nối. Dữ liệu có thể đã dừng.",
  SPEC_MISSING: "Thiếu thông số hợp đồng của broker nên không tính được lot.",
  ENGINE_ERROR: "Bộ máy quyết định gặp lỗi và chưa có quyết định mới.",
  NO_DECISION: "Bộ máy quyết định chưa tạo quyết định nào.",
  WRITER_LOCK: "Một tiến trình khác đang giữ quyền ghi bàn PAPER. Tiến trình này chỉ đọc.",
  PAPER_STATE_ERROR: "Trạng thái bàn PAPER không khớp nhật ký. Mọi lệnh mới bị chặn cho tới khi khôi phục.",
  MARKET_CLOSED: "Thị trường đang đóng cửa.",
  NEWS_UNKNOWN: "Chưa có lịch tin kinh tế: hãy tự kiểm tra tin trước khi tin vào một setup.",
  SPREAD_WIDE: "Spread đang rộng.",
};

export function humanCondition(code: string, fallback: string): string {
  return CONDITION_VI[code] ?? fallback;
}

export const BLOCKER_VI: Record<string, string> = {
  PAPER_STATE_ERROR: "Trạng thái PAPER lỗi: không thể mở lệnh.",
  WRITER_LOCK: "Tiến trình này chỉ đọc: không thể mở lệnh.",
  CLOSURE_NEAR: "Gần giờ thị trường đóng cửa: không mở lệnh mới.",
  EXPIRED: "Kế hoạch đã hết hạn.",
  COOLDOWN: "Đang nghỉ sau lệnh trước.",
  OPEN_POSITION: "Đang có lệnh paper mở.",
};

export const STAGE_VI: Record<string, string> = {
  "Market & data": "Thị trường & dữ liệu",
  "Spread & regime": "Spread & chế độ H4",
  "H1 direction": "Hướng H1",
  "H4 / M15 alignment": "H4 / M15 đồng thuận",
  "M15 setup": "Setup M15",
  "M5 trigger": "Kích hoạt M5",
  "M1 execution": "Thực thi M1",
  "Trade plan": "Kế hoạch lệnh",
};

export const REFUSAL_VI: Record<string, string> = {
  NO_DIRECTION: "H1 chưa có hướng rõ",
  TIMEFRAME_CONFLICT: "Các khung thời gian chưa đồng thuận",
  NO_SETUP: "Chưa có pullback (setup) ở M15",
  NO_TRIGGER: "M5 chưa kích hoạt",
  VOLATILITY: "Biến động không phù hợp",
  VOLUME: "Tick volume thấp",
  SPREAD: "Spread quá rộng",
  RR: "R/R không đạt hoặc sát kháng cự/hỗ trợ",
  MARKET_CLOSED: "Thị trường đóng cửa",
};

export const TF_ROLE_VI: Record<string, string> = {
  H4: "chế độ",
  H1: "hướng",
  M30: "bối cảnh",
  M15: "setup",
  M5: "kích hoạt",
  M1: "thực thi",
};

export const EXIT_REASON_VI: Record<string, string> = {
  STOP_LOSS: "Chạm SL",
  TAKE_PROFIT: "Chạm TP",
  TIME_EXIT: "Hết thời gian giữ",
  MANUAL_CLOSE: "Đóng tay",
  CLOSURE_CLOSE: "Đóng trước giờ thị trường nghỉ",
  INVALIDATED: "Setup bị vô hiệu",
};

export const SIDE_VI: Record<string, string> = { BUY: "MUA", SELL: "BÁN" };

/** Wait-state context sentences are built from structured server fields only. */
export function trendText(label: string | undefined): string {
  switch (label) {
    case "BULLISH":
      return "H1 đang tăng";
    case "BEARISH":
      return "H1 đang giảm";
    case "NEUTRAL":
      return "H1 đi ngang";
    default:
      return "H1 chưa rõ";
  }
}

/** "Đang chờ:" sentences keyed by the server's refusal code (explanation of a state, never a forecast). */
export function waitingText(code: string | null, bullish: boolean | null, armed: { phase: string | null; age: number | null }): string | null {
  if (!code) return null;
  const side = bullish === null ? "" : bullish ? " tăng" : " giảm";
  if (code === "NO_TRIGGER" && armed.phase === "ARMED") {
    return `nến M5 kích hoạt${side} (setup đã hình thành ${armed.age ?? "?"} nến M5 trước)`;
  }
  const table: Record<string, string> = {
    NO_DIRECTION: "H1 xác lập hướng tăng hoặc giảm rõ ràng",
    TIMEFRAME_CONFLICT: "H4 và M15 ngừng đi ngược hướng H1",
    NO_SETUP: "một nhịp pullback ở M15 theo xu hướng H1 (khi đó setup được giữ 6 nến M5)",
    NO_TRIGGER: `nến M5 kích hoạt${side}`,
    SPREAD_TOO_WIDE: "spread quay lại mức bình thường",
    VOLATILITY_TOO_HIGH: "biến động bất thường lắng xuống",
    VOLATILITY_TOO_LOW: "biến động tăng lên",
    VOLUME_TOO_LOW: "tick volume M1 hồi phục",
    RR_TOO_LOW: "kế hoạch có R/R ròng từ 1,5 (chưa đủ khoảng trống tới mức giá kế tiếp)",
    TOO_CLOSE_TO_RESISTANCE: "thêm khoảng trống tới kháng cự kế tiếp",
    TOO_CLOSE_TO_SUPPORT: "thêm khoảng trống tới hỗ trợ kế tiếp",
    INVALID_STOP_DISTANCE: "khoảng cách SL hợp lệ",
    RISK_LIMIT: "lot đạt mức tối thiểu của broker trong giới hạn rủi ro",
    MARKET_CLOSED: "thị trường mở cửa",
    STALE_DATA: "dữ liệu thị trường mới",
    UNKNOWN_STATE: "đủ dữ liệu mọi khung và thông số broker",
    COOLDOWN: "hết thời gian nghỉ sau lệnh trước",
    DAILY_LIMIT: "ngày giao dịch tiếp theo",
    NEWS_UNKNOWN: "tin tức được xác minh",
    NEWS_WINDOW: "cửa sổ tin tức qua đi",
    BROKER_DISCONNECTED: "kết nối với broker",
  };
  return table[code] ?? null;
}

export const ACTIVITY_VI: Record<string, string> = {
  LOW: "Thấp",
  NORMAL: "Bình thường",
  HIGH: "Cao",
  SHOCK: "Đột biến",
  QUIET: "Yên ắng",
  GOOD: "Tốt",
  ELEVATED: "Nhỉnh",
  WIDE: "Rộng",
  UNKNOWN: "—",
};

/** The server writes the invalidation rule in English; show the known rules in Vietnamese. */
export function invalidationText(text: string | null): string | null {
  if (!text) return null;
  const m = /^H1 turns (bearish|bullish), or price closes beyond the stop$/.exec(text);
  if (m) return `H1 chuyển sang ${m[1] === "bearish" ? "giảm" : "tăng"}, hoặc giá đóng nến vượt qua SL`;
  return text;
}

export const PAPER_ACCOUNT_VI = "Tài khoản PAPER (vốn giả lập, không phải tài khoản FTMO)";
