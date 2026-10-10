# WORKSTATION: báo cáo hoàn tất (bàn làm việc XAUUSD trên desktop, PAPER ONLY)

> Viết cho: chủ dự án (đọc tiếng Việt, hiểu giao dịch) và các agent sau này cần tiếp tục mà không phải đoán.
> Ngày 2026-10-11, thị trường đóng cuối tuần. Số liệu lấy từ lệnh chạy lại trong phiên viết báo cáo này (mục 19) và từ `git`/`gh`.
> Nhãn mỗi mục: **ĐÃ KIỂM** (có bằng chứng chạy được), **CHƯA KIỂM**, **CHƯA LÀM**.
> Ràng buộc giữ nguyên: PAPER ONLY; DEMO và FUNDED khoá; không đụng v1.1.0, ngưỡng, holdout, Test-H; không tuyên bố edge.

## 0. Tóm tắt

* **Phán quyết:** DESKTOP TRADING WORKSTATION FUNCTIONALLY COMPLETE — FORWARD LIVE SIGNAL OBSERVATION PENDING. Pha di động: SHOULD WAIT.
* **Ba điều chưa xong:** (1) chưa thấy tín hiệu LIVE nào; (2) độ phủ quyết định chỉ **48,64%** (232/477) < 95%, nên bằng chứng forward chưa hợp lệ;
  (3) tin tức ở trạng thái BLOCKED chưa từng quan sát LIVE.
* **Phần không làm:** chỉ báo, BOS/CHoCH, chế độ 2 chart; không A/B cho công cụ vẽ. Bộ não chính tắc mới ở mức thiết kế.
* **Quyết định cần chủ dự án:** nguồn tin có SLA (ví dụ Finnhub, cần key) và có bật quản lý vị thế tự động hay không (đó là thay đổi alpha).
* **Sự cố của chính sprint:** commit NEWS-01 (`e8e8fc3`) làm CI đỏ vì tôi chưa chạy bộ test Python đầy đủ trước khi push (mục 1).

## 1. Điểm xuất phát và điểm kết thúc — ĐÃ KIỂM

* Xuất phát `4d85be4` (TRADE-08, dùng PAPER hằng ngày). HEAD khi chạy lại các cổng: `5ad712e` (`git log 4d85be4..HEAD` có 7 commit).
* Commit: `b90a7e7` DATA-01, `17f3d8e` DATA-02, `55add95` TELEMETRY-01, `e8e8fc3` NEWS-01, `a614533` DRAW-01/CONSIST-01,
  `5cbb573` BROWSER-CI-01/POSITION-01/BRAIN-01, `5ad712e` sửa red team + báo cáo.
* CI (`gh run`): `5cbb573` và `5ad712e` xanh 8/8 job (ma trận 3 Python x 2 hệ điều hành, dashboard, trình duyệt). `e8e8fc3` đỏ ở cả 6 job Python:
  6 test của `tests/unit/api/test_trade_news_wiring.py` còn mã hoá từ vựng 3 trạng thái tin. Nguyên nhân quy trình: push sau khi chỉ chạy một phần test.
  Đã sửa ở `5cbb573`; từ đó bộ test đầy đủ chạy nền trước mỗi lần push.
* Báo cáo này nằm trong commit sau `5ad712e`; hash cuối và kết quả CI của nó ghi ở phần cuối (mục 26).

## 2. Các pha — ĐÃ KIỂM

