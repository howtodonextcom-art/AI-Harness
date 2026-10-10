# Bàn giao dịch PAPER: báo cáo hoàn tất (TRADING_DESK_FINAL_COMPLETION)

Phạm vi: bàn giao dịch `/trade` là sản phẩm **PAPER** dùng được hằng ngày. Không có lệnh MT5 nào được gửi, DEMO và FUNDED vẫn KHÓA, không có tuyên bố về edge, không đụng TEST-H/HOLDOUT, không chỉnh ngưỡng baseline, mặc định vẫn là v1.1.0 (v1.2.0/v1.2.1 cài sẵn, `AVAILABLE / INACTIVE`), không thực hiện v1.3 và không dùng cửa sổ E3/E4.

HEAD khởi đầu `6ac05da`. Các commit của sprint: `b323b28` (lõi), `3335b1a` (giao diện + nghiệm thu trình duyệt), `4c63243` (parity M1, reachability, resume), `4d8a371`, `c4b883e` (sửa theo review độc lập).

## 1. Bằng chứng từng tính năng

Cột: **BE** backend · **UI** giao diện · **API** qua API thật · **REPLAY** nghiệm thu replay (dữ liệu FTMO đã đốt qua `TradeEngine`/`PaperDesk` thật) · **LIVE** đã xác minh trên dữ liệu sống · **OWNER** dùng được ngay · LIMIT = giới hạn.

| Tính năng | BE | UI | API | REPLAY | LIVE | OWNER | Giới hạn |
|---|---|---|---|---|---|---|---|
| Hero BUY/SELL/WAIT/ARMED/OPEN/EXITED tính ở server | ✔ | ✔ | ✔ | ✔ | ✔ (MARKET CLOSED, WAIT trước đó) | ✔ | Chưa thấy BUY/SELL **live** (tần suất thấp) |
| WAIT hữu ích (chuỗi tầng, "Waiting for") + hàng bấm đổi khung | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | Mô tả trạng thái, không dự báo |
| Kế hoạch Entry/SL/TP/RR/rủi ro/lot (spec broker) | ✔ | ✔ | ✔ | ✔ | — | ✔ | Plan chỉ xuất hiện khi có setup |
| Trạng thái lỗi riêng (API down, stale, MT5 mất, thiếu spec, đóng cửa, paper hỏng, hai writer, hết hạn) | ✔ | ✔ | ✔ | ✔ (14 ca trình duyệt) | một phần (đóng cửa) | ✔ | UNAVAILABLE ≠ WAIT |
| Biểu đồ M1–H4, marker/EXIT từ đối tượng server, đường kế hoạch, ma trận khung | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | marker snap theo nến M5 trigger (lệch trên M1) |
| Mở paper có xác nhận, server kiểm lại độc lập | ✔ | ✔ | ✔ | ✔ | — | ✔ | |
| Thẻ vị thế (MFE/MAE, vào kế hoạch vs khớp), đóng tay đúng một lần | ✔ | ✔ | ✔ | ✔ | — | ✔ | |
| Thoát tự động SL / TP / TIME | ✔ | ✔ | ✔ | ✔ (cả BUY và SELL) | — | ✔ | |
| Journal (đủ cột, nguồn gốc, banner replay, báo desk lỗi) | ✔ | ✔ | ✔ | ✔ | — | ✔ | |
| Trạng thái paper hỏng → FAIL CLOSED | ✔ | ✔ | ✔ | ✔ | — | ✔ | |
| Khôi phục từ journal (dry-run rồi `--apply`) | ✔ | CLI | — | ✔ | — | ✔ (CLI) | cần dừng stack |
| Một tiến trình ghi (khóa OS, metadata, stale) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | |
| Crash-consistency (kiểm thử cắm lỗi từng khe) | ✔ | — | — | ✔ | — | — | mô phỏng trong tiến trình, chưa có test kill tiến trình/ghi dở |
| Chính sách cuối tuần/đóng cửa (mặc định chặn mở mới sát giờ đóng) | ✔ | ✔ | ✔ | ✔ | — | ✔ | |
| Parity cadence M1 live ↔ M5 ↔ `evaluate` | ✔ | — | — | ✔ | — | — | xem mục 3 |
| Reachability BUY và SELL qua hàm nhãn thật | ✔ | — | — | ✔ | — | — | dữ liệu đã đốt, test cần `data/market` |
| Cô lập namespace LIVE/REPLAY | ✔ | ✔ | ✔ | ✔ | ✔ | — | |
| Cảnh báo (số hôm nay, cuối, Telegram?, file; không bí mật; không lặp) | ✔ | ✔ | ✔ | ✔ | ✔ (FILE_FALLBACK) | ✔ | Telegram chưa cấu hình |
| Phễu + phân bố từ chối từ telemetry server | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | |
| Forward acceptance F0–F4 | ✔ | ✔ | ✔ | ✔ | F0 | ✔ | Không giả F3/F4 |
| Hiển thị phiên bản chiến lược ACTIVE/INACTIVE | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | |
| Tin tức NOT VERIFIED | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | Chưa có lịch kinh tế |
| Hợp đồng frontend ↔ backend (golden thật, tsc + pytest) | ✔ | ✔ | — | ✔ | — | — | |
| Evaluator batch: chặn fan-out, ngắt rồi tiếp tục = chạy liền | ✔ | — | — | ✔ | — | — | |
| Bot DEMO cũ KHÓA; `/legacy` ghi LEGACY / NOT ACTIVE | ✔ | ✔ | — | — | — | ✔ | |

