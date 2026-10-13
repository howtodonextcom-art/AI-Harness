# Sổ tài sản thuật toán V1 (và V2)

Ngày: 2026-10-13 · Nguồn: đọc mã `xau-edge/src/xau_edge/` và `xau-edge-v2/src/xau_edge_v2/`, đếm gọi bằng grep (số tệp import/test là **ước lượng bằng grep**, không phải phủ). "Độc lập thông tin" = khả năng mang thông tin ngoài chuỗi V1; **chưa chứng minh cho mục nào**.

| # | Thuật toán | Sự kiện thị trường | Định nghĩa | Đầu vào / khung | Nhân quả | Nơi gọi hiện tại | Test | Điểm yếu | Tái dùng | Bằng chứng cần để đưa vào ứng viên |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `structure.analyse_structure` (V1 = V2 `core/structure.py`) | swing, xu hướng HH/HL, BOS/CHoCH, S/R | pivot: cao hơn `left=3` nến trước, ≥ `right=3` sau; xác nhận tại i+3; phá = **đóng** vượt swing chưa phá | OHLC, mọi khung | Có (kiểm repaint) | live (V1 và V2) | có | 48% BOS/CHoCH mất mức ≤3 nến (DEV') | Dùng (V2 mô tả) | HC1 |
| 2 | `classify_regime` | SHOCK/HIGH_VOL/TREND/LOW_VOL/RANGE | ADX≥25, ATR/median, range≥3 ATR; khớp đầu tiên thắng | ADX, ATR | Có | live H4 veto | có | trung vị 5 nến/chế độ, 87 đổi/1000 nến | Dùng, cần bộ lọc bền | HD1 + biến thể K+1 |
| 3 | `trading/patterns.py` (V1): pin_bar, engulfing, inside/outside, range_expansion, compression, breakout, failed_breakout | nến/nén/phá vỡ | `detect_patterns` | OHLC, ATR | cần kiểm | **không dùng trong baseline** (grep baseline: 0); dùng ở market_state và nghiên cứu (8 importer) | 11 test tệp | định nghĩa chưa hợp nhất với V2 | V2 viết lại `price_action.py` có `known_at` và test repaint | tăng thông tin sau điều kiện (NOT_TESTED) |
| 4 | `features/candles.py` `candle_geometry` | thân/bấc theo tỉ lệ | tỉ lệ thân/bấc/range | OHLC | có | 1 importer | 2 | ít dùng | Tái dùng ý tưởng | như #3 |
| 5 | `trading/setup_machine.py` + `baseline_v12.py` | vòng đời setup: ARMED→TRIGGERED / EXPIRED / INVALIDATED | replay `lookback` M5 close, không trạng thái ngầm | nhãn H1/M15/M5 | Có (hàm thuần) | **không chạy live** (CONTROL = 1.1.0); `baseline_v12` 0 test trực tiếp | 4 (setup_machine) | pre-đăng ký có tiêu chí thay v1.1 chưa đạt/chưa chạy | **Bị bỏ rơi**: C1 của V2 trùng ý | prereg V1 + Stage A DEV' |
| 6 | `trading/arming.py`, `setup_alerts.py` | cảnh báo "sắp đủ điều kiện" | thang trạng thái | state | — | `arming` 0 importer; `setup_alerts` 2 | 2 / 1 | chưa nối UI V2 | **Bị bỏ rơi**: tương đương thang điều kiện mới của V2 | UX |
| 7 | `structure.reversal`, `formation`, `wolfe`, `pattern_stats`, `detection` | đảo chiều, hình thái, Wolfe | descriptive | OHLC | nhiều chỗ dùng hậu kiểm | nghiên cứu mô tả (policy "chỉ mô tả") | 3–5 mỗi mô-đun | cực trị hồi cứu dễ repaint | Chỉ nghiên cứu | không có tuyên bố dự đoán nào |
| 8 | V2 `core/candidate.py` C1/C2/C3a/C3b/C7 | vòng đời + chi phí + gate | 14 biến thể quanh `decide()` | state | replay tất định đã test | chỉ nghiên cứu (không nối live) | có | chưa có outcome | Dùng | spec 1.1.0 chốt + Stage A + VALIDATION' một lần |
| 9 | V2 `intelligence/*` (mới) | xem báo cáo `V2_MARKET_INTELLIGENCE_ARCHITECTURE.md` | | | có test repaint | live (mô tả) | 34 + 5 + 14 | nhãn EXPANSION quá thường | — | đo thông tin gia tăng |
| 10 | ML V0 (V2 `ml/*`, báo cáo G6) | xác suất sự kiện | walk-forward, đặc trưng `ml/features.py` (chi tiết: `V2_G6_ML_V0_REPORT.md`) | features điểm-thời-gian | trạng thái register: CONTAMINATED (lý do chi tiết: `docs/research/research_status_register.json`) | không quyền, không suy luận live | có | kết quả cũ không dùng được | Không hồi sinh | dữ liệu sạch + `V2_ML_RESEARCH_ROADMAP.md` |

## Nhận xét
1. Tài sản đáng chú ý nhất bị bỏ: **vòng đời v1.2** (#5) và **thang arming** (#6).
2. Thư viện nến V1 (#3) chưa từng vào quyết định baseline; V2 live trước đây cũng không; giờ chỉ vào lớp mô tả.
3. Không mục nào được coi là có giá trị dự đoán chỉ vì có mã.
