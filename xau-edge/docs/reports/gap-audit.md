# Gap audit và lộ trình "bot demo chạy tự động" (2026-10-08)

Viết cho chủ dự án. Phạm vi đã chốt: **bot tự động trên tài khoản demo FTMO (MT5)**, không tiền thật.
Tài liệu này chỉ là kiểm toán và kế hoạch; chưa có code nào được thêm.

## 1. Tóm tắt

1. Hệ thống phân tích đã đầy đủ (dữ liệu → tín hiệu → API/dashboard → paper broker), nhưng **không có thành phần
   nào biến tín hiệu thành lệnh trên MT5 demo**, và **không có tiến trình chạy liên tục** (mọi thứ là script chạy tay).
2. Rào cản lớn nhất **không phải kỹ thuật**: chưa có edge nào qua tiêu chí đăng ký trước, nên evidence gate đóng và
   mọi tín hiệu là WAIT. Xây executor xong thì bot vẫn sẽ không vào lệnh nào, và đó là hành vi đúng.
3. Lệnh bị chặn thêm bởi `NEWS_UNKNOWN`: không có dữ liệu lịch kinh tế.
4. Có thể xây hạ tầng vận hành demo (executor, trạng thái bền vững, daemon, giám sát) mà không phản bội kết quả
   nghiên cứu, miễn là cổng bằng chứng giữ nguyên.
5. Cách duy nhất để bot có lệnh thật sự là có một ứng viên chiến lược qua `docs/evals/edge-criteria.md`
   (đếm vào Bonferroni) rồi qua forward test. Kế hoạch bên dưới sắp xếp theo hướng đó.

## 2. Đã bỏ qua hoặc hoãn

| Hạng mục | Nguồn | Trạng thái thật | Bằng chứng | Ảnh hưởng |
|---|---|---|---|---|
| `MT5ExecutionBroker` (gửi lệnh demo) | brief §31, ADR-0018 | Không làm, cố ý | `execution/` chỉ có `interface, paper, safety, trader, forward`; test quét không có hàm order | **Chặn** bot demo |
| Tiến trình chạy liên tục (daemon/scheduler) | brief §30, §50 | Không có | `scripts/` toàn script chạy tay (`current_signal`, `forward_test`) | **Chặn** |
| Kill switch bền vững, trạng thái lệnh/vị thế sau restart | final-status "Not done" | Chỉ trong bộ nhớ | `risk/` kill switch in-memory; API paper "state in memory" | **Chặn** (restart làm mất giới hạn rủi ro) |
| Đối soát với broker (vị thế thật vs nội bộ) | brief §32 | Không có | không có reader vị thế/account ngoài `ReadOnlyMt5Client` bars | **Chặn** |
| Dữ liệu lịch kinh tế + nghiên cứu cửa sổ news | brief §27, epic 19 | Chỉ interface và guard fail-closed | `news/calendar.py`; mọi tín hiệu `NEWS_UNKNOWN` | **Chặn** mọi BUY/SELL |
| Forward test theo lịch | epic 18 | Tool xong, chưa chạy | `scripts/forward_test.py`, guard 100 lệnh | Chặn kết luận |
| Test period | edge-criteria | Chưa từng chạy (đúng) | báo cáo checkpoint-1 | Chỉ mở khi có ứng viên khóa trước |
| Holiday calendar | final-status | Chỉ phân loại cảnh báo validator | không module nào dùng | Thấp |
| Mô hình chi phí: swap thứ Tư x3, partial fill, latency, margin | ADR-0015 | Không mô hình | final-status | Trung bình (sai lệch live vs backtest) |
| Slippage 3 điểm chưa đo, commission 0 chưa xác minh | final-status "Assumptions" | Giả định | | Trung bình; cần đo trên demo |
| Test trình duyệt dashboard trong CI | final-status | Chỉ lint/type/build + ảnh chụp tay | | Thấp |
| Giám sát/cảnh báo (heartbeat, mất kết nối MT5, dữ liệu cũ, lệnh bất thường) | brief §37 | Chỉ log có cấu trúc | `observability.py`; không có alert | **Chặn** vận hành không giám sát |
| Xác nhận luật tự động hóa của FTMO | final-status | "Không nêu trên trang objectives" | `configs/prop/` | Cần xác minh trước khi chạy EA/bot |
| Docker, STUMPY/tslearn | final-status | Không cần | | Không ảnh hưởng |
| Phase 12–13 của brief (bán tự động, tự động) | ADR-0018 | Ngoài phạm vi cho tới nay | | Bản kế hoạch này mở phần demo |