| Pha | Kết quả |
|---|---|
| A. Dữ liệu | Xong: nguyên nhân gốc, chính sách sửa có kiểm toán, công cụ kiểm độc lập, giám sát mọi ổ |
| B. Độ phủ telemetry | Xong phần đo và cổng 95%; giá trị đo hiện thấp (mục 4) |
| C. Tin tức | Xong lõi (nguồn thật, 6 trạng thái, job nền, UI, marker); còn hạn chế nguồn |
| D. Phân tích chart | Xong công cụ vẽ, quản lý, R:R thủ công, mức tuần/phiên, sửa gốc resize. **CHƯA LÀM** chỉ báo, cấu trúc nâng cao, 2 chart |
| E. Nhất quán | Xong: một múi giờ, tuổi dữ liệu do máy chủ đo, trang control, bảng sức khoẻ |
| F. CI trình duyệt | Xong: job `dashboard-e2e` xanh trên GitHub |
| G. Quản lý vị thế | Xong ở dạng kiểm toán tài liệu |
| H. Bộ não chính tắc | Xong ở dạng thiết kế; **CHƯA LÀM** adapter và harness |

## 3. Parity nến (DATA-01/02) — ĐÃ KIỂM

* Nguyên nhân: terminal sửa muộn `tick_volume` (M1 13:54 UTC lưu 238, terminal 239; cùng +1 ở M5/M15/M30/H1). Ledger chỉ-thêm nên không ghi đè; cửa sổ đối chiếu
  chỉ 200 nến nên không bao giờ sửa; sức khoẻ feed báo DEGRADED mãi.
* Phân loại: LATE TICK, FORMING-BAR ERROR, UNKNOWN (giá/spread/volume quá ngưỡng), REPAIR BUG (thiếu trong kho), BOUNDARY ERROR.
* Chính sách xác định: chỉ nến đã ổn định, chỉ lệch `tick_volume` nhỏ (3 tick hoặc 0,5%), qua đường `BAR_REPAIRED` có kiểm toán (giá trị cũ/mới, lý do, thời điểm).
  Giá, spread, thiếu nến không bao giờ tự sửa. Đối chiếu sâu 3 ngày lúc khởi động.
* Chạy lại hôm nay: `scripts/audit_bar_parity.py --days 14` (copy_rates_range độc lập, chỉ đọc): **0 chênh lệch, 0 không giải thích được, 0 trùng, 0 lệch biên**.
* Ledger tick (205M tick) được kiểm lại tính toàn vẹn mà không tải lại. Ledger tick không dùng làm chuẩn volume: MT5 chỉ đếm tick đổi giá (40/40 phút mẫu lệch).
* Đĩa: collector giờ theo dõi mọi ổ; C: (MT5 và Windows) còn ~14,8 GB hiện cảnh báo (`disk` = WARN trong bảng sức khoẻ LIVE).

## 4. Độ phủ telemetry (TELEMETRY-01) — ĐÃ KIỂM

* Nhịp thật: một dòng quyết định cho mỗi nến M1 đóng mới khi thị trường mở; engine không ghi bù phần đã lỡ.
* Đo lại trên API LIVE hôm nay: **232/477 = 48,64%**, 2 khoảng thiếu (30 và 215 phút) trùng với lúc tiến trình engine không chạy khi restart.
* Cổng cứng: dưới 95% thì forward acceptance nói "FORWARD EVIDENCE INCOMPLETE" (LIVE hôm nay: `level=F0`, `evidence_complete=false`).
* Hạn chế đã biết: kỳ vọng lấy từ nến đã lưu nên không thấy nến collector lỡ; cửa sổ bắt đầu từ dòng telemetry đầu tiên (mục 22).

## 5. Nguồn tin và trạng thái LIVE (NEWS-01) — ĐÃ KIỂM, một phần CHƯA KIỂM

* Rubric định trước, 4 ứng viên (`NEWS_SOURCE_DECISION.md`): chọn Forex Factory weekly JSON. Giới hạn: không chính thức, chỉ tuần hiện tại, không published/updated,
  bị giới hạn tốc độ (đã gặp HTTP 429 khi thử thật), chưa có nguồn thứ hai. Finnhub cần key nên chưa đánh giá được; Trading Economics đã ngừng guest.
* Trường point-in-time: `time_utc` (sự kiện), `available_at` (lần đầu ta thấy), `currency`, `source`, `published_at` (trống khi nguồn không có), `ingested_at`, `updated_at`, impact, title.
  File 4 cột cũ vẫn đọc được.
