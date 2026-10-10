# WORKSTATION: báo cáo hoàn tất (bàn làm việc XAUUSD trên desktop, PAPER ONLY)

> Ngày: 2026-10-11 (thị trường đóng cuối tuần khi viết). Mọi con số dưới đây lấy từ lệnh chạy thật trong phiên này.
> Không có lệnh thật, không bật DEMO/FUNDED, không đụng v1.1.0, ngưỡng, holdout hay Test-H.

## 1. Điểm xuất phát và điểm kết thúc

* Xuất phát: `4d85be4` (TRADE-08 xong ở mức dùng PAPER hằng ngày).
* Commit của sprint: `b90a7e7` DATA-01, `17f3d8e` DATA-02, `55add95` TELEMETRY-01, `e8e8fc3` NEWS-01, `a614533` DRAW-01/CONSIST-01,
  `5cbb573` BROWSER-CI-01/POSITION-01/BRAIN-01, và commit cuối chứa báo cáo này (xem `git log`; HEAD cuối được ghi ở mục 19).
* CI đã xanh trên `5cbb573` (8/8 job, kể cả job trình duyệt mới). Commit NEWS-01 `e8e8fc3` đã ĐỎ trên CI vì 6 test cũ của
  `test_trade_news_wiring.py` còn mã hoá từ vựng 3 trạng thái; tôi chưa chạy bộ test Python đầy đủ trước khi push commit đó. Đã sửa ở `5cbb573`.

## 2. Các pha đã làm

| Pha | Kết quả |
|---|---|
| A. Dữ liệu | Hoàn tất: nguyên nhân gốc, chính sách sửa có kiểm toán, công cụ kiểm độc lập, giám sát mọi ổ đĩa |
| B. Độ phủ telemetry | Hoàn tất: đo, cổng 95%, thẻ Hệ thống |
| C. Tin tức | Hoàn tất lõi (nguồn thật, 6 trạng thái, job nền, UI); marker trên chart làm sau blind A/B |
| D. Phân tích chart | Hoàn tất công cụ vẽ + quản lý + RR thủ công + mức tuần/phiên + sửa gốc resize; KHÔNG làm chỉ báo/cấu trúc/2 chart (mục 10) |
| E. Nhất quán | Hoàn tất: một múi giờ, tuổi dữ liệu do máy chủ đo, trang control, bảng sức khỏe |
| F. CI trình duyệt | Hoàn tất: job `dashboard-e2e`, goldens từ backend thật gồm TP/SL/TIME |
| G. Quản lý vị thế | Hoàn tất ở dạng kiểm toán tài liệu (`POSITION_MANAGEMENT_AUDIT.md`) |
| H. Bộ não chính tắc | Hoàn tất ở dạng thiết kế (`docs/architecture/canonical-brain.md`); KHÔNG kích hoạt gì |

## 3. Phát hiện về parity nến (DATA-01/02)

* Nguyên nhân: terminal sửa muộn `tick_volume` (ví dụ M1 13:54 UTC lưu 238, terminal 239; cùng +1 ở M5/M15/M30/H1); ledger chỉ-thêm
  nên không ghi đè; cửa sổ đối chiếu chỉ 200 nến nên không bao giờ sửa; sức khỏe feed báo DEGRADED vĩnh viễn.
* Phân loại: LATE TICK, FORMING-BAR ERROR, UNKNOWN (giá/spread/volume lệch quá ngưỡng), REPAIR BUG (thiếu trong kho), BOUNDARY ERROR.
* Chính sách xác định: chỉ nến đã ổn định, chỉ lệch `tick_volume` nhỏ có chặn (3 tick hoặc 0,5%), qua đường có kiểm toán `BAR_REPAIRED`
  (giá trị cũ/mới, lý do, thời điểm). Giá/spread/thiếu nến KHÔNG BAO GIỜ tự sửa. Đối chiếu sâu 3 ngày khi khởi động.
* Kiểm tra độc lập: `scripts/audit_bar_parity.py` (copy_rates_range riêng) ra 0 chênh lệch trên 14 ngày, feed `GOOD`.
* Ledger tick (205M tick) được kiểm lại tính toàn vẹn mà không tải lại; tick ledger KHÔNG phải nguồn đối chiếu volume (40/40 phút mẫu lệch,
  vì MT5 chỉ đếm tick đổi giá).
