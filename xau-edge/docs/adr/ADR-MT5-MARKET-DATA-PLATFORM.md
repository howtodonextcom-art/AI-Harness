# ADR-MT5-MARKET-DATA-PLATFORM: nguồn dữ liệu thị trường first-party từ terminal FTMO MT5

* Trạng thái: chấp nhận (2026-10-09)
* Liên quan: ADR-0019/0020 (thực thi), `docs/MT5_DATA_PLATFORM.md`

## Bối cảnh

Nghiên cứu, backtest, tín hiệu, paper và demo cần cùng một nguồn giá, khối lượng, spread và đồng hồ
như nơi lệnh khớp thật (FTMO). TradingView không phải nguồn thực thi và không có API chính thức để
trích dữ liệu; websocket không chính thức bị loại.

## Quyết định

1. **Nguồn chuẩn**: terminal FTMO MT5 đã đăng nhập, qua gói Python `MetaTrader5`, chỉ các hàm dữ liệu
   (`ReadOnlyMt5Client`, allowlist). Không có đường nào tới lệnh/vị thế/lịch sử deal.
2. **Chỉ DEMO**: guard loại tài khoản không DEMO (fail closed). Dùng phiên của terminal; không nhận
   hay lưu thông tin đăng nhập.
3. **Collector tách khỏi API**: một tiến trình sở hữu kết nối MT5, ghi kho + `live.json` + status;
   API chỉ đọc file. Lý do: một kết nối duy nhất, API không phụ thuộc MT5, CI không cần MT5.
4. **Kho nến bất biến**: chỉ nến đã đóng, parquet theo tháng, ghi nguyên tử, không ghi đè, thay đổi
   được ghi sự kiện, manifest SHA-256. `RawStore` nghiên cứu hiện có giữ nguyên.
5. **Đồng hồ**: thời gian MT5 là giờ máy chủ gán nhãn UTC; chuyển bằng `BrokerClock` `NY+7`, kiểm tra
   sống: tuổi tick ≈ 0 s.
6. **Khối lượng**: chỉ tick volume; `VolumeType` mô tả sẵn có, không mô tả ý nghĩa.
7. **Giao thức UI**: polling GET. Không SSE/WebSocket ở giai đoạn này.
8. **Kiểm thử**: CI dùng client giả; test sống đánh dấu `mt5`, CI chạy `-m "not mt5"`.

## Hệ quả

* Chiều sâu lịch sử bị chặn bởi `MaxBars` của terminal (100000): cần chủ dự án nâng và khởi động lại.
* Collector phải đang chạy để có dữ liệu mới; `check_market_data_health.py` báo STALE/UNKNOWN nếu không.
* Terminal phải chạy trên cùng máy (gói MetaTrader5 chỉ Windows).
* TradingView chỉ là tham chiếu hình ảnh thủ công, không bao giờ là nguồn sự thật.

## Phương án đã loại

CSV export thủ công (không tăng dần), Expert Advisor/bridge (thêm bề mặt thực thi), TradingView
(không thực thi, không API), nhà cung cấp dữ liệu thứ ba (khác feed/spread/đồng hồ của FTMO).
