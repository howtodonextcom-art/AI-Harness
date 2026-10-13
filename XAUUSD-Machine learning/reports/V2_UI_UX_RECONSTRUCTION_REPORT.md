# V2 · Báo cáo tái cấu trúc UI/UX (hỗ trợ quyết định, không chỉ BUY/SELL/WAIT)

Ngày: 2026-10-13 · Bằng chứng: ảnh thật từ dịch vụ đang chạy `reports/evidence/intel/intel_{1440x900,1152x720}_{fold,full,market_drawer}.png`; e2e Playwright **51 passed** (46 cũ + 5 mới), axe WCAG 2 A/AA sạch cả khi mở ngăn "Thị trường".

## 1. Trước / sau (cùng dữ liệu sống)
| Câu hỏi của trader | Trước (P0) | Sau |
|---|---|---|
| Thị trường đang làm gì? | chỉ nhãn MTF một dòng | ngăn "Thị trường": tóm tắt, bảng 5 khung (chế độ, pha biến động), mức quan trọng kèm khoảng cách (ATR), sự kiện nến/cấu trúc kèm giờ **biết** |
| Vừa thay đổi gì? | không | "Vừa thay đổi" (REGIME, VOLATILITY, SCENARIO, CHAIN, GATES, GOVERNOR, EVENT) |
| Kịch bản nào đáng theo dõi? | không | 5 kịch bản + trạng thái + xác nhận/vô hiệu có mức giá |
| Vì sao chiến lược chờ? | "SPREAD_TOO_WIDE" dù H1 không có hướng | 3 dòng ở màn hình đầu: **Thị trường chặn** (+ "cần: …"), **Cổng** (spread/biến động/dữ liệu), **Tài khoản** (cooldown/giới hạn) |
| Cần gì để BUY/SELL? | `next_condition` có trong API, UI không hiện | hiện ngay sau "Thị trường chặn" và phễu 11 bước (✓ ✗ ·) |
| Dữ liệu tươi cỡ nào? | tuổi nến từng khung (đã có) | + "quyết định dựa trên nến đã đóng · M5 đóng lúc HH:MM UTC · giá cách N s" (đỏ khi >5 s) |
| Ứng viên V2 chạy chưa? | không rõ | "Chiến lược v1.1.0 (UNVALIDATED, ứng viên V2 không hoạt động)" |

## 2. Bố cục và ràng buộc
- **Hợp đồng một màn hình** (e2e hiện có: 1920×1080, 1440×900, 1152×864 không cuộn trang) **được giữ**. Một thử nghiệm đầu đặt panel đầy đủ dưới biểu đồ làm vỡ hợp đồng (4 e2e đỏ); đã đổi: 3 dòng lý do nằm trong **hai dòng có sẵn** của SystemPanel (đã đưa lên đầu, ẩn dòng headline trùng lặp), panel đầy đủ ở **ngăn "Thị trường"** (hash `#market`).
- 1440×900: lý do nằm ở y≈219–289 (trong màn hình đầu). 1152×720: y≈216–286, **thấy được cả hai dòng** (trước đó khối chặn bị cuộn ẩn). Ảnh `intel_1152x720_fold.png`.
- Panel đầy đủ **không có nút** (e2e: 0 button): tránh nhầm với quyền hành động.

## 3. Phân tách khái niệm
Quan sát (ngăn Thị trường) ≠ Kịch bản (xác nhận/vô hiệu có mức) ≠ Ủy quyền chiến lược (v1.1.0, chuỗi, cổng, governor) ≠ Hành động của người (HumanPanel, giữ nguyên, CHẤP NHẬN chỉ ghi nhật ký).
"WAIT thị trường" tách khỏi "HOLD hệ thống": `system_hold` chỉ chứa COOLDOWN/DAILY_LIMIT/RISK_LIMIT, hiển thị "TK: …".

## 4. Chưa làm / hạn chế (trung thực)
- Không vẽ chú thích sự kiện lên biểu đồ (ChartPanel không đổi): hiện chỉ liệt kê. Có thể làm sau dưới dạng marker không repaint (đã có `known_at`).
- Chưa có timeline vòng đời setup (v1.2/C1 chưa nối live) và chưa hiển thị bất định/xác suất mô hình (ML không hoạt động).
- 1152×720: trong thẻ Hệ thống vẫn phải cuộn để thấy các dòng thấp hơn (Entry/SL/TP); đây là giới hạn bố cục cũ, chưa đổi.
- Chưa kiểm khả dụng với người dùng thật.

## 5. Kiểm thử
`apps/web/e2e/intelligence.spec.ts` (5): cảnh deterministic mock (H1 không hướng + spread rộng + cooldown) hiển thị đúng ba tầng và "Spread" **không** xuất hiện ở dòng thị trường; vừa màn hình đầu ở 1440×900 và 1152×720; ngăn Thị trường đủ 5 kịch bản + phễu + nhãn thời gian + axe; 0 nút.
