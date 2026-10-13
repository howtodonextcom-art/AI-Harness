# V2 G8: độ tin cậy và nền tảng bằng chứng forward

Ngày: 2026-10-13 · repo `xau-edge-v2` (local, chưa push) · V1 **không bị sửa**.

Quyết định đã áp dụng: **không mở Test-H** · **giữ nguyên tiêu chí đăng ký trước, loại ML V0 tại Kiểm định** · K=2 → cận dưới **một phía** 97,5% (Bonferroni α=0,05) · **tạm dừng ML candidate này** · chuyển G8 · broker execution NONE · tiền thật KHÓA.

## 1. Việc ghi nhận quyết định ML (trước G8)

| Mục | Kết quả |
|---|---|
| ML V0 | **LOẠI tại Kiểm định**; tiêu chí không đổi; Test-H/Holdout **chưa bao giờ mở** (0 lần nhìn trong sổ cái, không có tệp duyệt) |
| Sổ cái K | họ `K_V2_VOL_V0` **ĐÓNG** (`FAMILY_CLOSED`); K không bị tiêu; mã từ chối mở cửa sổ cho họ đã đóng (test) |
| Registry | `har_ridge` và `lightgbm_regressor` ở **RETIRED**, authority NONE |
| Làm rõ thống kê | với claim "cải thiện > 0": **cận dưới MỘT PHÍA 97,5%** = bách phân vị thứ 2,5 của bootstrap (α/K = 0,025). Mã trả `lower97.5_one_sided`; ngăn Mô hình dùng đúng khóa. Câu chữ "hai phía 97,5%" của spec 1.1.0 (chặt hơn cần) được thay thế cho các họ sau, **không kết quả nào đổi**: cận dưới một phía trên Kiểm định là 0,0082 > 0 và V0 bị loại vì tiêu chí "dương ≥ 75% số năm" (2/3) |
| Thay đổi lúc làm rõ | chạy lại lần chính thức (xác định) rồi mới loại: số liệu giống hệt, thêm khóa một phía |

## 2. Forward evidence: đã xây

| Hạng mục | Nội dung |
|---|---|
| Nhật ký quyết định | mỗi nến M5 **đã đóng** một dòng (hành động, mức sẵn sàng, mã từ chối, giá, spread, ATR, chất lượng dữ liệu, id, phiên bản chiến lược); khóa duy nhất theo nến, dòng đầu thắng, không bịa khi không có quyết định |
| Độ phủ quan sát | nến đã ghi so với nến M5 đóng trong kho; **mọi khoảng trống được liệt kê** (một mẫu forward có khoảng trống âm thầm không phải mẫu forward) |
| Giao thức đăng ký trước | `docs/forward/FORWARD_EVIDENCE_PROTOCOL.md`: kết luận về lợi thế chỉ khi ≥ 100 lệnh đóng cùng phiên bản, ≥ 60 ngày, độ phủ ≥ 95% **và** giả thuyết forward do chủ dự án duyệt (họ K riêng); kế hoạch phân tích cố định (R ròng, bootstrap khối theo ngày, cận một phía, độ nhạy bắt buộc); không điểm dừng sớm |
| API/UI | `GET /api/v2/forward/summary`; ngăn "Bằng chứng": độ phủ, khoảng trống, phễu quyết định, tín hiệu, lệnh (R, Wilson 95%), so với mua-và-giữ, mức tối thiểu và **`claim_allowed`** (hiện luôn CHƯA, kèm lý do) |
| Nhãn bằng chứng | vẫn `UNVALIDATED`; tóm tắt luôn ghi "MÔ TẢ, không phải bằng chứng" và cảnh báo mẫu quá nhỏ |

## 3. Độ tin cậy: đã xây và đã chứng minh

| Hạng mục | Bằng chứng |
|---|---|
| Toàn vẹn CSDL | kiểm tra SQLite khi khởi động, hiển thị ở `/health` (FAIL nếu có vấn đề); test: file hỏng **bị phát hiện** (không bao giờ trông khỏe) |
| Sao lưu | sao lưu trực tuyến mỗi ngày UTC (API sao lưu của SQLite), giữ 14 bản; test: bản sao nhất quán, khôi phục được, không chứa thay đổi sau đó; xoay vòng đúng |
| **Sập tiến trình** | test giết tiến trình thật (`os._exit`): giữa giao dịch ⇒ **không còn nửa nào** (cả vị thế lẫn nhật ký đều mất, không dòng mồ côi); ngay sau commit ⇒ **đủ cả hai** (điền vào chỗ trống tôi đã nêu ở G7) |
| Watchdog vòng nền | lượt cuối, số lỗi, thời gian; FAIL nếu chưa xong lượt nào sau ngưỡng, WARN nếu quá 3×nhịp+10 s hoặc lượt gần nhất lỗi; một lượt lỗi không dừng engine, được đếm và **không bao giờ báo là thành công** |
| Lệnh mở + dữ liệu cũ | `/health` cảnh báo "N lệnh đang mở nhưng dữ liệu M1 cũ: không có nến mới để quản lý SL/TP" |
| Sửa lỗi sản xuất từ G6 | ổ cắm lấy mốc đầu trước vân tay quyết định (sự kiện `paper` không còn bị bỏ sót) |

### Soak 12 phút trên dịch vụ thật (`reports/evidence/g8/soak_12min.json`, chỉ đọc)

