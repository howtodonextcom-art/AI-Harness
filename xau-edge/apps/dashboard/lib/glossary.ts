/** One short sentence per trading term the page uses. Plain language, no formulas, no advice. */
export const GLOSSARY: Record<string, { title: string; text: string }> = {
  bid: { title: "Bid (giá bán ra)", text: "Giá bạn nhận được khi BÁN. Lệnh MUA đóng ở giá này." },
  ask: { title: "Ask (giá mua vào)", text: "Giá bạn phải trả khi MUA. Lệnh BÁN đóng ở giá này." },
  spread: { title: "Spread", text: "Chênh lệch Ask - Bid: chi phí vào lệnh. Spread rộng làm lệnh khó có lãi hơn." },
  rr: { title: "R/R (lãi so với lỗ)", text: "Lãi dự kiến khi chạm TP chia cho lỗ khi chạm SL, đã trừ spread. 1,9 nghĩa là lãi gấp 1,9 lần mức lỗ." },
  r: { title: "R", text: "Một đơn vị rủi ro = khoản lỗ nếu chạm SL. +1R là lãi bằng đúng mức rủi ro đã chọn." },
  mfe: { title: "MFE", text: "Mức lãi tạm tính cao nhất lệnh từng đạt khi đang mở." },
  mae: { title: "MAE", text: "Mức lỗ tạm tính sâu nhất lệnh từng chịu khi đang mở." },
  tickvol: { title: "Tick volume", text: "Số lần giá đổi trong khoảng thời gian: đo độ sôi động, không phải khối lượng khớp thật của sàn." },
  bias: { title: "Thiên hướng (bias)", text: "Hướng thị trường đang nghiêng về theo xu hướng H1. Chỉ là mô tả, KHÔNG phải tín hiệu vào lệnh." },
  setup: { title: "Setup", text: "Nhịp điều chỉnh (pullback) ở M15 theo xu hướng H1. Có setup vẫn chưa được vào lệnh: còn chờ nến M5 xác nhận trigger." },
  trigger: { title: "Trigger", text: "Nến M5 đóng xác nhận hướng đi sau setup. Khi trigger xác nhận và kế hoạch đầy đủ, hành động mới thành MUA/BÁN PAPER." },
  entry: { title: "Entry (giá vào)", text: "Giá kế hoạch để vào lệnh, theo giá thị trường lúc đó. Giá khớp thật có thể lệch nhẹ." },
  risk: { title: "Rủi ro", text: "Số tiền (và % vốn paper) bạn mất nếu giá chạm SL. Bàn chỉ cho chọn các mức nhỏ: 0,10%, 0,25%, 0,50%." },
  lot: { title: "Lot", text: "Khối lượng lệnh, bàn tự tính để khoản lỗ khi chạm SL đúng bằng mức rủi ro đã chọn." },
  sl: { title: "SL (cắt lỗ)", text: "Mức giá bàn tự đóng lệnh để giới hạn lỗ." },
  tp: { title: "TP (chốt lời)", text: "Mức giá bàn tự đóng lệnh để chốt lãi." },
  hold: { title: "Giữ tối đa", text: "Thời gian giữ lệnh dài nhất: tới hạn này bàn tự đóng lệnh (TIME EXIT) dù chưa chạm SL hay TP." },
  paper: { title: "PAPER", text: "Lệnh giả lập: không có lệnh nào được gửi tới MT5 hay tài khoản thật." },
};
export type TermId = keyof typeof GLOSSARY;
