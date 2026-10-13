# V2 · G9 Human Decision Layer + G10 M1 Execution Intelligence — Báo cáo triển khai

Ngày: 2026-10-13 · Schema `2.0.0-g10` · Chiến lược khóa: baseline v1.1.0 · Chế độ: PAPER only.
Định vị: **HUMAN-IN-THE-LOOP XAUUSD DECISION SUPPORT TERMINAL**. Hệ thống chỉ khuyến nghị; con người quyết định.

## 1. Phạm vi và những gì KHÔNG làm
Không Telegram, không gửi lệnh broker, không Demo, không họ ML mới, không chỉ báo mới, không đổi ngưỡng BUY/SELL, không đổi quy tắc rủi ro, không luật R:R/SL/TP mới. Các tệp chiến lược được khóa bằng sha256 (mục 8).

## 2. G9 — Human Decision Layer
- **Lớp tách biệt trên giao diện**: THIÊN HƯỚNG · SETUP · M5 TRIGGER · M1 EXECUTION · CHẶN CHÍNH · ĐIỀU KIỆN PHỤ · Entry/SL/TP · R:R ròng · rủi ro · chi phí · hạn/vô hiệu · bằng chứng (thẻ **HỆ THỐNG**, khuyến nghị tham khảo); thẻ **QUYẾT ĐỊNH CỦA BẠN** (CHẤP NHẬN / CHỜ / BỎ QUA + lý do); thẻ riêng **AUTO PAPER: CHỈ ĐỂ NGHIÊN CỨU** (dưới biểu đồ).
- **Khuyến nghị** (`SystemAdvice`): `BUY_CANDIDATE`, `SELL_CANDIDATE`, `WAIT`, `HOLD`, `EXIT_WATCH` — không phải lệnh. Đầu ra gốc của chiến lược (`strategy_action`) luôn hiển thị riêng, không bị ghi đè.
- **Nhật ký `human_decisions`** (SQLite, chỉ thêm): decision_id, timestamp, system_action, system_bias, setup_state, trigger_state, m1_execution_state, entry, sl, tp, rr, risk, human_choice, human_reason, paper_mode, strategy_version, evidence_label (+ setup_id, giá, hết hạn). Trigger CSDL từ chối UPDATE/DELETE. Đổi ý = hàng mới.
- **API**: `POST /api/v2/human/decision` (chỉ nhận `choice`, `setup_id`, `reason`; máy chủ tự chụp mọi con số), `GET /api/v2/human/decisions`. Từ chối: ứng viên cũ/đã đổi, hết hạn, không có dữ liệu, không có ứng viên, đang giữ lệnh, sai origin (403). Sự kiện WS `human`.
- **CHẤP NHẬN không gửi gì**: `api/human.py` không import `paper.desk` hay `open_position` (quét AST + test chạy khi `open_position` ném lỗi).

### Kiểm thử G9 (test #6 persistence)
`tests/api/test_human_api.py` (18 test): ghi từng lựa chọn; ACCEPT không đổi tín hiệu hệ thống lẫn sổ PAPER; UPDATE/DELETE/INSERT sai bị CSDL từ chối; request không mang được giá/lot; lý do được làm sạch; các từ chối; **lựa chọn còn sau khi khởi động lại app**; AUTO PAPER độc lập; sự kiện WS; quét AST không có đường broker.
E2E (`e2e/human.spec.ts`, 7 test): ma trận trạng thái, luồng 3 nút (chỉ gửi `choice/setup_id/reason`), từ chối của máy chủ hiện ra, lựa chọn còn sau reload, bảng quyết định trong Nhật ký chỉ đọc.

## 3. G10 — M1 Execution Intelligence
`core/execution.py` (tất định, nhân quả, giải thích được): chỉ trả lời "giờ có phải thời điểm tốt để thực thi ý tưởng H1/M15/M5 đã ủng hộ không?". Hướng sao chép từ H1 — **M1 không bao giờ đảo hướng** (test thuộc tính 300 mẫu ngẫu nhiên).
Đặc trưng: spread, phân vị spread, spread/ATR, biến động vi mô, thân nến, bấc, vị trí đóng, động lượng ngắn, bị từ chối tại vùng entry, phá vỡ thất bại, khoảng cách tới entry kế hoạch, chỗ còn lại tới TP, R:R ròng hiện tại, độ trễ/đuổi giá.
Trạng thái: `TOO_EARLY, WATCH, FORMING, CONFIRMED, EXECUTION_WINDOW, TOO_LATE, INVALIDATED`; chất lượng `GOOD/CAUTION/BAD`. Khi chưa có setup được ủng hộ: "chưa áp dụng" (không bịa trạng thái).
`core/advice.py` ánh xạ sang khuyến nghị: chiến lược BUY nhưng M1 `TOO_LATE` ⇒ khuyến nghị **WAIT** (chiến lược vẫn nói BUY, hiển thị riêng).