## 2. Bằng chứng trình duyệt (ACCEPTANCE REPLAY, KHÔNG PHẢI LIVE)

`apps/dashboard/e2e-acceptance/desk.spec.ts` (18 ca) chạy build production trong Chromium với API thật trên dữ liệu đã đốt (`scripts/serve_acceptance.py`), ảnh trong `docs/reports/img/trading-desk/` (mỗi ảnh tự ghi "ACCEPTANCE REPLAY — NOT LIVE" trên trang; ảnh `00` là LIVE thật):

| # | Ảnh | # | Ảnh |
|---|---|---|---|
| 00 | LIVE: thị trường đóng cửa | 10 | STALE |
| 01 | WAIT | 11 | EXPIRED SETUP |
| 02 | BUY thật (2025-12-05 14:45, v1.2.1) | 12 | PAPER_STATE_ERROR |
| 03 | Vị thế paper đang mở | 13 | Hai tiến trình ghi |
| 04 | SELL thật (2025-08-14 18:05, v1.2.1) | 14 | API down |
| 05 | Thoát TAKE_PROFIT (+1.987R) | 15 | MARKET CLOSED |
| 06 | Đóng tay | 16 | CLOSURE_NEAR (chính sách) |
| 07 | Thoát STOP_LOSS | 17 | Di động 390×844 |
| 08 | Thoát TIME_EXIT | 18 | Zoom 200% |
| 09 | Journal | | |

Không có JSON BUY/SELL viết tay: hero/kế hoạch/marker/journal đều là serialization của backend. Bộ e2e mock (89 test) dùng golden sinh từ cùng backend.

## 3. Phát hiện đo lường quan trọng: cadence M1 so với M5

Tần suất baseline trước đây (0,1–0,23 setup/ngày) được đo **chỉ tại thời điểm đóng nến M5**. Ở cadence live (engine bước mỗi M1) có điều khác: cổng thực thi M1 của v1.1.0 ("nến M1 ngược mạnh → NO_TRIGGER") bật/tắt giữa các nến M5, nên một tín hiệu có thể xuất hiện lúc 11:02 mà không có ở 11:00. Đã đo: tại mọi thời điểm đóng M5, engine cadence M1, engine cadence M5 và `evaluate` độc lập **khớp tuyệt đối** (0 sai lệch); các quyết định hành động chỉ-giữa-nến được liệt kê riêng (không bị ẩn). Hệ quả: tần suất live **có thể cao hơn** số đã công bố. Không chỉnh gì cho điều này (không tối ưu để tăng tần suất); đây là lưu ý đo lường.

Kết quả đã chạy: v1.1.0 2025-08-14 06:00–20:00: 840 bước M1, 168 thời điểm M5, 0 sai lệch, 2 quyết định chỉ-giữa-nến (1 setup); v1.2.1 2025-12-05 12:00–18:00: 360 bước, 72 thời điểm, 0 sai lệch, 0 chỉ-giữa-nến. Tuần 2025-08-11→08-16 (v1.1.0): 6 710 bước M1, 1 342 thời điểm M5, 0 sai lệch, 2 quyết định hành động tại thời điểm đóng M5 và 4 bước M1 hành động chỉ-giữa-nến (2 setup riêng biệt), 0 cảnh báo trùng. Nghĩa là trong tuần đó có thêm 2 setup mà phép đo ở thời điểm đóng M5 không thấy, so với 2 setup đã thấy.

