# V2 ARCHITECTURE DECISION (G1 · đề xuất, chờ bạn duyệt)

Ngày: 2026-10-12 · Trạng thái: **ĐỀ XUẤT — chưa đóng băng.** Quy tắc của đặc tả (mục 85): ba kiến trúc ứng viên, tiêu chí và trọng số **được định nghĩa trước khi chấm**, chọn một, viết ADR, **chưa viết mã kiến trúc**. Quyết định này **tạm thời** cho tới khi G2 đo thực tế (xem cổng ở mục 4).

## 1. Tiêu chí và trọng số (khóa trước khi chấm)

| Tiêu chí | Trọng số | Câu hỏi quyết định |
|---|---|---|
| Đúng đắn (correctness) | 20 | Một đường quyết định duy nhất, xác định, replay khớp live? |
| Đơn giản | 15 | Ít tiến trình, ít loại giao tiếp, ít mã keo? |
| Độ trễ | 10 | Từ nến/quote đến màn hình? |
| Độ tin cậy | 15 | Chịu được MT5 rớt, collector kẹt, API khởi động lại? |
| Phù hợp ML | 15 | Huấn luyện offline, suy luận trực tuyến, registry, shadow? |
| Dễ kiểm thử | 15 | Lõi thuần, test thuộc tính, replay, trình duyệt? |
| Dễ bảo trì | 10 | Một người vận hành nổi không? |

Điểm 1–5 (5 = tốt nhất); tổng điểm = Σ(trọng số × điểm) ÷ 5 để quy về thang 100.

## 2. Ba kiến trúc ứng viên

**O1: Tiến hóa V1.** Giữ Next.js (Node) + FastAPI có luồng engine bên trong + collector tách riêng; dọn dẹp, gộp hàm trùng, thay poll bằng SSE.

**O2: SPA tĩnh + MỘT dịch vụ Python.** Giao diện Vite + React + TypeScript build thành **tệp tĩnh** do FastAPI phục vụ cùng gốc (không còn tiến trình Node khi chạy). Một tiến trình Python chứa: Decision Governor, ML suy luận, PAPER, journal, API REST + WebSocket. **Collector là tiến trình riêng** (thư viện MT5 chặn, cô lập lỗi) ghi vào kho chuẩn. Huấn luyện ML là **tiến trình ngoại tuyến riêng** (không bao giờ trong tiến trình phục vụ).

**O3: Đường ống sự kiện.** Collector, tính trạng thái, suy luận ML, quyết định, API là các tiến trình riêng nói chuyện qua message bus (NATS/Redis/ZeroMQ); UI SPA hoặc Next.

```
O2 (đề xuất):
 MT5 ─▶ [collector proc] ─▶ Parquet/DuckDB (kho chuẩn, bất biến)
                                   │ (đọc)
                                   ▼
        [xau-edge-v2 service proc]  data ─▶ features ─▶ state ─▶ rule candidate ─▶ ML (suy luận) ─▶
                                     plan ─▶ risk governor ─▶ DECISION GOVERNOR ─▶ paper ─▶ journal
                                     REST /api/v2/* + WebSocket /ws  +  static SPA (/)
        [offline trainer]  dataset ─▶ walk-forward ─▶ calibration ─▶ model registry (artefact có phiên bản)
```

## 3. Chấm điểm

| Tiêu chí (trọng số) | O1 | O2 | O3 | Lý do chính |
|---|---|---|---|---|
| Đúng đắn (20) | 3 | **4** | 3 | O2: một tiến trình ⇒ một hàm quyết định, replay dùng chính mã live; O1 kế thừa hai điểm vào; O3 nhất quán cuối cùng làm replay parity khó |
| Đơn giản (15) | 3 | **4** | 1 | O3 thêm bus, serialization, giám sát nhiều tiến trình; O2 bỏ Node khi chạy |
| Độ trễ (10) | 4 | **5** | 3 | O2 đẩy WebSocket trực tiếp, không bước proxy Next; O3 thêm bước bus (V1 đã đạt ngưỡng, chênh nhỏ) |
| Tin cậy (15) | 3 | **4** | 3 | O2: collector cô lập; điểm yếu: engine và API chung miền lỗi ⇒ cần supervisor, health và chế độ fail-closed; O3 cô lập nhiều hơn nhưng nhiều chế độ lỗi hơn |
| Phù hợp ML (15) | 3 | **4** | 4 | O2: suy luận trong tiến trình (độ trễ thấp), huấn luyện tách; O3 cô lập ML tốt nhưng thêm độ trễ và hợp đồng |
| Dễ kiểm thử (15) | 3 | **5** | 2 | O2: lõi thuần + API in-process + Playwright; O3 cần test tích hợp nhiều tiến trình |
| Dễ bảo trì (10) | 3 | **4** | 2 | một người vận hành |
| **Tổng (thang 100)** | **62** | **85** | **52** | |