* Đĩa: collector giờ theo dõi mọi ổ (trước đây C: chứa MT5 và Windows vô hình); C: còn ~14,8 GB hiện cảnh báo.

## 4. Độ phủ telemetry (TELEMETRY-01)

* Nhịp thật: một dòng quyết định cho mỗi nến M1 đóng mới khi thị trường mở; engine không ghi bù phần đã lỡ.
* Đo trên LIVE: 232/477 = **48,64%** (cửa sổ 09/10 12:53 UTC đến 10/10), hai khoảng thiếu 30 và 215 phút = tiến trình engine không chạy lúc restart.
* Cổng cứng: dưới 95% thì forward acceptance nói "FORWARD EVIDENCE INCOMPLETE"; thẻ Hệ thống hiện kỳ vọng/ghi nhận/thiếu/trùng/trễ và từng khoảng thiếu.

## 5. Nguồn tin và trạng thái LIVE (NEWS-01)

* Rubric định trước, 4 ứng viên: chọn Forex Factory weekly JSON (`docs/reports/NEWS_SOURCE_DECISION.md`). Giới hạn nói thẳng: không chính thức,
  chỉ tuần hiện tại, không có published/updated, bị giới hạn tốc độ (đã gặp HTTP 429 khi thử thật), chưa có nguồn thứ hai.
* Trường point-in-time: `event_time` (time_utc), `available_at` (lần đầu ta thấy), `currency`, `source`, `published_at` (trống khi nguồn không có),
  `ingested_at`, `updated_at`, impact, title (category). File 4 cột cũ vẫn đọc được.
* Trạng thái: `CLEAR/BLOCKED/UNKNOWN/NOT_CONFIGURED/STALE/ERROR`; chỉ CLEAR là xanh; chiến lược vẫn chỉ thấy CLEAR/BLOCKED/UNKNOWN. Dải TIN trên /trade
  (thêm: tin mạnh trong 90 phút tới thì dải chuyển vàng và nói khi nào cửa sổ chặn mở), thẻ Hệ thống, đường dọc trên chart.
* LIVE: `data/news/calendar.csv` 24 sự kiện USD/All, API và trình duyệt thật đọc CLEAR. **BLOCKED/STALE/ERROR chưa quan sát LIVE** (không có tin mạnh trong
  cửa sổ; kiểm bằng unit + mock). Job nền `scripts/run_news_refresher.py` chạy trong supervisor.

## 6. Bổ sung cho chart desktop (DRAW-01)

Đường xu hướng, tia, đường dọc, vùng (hộp), Fibonacci (7 mức), R:R thủ công ("PHÂN TÍCH THỦ CÔNG — KHÔNG PHẢI TÍN HIỆU"), tuần trước cao/thấp (PWH/PWL),
cao/thấp phiên Á/Âu/Mỹ, đường tin tức; kéo điểm, kéo cả nét, Delete, Esc huỷ, khoá; bảng quản lý (tên, khoá, xoá, xoá tất cả có xác nhận).
**Sửa gốc resize/maximize**: sau khi đổi kích thước, khoảng nhìn của người dùng được khôi phục (trước đây nến giữ bề rộng nên chừa khoảng trống bên trái).
Lỗi thật tìm ra khi làm: thư viện chart nuốt cú bấm thứ hai trong 500 ms ở vị trí khác (nên điểm thứ hai của đường bị mất) → dùng click gốc của trình duyệt.

## 7. Kết quả A/B

* Marker tin trên chart: 3 thiết kế, reviewer mù, nhãn xáo trộn: đường dọc + nhãn **14/30** (thắng), dải bóng **13/30**, cờ trên trục **12/30**.
  Lỗi của người thắng đã sửa: thêm dải cửa sổ chặn cho tin mạnh, cắt nhãn, đẩy nhãn khi sát mép/chồng nhau.
* KHÔNG chạy A/B cho công cụ vẽ, chỉ báo, lớp cấu trúc. Nói rõ để không bị hiểu là đã đánh giá.

## 8. Lưu trữ nét vẽ