* Sáu trạng thái: CLEAR/BLOCKED/UNKNOWN/NOT_CONFIGURED/STALE/ERROR; chỉ CLEAR là xanh; chiến lược vẫn chỉ thấy CLEAR/BLOCKED/UNKNOWN.
  Tin mạnh trong 90 phút tới làm dải TIN chuyển vàng và nói khi nào cửa sổ chặn mở.
* LIVE: `data/news/calendar.csv` 24 sự kiện USD/All; API LIVE hôm nay trả CLEAR. **BLOCKED, STALE, ERROR chưa quan sát LIVE** (chỉ unit test và mock).
  Job `scripts/run_news_refresher.py` chạy như tiến trình con của supervisor.

## 6. Bổ sung cho chart desktop (DRAW-01) — ĐÃ KIỂM

Đường xu hướng, tia, đường dọc, vùng, Fibonacci (7 mức), R:R thủ công ("PHÂN TÍCH THỦ CÔNG — KHÔNG PHẢI TÍN HIỆU"), PWH/PWL, cao/thấp phiên Á/Âu/Mỹ, đường tin.
Kéo điểm, kéo cả nét, Delete, Esc huỷ, khoá; bảng quản lý (tên, khoá, xoá, xoá tất cả có xác nhận).
**Sửa gốc resize/maximize:** sau khi đổi kích thước, khoảng nhìn của người dùng được khôi phục (trước đó nến giữ bề rộng nên chừa trống bên trái); test mở rộng rồi thu nhỏ đạt.
Lỗi thật tìm ra khi làm: lightweight-charts nuốt cú bấm thứ hai trong 500 ms ở vị trí khác, nên điểm thứ hai của đường bị mất; chuyển sang click gốc của trình duyệt.

## 7. Kết quả A/B — ĐÃ KIỂM (chỉ một A/B)

* Marker tin trên chart: 3 thiết kế, reviewer mù, nhãn xáo trộn. Đường dọc + nhãn **14/30** (thắng), dải bóng 13/30, cờ trên trục 12/30. Lỗi của người thắng đã sửa
  (thêm dải cửa sổ chặn cho tin mạnh, cắt nhãn, đẩy nhãn khi sát mép hoặc chồng nhau).
* **CHƯA LÀM** A/B cho công cụ vẽ, chỉ báo, lớp cấu trúc.

## 8. Lưu nét vẽ — ĐÃ KIỂM

Khoá `xau-edge:v3:{LIVE|REPLAY}:XAUUSD:drawings`; điểm là (giây UTC thật, giá) nên đổi múi giờ hay khung giờ không làm nét vẽ dịch; ID ổn định; tối đa 60; dữ liệu hỏng bị bỏ qua, không sập chart;
không bao giờ vào quyết định, cảnh báo, nhật ký hay endpoint. Test: giữ qua reload, đổi khung, đổi múi giờ, điều hướng sang /journal rồi quay lại (cả trên LIVE thật). Hạn chế: mọi replay dùng chung một khoá (mục 22).

## 9. Lớp cấu trúc thị trường — ĐÃ KIỂM / CHƯA LÀM

Có sẵn: kháng cự/hỗ trợ M15, PDH/PDL. Mới: PWH/PWL, cao/thấp phiên (test với dữ liệu có khoảng nghỉ cuối tuần). **CHƯA LÀM** BOS/CHoCH và swing overlay (không có prototype hay đánh giá).

## 10. Quyết định về chỉ báo — CHƯA LÀM (có chủ ý)

Không thêm chỉ báo nào. Lý do: chưa có rubric hay A/B chứng minh chỉ báo giúp ích, và thêm chỉ báo dễ bị đọc như tín hiệu. Chế độ 2 chart (H1+M5) không làm vì chưa chứng minh cần thiết. Cả hai vẫn mở.

## 11. Múi giờ nhất quán (CONSIST-01) — ĐÃ KIỂM