## 4. Kiểm thử và cổng chất lượng

| Cổng | Kết quả |
|---|---|
| `ruff check` / `ruff format --check` | PASS |
| `mypy --strict` (239 file nguồn) | PASS |
| `pytest -m "not mt5"` | PASS: 2535 passed, 1 SKIP (symlink cần quyền trên Windows), 3 deselected |
| `pytest -m mt5` | PASS: 3 passed |
| Dashboard `eslint`, `tsc`, `next build` | PASS |
| Playwright e2e mock (golden thật) | PASS: 89 |
| Playwright nghiệm thu trình duyệt (replay API thật) | PASS: 18 |
| XFAIL | 0 |

Test dài cần `data/market` (reachability, parity, vòng đời, resume) tự SKIP nếu thiếu dữ liệu; CI không có dữ liệu đã đốt nên chạy phần hợp đồng không cần dữ liệu (`test_contract_goldens.py`).

## 5. Đánh giá độc lập

Một subagent tách biệt (đọc-chỉ, brief trung lập) rà soát toàn bộ phần thay đổi. Kết quả xác nhận được và cách xử lý:

| Mức | Phát hiện | Xử lý |
|---|---|---|
| HIGH | Hero hiện "BUY READY" khi desk paper lỗi | Sửa: `PAPER_STATE_ERROR` đưa hero về `UNAVAILABLE`; test cả backend và trình duyệt |
| HIGH | `scripts/trade_acceptance_replay.py` hỏng (desk LIVE trên nguồn replay) | Sửa + test chạy script thật |
| MEDIUM | Journal không báo desk lỗi (hiện "chưa có lệnh") | Thêm `desk_fault` + cảnh báo đỏ |
| MEDIUM | Mở lệnh dùng quote cache cũ | Đọc lại quote mới và từ chối nếu stale |
| MEDIUM | Thẻ xác nhận không gắn với setup | Gắn với setup/SL/TP/rủi ro; tự đóng khi đổi |
| MEDIUM | Lỗi engine không bao giờ xóa, giữ quyết định cũ | Xóa khi hồi phục; mất quyết định cũ khi lỗi |
| nghi ngờ | Không đọc được snapshot → desk rỗng im lặng | Đặt `load_error` (fail closed) |
| LOW | Mã lý do journal sai (`CLOSURE_CLOSE`, `INVALIDATED`) | Sửa |

Chưa sửa (LOW, ghi nhận): marker tín hiệu snap theo nến M5 trigger nên lệch trên M1 và hiện trên nến còn đang hình thành ở M15+; dòng journal cuối bị cắt dở có thể nuốt dòng ghi tiếp theo (cần mất điện giữa chừng; khởi động lại tự hủy orphan); `paper.modify` chỉ lưu cuối `process_bars` và snapshot không `fsync` (break-even/trailing tắt mặc định); desk lỗi không quản lý vị thế đang mở (fail-closed có chủ đích, phải chạy khôi phục); tuổi dữ liệu đóng băng giữa các lần tính lại; thông báo lỗi có thể chứa đường dẫn cục bộ (không có token/ID tài khoản); ngày governor theo UTC; `claim_root` kiểm-rồi-ghi.

## 6. Giới hạn trung thực

* **Chưa có setup live thật**: forward acceptance ở **F0**. Replay không nâng được mức này. Phán quyết: `LIVE SETUP ACCEPTANCE PENDING`.
* Mọi BUY/SELL đã xem là từ dữ liệu lịch sử đã đốt. Quote replay (close M1 + spread nến) khác quote live.
* Crash-consistency được kiểm bằng cắm lỗi trong tiến trình; chưa kill tiến trình thật hay mô phỏng ghi dở.
* Không có edge được chứng minh; kết quả mô phỏng nhỏ không chứng minh gì.
* DEMO chưa thể mở: không đủ điều kiện (forward F0). Bản nháp `docs/prompts/NEXT_DEMO_EXECUTION_PROMPT.md` giữ nguyên, không thực thi.