Điểm số là **nhận định**, chưa có phép đo; hiệu năng và tải được kiểm ở G2 (mục 4).

## 4. Quyết định đề xuất và cổng xác nhận ở G2

**Chọn O2 (tạm thời).** Cổng G2 (đo trên bộ khung tối thiểu, so với V1 đã đo ở `V2_PERFORMANCE_BASELINE.md`); **không đạt cổng nào ⇒ dừng và báo cáo, không "giải thích cho qua" (mục 97)**:

| Cổng | Điều kiện (*không tệ hơn V1*, chưa hứa cải thiện) | Số V1 để so |
|---|---|---|
| Bundle | JS truyền ≤ V1 | 291.221 byte nén, 13 file |
| Mạng khi rảnh | request/phút và MB/phút ≤ V1 | 80 req/phút, ~1,4 MB/phút |
| Tiến trình khi chạy | ≤ V1 | 5 Python + 1 Node |
| RAM (không tính collector) | ≤ V1 API+Node | 188 + 29 MB |
| Khởi động đến render đầu | ≤ 1,5 s (mục 55) | FCP 324 ms, LCP 776 ms |
| Độ trễ quyết định p95 | ≤ 100 ms (mục 55) | 63,5 ms |
| Trình duyệt | console sạch, không 503 | — |

Nếu O2 thua V1 ở bất kỳ cổng nào, dùng O1 (ít rủi ro nhất) và ghi ADR sửa đổi.

## 5. ADR đề xuất (sẽ viết thành file ở G1/G2 sau khi bạn duyệt)

| ADR | Quyết định | Trạng thái |
|---|---|---|
| V2-001 | Một route `/` + ngăn kéo (`#journal`, `#evidence`, `#data`, `#model`) | đề xuất |
| V2-002 | O2: SPA tĩnh + một dịch vụ Python + collector riêng + trainer ngoại tuyến | đề xuất, chờ cổng G2 |
| V2-003 | Dữ liệu: Parquet bất biến + Polars/DuckDB đọc phân tích; **SQLite** cho trạng thái giao dịch (paper, journal, registry, K ledger); không thêm DB khác | đề xuất |
| V2-004 | Lịch sử theo khoảng (`from/to/before/limit`) + sự kiện live WebSocket delta; không poll toàn cửa sổ | đề xuất (mục 115) |
| V2-005 | Thang thẩm quyền ML: RESEARCH → … → PAPER_ACTIVE; V0 chỉ ROLE A (biên độ), không thẩm quyền | đề xuất |
| V2-006 | Không import từ `reference-v1`; chép có chọn lọc, đọc lại, kèm test riêng | theo đặc tả |
| V2-007 | Một sổ cái K duy nhất; kế thừa K tổng = 44 | cần bạn duyệt |
| V2-008 | Một hàm cỡ lệnh duy nhất; không còn đường nào gửi lệnh trong V2 (chỉ giao diện `ExecutionPort` không có bản cài gửi lệnh) | theo đặc tả |

## 6. Bố cục gói (mục 14)

```
xau-edge-v2/
  src/xau_edge_v2/
    data/        collector adapter, canonical store, validators, freshness, ranges (phục vụ lịch sử)
    features/    feature contract + engine (một nguồn đặc trưng cho rule và ML)
    structure/   swings, regime, BOS/CHoCH (không repaint)
    decision/    market_state, lifecycle 0–6, rule_candidate, plan(SL/TP), decision_governor
    ml/          datasets, labels, models, walkforward, calibration, registry, inference, health
    risk/        sizing (hàm duy nhất), costs (theo kỷ nguyên), governor (giới hạn/lỗ ngày/kill switch)
    execution/   ExecutionPort (interface) + PaperExecution
    journal/     nhật ký, đánh giá hậu kiểm, benchmark beta
    api/         FastAPI: REST + WebSocket + phục vụ SPA tĩnh
    research/    ledger K, đăng ký giả thuyết, tiêu chí edge, khóa Test-H/holdout
  apps/web/      Vite + React + TypeScript (một trang)
  tests/ ... docs/adr/
```

## 7. Hợp đồng dữ liệu cho biểu đồ (mục 111–118)

`GET /api/v2/market/bars?symbol=XAUUSD&timeframe=M15&from=...&to=...&limit=1000&before=...` →
`{ bars: [...], oldest_available, newest_available, has_more_before, has_more_after, data_version }`