Một khoá `xau-edge.market.zone` cho `/trade`, `/market`, `/journal`, `/control`; hook `useDisplayZone` đọc khi tải và theo dõi tab khác qua sự kiện `storage`; giờ ở /control và /journal theo múi giờ này.
Test: đặt ở /market thì journal và trade theo; đổi ở tab khác thì tab này theo.

## 12. Ngữ nghĩa tuổi dữ liệu — ĐÃ KIỂM

Máy chủ đo bốn loại: QUOTE AGE, LAST BAR AGE, COLLECTOR HEARTBEAT AGE, LAST DECISION AGE; trạng thái FRESH/STALE/MARKET_CLOSED/UNAVAILABLE/REPLAY.
Thị trường đóng thì báo giá và nến cũ là MARKET_CLOSED, không phải STALE, còn nhịp tim collector vẫn phải mới. Tuổi đo lại lúc phục vụ (red team phát hiện bản đầu bị đóng băng theo lần tính cuối; đã sửa và có test).
LIVE hôm nay: quote/bar/decision = MARKET_CLOSED, heartbeat = FRESH.

## 13. Trang /control — ĐÃ KIỂM

API không bật điều khiển web: trang hiện "CONTROL DISABLED", dừng poll hoàn toàn (test đếm request không tăng trong 7 giây), có nút "Kiểm tra lại". Hết cảnh "quay mãi" và 503 liên tục.

## 14. Sức khoẻ hệ thống — ĐÃ KIỂM

Thẻ trong tab Hệ thống: MT5, collector, nến khớp terminal, lưu tick, ổ đĩa, API, dashboard, độ phủ quyết định, tin tức, quyền ghi bàn PAPER, phiên bản chiến lược, nguồn dữ liệu; mỗi dòng OK/WARN/ERROR/UNKNOWN kèm lý do.
LIVE hôm nay: 9 dòng OK, `disk` WARN (ổ C:), `decision_coverage` WARN (48,64%). Replay: các dòng collector là UNKNOWN, không phải OK.

## 15. CI trình duyệt — ĐÃ KIỂM

Job `dashboard-e2e` (Playwright mock API, goldens do backend thật sinh, axe) xanh trên GitHub ở `5cbb573` và `5ad712e`. Thêm goldens `closed_sl` và `closed_time` do replay thật (script dừng nếu lý do thoát không đúng).
`states.spec.ts` kiểm từng trạng thái WAIT/BUY/SELL/HOLD/TP/SL/TIME/INVALIDATED/UNAVAILABLE (stale, hỏng trạng thái paper, xung đột quyền ghi, API sập).

## 16. Kiểm toán quản lý vị thế — ĐÃ KIỂM (tài liệu)

`POSITION_MANAGEMENT_AUDIT.md`: đã có SL cố định, TP1, hạn giữ 120 phút, đóng tay, giới hạn rủi ro, nhật ký. Hoà vốn và trailing có mã nhưng TẮT mặc định; chốt từng phần chưa có mã. Bật chúng là thay đổi alpha (cần quản trị), không phải UX.

## 17. Kiến trúc bộ não chính tắc — CHƯA LÀM (chỉ thiết kế)

`docs/architecture/canonical-brain.md`: xác nhận từ mã có HAI bộ não (Trading Core cho /trade và PAPER; `signals.engine` cho bot DEMO legacy). Cầu `trading/adapter.py` có nhưng chỉ được test, không nối vào bot.
Thiết kế TradeEngine → TradingSignal → Execution Intent → adapter Paper/Demo/Funded, hợp đồng tín hiệu, decision-parity harness (ghi rõ ánh xạ lý do từ chối đang mất thông tin: 7 lý do gộp vào một), phân loại KEEP/ADAPT/DEPRECATE/DELETE LATER.
Chưa viết adapter hay harness.

## 18. Kế hoạch di chuyển demo — CHƯA LÀM

