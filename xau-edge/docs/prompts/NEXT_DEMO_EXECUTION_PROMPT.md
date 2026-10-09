# DỰ THẢO — Prompt cho sprint "Thực thi DEMO" (KHÔNG chạy trong sprint TRADE-01)

> Chỉ chạy khi chủ sở hữu xác nhận bằng văn bản. Điều kiện tiên quyết ở cuối tài liệu.

## Mục tiêu

Nối kế hoạch lệnh của Trading Desk (đã chạy ổn định ở chế độ PAPER) tới tài khoản **FTMO DEMO** bằng một executor có bảo vệ, KHÔNG tiền thật, KHÔNG funded, và **không có tự động hoàn toàn** cho tới khi từng cổng bên dưới xanh.

## Phạm vi

1. **Ủy quyền mật khẩu trade**: owner tự đặt `MT5_TRADE_PASSWORD` trong `.env` (agent không đọc/in giá trị). `demo_lock_status()` phải chuyển từ LOCKED sang UNLOCKED_BY_CONFIG chỉ khi: `account_trade_allowed=true`, mật khẩu có mặt, `XAU_EDGE_ENABLE_DEMO_TRADING=true`, `XAU_EDGE_DEMO_DRY_RUN=false`, tài khoản nằm trong `DEMO_ALLOWED_ACCOUNTS`, và `trade_mode == DEMO`.
2. **Trạng thái `DEMO_ARMED`**: máy trạng thái DISARMED → ARMED (owner bấm, có hết hạn) → mỗi lệnh vẫn cần xác nhận thủ công ở giai đoạn đầu (chế độ "một lệnh một xác nhận"). Mặc định DISARMED sau mỗi lần khởi động.
3. **`order_check` bắt buộc trước `order_send`**: từ chối nếu retcode không OK, margin không đủ, volume/stops không hợp lệ.
4. **SL/TP đặt cùng lệnh** (không đặt sau); kiểm `stops_level`/`freeze_level`; từ chối nếu broker sửa SL/TP.
5. **Đối chiếu vị thế (reconciliation)**: sau mỗi lệnh và mỗi chu kỳ, so vị thế MT5 với sổ nội bộ; lệch ⇒ dừng và báo.
6. **Tự đóng**: theo cùng quy tắc thoát của paper (SL/TP/thời gian/vô hiệu), cộng đóng khẩn khi spread bất thường hoặc mất kết nối.
7. **Hiệu chỉnh thực thi**: ghi giá quyết định vs giá khớp vs trượt giá, spread lúc vào; so với giả định slippage của paper; báo cáo.
8. **Giới hạn cứng**: 0.01–0.10 lot ban đầu, 1 lệnh mở, giới hạn lỗ ngày, kill switch, tự DISARM khi lỗi bất thường.

## Bất biến (không được vi phạm)

* Giữ nguyên hàm quyết định thuần `decision_core.evaluate`; thực thi chỉ NHẬN `TradingDecision`, không tự suy luận.
* Mọi lệnh gắn `setup_id`/`decision_id`; idempotent (không gửi hai lần một setup).
* Tin tức: tự động DEMO phải `allow_unknown_news=False`; cần lịch kinh tế đáng tin hoặc chế độ "owner xác nhận tin" từng lệnh.
* Không `--no-verify`; không in/đọc `.env`; không lộ số dư/login.
* Không bật funded; không dùng Test-H/Holdout để chỉnh.
* Kiểm thử bằng client MT5 giả (không `order_send` thật trong CI); chỉ một thử nghiệm smoke 0.01 lot do owner kích hoạt thủ công trên DEMO.

## Giao nộp

Module executor + máy trạng thái, API `/trade/demo/*` (token + Host/Origin như control plane), UI hiển thị trạng thái ARMED/lệnh/đối chiếu, red team (lệnh trùng, đóng đôi, mất kết nối giữa chừng, retcode lạ, spread nổ), tài liệu `docs/DEMO_EXECUTION.md`, báo cáo hiệu chỉnh.

## Điều kiện tiên quyết (owner xác nhận)

1. Bàn paper chạy ≥ 2 tuần không lỗi vận hành; parity xanh; không có lỗi HIGH/CRITICAL mở.
2. Owner hiểu baseline CHƯA được kiểm chứng; DEMO là để đo thực thi/vận hành, không phải bằng chứng lợi nhuận.
3. Mật khẩu trade MT5 do owner cung cấp trực tiếp trong `.env`.
4. Quy tắc xử lý tin tức đã chọn.
