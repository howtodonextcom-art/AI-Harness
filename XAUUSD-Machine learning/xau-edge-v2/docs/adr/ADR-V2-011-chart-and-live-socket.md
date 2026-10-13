# ADR-V2-011: biểu đồ theo khoảng, nối nến live, và ổ cắm live chỉ báo "đã đổi"

Trạng thái: **ĐÃ DUYỆT** (G5, 2026-10-13) · Liên quan: ADR-V2-004 (lịch sử theo khoảng), ADR-V2-009, ADR-V2-010.

## Quyết định

1. **Thư viện biểu đồ:** TradingView Lightweight Charts 5.2.1 (Apache-2.0, ghim đúng phiên bản), nến + khối lượng tick + đường giá Entry/SL/TP1/TP2 khi có kế hoạch. Logo ghi công của thư viện (một liên kết trong khung biểu đồ) được **giữ** vì giấy phép; test "không điều hướng" loại riêng liên kết này.
2. **Lịch sử:** trang đầu là 500 nến mới nhất; kéo sang trái tới sát nến cũ nhất đã tải thì gọi `before=<nến cũ nhất>` với 1000 nến, tới hết kho (`has_more_before=false`). Không có trần cứng 400 nến. Hợp nhất bằng `mergeBars` (thuần, có test): tăng nghiêm ngặt, mỗi thời điểm một nến, bản đến sau thắng. Đổi khung: phản hồi của khung đã rời đi bị loại bỏ (token). Giữ nguyên vùng nhìn khi chèn nến cũ.
3. **Nến đang hình thành** lấy từ `live.json` của collector (REST `GET /api/v2/market/forming`, và sự kiện socket `live`). `withForming` bỏ nến forming có thời điểm <= nến đóng cuối: **bản đã đóng luôn thắng**, nên mối nối không bao giờ trùng. Hàng không hợp lệ (OHLC sai, định dạng lạ) bị bỏ, không phục vụ.
4. **Socket (`/ws`)** chỉ báo *sự kiện đã xảy ra*, không mang quyết định: `hello`, `live` (quote + nến forming khi file live đổi), `state` (dấu vân tay quyết định đã đổi, client tự lấy `/api/v2/state`), `heartbeat`. `seq` tăng 1 mỗi sự kiện, mọi loại; khoảng hở → client lấy lại qua REST. `data_version` trên mọi sự kiện: đổi thì client hợp nhất 10 nến mới nhất, không tải lại lịch sử.
5. **Dấu vân tay quyết định** loại `generated_at` và `decision_id` (id băm theo thời điểm nên đổi mỗi giây): chỉ thay đổi có ý nghĩa mới phát `state`.
6. **Bảng khung thời gian** (`StateSnapshot.mtf`): vai trò và phán quyết từng khung theo chuỗi (H4 chặn, H1 hướng duy nhất, M30 hiển thị, M15 setup, M5 trigger, M1 chặn) + độ mới.

## Hệ quả

- Hợp đồng `2.0.0-g5`: thêm `FormingBar/FormingResponse`, `MtfRow`, sự kiện `live`/`state`, `GET /api/v2/market/forming`.
- Bundle JS 126 KB gzip (G2: 73 KB; V1: 291 KB tổng JS).
- Chưa làm: tô vùng phiên, marker lệnh PAPER (chưa có paper desk, G7), đo/so khung trên điện thoại (ngoài phạm vi, chỉ desktop).