Cổng 7 điều kiện (mục 6 của tài liệu bộ não): dry-run bằng TradingSignal, parity 0 khác biệt ít nhất 1 tuần LIVE, độ phủ ≥ 95%, dữ liệu và tin sạch, forward từ F2, chủ dự án xác nhận bằng văn bản, FUNDED vẫn khoá. Chưa mở.

## 19. Kiểm thử — ĐÃ KIỂM (chạy lại trong phiên này)

| Cổng | Kết quả |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 656 files already formatted |
| `uv run mypy` (cấu hình repo, như CI) | Success: no issues found in 443 source files |
| `uv run pytest -m "not mt5"` | **2601 passed, 1 skipped, 3 deselected** trong 8 phút 57 giây (skip: symlink cần quyền trên Windows) |
| `pytest -m mt5` | KHÔNG chạy (nối terminal FTMO thật); thay bằng `audit_bar_parity.py` chỉ đọc: 0 chênh lệch / 14 ngày / 6 khung |
| `eslint .`, `tsc --noEmit`, `next build` | sạch, sạch, thành công |
| Playwright mock (gồm 3 test axe) | **291 passed** (20 file) |
| Playwright acceptance trên backend thật (replay) | **31 passed** |
| CI GitHub `5ad712e` | 8/8 xanh |

Tăng so với đầu sprint: Python 2566 → 2601 test; Playwright mock 238 → 291.

## 20. Bằng chứng trình duyệt — ĐÃ KIỂM

* LIVE :3000/:8000 bằng trình duyệt thật (build mới nhất): dải TIN, thẻ Hệ thống (tuổi 4 loại, 12 dòng sức khoẻ), độ phủ 48,64%, vẽ xu hướng/vùng/R:R/Fibonacci, nét vẽ và cảnh báo còn nguyên sau khi sang /journal rồi quay lại.
* Luồng phân tích chart (mở /trade, đọc quyết định, đổi khung, vẽ xu hướng, vẽ vùng, R:R, xem S/R, xem tin, đặt cảnh báo, journal, quay lại): 8 bước đầu đạt trong ~4,3 giây tự động; bước journal và quay lại đạt riêng.
  Chưa đo thời gian người thật.
* Thử năm giây (người chấm mới, 4 ảnh 1440x900): trả lời đúng symbol, giá, mở/đóng, hành động, Entry/SL/TP, vị thế, LIVE hay replay. Điểm yếu thật: thiên hướng thị trường không hiện bằng chữ khi có BUY/SELL hoặc thị trường đóng;
  "CPI sau 40 phút" cạnh "chưa vào cửa sổ tin" mơ hồ (đã sửa: dải vàng và nói khi nào cửa sổ chặn mở); hộp R:R thủ công cạnh vị thế thật dễ rối (đã gắn nhãn không phải tín hiệu); cảnh báo Telegram màu cam tranh với kết luận.
* Hiệu năng LIVE (10 giây): 60 FPS, 564 nút DOM, 0 long task, 16 request/10 giây, heap 11 MB, chart không bị tạo lại. Đo một lần, chưa đo với nhiều nét vẽ.

## 21. Red team (reviewer riêng, chỉ đọc mã) — ĐÃ KIỂM

Không có HIGH; 7 MEDIUM, 5 LOW. Đã sửa: mốc làm mới ở tương lai thành ERROR; lịch rỗng là UNKNOWN; độ tươi lấy từ bản ghi của job cập nhật (không phải mtime); ngày feed không offset bị từ chối; tuần cụt và tuần nối không liền bị từ chối;
chuyển hướng https sang http bị chặn; tuổi báo giá/nến đo lại lúc phục vụ; ngưỡng STALE 48 giờ thành 12 giờ; timer của chart dừng khi tab ẩn. Mỗi lỗi có test hồi quy.
Chưa sửa: xem mục 22. Chưa có vòng red team thứ hai sau các sửa.

## 22. Hạn chế còn lại — ĐÃ KIỂM (liệt kê trung thực)