### Ma trận trạng thái M1 (test #7) — `tests/unit/test_execution.py`
| Tình huống | Trạng thái | Chất lượng |
|---|---|---|
| nến đúng thời điểm, giá gần entry, còn chỗ | EXECUTION_WINDOW | GOOD |
| ask 2001.5 (đuổi giá) | TOO_LATE | — |
| ask 2009 (hết phần thưởng) | TOO_LATE | — |
| giá đóng ngoài SL | INVALIDATED | — |
| xa vùng entry, chưa có nến xác nhận | TOO_EARLY / WATCH | — |
| nến yếu đang hình thành | FORMING | — |
| nến bị từ chối / phá vỡ thất bại | không vào CONFIRMED | CAUTION/BAD |
| CONFIRMED + spread rộng | CONFIRMED | BAD |
| không setup / thiếu M1 | không áp dụng (`M1_UNKNOWN`) | — |
| phiên bản SELL (đối xứng) | tương tự | — |
| 300 chuỗi nến ngẫu nhiên | hướng không bao giờ đổi | — |
| cùng đầu vào hai lần | cùng kết quả (tất định) | — |

## 4. Ma trận trạng thái giao diện (test #5, ảnh)
Ảnh: `reports/evidence/g9_g10/matrix-{buy-candidate,late-wait,no-setup,hold,exit-watch}.png`; `human-after-choice.png`; `journal-human-log.png`; `live-1440x900.png`, `live-1920x1080.png` (dịch vụ thật).
| Khuyến nghị | 3 nút | Ghi chú |
|---|---|---|
| ỨNG VIÊN MUA/BÁN | bật | hiện kế hoạch |
| CHỜ (M1 quá muộn, chiến lược vẫn BUY) | tắt, nêu lý do | chặn chính "M1: quá muộn" |
| CHỜ (không setup) | tắt | M1 "chưa áp dụng" |
| GIỮ (PAPER) / THEO DÕI THOÁT | tắt | không có ứng viên mới |

## 5. QA trình duyệt (test #4)
- Playwright **46/46** (37 cũ đã cập nhật testid + 9 mới); mỗi ô ma trận chạy axe WCAG2A/AA = 0 vi phạm, 0 lỗi console.
- Dịch vụ thật (:8200, sau khi khởi động lại): 0 lỗi console, 0 phản hồi HTTP ≥ 400.
- Giữ nguyên hợp đồng bố cục: một màn hình ≥1152 px, biểu đồ chiếm phần cao còn lại (đo bằng cột trái gồm AUTO PAPER).
- Chưa kiểm: bố cục điện thoại (phạm vi desktop-only); chưa có ứng viên thật trong thị trường lúc kiểm — luồng ứng viên được kiểm bằng trạng thái mô phỏng ở E2E và bằng test API có trạng thái ép buộc.

## 6. Cổng chất lượng
`ruff` sạch · `mypy` 53 tệp sạch · `pytest` **1.812 passed** · OpenAPI không lệch · Playwright 46/46 · `npm run test:unit` đạt.

## 7. Bằng chứng không có đường gửi lệnh broker (test #9)
1. Danh sách POST/PUT/DELETE trong OpenAPI chỉ gồm 3: `human/decision`, `paper/open-current`, `paper/positions/{id}/close` (hai cái sau là sổ PAPER nội bộ; test khóa danh sách này).
2. `grep order_send|MetaTrader5|OrderSend` trong `src/` = 0 kết quả.
3. `api/human.py` bị quét AST: không import broker/`paper.desk`/`open_position`; test chạy ACCEPT khi `open_position` ném lỗi vẫn ghi nhận bình thường.
4. Gói V2 ghi duy nhất `data/paper.sqlite3`; kho Parquet chỉ đọc.

## 8. Bằng chứng đầu ra chiến lược không đổi (test #8)
- `tests/unit/test_strategy_lock.py`: sha256 của decision.py, risk.py, market_state.py, structure.py, indicators.py, frames.py, costs.py + hằng số (ATR_K 1.25, MAX_STOP_ATR 3.0, R_MULTIPLE 2.0, MIN_NET_RR 1.5, WIDE_SPREAD_PERCENTILE 0.9, MAX_SPREAD_TO_ATR 0.15, mặc định DecisionConfig). Không tệp nào bị sửa; test xanh.
- Bộ golden-parity với V1 baseline v1.1.0 vẫn xanh trong 1.812 test.
- Lớp M1/advice chỉ cộng thêm, đọc kết quả chiến lược; `strategy_action` hiển thị nguyên bản.

## 9. Hạn chế trung thực
- Chưa có tín hiệu BUY/SELL thật được chuỗi G9/G10 xử lý trên thị trường thật; chiến lược vẫn **UNVALIDATED**, forward-evidence vẫn đang tích lũy (chưa đủ 100 lệnh/60 ngày).
- Ngưỡng M1 (STRONG_BODY 0.6, FAILED_LOOKBACK 10, …) là tham số thiết kế khởi đầu, chưa hiệu chỉnh bằng dữ liệu; không được dùng để tuyên bố edge.
- Hai mục chủ dự án còn mở, ngoài phạm vi: token Telegram, sao lưu ngoài thiết bị.
- Nút "Mở lệnh PAPER theo kế hoạch hiện tại" trong ngăn Nhật ký vẫn theo tín hiệu chiến lược gốc (PAPER nghiên cứu), độc lập với lớp con người.

## 10. Kết luận: **PASS**
Mọi tiêu chí chấp nhận G9 đạt (lớp tách biệt; 3 lựa chọn hoạt động; còn sau khi khởi động lại; tín hiệu hệ thống không bị ghi đè; AUTO PAPER độc lập; không đường broker; PAPER only; test trình duyệt, a11y, không lỗi console/API; chiến lược không đổi). G10 đạt các tiêu chí tất định/giải thích được/không đảo hướng. Điều kiện còn lại là bằng chứng forward, không thuộc phạm vi hai giai đoạn này.
