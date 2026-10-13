# V2 G4: lõi quyết định chuẩn và parity quyết định với V1

Ngày: 2026-10-13 · repo `xau-edge-v2` (local, chưa push) · V1 HEAD `daf22f6` **không bị sửa**.

Quyết định đã áp dụng: G3 PASS · G4 duyệt · endpoint tick nhỏ **có** · tick streaming/UI **không** · ML **chưa bắt đầu** · tuning chiến lược **cấm** · K=44 **không kế thừa** · Test-H/Holdout **không mở** · V1 chỉ đọc. Mục tiêu: *parity xác định + lõi chuẩn sạch*.

## 1. Đã xây (`src/xau_edge_v2/core/`, thuần NumPy, không I/O, không import V1)

| Module | Nội dung |
|---|---|
| `indicators` | EMA, RSI, ATR, ADX/DI (Wilder), z-score/percentile/ratio khối lượng; causal, độ dài đầu ra = đầu vào |
| `structure` | swing không repaint (xác nhận sau `right` nến), HH/HL, xu hướng, BOS/CHoCH theo **giá đóng cửa**, hỗ trợ/kháng cự; regime SHOCK/HIGH_VOL/TREND/LOW_VOL/RANGE; thân nến mạnh, mở rộng biên |
| `frames` | kỷ luật nến đã đóng (`available_at = open + khung`); khung thiếu không bị bịa |
| `market_state` | H4 regime → H1 xu hướng → M15 cấu trúc/pullback → M5 động lượng → M1 chất lượng thực thi; spread percentile; phiên; PDH/PDL theo **ngày broker**; chất lượng dữ liệu |
| `risk` | SL hybrid (cấu trúc + đệm, sàn 1,25 ATR, trần 3 ATR), TP theo R bị chặn bởi mức đối diện, **R/R ròng sau spread**, **một hàm cỡ lệnh duy nhất** |
| `costs` | chi phí vòng tròn có trạng thái từng thành phần; thống kê spread từ tick |
| `decision` | chuỗi quyết định baseline **v1.1.0** (WAIT là bình thường), mức sẵn sàng 0..6 xác định, id ổn định |

Ngoài lõi: `GET /api/v2/state` trả quyết định thật (PAPER, `UNVALIDATED`, kèm `decision_id`, chuỗi lý do, cảnh báo, hạn hiệu lực, kế hoạch, rủi ro, chi phí); `GET /api/v2/market/ticks?from&to&limit` (tối đa 20.000, `has_more`, lỗi có mã `TICKS_*`); hợp đồng `2.0.0-g4`; ADR-V2-010.

Điểm khác với V1 (có chủ đích, không đổi hành vi quyết định): chỉ một hàm cỡ lệnh (V1 có ba); mức sẵn sàng 0..6 là *thêm*; hard gate vẫn thắng nhưng mức sẵn sàng trung thực; PDH/PDL chỉ quét 240 nến H1 gần nhất (kết quả đã khớp V1 ở mọi mẫu).

## 2. Parity với V1 (`scripts/parity/golden_core.py`, chạy bằng interpreter V1)

Tổng cộng **353.369 phép kiểm, 0 sai lệch, chênh lệch tuyệt đối lớn nhất 0,0** (giống từng bit trong mọi mẫu). Hạt giống cố định 20261013. Không lấy mẫu Test-H (2022-01-01…2025-04-30) và Holdout (2026-05-01…): chỉ các tháng 2008–2021 và 2025-05…2026-04; đây là so hai cách cài đặt cùng một phép tính, **không đo hiệu suất**.

| Lần chạy | Phép kiểm | Sai lệch | Phạm vi |
|---|---|---|---|
| Đầy đủ (1.183 s) | 276.824 | 0 | A: nhân số học trên 60 chuỗi ngẫu nhiên (chỉ báo 600, cấu trúc 420, regime 60, mẫu nến 120, SL 4.146, TP 4.822, **cỡ lệnh 9.600** gồm mọi nhánh từ chối). B: 1.201 thời điểm thật trên 30 tháng, 40.834 so sánh trạng thái + 165.738 so sánh snapshot từng khung. C: 50.484 so sánh quyết định (hành động, lý do từ chối, chuỗi lý do, cảnh báo, trạng thái M1, `decision_id`) dưới 7 biến thể ngữ cảnh (cổng thị trường/dữ liệu/spec/feed/cooldown/giới hạn, tin, equity, quote, spread) |
| Phủ đường kế hoạch (776 s) | 76.545 | 0 | nới 2 cổng nhãn biến động (cả hai bên) để chạm đường SL/TP/cỡ lệnh/chi phí: 343 thời điểm, 243 thời điểm có chuỗi tới mức TRIGGER trở lên, **53 quyết định MUA/BÁN** so entry/SL/TP1/TP2/R:R ròng/tỉ lệ thắng cần thiết/lô/rủi ro/hạn hiệu lực/chất lượng điểm vào/`setup_id`/`decision_id` |

