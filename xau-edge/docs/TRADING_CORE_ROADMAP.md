# Lộ trình Trading Core

Nguyên tắc: đo thành công bằng câu hỏi "chủ sở hữu có mở một trang và đưa ra quyết định PAPER có kỷ luật, minh bạch, rủi ro xác định trên dữ liệu FTMO sống không?", không bằng số module hay số test.

## Đã xong (sprint TRADE-01)

| Hạng mục | Trạng thái | Bằng chứng |
|---|---|---|
| Adapter dữ liệu sống duy nhất (ledger + live.json), không dùng `data/raw` | Xong | `trading/live_source.py`, `test_live_path_isolation.py` |
| Phân cấp H4 regime / H1 hướng / M30 ngữ cảnh / M15 setup / M5 trigger / M1 thời điểm | Xong | `trading/baseline.py` v1.1.0 |
| Trade plan (entry thực thi, SL cấu trúc/ATR, TP cấu trúc, R/R ròng, hết hạn) | Xong | `levels.py`, `baseline.py` |
| Máy tính rủi ro 0.10/0.25/0.50% theo spec broker, làm tròn xuống | Xong | `risk_calc.py`, `/trade/risk` |
| Paper desk (PENDING/OPEN/CLOSED/CANCELLED, thoát tự động, thủ công, journal) | Xong | `paper_desk.py` |
| Cảnh báo setup (dedupe, nhớ qua restart, vô hiệu hóa) | Xong | `setup_alerts.py` |
| Telemetry quyết định + thống kê ngày | Xong | `telemetry.py` |
| Trang `/trade`, `/journal`, điều hướng Trade/Market/Journal/Research/System | Xong | `apps/dashboard`, Playwright |
| Khóa DEMO giải thích bằng lý do cụ thể | Xong | `demo_lock.py` |
| `/signals` cũ đánh dấu deprecated + chặn dữ liệu cũ | Xong | `api/app.py` |
| Replay smoke, parity, soak, red team, đo hiệu năng | Xong | `docs/reports/TRADING_CORE_ACCEPTANCE.md` |

## Chưa làm / chủ đích để sau

1. **Lịch tin tức kinh tế**: hiện `NEWS_UNKNOWN` (paper cho phép với cảnh báo). Cần nguồn lịch đáng tin trước khi tự động hóa.
2. **Thực thi DEMO** (`NEXT_DEMO_EXECUTION_PROMPT.md`): mật khẩu trade MT5 (owner), `order_check`/`order_send`, SL/TP trong lệnh, đối chiếu vị thế, tự đóng, hiệu chỉnh trượt giá. KHÔNG làm trong sprint này.
3. **Kiểm chứng edge**: 0%. Cần giao thức tiền đăng ký trên dữ liệu chưa chạm; không suy ra từ kết quả paper.
4. **Quản lý vị thế nâng cao** (BE/trailing) đã có nhưng TẮT; chỉ bật khi có lý do định lượng ngoài mẫu.
5. **Đa lệnh/đa symbol**: ngoài phạm vi (1 lệnh, XAUUSD).

## Cổng chuyển giai đoạn

| Từ → Đến | Điều kiện |
|---|---|
| Paper desk → Demo execution | Owner xác nhận bằng văn bản; mật khẩu trade; soak paper ≥ 2 tuần không lỗi vận hành; parity xanh; lịch tin tức hoặc quy tắc tránh tin thủ công rõ ràng |
| Demo → Funded | Ngoài lộ trình này; cần edge được kiểm chứng và quy tắc FTMO đã xác minh |

## Đóng băng

Edge Program V1/V2, ML, chiến lược cũ, kiến trúc backtest, Research Console, khung toàn vẹn, tự động funded: chỉ sửa lỗi nghiêm trọng.
