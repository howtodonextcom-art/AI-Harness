# V2 · Product Audit Gate P0: Báo cáo kiểm toán độc lập (tổng hợp)

Ngày: 2026-10-13 · Phạm vi: chỉ đọc + đo. Không đổi chiến lược, ngưỡng, rủi ro, UI; không mở Validation/Confirm-C/Test-H/Holdout; không promote Candidate; không retrain ML; collector và PAPER không bị chạm. **Dừng tại Gate P0.**

Viết cho: chủ dự án (người quyết định có đầu tư tiếp vào V2 hay không).

## 0. Điều cần nói thẳng trước
1. **Ảnh chụp màn hình anh nói đã đính kèm (FTMO BUY bên trái, V2 WAIT bên phải) KHÔNG đến được em.** Phần UX dùng ảnh em tự chụp từ V2 đang chạy (`reports/evidence/audit_p0/ui_1440x900.png`, `ui_1152x720.png`, `ui_1920x1080.png`). Em không có dữ liệu về lệnh BUY FTMO nên không dùng nó làm chân lý và không kết luận "V2 lẽ ra phải BUY".
2. Một vài nhận định trong bản nháp nội bộ trước đó được em sửa lại sau khi đọc code: ChartPanel **có** hiển thị `readiness_level/6` (không phải "không có thang sẵn sàng"); SystemPanel thì không hiển thị `next_condition` (đã kiểm bằng grep).
3. Mọi thứ dưới đây gắn nhãn: **VERIFIED IN RUNTIME** (đo trên hệ thống đang chạy 2026-10-13), **TESTED** (có test), **IMPLEMENTED** (có mã, chưa đo), **RESEARCH ONLY**, **PLANNED**, **UNVALIDATED**, **NOT MEASURED**.

## 1. Kết luận một đoạn
V2 hôm nay là **V1 baseline v1.1.0 trong một vỏ tốt hơn rất nhiều**: kho dữ liệu sạch có hash, replay tất định, sổ PAPER có kỷ luật, lớp quyết định của người, API/WS có hợp đồng kiểu, độ trễ thấp và đo được. **Bộ não quyết định live là V1 v1.1.0** (Candidate V2 không được nối vào API: 0 tham chiếu trong `src/` ngoài research; VERIFIED bằng grep). Không có bằng chứng nào V2 dự đoán tốt hơn V1; mẫu forward duy nhất: 1 lệnh AUTO, −1,0R, **không phải bằng chứng**. V2 cải thiện **độ tin cậy, quan sát và kỷ luật**; chưa cải thiện **trí tuệ giao dịch**. Với tư cách công cụ hỗ trợ quyết định, V2 hiện **trung thực nhưng ít thông tin**: nó nói "WAIT" đúng nhưng nói "cần gì để thành BUY/SELL" kém.

## 2. Thẻ điểm điều hành (0–10)
Thang: 0 = không có; 3 = có mã, chưa dùng được/chưa đo; 5 = dùng được, đã đo, hạn chế rõ; 7 = tốt, có test + đo runtime; 9–10 = có bằng chứng out-of-sample (chưa có mục nào).

| Chiều | Điểm | Căn cứ chính |
|---|---|---|
| Thông tin (dữ liệu, độ tươi, độ đúng) | **7** | clean store 190 tháng PASS, hash; quote p50 0,9 s / p95 2,7–3,4 s (đo); WS 0 seq gap |
| Hỗ trợ quyết định (người đọc xong biết làm gì) | **4** | WAIT + blocker có; `next_condition` không hiển thị; chuỗi bị che bởi hard gate |
| Thời điểm vào lệnh (execution timing) | **4** | M1 advisory (G10) chỉ chặn, không đề xuất; chưa đo giá trị |
| Quản trị rủi ro | **7** | sizing 0,25%, governor, cooldown, daily limit, PAPER-only (TESTED); nhưng governor trộn vào lý do WAIT |
| Nghiên cứu / tái lập | **8** | manifest, spec hash, replay restore bằng từng bit, ledger nhiễm dữ liệu; điểm yếu: chưa có outcome hợp lệ |
| Giá trị dự đoán đã chứng minh | **1** | không có bằng chứng out-of-sample; 1 lệnh forward; ML V0 bị gắn CONTAMINATED |
| Hiệu năng / vận hành | **8** | compute ~17 ms, REST p50 8–22 ms, V2 ~3,6% 1 lõi / 112 MB |