Khoá `xau-edge:v3:{LIVE|REPLAY}:XAUUSD:drawings`; điểm là (giây UTC thật, giá) nên đổi múi giờ hoặc khung giờ không làm nét vẽ dịch chuyển; ID ổn định;
tối đa 60; dữ liệu hỏng/sửa tay bị bỏ qua không làm sập chart; không bao giờ vào quyết định, cảnh báo, nhật ký hay endpoint. Test: giữ qua reload, đổi khung, đổi
múi giờ; LIVE không lẫn REPLAY (xem hạn chế ở mục 22).

## 9. Lớp cấu trúc thị trường

Đã có sẵn (TRADE-07/08): kháng cự/hỗ trợ M15, PDH/PDL. Mới: PWH/PWL, cao/thấp phiên. **Chưa làm** BOS/CHoCH hay swing overlay (không có prototype/đánh giá).

## 10. Quyết định về chỉ báo

**Không thêm chỉ báo nào** (MA, RSI...). Lý do: chưa có rubric/A/B chứng minh chỉ báo giúp ích, và thêm chỉ báo dễ bị đọc như tín hiệu. Chế độ 2 chart (H1+M5)
**không làm** vì chưa chứng minh cần thiết. Hai việc này vẫn mở.

## 11. Múi giờ nhất quán (CONSIST-01)

Một khoá `xau-edge.market.zone` cho `/trade`, `/market`, `/journal`, `/control`; hook `useDisplayZone` đọc khi tải và theo dõi tab khác qua sự kiện `storage`;
thời gian ở /control và /journal theo múi giờ này. Test: đặt ở /market, journal và trade theo; đổi ở tab khác thì tab này theo.

## 12. Ngữ nghĩa tuổi dữ liệu

Máy chủ đo bốn loại: QUOTE AGE, LAST BAR AGE, COLLECTOR HEARTBEAT AGE, LAST DECISION AGE, mỗi loại một trạng thái (`FRESH/STALE/MARKET_CLOSED/UNAVAILABLE/REPLAY`).
Thị trường đóng thì báo giá/nến cũ là `MARKET_CLOSED`, không phải `STALE`; nhịp tim collector vẫn phải mới. Tuổi được đo lại tại thời điểm phục vụ (red team: trước đó đóng băng
theo lần tính cuối; đã sửa).

## 13. Trang /control

Khi API không bật điều khiển web: "CONTROL DISABLED", **dừng poll hoàn toàn** (test đếm request không tăng trong 7 giây), nút "Kiểm tra lại". Không còn "quay mãi".

## 14. Sức khỏe hệ thống

Thẻ trong tab Hệ thống: MT5, collector, nến khớp terminal, lưu tick, ổ đĩa, API, dashboard, độ phủ quyết định, tin tức, quyền ghi bàn PAPER, phiên bản chiến lược,
nguồn dữ liệu; mỗi dòng OK/WARN/ERROR/UNKNOWN kèm lý do. Replay: các dòng collector là UNKNOWN, không phải OK. LIVE hiện: WARN vì ổ C: và độ phủ 48,6%.

## 15. CI trình duyệt

Job `dashboard-e2e` (Playwright mock API, bộ goldens do backend thật sinh, axe) chạy trên GitHub: xanh trên `5cbb573`. Goldens mới `closed_sl`, `closed_time` do replay thật
(SL và TIME_EXIT), `states.spec.ts` kiểm từng trạng thái WAIT/BUY/SELL/HOLD/TP/SL/TIME/INVALIDATED/UNAVAILABLE.

## 16. Kiểm toán quản lý vị thế

`docs/reports/POSITION_MANAGEMENT_AUDIT.md`: đã có SL/TP1/hạn giữ 120 phút/đóng tay/giới hạn rủi ro; break-even và trailing có mã nhưng TẮT; chốt từng phần không có mã.
Bật chúng là thay đổi alpha (cần quản trị), không phải UX.

## 17. Kiến trúc bộ não chính tắc