## 3. Rào cản để bot chạy được

### (a) Thiếu kỹ thuật, xây được

| ID | Mô tả | Cách gỡ |
|---|---|---|
| A1 | Executor MT5 demo | `MT5ExecutionBroker` cài `ExecutionBroker`; chỉ nhận lệnh từ `PaperTrader` pipeline (signal → risk → safety); guard DEMO + whitelist tài khoản/symbol; magic number riêng; SL/TP bắt buộc; idempotency theo `signal_hash` |
| A2 | Trạng thái bền vững | SQLite/DuckDB: lệnh, vị thế, kill switch, bộ đếm ngày, `last_decision_bar`; khôi phục sau restart; kill switch mặc định "tripped" nếu trạng thái hỏng |
| A3 | Đối soát | Mỗi chu kỳ đọc vị thế/lệnh/account từ MT5, so với sổ nội bộ; lệch → trip kill switch |
| A4 | Daemon | Vòng lặp theo đóng nến M15: fetch bars → validate → signal → risk → executor; heartbeat; dừng an toàn; chống chạy hai bản |
| A5 | Giám sát | Cảnh báo (file + tùy chọn webhook): data stale, MT5 mất kết nối, kill switch, từ chối lặp lại, chênh lệch đối soát |
| A6 | Dữ liệu news | Chọn nguồn lịch kinh tế bằng `search-first` (đối chiếu giấy phép/độ tin cậy); lưu snapshot có `available_at`; chạy nghiên cứu cửa sổ news đã đăng ký |
| A7 | Đo chi phí thực | Ghi spread/slippage/commission thực tế từ lệnh demo, hiệu chỉnh `CostModel` |
| A8 | Chaos/failure tests | Rớt kết nối giữa lệnh, requote, từ chối lệnh, restart giữa chừng |

### (b) Thiếu bằng chứng, kỹ thuật không giải quyết được

| ID | Mô tả | Hướng |
|---|---|---|
| B1 | Chưa có edge: analogue, baseline A/B/C, 4 mô hình đều FAIL trên dev và validation | Giả thuyết mới đi qua registry như biến thể được đếm (Bonferroni α=0.05/K); giữ test period khóa |
| B2 | Dữ liệu hạn chế: 1 broker, 1 symbol, 17 tháng | Thêm tick data, broker thứ hai, lịch sử dài hơn để biết null có do thiếu dữ liệu |
| B3 | Forward test cần thời gian lịch | Bắt đầu chạy replay/forward hằng ngày ngay (không cần ứng viên để thu mẫu và đo chi phí) |

Trung thực: có khả năng đáng kể không có edge trong không gian giả thuyết này. Khi đó kết quả đúng là bot demo chạy
đúng cơ chế, WAIT liên tục, và dự án dừng/đổi giả thuyết thay vì hạ tiêu chuẩn.

### (c) Cần bạn quyết định

| ID | Quyết định | Khuyến nghị |
|---|---|---|
| C1 | Có cho bot đặt lệnh demo khi chưa có edge? | **Không** qua evidence gate chính. Nếu muốn kiểm tra đường ống, thêm chế độ `pipeline_smoke` tách biệt, lot tối thiểu, gắn nhãn, không bao giờ tính vào bằng chứng |
| C2 | Nguồn lịch kinh tế | Chọn sau bước `search-first`; ưu tiên nguồn có lịch sử + giấy phép rõ |
| C3 | Giới hạn rủi ro demo (risk/lệnh, lot tối đa, lệnh/ngày) | Giữ mặc định hiện có trong `configs/prop/ftmo_*.yaml` |
| C4 | Nơi chạy daemon (máy này hay VPS Windows có MT5) | MT5 chỉ chạy trên Windows; VPS sau khi A1–A5 ổn |
| C5 | Luật FTMO về bot/EA | Bạn kiểm tra điều khoản tài khoản; mình không tự suy diễn |

