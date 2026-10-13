# ADR-V2-012: Paper Desk (sổ lệnh PAPER, quản lý bằng nến M1, bộ kiểm soát V1, SQLite riêng của V2)

Trạng thái: **ĐÃ DUYỆT** (G7, 2026-10-13) · Liên quan: ADR-V2-003 (không ghi vào kho dùng chung), ADR-V2-008 (không có đường gửi lệnh), ADR-V2-010, ADR-V2-011.

## Quyết định

1. **PAPER là chế độ duy nhất.** Paper Desk không có kết nối broker/MT5, không có hàm hay trường mô tả lệnh thật; test chặn tên `send_order`/`order_send`… và chặn module có `mt5`. "Demo/MT5 order: chưa mở" vẫn đúng.
2. **Nơi ghi duy nhất của V2:** một tệp SQLite riêng (`data/paper.sqlite3`, ngoài git). Kho nến/tick/live dùng chung vẫn **chỉ đọc**. Mỗi thay đổi là một giao dịch (`BEGIN IMMEDIATE`); nhật ký **chỉ thêm** (không có hàm sửa/xóa); `setup_id` là UNIQUE nên một setup **không bao giờ mở hai lần** (kể cả sau khi khởi động lại); equity khởi đầu ghi **một lần** và không bị ghi đè khi đổi cấu hình.
3. **Khớp lệnh (đều là GIẢ ĐỊNH, ghi trong `assumptions` của API và trong UI):** vào tại quote thực thi (ask cho MUA, bid cho BÁN) cộng 3 điểm trượt giá bất lợi; SL khớp kèm trượt giá bất lợi, TP khớp đúng mức; hoa hồng 0; swap theo số đọc terminal ngày 2026-10-08, mỗi lần qua 17:00 New York ngày thường; rủi ro thật được tính lại **từ giá khớp**.
4. **Quản lý lệnh bằng nến M1 đã đóng** mở sau phút vào lệnh (không dùng nến đang hình thành lúc vào, không nhìn ngược về giá trước khi vào). MUA thoát theo bid (đỉnh/đáy nến); BÁN thoát theo ask (cộng spread của nến). **Một nến chạm cả SL và TP thì coi SL trước** và đánh dấu `ambiguous`. Chỉ có SL/TP cố định; TP2 chỉ để hiển thị; một lệnh mở tại một thời điểm. MAE/MFE (điểm) được ghi.
5. **Bộ kiểm soát (governor) giữ nguyên ngưỡng của V1:** tối đa 1 lệnh mở, rủi ro tổng 1%, 2 lệnh/giờ, 3 lệnh/phiên, 6 lệnh/ngày (ngày broker NY+7), nghỉ 30 phút sau lệnh thua và 240 phút sau chuỗi 3 thua, dừng lệnh mới khi lỗ ngày ≥ 2%, **cắt hết lệnh mở khi lỗ ngày (gồm lãi/lỗ nổi) ≥ 3,5%**. Kết quả của bộ kiểm soát đi vào quyết định (cờ cooldown/daily/risk) nên một lệnh bị chặn hiện đúng mã từ chối; equity dùng để cỡ lệnh là equity của sổ (gồm lãi/lỗ nổi), không còn là hằng số cấu hình.
6. **Tự động mở (`XAU_V2_AUTO_PAPER`, mặc định BẬT)** vì forward-evidence cần tín hiệu tự nhiên; tắt được bằng biến môi trường. Engine nền (3 giây/lần) quản lý lệnh, tự mở khi quyết định là BUY/SELL **còn hạn** và chưa dùng setup đó. Lỗi một lượt không dừng engine. Quyết định được chia sẻ ~1 giây giữa trang, socket và engine (không tính lại ba lần).
7. **Hai thao tác ghi qua HTTP** (`POST /api/v2/paper/open-current`, `POST /api/v2/paper/positions/{id}/close`): máy chủ tự tính lại mọi thứ (client **không gửi giá/lô/mức**), từ chối `Origin` lạ (403), trả mã lỗi có tên (`NO_VALID_PLAN`, `POSITION_ALREADY_OPEN`, `SETUP_ALREADY_USED`, `QUOTE_UNAVAILABLE`, `POSITION_NOT_FOUND`, `POSITION_NOT_OPEN`). Đóng tay cần quote **mới**, và dùng phía đóng của quote. Không có `PUT/PATCH/DELETE`.
8. **Khi đang giữ lệnh:** `GET /api/v2/state` trả `HOLD` với lệnh làm kế hoạch (giá khớp, SL, TP, R/R) và PnL nổi; biểu đồ vẽ đường Entry/SL/TP của lệnh và đánh dấu vào/ra theo từng khung.

## Hệ quả

- Hợp đồng `2.0.0-g7`; socket có sự kiện `paper` (vị thế đổi, client tự lấy lại qua REST).
- Chưa có: dời SL/trailing, chốt từng phần theo TP2, nhiều lệnh đồng thời, so sánh với mua-và-giữ, vi phạm kỷ luật/bất đồng quy tắc-ML (cần ML ở G6), swap thật, hoa hồng thật, và đọc lại swap từ terminal (số liệu 2026-10-08 có thể đã đổi).
- **Forward-evidence là yêu cầu riêng:** sổ này ghi *quan sát*, không phải bằng chứng; mẫu nhỏ không cho kết luận (UI nói rõ).