* Marker "TP" bị cắt ở mép phải (TRADE-08): thử với lối thoát ở nến mới nhất trên 1440x900 thì nhãn hiện đủ; không tái hiện, chưa kết luận hết trên mọi mức zoom.
* Thiên hướng thị trường không hiện bằng chữ trong màn BUY/SELL và đóng cửa (hành động đã mang hướng).
* Độ phủ quyết định: không thấy nến collector lỡ; cửa sổ bắt đầu từ dòng telemetry đầu tiên.
* Nét vẽ REPLAY dùng chung một khoá cho mọi bộ replay.
* Tin: một nguồn không chính thức, chỉ tuần hiện tại; hạ impact hay thiếu hàng ở nguồn không tự phát hiện; tin đột xuất không bao giờ cảnh báo; marker chỉ có tin trong 24 giờ tới.
* Sửa volume muộn có trần mỗi lần (3 tick hoặc 0,5%) nhưng không có trần tích luỹ; quyết định cũ đã ghi có thể không tái lập chính xác.
* `mypy --strict scripts` còn 37 lỗi ở script cũ (CI chạy `mypy` theo cấu hình repo, xanh).

## 23. Tín hiệu LIVE thật — ĐÃ KIỂM

**LIVE ACTIONABLE SIGNAL NOT YET OBSERVED.** Thị trường đóng suốt phiên; forward acceptance F0, và vì độ phủ 48,64% < 95% nó đang nói "FORWARD EVIDENCE INCOMPLETE". Replay không nâng được mức F.

## 24. Trạng thái edge — ĐÃ KIỂM

Không có edge được kiểm định: Edge Program V1 (B) NO EDGE WITHIN BUDGET, V2 Batch A 0/20; chiến lược `xau_mtf_baseline v1.1.0`, nhãn UNVALIDATED_OPERATIONAL_BASELINE. Sprint này không tuyên bố edge.

## 25. Cổng tiếp theo

1. Giữ engine chạy liên tục lúc thị trường mở để độ phủ lên ≥ 95%.
2. Quan sát một setup LIVE thật và, khi có tin mạnh, trạng thái BLOCKED thật.
3. Viết adapter và decision-parity harness (BRAIN-01) ở chế độ dry-run, rồi mới bàn cổng DEMO.
4. Chủ dự án quyết định: nguồn tin có SLA; có bật quản lý vị thế tự động hay không.

---

## Bảng kiểm kê dữ liệu thời gian thực

| Dữ liệu | Nguồn | Tần suất | Trạng thái | Ghi chú |
|---|---|---|---|---|
| Nến M1..H4 | collector MT5 → `data/market` | mỗi nến đóng | THẬT, 0 chênh lệch với terminal | chỉ sửa tick_volume muộn, có kiểm toán |
| Báo giá | collector → `live.json` | ~giây | THẬT | MARKET_CLOSED khi thị trường đóng |
| Tick | collector → tick ledger | liên tục | THẬT, trễ ~3 giây | 205M tick |
| Quyết định | TradeEngine (API) | mỗi nến M1 mới | THẬT, độ phủ 48,64% | không ghi bù |
| Lịch tin | Forex Factory weekly → `data/news/calendar.csv` | làm mới ít nhất mỗi 4 giờ | THẬT, nguồn không chính thức | BLOCKED chưa thấy LIVE |
| Tuổi dữ liệu, sức khoẻ | máy chủ đo mỗi lần phục vụ | mỗi request | THẬT | |
| Cảnh báo giá, nét vẽ | trình duyệt (localStorage) | — | của người dùng | không ảnh hưởng quyết định |

## Bảng kiểm kê tính năng desktop

