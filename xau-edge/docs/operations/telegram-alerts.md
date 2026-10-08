# Cảnh báo qua Telegram

Kênh cảnh báo do chủ dự án chọn: **Telegram**. Code: `src/xau_edge/ops/notifier.py`.
Token và chat id chỉ nằm trong biến môi trường / `.env` (không hard-code, không log, không commit).

## 1. Tạo bot và đặt hai biến (chủ dự án tự làm trên máy mình)

1. Trong Telegram, mở chat với `@BotFather`, gửi `/newbot`, đặt tên. BotFather trả về **bot token**
   (dạng `123456789:AA...`). **Không dán token vào chat với bất kỳ ai/AI, không đưa vào Git.**
2. Mở chat với bot vừa tạo và gửi một tin bất kỳ (ví dụ `hi`), để bot được phép nhắn lại cho bạn.
3. Lấy **chat id** của bạn: mở trình duyệt, vào
   `https://api.telegram.org/bot<TOKEN>/getUpdates` (thay `<TOKEN>` tại chỗ, trong chính trình duyệt
   của bạn) và tìm `"chat":{"id": 123456789`. Số đó là chat id. Nhóm có id âm.
   Cách khác: nhắn `@userinfobot` để biết id của chính bạn (không cần token).
4. Mở file `.env` trên máy chạy bot bằng trình soạn thảo và thêm hai dòng (chỉ tên biến ở đây):

   ```
   XAU_EDGE_TELEGRAM_BOT_TOKEN=<token của bạn>
   XAU_EDGE_TELEGRAM_CHAT_ID=<chat id của bạn>
   ```

5. Thử gửi một tin kiểm tra (không in token):

   ```powershell
   uv run python -c "from xau_edge.ops.notifier import *; d=build_dispatcher(); print(d.dispatch(AlertEvent(code='TEST', severity='info', message='xau-edge alert test')))"
   ```

Nếu lộ token (dán nhầm vào chat, commit nhầm): vào `@BotFather`, `/revoke`, tạo token mới.

Biến tùy chọn (mặc định trong ngoặc): `XAU_EDGE_ALERT_MIN_INTERVAL_MINUTES` (15),
`XAU_EDGE_ALERT_CRITICAL_REPEAT_MINUTES` (30), `XAU_EDGE_ALERT_MAX_PER_HOUR` (30).

## 2. Hành vi

| Quy tắc | Chi tiết |
|---|---|
| Không bao giờ ném lỗi vào vòng lặp bot | `notify`/`dispatch` trả về kết quả, mọi exception được nuốt và ghi log đã che token |
| Chống trùng | Cùng `code` không gửi lại trong `min_interval` (15 phút) |
| Critical còn hiệu lực | Nếu bot tiếp tục `dispatch` cùng một alert `critical` mỗi chu kỳ, nó được gửi lại mỗi `critical_repeat` (30 phút) |
| Leo thang | Đổi từ `warning` sang `critical` cho cùng code: gửi ngay |
| Giới hạn tốc độ | Tối đa 30 tin/giờ cho alert không critical; critical không bị chặn |
| Mất mạng | Ghi vào `data/execution/alerts.jsonl` (`"delivered": false` + lý do đã che token) |
| Chưa cấu hình | `NullNotifier`: mọi alert đi vào file fallback, bot vẫn chạy |
| Che token | `redact()` loại token và mọi chuỗi có dạng bot token khỏi lỗi/log; `repr` của notifier và settings không lộ token |

Trạng thái chống trùng nằm trong bộ nhớ: sau khi restart tiến trình, alert đang active được gửi lại một lần.
`dispatcher.resolve(code)` xóa trạng thái khi điều kiện đã hết.

## 3. Các sự kiện (`AlertCode`)

`KILL_SWITCH_TRIPPED`, `RECONCILE_MISMATCH`, `STALE_DATA`, `HEARTBEAT_DEAD`, `NEAR_DAILY_LOSS_FLOOR`,
`ORDER_REFUSED`, `NEWS_COVERAGE_ENDING`, `AUTO_FLATTEN`, `ROLLOUT_TIER_CHANGE`, `CLOCK_DRIFT`.
Alert từ `evaluate_health` (`execution/status.py`) và từ `news/update.py` được chuyển bằng
`AlertEvent.from_alert(alert)`.

## 4. Cách nối vào bot (dành cho `scripts/demo_trader.py`)

```python
from xau_edge.ops.notifier import AlertEvent, build_dispatcher

dispatcher = (
    build_dispatcher()
)  # đọc XAU_EDGE_TELEGRAM_*; đường dẫn fallback mặc định data/execution/alerts.jsonl
for alert in evaluate_health(status, state, now):  # mỗi chu kỳ
    dispatcher.dispatch(AlertEvent.from_alert(alert))
```

Không có endpoint nào trong tài liệu này cho phép nhận lệnh từ Telegram: kênh này **chỉ một chiều (đẩy cảnh báo)**.
