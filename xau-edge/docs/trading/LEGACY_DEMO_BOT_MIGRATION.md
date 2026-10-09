# Kế hoạch di chuyển bot DEMO cũ sang TradeEngine / data/market

Trạng thái: **kế hoạch**, không thực thi trong sprint này. Bot cũ KHÔNG được bật.

## 1. Hiện trạng (đã kiểm)

`scripts/demo_trader.py` (bot DEMO cũ) dựng quyết định từ **`data/raw`** (`RawStore` + `DatasetCatalog(data_dir/"raw")`) bằng engine tín hiệu cũ (`xau_edge.signals.*`, EdgeProgram). Luồng này:

* dùng dữ liệu nghiên cứu có thể cũ nhiều tháng (không phải ledger sống `data/market`);
* là engine quyết định thứ hai, độc lập với `TradeEngine` (hai nguồn sự thật cho "BUY/SELL");
* đã bị KHÓA bởi cấu hình (không mật khẩu trade, dry-run, không tài khoản cho phép).

Các script khác còn đọc `data/raw` (`current_signal.py`, `forward_test.py`) chỉ phục vụ nghiên cứu/đối chiếu, không phát lệnh.

## 2. Nguyên tắc

Không duy trì hai engine quyết định. Chức năng thực thi của bot cũ được **thay thế** bằng một lớp thực thi mỏng nhận `TradingDecision` từ `TradeEngine` (nguồn duy nhất), thay vì sửa bot cũ để đọc `data/market`.

## 3. Ánh xạ chức năng

| Bot cũ | Thay bằng | Ghi chú |
|---|---|---|
| Tạo tín hiệu từ `data/raw` | `TradeEngine.view()` / `decision_core.evaluate` trên `data/market` | đã có, parity live=replay=paper |
| Kiểm tra dữ liệu cũ/đồng hồ | `LiveTradingMarketSource` (độ tươi từng khung, quote ≤30 s, collector ≤60 s) | đã có |
| Định cỡ lệnh | `risk_calc` + `sizing` theo spec broker | đã có |
| Cooldown/giới hạn ngày | `TradeGovernor` trong `PaperDesk` | dùng chung cho demo |
| Sổ lệnh/journal | `paper_journal.jsonl` (provenance) + journal thực thi | mở rộng thêm trường `order_check`, `retcode` |
| Gửi lệnh MT5 | **mới**, sprint DEMO: executor (`order_check` → `order_send`, SL/TP trong lệnh) | `NEXT_DEMO_EXECUTION_PROMPT.md` |
| Đối chiếu vị thế | **mới**: reconciliation MT5 ↔ sổ nội bộ | chặn khi lệch |
| Tự đóng | quy tắc thoát của `PaperDesk` + đóng khẩn | cùng một bộ quy tắc |
| Web control `/control/*` | giữ cho khởi động/dừng/kill switch; bỏ chọn tín hiệu cũ | token + Host/Origin như hiện nay |

## 4. Các bước (mỗi bước có cổng)

1. **Đóng băng**: ghi chú tại đầu `demo_trader.py`: DEPRECATED, đọc `data/raw`, không dùng; test kiểm bot không thể bật khi `account_trade_allowed` false (đã có qua `demo_lock`).
2. **Executor mới** (module riêng, không import `data/raw`, `signals.engine`): nhận `TradingSignal`; kiểm `setup_id` còn hiệu lực; idempotent theo `setup_id`.
3. **Chạy song song chế độ bóng (shadow)**: executor chỉ log lệnh *sẽ* gửi và so với lệnh paper cùng `setup_id`; mọi lệch giá/lot là lỗi.
4. **DEMO_ARMED + xác nhận từng lệnh** (owner), sau đó mới xét tự động.
5. **Gỡ bot cũ** sau khi executor mới qua red team và thời gian chạy bóng ổn định; xóa/đánh dấu `scripts/demo_trader.py` và các route chỉ phục vụ nó.

## 5. Điều kiện chặn (không bỏ qua)

* mật khẩu trade MT5 do owner cung cấp trực tiếp trong `.env` (agent không đọc);
* tin tức: tự động DEMO phải `allow_unknown_news=False` ⇒ cần lịch tin hoặc xác nhận tin theo từng lệnh;
* tần suất tín hiệu của baseline thấp (xem `SIGNAL_FUNNEL_ANALYSIS.md`): chạy bóng cần nhiều tuần để có đủ mẫu vận hành;
* không bật funded; không dùng Test-H/Holdout.