`docs/architecture/canonical-brain.md`: xác nhận HAI bộ não (Trading Core cho /trade và PAPER; `signals.engine` cho bot DEMO legacy); cầu `trading/adapter.py` có nhưng không nối.
Thiết kế TradeEngine → TradingSignal → Execution Intent → adapter Paper/Demo/Funded; hợp đồng tín hiệu; decision-parity harness; phân loại KEEP/ADAPT/DEPRECATE/DELETE LATER.

## 18. Kế hoạch di chuyển demo

Cổng 7 điều kiện ở mục 6 của tài liệu bộ não: dry-run bằng TradingSignal, parity 0 khác biệt ≥ 1 tuần LIVE, độ phủ ≥ 95%, dữ liệu/tin sạch, forward ≥ F2, xác nhận bằng văn bản của chủ,
FUNDED vẫn khoá. **Chưa mở.**

## 19. Kiểm thử (số liệu thật)

| Cổng | Kết quả |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 655 files already formatted |
| `uv run mypy` (cấu hình repo, như CI) | Success: no issues found in 443 source files |
| `uv run pytest -m "not mt5"` (toàn bộ) | **2601 passed, 1 skipped, 3 deselected** trong 13 phút 18 giây (skip: symlink cần quyền trên Windows). Một file test sửa nhỏ sau đó (`test_trade_news_wiring.py`) chạy lại riêng: 7 passed |
| `pytest -m mt5` | KHÔNG chạy (kết nối terminal FTMO thật); thay bằng `scripts/audit_bar_parity.py` chỉ đọc: 0 chênh lệch trên 14 ngày, 6 khung, 0 trùng, 0 lệch biên |
| `eslint .` | sạch (exit 0) |
| `tsc --noEmit` | sạch |
| `next build` | thành công |
| Playwright (mock API, goldens từ backend thật, gồm axe) | **291 passed** (20 file; a11y.spec.ts có 3 test axe) |
| Playwright acceptance trên backend thật (replay `serve_acceptance.py`) | **31 passed** trong 5,5 phút |
| Trình duyệt thật trên LIVE :3000/:8000 | đạt (mục 20) |
| CI GitHub trên `5cbb573` | 8/8 xanh (6 ma trận Python, dashboard, trình duyệt) |

Tăng so với đầu sprint: Python 2566 → 2601 test; Playwright mock 238 → 291.

## 20. Bằng chứng trình duyệt

* LIVE trên :3000 (build mới nhất, trình duyệt thật): dải TIN CLEAR, thẻ Hệ thống (tuổi 4 loại, 13 dòng sức khỏe), độ phủ 48,6%, vẽ xu hướng/vùng/R:R/Fibonacci, giữ qua điều hướng /journal rồi quay lại.
* Luồng phân tích chart (mở /trade → đọc quyết định → đổi khung → vẽ xu hướng → vẽ vùng → R:R → xem S/R → xem tin → đặt cảnh báo → journal → quay lại): 8/8 bước đạt trên LIVE trong ~4,3 giây tự động; nét vẽ và cảnh báo còn nguyên sau khi quay lại.
* Thử năm giây (người chấm mới, 4 ảnh 1440×900): trả lời đúng symbol, giá, mở/đóng, hành động, Entry/SL/TP, vị thế, LIVE/replay. Điểm yếu thật: **thiên hướng thị trường không hiện bằng chữ** khi có BUY/SELL hoặc thị trường đóng;
  "CPI sau 40 phút" cạnh "chưa vào cửa sổ tin" đọc mơ hồ (đã sửa: dải vàng + nói khi nào cửa sổ mở); hộp R:R thủ công cạnh vị thế thật dễ rối (đã gắn nhãn "KHÔNG PHẢI TÍN HIỆU"); cảnh báo Telegram màu cam tranh với kết luận.
* Hiệu năng LIVE (10 giây): 60 FPS, 564 nút DOM, 0 long task, 16 request/10 s (decision 4, bars 4, các endpoint khác 2), heap 11 MB, chart không bị tạo lại, 11 canvas.

## 21. Red team (reviewer riêng, chỉ đọc mã)