Đọc cho đúng:
1. Lần chạy đầy đủ **chỉ gặp 1 thời điểm MUA/BÁN** (hiếm: cổng spread/biến động chặn phần lớn), nên đường kế hoạch nhờ lần chạy "phủ đường kế hoạch" (53 so sánh) và nhân số học (A). Tỉ lệ MUA/BÁN thấp là đặc tính của baseline, không phải lỗi của V2.
2. Parity chứng minh **V2 làm đúng phép tính của V1**, không chứng minh baseline đúng hay có lợi thế (nhãn `UNVALIDATED`, không có kết luận về lợi nhuận).
3. Chưa kiểm: lifecycle v1.2.x (không mang sang), quote/spread đang chạy thật khi thị trường mở (collector đang dừng, xem mục 4), chi phí so với fill thật.

Fixture đóng băng: `tests/golden/core_golden.json` (348 ca) và `core_golden_plans.json` (169 ca: 20 BUY, 33 SELL, 116 WAIT); pytest tái tạo chúng **không cần V1**.

## 3. Kiểm tra chất lượng

| Kiểm tra | Kết quả |
|---|---|
| `ruff` / `ruff format` | sạch |
| `mypy --strict` | không lỗi (27 file nguồn) |
| `pytest` | **650 đạt** (G3: 84): 45 test lõi (không repaint, nến đang hình thành không dùng, thuộc tính cỡ lệnh bằng Hypothesis, từng khâu của chuỗi có lý do + mức riêng, cổng cứng chặn ở mức 5, chính sách tin, id ổn định, `Decision` không có trường lệnh), 518 test golden (517 ca + 1 kiểm độ phủ MUA/BÁN), tick API, hợp đồng |
| Hợp đồng OpenAPI | `export_openapi.py --check` đồng bộ; kiểu TS sinh lại |
| Playwright + axe | 17 đạt (test "5 giây" được nới: dữ liệu thật thay đổi nên chỉ đòi có câu trả lời hợp lệ, lý do, và kế hoạch rỗng khi WAIT) |

## 4. Trạng thái dữ liệu hiện tại (không thuộc G4)

Kho dữ liệu đọc được (269 tệp tháng), nhưng **collector của V1 đã dừng từ 18:11 UTC 2026-10-12**: nến M1 cuối 18:09, quote cuối 18:11. Vì thị trường đang mở, `/api/v2/state` đúng khi trả `WAIT: dữ liệu cũ` và `/health` là `DEGRADED`. Không phải lỗi V2; cần chủ dự án mở lại MT5 và collector. V2 không khởi động collector.

## 5. Giới hạn và việc chưa làm

- Equity paper `10.000` là **giả định cấu hình** cho đến khi có paper desk (G7); lô/rủi ro hiển thị phụ thuộc giả định này.
- Chi phí: trượt giá 3 điểm và hoa hồng 0 là **giả định** (nhãn ASSUMED); swap từ terminal ngày 2026-10-08, chưa đọc lại. Chưa gọi tick endpoint trong quyết định (mới có công cụ `spread_stats_from_ticks`); đo chi phí theo kỷ nguyên là việc của giai đoạn sau.
- UI chưa hiển thị chuỗi lý do/cảnh báo/hạn hiệu lực (G5). Biểu đồ, WebSocket đẩy quyết định, nến đang hình thành: G5.
- Chưa có chính sách K (ADR-V2-007) → không đăng ký giả thuyết nào; cần chốt trước G6.

## 6. Bước tiếp theo đề xuất

**G5: biểu đồ và UI quyết định**: gộp lịch sử + nến đang hình thành, kéo trái tải thêm theo `before`, hiển thị kế hoạch/lý do/mức sẵn sàng 0..6 từ `/state`, đẩy cập nhật qua WebSocket. Cần bạn duyệt G5 và quyết định (a) mở lại collector (hoặc cho V2 dùng dữ liệu cũ để phát triển UI), (b) chính sách K trước G6.