- Phân trang theo con trỏ lùi (`before`) hoặc khoảng (`from/to`); luôn trả nến đã đóng cộng nến đang hình thành nếu `to` ở mốc hiện tại.
- **WebSocket** `/ws`: sự kiện `quote`, `bar_forming`, `bar_closed`, `decision`, `model_status`, `health`; mỗi sự kiện có `seq` và `data_version`, nên client phát hiện lỡ và tự lấy lại phần thiếu.
- Một chuỗi có thứ tự duy nhất: lịch sử + live gộp theo `time`; **không thay thế toàn bộ chuỗi; không trùng timestamp** (kiểm bằng test).
- Backfill: khi vùng nhìn thấy gần ranh giới trái (< buffer), yêu cầu trang cũ hơn, **prepend**, giữ vị trí logic để **không nhảy** (V1 `TerminalChart` đã giữ zoom/pan khi append; phần prepend là mới).

### Chiến lược cửa sổ phía client (phải đo trước khi chọn, mục 118)

| Chiến lược | Mô tả | Chỉ số chọn (đặt trước) |
|---|---|---|
| S1 Cửa sổ trượt có prepend | Giữ `viewport × k` nến, đẩy phía xa ra | bộ nhớ, độ trễ lấp chỗ trống sau kéo, độ nhảy (px), trùng timestamp = 0, FPS ≥ 55 |
| S2 Cache theo trang | Trang cố định 2.000 nến, LRU, ghép các trang đang nhìn thấy | như trên + tỷ lệ cache hit |
| S3 LOD phía server | Zoom xa dùng khung lớn hơn/cộng gộp OHLC | như trên + sai khác thị giác khi chuyển mức |

Chọn một sau benchmark ở G5; dữ liệu V1: một trang 5.000 nến ~720 KB, 45–92 ms (đủ nhanh để backfill).

## 8. Vòng đời quyết định và Decision Governor (mục 9, 40, 41)

- Vòng đời **xác định** (không phải xác suất): L0 NEUTRAL · L1 BUY/SELL BIAS · L2 WATCH · L3 SETUP ARMED · L4 TRIGGER · L5 PLAN VALID · L6 READY; sau đó POSITION OPEN → HOLD → EXIT.
- **Một** Decision Governor nhận: MarketState, RuleCandidate, MLPrediction, ExecutionState, TradeGeometry, RiskState → trả WAIT/BUY/SELL/HOLD/EXIT/UNAVAILABLE kèm `reason_codes`, bằng chứng, trạng thái mô hình, tóm tắt rủi ro.
- **Không bỏ phiếu mô hình** (EMA/RSI/ML đếm phiếu): mỗi đầu vào có vai trò ngữ nghĩa riêng. Quy tắc an toàn (thị trường đóng, dữ liệu cũ, rủi ro, kill switch…) **ML không được ghi đè**.
- **Fail-closed:** MT5 rớt, collector kẹt, nến cũ, thiếu khung, spread rộng, mô hình không khả dụng/quá hạn, đĩa cảnh báo ⇒ WAIT hoặc UNAVAILABLE.

## 9. Rủi ro của quyết định này và điều tôi không chắc

1. **Điểm số là nhận định.** Điểm yếu của O2: engine và API chung một tiến trình. Giảm thiểu: supervisor, health, test mất kết nối, huấn luyện ngoài tiến trình; **chỉ xác nhận ở G8.**
2. Viết lại SPA tĩnh thay Next.js có thể không đem lại khác biệt thật cho người dùng (V1 đã tải 332 ms). Lợi ích kỳ vọng nằm ở số tiến trình, tải mạng khi rảnh, bundle, và đơn giản vận hành: **chỉ khẳng định sau đo ở G2.**
3. WebSocket thêm trạng thái phải quản lý (kết nối lại, lỡ sự kiện). Giảm thiểu bằng `seq` và API backfill; kiểm bằng test ngắt kết nối.
4. Chưa quyết định nơi chạy thư mục V2 và có dùng chung `data/market` của V1 (chỉ đọc) hay không (đề xuất: **dùng chung, chỉ đọc, qua cấu hình**).
5. Cần cài `node`/`npm` packages (Vite, React) và dùng Playwright: cần bạn đồng ý trước khi cài (kích thước sẽ nêu).

## 10. Các quyết định cần bạn duyệt trước G2

1. O2 hay O1 hay O3 (tôi đề xuất O2 tạm thời, có cổng G2).
2. Thư mục gốc V2: `XAUUSD-Machine learning\xau-edge-v2\` có ổn không?
3. V2 đọc chung `Z:\...\xau-edge\data\market` (chỉ đọc) ở G3 thay vì sao chép 1,8 GB?
4. K kế thừa 44 (V2-007).
5. Cho phép cài các gói frontend (Vite, React, TypeScript, Playwright) khi vào G2.