Không có HIGH. 7 MEDIUM + 5 LOW. Đã sửa: dấu thời gian làm mới ở tương lai thành ERROR; lịch rỗng là UNKNOWN; nguồn tươi lấy từ bản ghi của job cập nhật (không phải mtime); ngày không offset bị từ chối;
tuần thiếu (feed cắt cụt) và tuần nối không liền bị từ chối; chuyển hướng https→http bị chặn; tuổi báo giá/nến đo lại lúc phục vụ; ngưỡng STALE 48 h → 12 h; timer của chart dừng khi tab ẩn.
Chưa sửa (ghi ở mục 22): độ phủ không thấy khoảng thiếu của collector; cửa sổ độ phủ bắt đầu ở dòng telemetry đầu; scope REPLAY chung cho mọi bộ replay; sai số tích luỹ của sửa volume không có trần; hạ impact trong feed không phát hiện.

## 22. LOW và hạn chế còn lại (trung thực)

* Marker "TP" bị cắt ở mép phải (TRADE-08): thử với lối thoát ở nến mới nhất trên 1440×900 thì nhãn hiện đủ; không tái hiện, chưa kết luận đã hết trên mọi mức zoom.
* Thiên hướng thị trường không hiện bằng chữ trong màn BUY/SELL/đóng cửa (hành động đã mang hướng).
* Độ phủ quyết định so với nến đã lưu: không thấy nến collector lỡ; cửa sổ bắt đầu từ dòng telemetry đầu tiên.
* Nét vẽ REPLAY dùng chung một khoá cho mọi bộ replay.
* Tin: một nguồn không chính thức, chỉ tuần hiện tại, không published/updated; hạ impact hay thiếu hàng ở nguồn không tự phát hiện; tin đột xuất không bao giờ cảnh báo.
* Chưa có chỉ báo, chưa có BOS/CHoCH, chưa có chế độ 2 chart; chưa chạy A/B cho công cụ vẽ.
* Marker/đường tin chỉ có tin trong 24 giờ tới (API không trả tin quá khứ).
* `mypy --strict scripts` còn 37 lỗi ở các script cũ (CI chạy `mypy` theo cấu hình repo, xanh).

## 23. Tín hiệu LIVE thật

**LIVE ACTIONABLE SIGNAL NOT YET OBSERVED.** Thị trường đóng suốt phiên này; forward acceptance F0, và vì độ phủ 48,6% < 95% nó đang nói "FORWARD EVIDENCE INCOMPLETE". Replay không nâng được mức F.

## 24. Trạng thái edge

Không có edge được kiểm định: Edge Program V1 (B) NO EDGE WITHIN BUDGET, V2 Batch A 0/20; chiến lược `xau_mtf_baseline v1.1.0` nhãn UNVALIDATED_OPERATIONAL_BASELINE. Không có tuyên bố edge trong sprint này.

## 25. Cổng tiếp theo

1. Giữ engine chạy liên tục trong giờ mở cửa để độ phủ ≥ 95% (không có độ phủ thì forward evidence vô nghĩa).
2. Quan sát một setup LIVE thật và, nếu có tin mạnh, trạng thái BLOCKED thật.
3. Nối adapter + decision-parity harness (BRAIN-01) ở chế độ dry-run, rồi mới bàn cổng DEMO.
4. Quyết định của chủ dự án: nguồn tin có SLA, và có bật quản lý vị thế tự động hay không (thay đổi alpha).

---

## Bảng kiểm kê dữ liệu thời gian thực

| Dữ liệu | Nguồn | Tần suất | Trạng thái | Ghi chú |
|---|---|---|---|---|
| Nến M1..H4 | collector MT5 → `data/market` | mỗi nến đóng | THẬT, parity 0 chênh lệch | sửa có kiểm toán chỉ cho tick_volume muộn |
| Báo giá | collector → `live.json` | ~giây | THẬT | MARKET_CLOSED khi thị trường đóng |
| Tick | collector → tick ledger | liên tục | THẬT, trễ ~3 s | 205M tick, toàn vẹn đã kiểm |
| Quyết định | TradeEngine (API) | mỗi nến M1 mới | THẬT, độ phủ 48,6% | engine không ghi bù |
| Lịch tin | Forex Factory weekly → `data/news/calendar.csv` | làm mới mỗi ≥ 4 giờ | THẬT, nguồn không chính thức | BLOCKED chưa thấy LIVE |
| Tuổi dữ liệu / sức khỏe | máy chủ đo mỗi lần phục vụ | mỗi request | THẬT | |
| Cảnh báo giá, nét vẽ | trình duyệt (localStorage) | — | của người dùng | không ảnh hưởng quyết định |