## 3. Ba can thiệp ưu tiên cao nhất (đề xuất, chưa làm)
1. **Làm lộ "cần gì để đổi trạng thái"** (UI + API, không đổi logic): hiển thị `next_condition`, và thang điều kiện theo chuỗi thật (H1→M15→M5→M1) kèm cổng đang chặn, tách cổng an toàn khỏi trạng thái governor. Thấy được ngay, kiểm bằng test.
2. **Ghi `decision_log` theo sự kiện đổi trạng thái (không chỉ M5 close) + nhãn nguyên nhân WAIT tách bạch** (bảo vệ dữ liệu cho mọi phân tích sau; hiện đã làm mất lệnh AUTO 07:43).
3. **Chạy Stage A của Candidate trên DEV' (chỉ tạo tín hiệu) sau khi anh chốt spec 1.1.0** — con đường duy nhất để biết liệu có cải thiện "não" thật, trong ràng buộc bảo vệ cửa sổ khóa.

## 4. Năm câu trả lời thẳng
1. **V2 làm tốt hơn V1 đáng kể ở:** nguồn dữ liệu sạch và có thể chứng minh, tái lập tất định, sổ PAPER/journal, lớp quyết định của người, đo lường độ trễ, hợp đồng API, kiểm thử (1.925 test, mypy strict). Chi tiết `V1_V2_FUNCTIONAL_PARITY_AND_DIFFERENCE.md`.
2. **V2 vẫn chưa làm được cho trader XAUUSD thật:** không có bất kỳ biên lợi nhuận nào đã chứng minh; không giải thích "tại sao chưa BUY" theo từng tầng; không có nhận diện cấu trúc nến/thanh khoản trong đường quyết định live; quote là snapshot ≤1 Hz nên bỏ lỡ ~47% quote riêng biệt của MT5 trong mẫu đo; không có cảnh báo "sắp đủ điều kiện".
3. **WAIT hiện nay chủ yếu là:** *kỷ luật rủi ro + thiết kế chiến lược*, với một phần là *khuyết điểm triển khai ở lớp hiển thị*. Không phải độ trễ dữ liệu (độ trễ ≪ khung M5). Phân bố bar đã log: hard gate spread ~33%, biến động ~27%, governor ~24%, thiếu hướng/setup ~24% (VERIFIED, mẫu `decision_log`; giới hạn: chỉ lấy mẫu M5 close). Không có dấu hiệu bug logic gây starvation, nhưng governor lẫn vào lý do WAIT làm "WAIT thị trường" khó tách khỏi "WAIT do hệ thống tự hạn chế".
4. **Ba cải tiến giá trị đo được cao nhất mà không phá toàn vẹn nghiên cứu:** (a) lộ `next_condition`/thang điều kiện, (b) nhật ký quyết định theo sự kiện + tách nhãn nguyên nhân, (c) Stage A trên DEV' sau khi duyệt spec. Đều có tiêu chí kiểm ở `V2_TOP_10_ROOT_CAUSES_AND_REMEDIATION.md`.
5. **Nếu dừng phát triển hôm nay:** V2 là **công cụ giám sát + sổ kỷ luật PAPER hữu ích**, nhưng **chưa phải công cụ hỗ trợ quyết định đủ giá trị**: nó an toàn và minh bạch, nhưng trader không nhận được thông tin hành động nào mà V1 hoặc tự đọc biểu đồ chưa cho. Giá trị chính hiện là nền tảng nghiên cứu đáng tin để *kiểm tra* ý tưởng, chưa phải bản thân ý tưởng.

## 5. Điều không thể kết luận
Không thể nói V2 "kiếm được tiền" hay "không kiếm được tiền". Không thể nói MT5/FTMO BUY là đúng hay sai. Công suất thống kê hiện tại (~663 lệnh cho 0,20R) cho thấy cần thời gian forward dài; mọi kết luận về edge đều **UNVALIDATED**.

## 6. Giới hạn của cuộc kiểm toán
Không đo: độ trễ trình duyệt/vẽ chart (frontend render), p99 lâu dài (mẫu ~4–10 phút), tải nhiều client, hồi phục sau crash trực tiếp trên prod, so khớp từng quyết định V1↔V2 theo thời gian thực (chỉ có test parity G4 đã báo cáo trước). Đọc mã V1 UI `/trade` chưa phủ toàn bộ.

Các báo cáo kèm: `V1_V2_FUNCTIONAL_PARITY_AND_DIFFERENCE.md`, `V2_TRADING_BRAIN_FORENSIC_AUDIT.md`, `V2_REALTIME_DATA_AND_LATENCY_AUDIT.md`, `V2_DATABASE_AND_PIPELINE_AUDIT.md`, `V2_UI_UX_AND_TRADER_VALUE_AUDIT.md`, `V2_TOP_10_ROOT_CAUSES_AND_REMEDIATION.md`, `V2_INTELLIGENCE_UPGRADE_ROADMAP.md`.