| Chỉ số | Kết quả |
|---|---|
| Yêu cầu / lỗi | **2.366 / 0** (7 endpoint, mỗi 2 giây) |
| Độ trễ p50 / p95 / max | health 39 / 63 / 121 ms · state 22 / 60 / 140 ms · paper 3 / 26 / 29 ms · forward 8 / 31 / 107 ms · model 5 / 30 / 39 ms · bars 500 nến 15 / 38 / 62 ms · quote 4 / 27 / 36 ms |
| Bộ nhớ (RSS) | 187,7 → 191,7 MB (min 185,1 · max 200,0), **dốc −8,9 MB/giờ** (không rò), 48 mẫu |
| CPU trung bình / luồng | 10,4% / 72 |
| Ổ cắm | 809 sự kiện (live 645, state 23, heartbeat 140), **0 khoảng hở `seq`** |
| Sức khỏe cuối | DEGRADED chỉ vì mô hình NOT_DEPLOYED (đúng), các kiểm tra khác OK |

(Lần soak 15 phút đầu hoàn tất nhưng **tập lệnh tôi viết bị lỗi in tiếng Việt trên console cp1252 trước khi ghi tệp**; đã sửa để ghi tệp trước và in ASCII, rồi chạy lại 12 phút. Số liệu ở trên là của lần chạy lại.)

### Bài giết dịch vụ thật (hard kill, không hook tắt máy)

Giết tiến trình dịch vụ đang chạy, để tắt khoảng 6,5 phút (collector vẫn chạy), khởi động lại:

| | Trước | Sau khởi động lại |
|---|---|---|
| Nến M5 đã ghi / mong đợi | 8 / 8 (độ phủ 100%) | 9 / 10 (**độ phủ 90%, 1 khoảng trống** hiện đúng vào đoạn tắt) |
| CSDL | n/a | **toàn vẹn**, sao lưu mới tạo, 0 lệnh mở, engine chạy ngay (0 lỗi) |
| Dữ liệu cũ | còn nguyên (không mất, không trùng dòng) | tiếp tục ghi từ nến mới |

Nghĩa là: tắt đột ngột **không mất dữ liệu**, và phần bị bỏ sót **không bị che giấu**: nó hiện thành khoảng trống làm giảm độ phủ (và nếu xảy ra đủ thường, mẫu sẽ không bao giờ đạt ngưỡng 95%).

## 4. Kiểm tra chất lượng

`ruff`, `ruff format`, `mypy --strict` (46 file) sạch · hợp đồng `2.0.0-g8` đồng bộ · **1.727 pytest đạt, 37 test Playwright + axe đạt, 9 test TS đạt**. Test mới: 8 (giao thức forward), 11 (độ tin cậy: toàn vẹn, sao lưu, sập tiến trình, engine, watchdog), thêm API/e2e cho bằng chứng forward; e2e dùng dữ liệu mô phỏng cho ngăn Bằng chứng và kiểm tra server thật `claim_allowed = false`.

## 5. Giới hạn (nói thẳng)

- **Vẫn chưa có lệnh PAPER tự nhiên nào** (tín hiệu hiếm). Phễu quyết định hiện chỉ tích lũy vài giờ nên **chưa nói được gì về tần suất tín hiệu**; con số ETA chỉ có nghĩa khi đã có lệnh đóng.
- Sao lưu **cùng ổ đĩa** với tệp gốc: **không chống được mất ổ/hỏng máy**. Dịch vụ **không tự chạy lại khi máy khởi động lại** (không có Windows service/Task Scheduler). Hai việc này cần chủ dự án (hoặc quyền sửa hệ thống mà tôi không tự ý làm).
- Không có thông báo ra ngoài (e-mail/Telegram) khi watchdog cảnh báo; chỉ hiện ở `/health` và giao diện.
- Soak 12 phút và một lần giết thủ công **không phải** chứng minh ổn định nhiều ngày; chưa soak qua cuối tuần/ngày lễ/chuyển DST/rollover; chưa thử đĩa đầy hay hỏng collector giữa lúc có lệnh mở (chỉ có test đơn vị cho cảnh báo).
- Giao thức forward chưa có giả thuyết được duyệt: dù đủ số liệu, hệ thống vẫn sẽ không cho phép kết luận cho tới khi bạn mở một họ K riêng (ADR mới).
- Độ phủ dùng nến M5 **có trong kho**: nếu collector rớt nến thì khoảng trống đó không bị đếm là thiếu (nằm ngoài phạm vi kiểm tra của V2 này; V1 có kiểm toán riêng).

## 6. Cần bạn

1. **Sao lưu ra ổ khác/đám mây** cho `data/backups/` và `data/paper.sqlite3` (hoặc cho tôi biết đường dẫn muốn dùng).
2. **Tự khởi động dịch vụ V2** khi máy bật (Task Scheduler/service): bạn muốn tôi tạo tác vụ không (cần quyền, sẽ nằm ngoài repo)?
3. Có muốn **thông báo ngoài** (Telegram/e-mail) khi watchdog cảnh báo không (cần token của bạn)?
4. Khi nào mở **họ K cho một giả thuyết forward** (ADR mới)? Chưa có thì mọi quan sát vẫn chỉ là mô tả.

Forward evidence tiếp tục chạy song song, không cần sprint riêng.