## Bảng kiểm kê tính năng desktop

| Tính năng | Có | Ghi chú |
|---|---|---|
| Hành động CHỜ/MUA/BÁN/GIỮ/THOÁT/KHÔNG KHẢ DỤNG + lý do + khi nào | CÓ | TRADE-08 |
| Entry/SL/TP/RR, thời hạn hiệu lực | CÓ | |
| Bàn PAPER, mở/đóng có xác nhận, nhật ký | CÓ | |
| Nhật ký (/journal) → chart | CÓ | |
| Cảnh báo giá | CÓ | |
| Đường ngang, thước đo | CÓ | |
| Đường xu hướng, tia, đường dọc, vùng, Fibonacci, R:R thủ công | CÓ | DRAW-01 |
| Quản lý nét vẽ, khoá, lưu theo nguồn | CÓ | |
| PWH/PWL, cao/thấp phiên, S/R, PDH/PDL | CÓ | |
| Tin: dải TIN, thẻ, đường dọc + dải cửa sổ | CÓ | NEWS-01 |
| Một múi giờ toàn site | CÓ | |
| Tuổi dữ liệu 4 loại, sức khỏe hệ thống | CÓ | |
| Độ phủ quyết định + cổng forward | CÓ | |
| Chỉ báo, BOS/CHoCH, 2 chart | KHÔNG | |
| Quản lý vị thế tự động / nút bảo vệ lãi | KHÔNG | thay đổi alpha |

## Ma trận hoàn tất

| Hạng mục | Mức | Ghi chú |
|---|---|---|
| DATA PARITY | COMPLETE | 0 chênh lệch, chính sách có kiểm toán, công cụ độc lập |
| TELEMETRY COVERAGE | COMPLETE (đo + cổng) | giá trị đo hiện 48,6%: còn phải giữ engine chạy |
| NEWS | PARTIAL | có nguồn thật + UI; nguồn không chính thức; BLOCKED chưa thấy LIVE |
| REAL-TIME DATA | COMPLETE | |
| SIGNAL UI | COMPLETE | |
| DESKTOP CHART | COMPLETE | resize đã sửa gốc |
| DRAWINGS | COMPLETE | |
| ANALYSIS (chỉ báo, cấu trúc nâng cao, 2 chart) | PARTIAL | chỉ có mức giá/phiên/tuần; không chỉ báo |
| JOURNAL | COMPLETE | |
| ALERTS | COMPLETE | |
| SYSTEM HEALTH | COMPLETE | |
| POSITION MANAGEMENT | PARTIAL | cố định SL/TP/hạn giữ; tự động bảo vệ lãi TẮT (quyết định alpha) |
| BROWSER CI | COMPLETE | job trên GitHub xanh |
| CANONICAL BRAIN | PARTIAL | thiết kế xong, chưa triển khai adapter/harness |
| DEMO READINESS | NOT STARTED (chủ ý) | cổng 7 điều kiện chưa mở |
| FUNDED READINESS | BLOCKED | khoá theo thiết kế, việc của chủ dự án |
| EDGE VALIDATION | BLOCKED | không có edge được kiểm định |

## Phán quyết

**DESKTOP TRADING WORKSTATION FUNCTIONALLY COMPLETE — FORWARD LIVE SIGNAL OBSERVATION PENDING**

Lý do không dùng "COMPLETE FOR DAILY PAPER USE": chưa quan sát tín hiệu LIVE nào, độ phủ quyết định hiện 48,6% (< 95%) nên bằng chứng forward chưa hợp lệ, và BLOCKED của tin chưa thấy LIVE.
Không phải "INCOMPLETE": mọi chức năng được yêu cầu cho bàn desktop đều chạy và được kiểm bằng trình duyệt thật.

## Pha di động

**SHOULD WAIT.** Chờ độ phủ ≥ 95% và một tín hiệu LIVE thật để biết cần gì trên điện thoại; hiện chưa có bằng chứng sử dụng thật cho thiết kế di động.
