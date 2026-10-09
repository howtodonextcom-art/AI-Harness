# Quy trình giao dịch PAPER hằng ngày

Mọi thứ ở đây là mô phỏng trên dữ liệu FTMO DEMO. Không có lệnh thật. Baseline chưa được kiểm chứng thống kê (xem `docs/OPERATIONAL_BASELINE.md`).

## 1. Khởi động

```powershell
.\scripts\start_market_stack.ps1     # collector + API (+ dashboard nếu bật)
.\scripts\status_market_stack.ps1    # phải thấy: collector alive, Feed health GOOD
```

Mở `http://localhost:3000/trade` (trang chủ `/` chuyển thẳng sang đây). API: `http://127.0.0.1:8000/trade/decision`.

## 2. Đọc trang /trade (từ trên xuống)

1. **Dải trạng thái**: `PAPER ONLY`, thị trường MỞ/ĐÓNG, bid/ask/spread (điểm), tuổi dữ liệu. Dữ liệu cũ hoặc API mất kết nối ⇒ banner đỏ và nút vào lệnh bị khóa.
2. **Quyết định**: BUY / SELL / WAIT, đếm ngược hiệu lực, nhãn bằng chứng `CHƯA KIỂM CHỨNG`, và `NEWS NOT VERIFIED` (không có lịch tin ⇒ tự kiểm tra tin trước khi vào lệnh paper).
3. **Lý do**: WAIT nêu chính xác lý do chặn (ví dụ "M5 chưa trigger", "spread quá rộng"). BUY/SELL nêu từng mắt xích.
4. **Kế hoạch lệnh** (chỉ khi BUY/SELL): Entry, SL, TP, R/R sau phí, tỉ lệ thắng hòa vốn, mô hình stop, điều kiện vô hiệu. Chọn rủi ro 0.10 / 0.25 / 0.50 % ⇒ lot và số tiền rủi ro đổi theo. Vốn là **vốn paper giả lập**, không phải số dư FTMO.
5. **Khung thời gian**: H4 → M1 với vai trò, trạng thái, hướng, tick volume tương đối, độ tươi.
6. **Cột phải**: lệnh paper đang mở (lãi/lỗ tạm tính, R, thời gian giữ, nút đóng), tick volume, cấu trúc & mức giá, tài khoản paper & kết quả hôm nay, thống kê quyết định hôm nay, **Khóa thực thi DEMO** (vì sao khóa).

## 3. Vào lệnh paper

1. Kiểm tra: `actionable` (nút "Mở lệnh PAPER" sáng), tin tức do bạn tự xác minh, setup còn hiệu lực.
2. Chọn % rủi ro, bấm "Mở lệnh PAPER BUY/SELL", rồi **Xác nhận** (hai bước).
3. Máy chủ kiểm lại setup còn là setup hiện tại; nếu đã đổi sẽ trả `DECISION_CHANGED` và không mở gì.
4. Khớp ở ask (BUY) / bid (SELL) cộng slippage giả định. Nếu giá khớp lệch kế hoạch quá 0.25R ⇒ lệnh bị HỦY, không vào.

Chặn vào lệnh (hiển thị lý do): đã có 1 lệnh mở, đang cooldown sau lệnh thua, chạm giới hạn lệnh/lỗ trong ngày/phiên.

## 4. Quản lý và thoát

Tự động theo nến M1 đã đóng: `STOP_LOSS`, `TAKE_PROFIT`, `TIME_EXIT` (120 phút). Thủ công: nút "Đóng lệnh paper ngay" (đóng ở bid/ask phía thoát; đóng lần hai bị từ chối `NOT_OPEN`). Cảnh báo: `BUY/SELL_SETUP_READY` (mỗi setup một lần, nhớ qua restart), `SETUP_INVALIDATED`, `PAPER_SL`, `PAPER_TP`, `PAPER_TIME_EXIT`, `PAPER_MANUAL_CLOSE`. Telegram nếu đã cấu hình, nếu không ghi `data/trade/alerts.jsonl`.

## 5. Journal (`/journal`)

Mọi lệnh paper kèm ảnh chụp quyết định, trạng thái thị trường khi vào, MFE/MAE theo R, lý do thoát, `code_version`. Số liệu nhỏ không chứng minh lợi thế: dùng để kiểm tra kỷ luật và vận hành, không để kết luận chiến lược có lời.

## 6. Hợp đồng thực thi DEMO (sprint SAU, chưa làm)

Muốn bật lệnh DEMO thật cần (không thuộc sprint này): mật khẩu trade MT5 (owner), `XAU_EDGE_ENABLE_DEMO_TRADING=true`, `XAU_EDGE_DEMO_DRY_RUN=false`, danh sách tài khoản cho phép, `order_check` trước `order_send`, SL/TP đặt cùng lệnh, đối chiếu vị thế, tự đóng, hiệu chỉnh thực thi. Prompt dự thảo: `docs/prompts/NEXT_DEMO_EXECUTION_PROMPT.md` (KHÔNG chạy).

## 7. Sự cố thường gặp

| Hiện tượng | Nguyên nhân | Xử lý |
|---|---|---|
| Banner "Không kết nối được API" | API dừng | `status_market_stack.ps1`, `start_market_stack.ps1` |
| `STALE_DATA` | collector/terminal mất kết nối | mở terminal FTMO, đăng nhập; collector tự nối lại |
| `UNKNOWN_STATE` | thiếu khung hoặc `symbol_spec` | chờ collector publish spec (≤10 phút sau khởi động) |
| `MARKET_CLOSED` | cuối tuần / nghỉ giữa ngày | chờ phiên mở |
| WAIT kéo dài | điều kiện chuỗi không thỏa | bình thường; xem "Quyết định hôm nay" để biết lý do phổ biến |

Không nới ngưỡng chỉ vì ít tín hiệu: mọi thay đổi tham số phải qua phiên bản hóa `STRATEGY_VERSION` và đánh giá riêng.

## Cập nhật: biểu đồ, "Why WAIT?" và các thiết lập

* **Biểu đồ** ở đầu `/trade` (mặc định M5; bấm ô khung trong ma trận để đổi khung): đường ENTRY/SL/TP, vị thế paper, marker BUY/SELL/EXIT, công tắc Signals / Trade Plan / Paper Trades / Structure / Volume và "Paper trade history". Chi tiết: `docs/reports/TRADING_CHART_ACCEPTANCE.md`.
* **Why WAIT?**: từng chặng PASS/FAIL/— và "Waiting for: …" (điều kiện kế tiếp, không phải dự báo).
* **Phiên bản baseline**: mặc định v1.1.0; `XAU_EDGE_BASELINE_VERSION=1.2.0` để thử v1.2 (xem `OPERATIONAL_BASELINE.md`).
* **AUTO_PAPER**: `XAU_EDGE_AUTO_PAPER=true` tự mở lệnh PAPER khi có quyết định hành động (mặc định TẮT, xác nhận thủ công). Chỉ chạm bàn paper, không thể tới `order_send`.
* **Replay nghiệm thu**: `uv run python scripts/trade_acceptance_replay.py --start 2025-12-01 --end 2025-12-29` chạy toàn bộ đường đi trên dữ liệu đã đốt (xem `PAPER_LIFECYCLE_ACCEPTANCE.md`).
* **Tần suất**: có thể nhiều ngày không có setup; đó là hành vi đúng của baseline đóng băng.