| Tính năng | Có | Ghi chú |
|---|---|---|
| Hành động CHỜ/MUA/BÁN/GIỮ/THOÁT/KHÔNG KHẢ DỤNG, lý do, khi nào | CÓ | TRADE-08 |
| Entry/SL/TP/RR, hạn hiệu lực | CÓ | |
| Bàn PAPER, mở/đóng có xác nhận, nhật ký, journal → chart | CÓ | |
| Cảnh báo giá, đường ngang, thước đo | CÓ | |
| Đường xu hướng, tia, đường dọc, vùng, Fibonacci, R:R thủ công | CÓ | DRAW-01 |
| Quản lý nét vẽ, khoá, lưu theo nguồn | CÓ | |
| PWH/PWL, cao/thấp phiên, S/R, PDH/PDL | CÓ | |
| Tin: dải TIN, thẻ, đường dọc và dải cửa sổ | CÓ | NEWS-01 |
| Một múi giờ toàn site; tuổi dữ liệu 4 loại; sức khoẻ hệ thống; độ phủ quyết định | CÓ | |
| Chỉ báo, BOS/CHoCH, 2 chart | KHÔNG | chưa làm, chưa đánh giá |
| Quản lý vị thế tự động hoặc nút bảo vệ lãi | KHÔNG | thay đổi alpha |

## Ma trận hoàn tất

| Hạng mục | Mức | Ghi chú |
|---|---|---|
| DATA PARITY | COMPLETE | 0 chênh lệch, chính sách có kiểm toán, công cụ độc lập |
| TELEMETRY COVERAGE | PARTIAL | đo và cổng xong; giá trị đo 48,64% < 95% |
| NEWS | PARTIAL | nguồn thật và UI; nguồn không chính thức; BLOCKED chưa thấy LIVE |
| REAL-TIME DATA | COMPLETE | |
| SIGNAL UI | COMPLETE | |
| DESKTOP CHART | COMPLETE | resize đã sửa gốc |
| DRAWINGS | COMPLETE | |
| ANALYSIS | PARTIAL | có mức giá/phiên/tuần; không chỉ báo, cấu trúc nâng cao, 2 chart |
| JOURNAL | COMPLETE | |
| ALERTS | COMPLETE | |
| SYSTEM HEALTH | COMPLETE | |
| POSITION MANAGEMENT | PARTIAL | SL/TP/hạn giữ cố định; tự động bảo vệ lãi tắt (quyết định alpha) |
| BROWSER CI | COMPLETE | job trên GitHub xanh |
| CANONICAL BRAIN | PARTIAL | chỉ thiết kế, chưa có adapter hay harness |
| DEMO READINESS | NOT STARTED | cổng 7 điều kiện chưa mở, có chủ ý |
| FUNDED READINESS | BLOCKED | khoá theo thiết kế, việc của chủ dự án |
| EDGE VALIDATION | BLOCKED | không có edge được kiểm định |

## Phán quyết

**DESKTOP TRADING WORKSTATION FUNCTIONALLY COMPLETE — FORWARD LIVE SIGNAL OBSERVATION PENDING**

Vì sao không chọn hai câu còn lại:
* Không chọn "COMPLETE FOR DAILY PAPER USE": chưa có tín hiệu LIVE nào, độ phủ 48,64% làm bằng chứng forward chưa hợp lệ, tin BLOCKED chưa thấy LIVE.
* Không chọn "INCOMPLETE": mọi chức năng yêu cầu cho bàn desktop đều chạy và được kiểm bằng trình duyệt thật cùng các bộ test ở mục 19.
* Phần PARTIAL (chỉ báo, bộ não chính tắc, quản lý vị thế tự động) không chặn việc dùng bàn PAPER hằng ngày; chúng được liệt kê để không bị hiểu nhầm là đã xong.

## Pha di động

**SHOULD WAIT.** Cần độ phủ ≥ 95% và ít nhất một tín hiệu LIVE thật để biết điện thoại cần gì; hiện chưa có bằng chứng sử dụng thật để thiết kế.

## 26. Ghi chú kết thúc

Hash của commit chứa báo cáo này và kết quả CI của nó: `b57e07d` (báo cáo này), CI `xau-edge-ci` xanh trên đúng commit đó (`gh run list`). Commit ghi dòng này chỉ sửa tài liệu.