Điều kiện tối thiểu để chạy demo an toàn: A1–A5 xong và qua A8, ADR mới thay thế phần liên quan của ADR-0018,
kill switch bền vững, đối soát hoạt động, DEMO guard kiểm tra ở mọi lần gửi lệnh. Không nên chạy tiền thật vì:
chưa có edge, chi phí chưa đo, chưa có forward test, chưa có lịch news.

## 4. Lộ trình ECC tiếp theo

Mỗi sprint theo vòng: kế hoạch → Gate A → test trước → cài đặt → review độc lập → kiểm tra → Gate B → commit → ghi nhận.

| Sprint | Mục tiêu | Epic mới | Done khi | Rủi ro chính |
|---|---|---|---|---|
| 15 | Nền vận hành bền vững | E20 State store, E21 Kill switch bền vững | Restart giữa chừng không mất kill switch/vị thế/bộ đếm; trạng thái hỏng → fail-closed; test chaos pass; ADR-0019 | Race condition khi khôi phục |
| 16 | Executor demo | E22 `MT5ExecutionBroker`, E23 Đối soát | Chỉ gửi lệnh khi pipeline cho phép; từ chối nếu không phải demo/whitelist; SL/TP luôn có; idempotent; đối soát lệch → kill; test dùng fake MT5 client (không cần terminal) và 1 test tích hợp đánh dấu `mt5` chạy tay | Đường gửi lệnh là bề mặt rủi ro lớn nhất: review bảo mật bắt buộc, test quét "không đường tắt" |
| 17 | Daemon + giám sát | E24 Scheduler/daemon, E25 Alerts | Chạy đóng nến M15 liên tục 24h trên demo ở chế độ WAIT; heartbeat; cảnh báo kích hoạt được bằng test; không chạy trùng | Phụ thuộc kết nối MT5 |
| 18 | News data | E26 Calendar ingestion, E27 News-window study | Snapshot lịch có `available_at`, kiểm tra leak; nghiên cứu cửa sổ đăng ký trước; `NEWS_UNKNOWN` chỉ còn khi thật sự thiếu dữ liệu | Nguồn dữ liệu/giấy phép |
| 19 | Đo chi phí thật + forward thu mẫu | E28 Cost calibration, E18 chạy | ≥ 2 tuần replay/forward có nhật ký; `CostModel` được hiệu chỉnh từ số đo, ghi vào ADR | Mẫu ít |
| 20+ | Nghiên cứu giả thuyết mới | E29… | Mỗi ý tưởng là biến thể đếm trong registry; chỉ mở test period cho một cấu hình khóa trước | Có thể vẫn không có edge |

Thứ tự phụ thuộc: 15 → 16 → 17; 18 và 19 có thể song song với 16–17 vì độc lập; 20+ chạy sau khi hạ tầng ổn.

## 5. Red-team

| Câu hỏi | Đánh giá |
|---|---|
| Executor có thể bị dùng để gửi lệnh tiền thật không? | Phải chặn bằng: guard DEMO ở mọi lần gửi, whitelist số tài khoản, ADR ghi rõ, test chứng minh. Rủi ro cao nhất của kế hoạch này |
| Có thể "nới" evidence gate để bot có lệnh? | Không; cổng giữ nguyên. Chế độ smoke (C1) tách biệt và gắn nhãn |
| Restart có thể xóa giới hạn rủi ro? | Hiện **có** (in-memory); Sprint 15 sửa |
| Demo có chứng minh được lợi nhuận thật? | Không: fill demo khác live; chỉ đo vận hành và chi phí xấp xỉ |
| Kế hoạch này có bị ép thành "chạy bằng mọi giá"? | Rủi ro có thật; tiêu chí Done của mỗi sprint là cơ chế đúng, không phải số lệnh hay lợi nhuận |

## 6. Bước tiếp theo đề nghị

Bạn trả lời C1–C5 (hoặc "mặc định") và duyệt Gate A cho **Sprint 15**; mình viết ADR-0019, test trước, rồi cài đặt.
