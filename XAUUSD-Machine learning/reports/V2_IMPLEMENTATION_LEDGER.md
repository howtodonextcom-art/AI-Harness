# V2 IMPLEMENTATION LEDGER (ma trận yêu cầu, khởi tạo ở G0)

Ngày: 2026-10-12 · Nguồn: đặc tả của bạn (mục 0–118; **tin nhắn bị cắt ở mục 119**, nên các yêu cầu từ mục 119 trở đi, gồm hiệu năng dữ liệu lớn cho biểu đồ, chưa có trong sổ cái này).

Trạng thái: `NOT_STARTED | IN_PROGRESS | PASS | BLOCKED | REJECTED`. Chỉ ghi `PASS` khi có bằng chứng chạy được. **Hiện tại chưa có mã V2; chỉ các mục G0 là PASS.**

## A. Giai đoạn G0 (đã làm)

| ID | Yêu cầu | Mục | Trạng thái | Bằng chứng / ghi chú |
|---|---|---|---|---|
| G0-01 | Đọc V1, reference-v1, 4 tài liệu đầu vào | 84, 110 | PASS | `V1_FORENSIC_BASELINE.md` |
| G0-02 | Đo V1 (độ trễ, UI, bộ nhớ, LOC) | 55–57, 67 | PASS (một lần đo) | `V2_PERFORMANCE_BASELINE.md`; chưa đo cold start, soak, FPS khi kéo |
| G0-03 | Kiểm chứng "hiện trạng V1" (mục 5) | 5 | PASS | 12 mục, 1 mục hiệu chỉnh (ổ C:) |
| G0-04 | Điều tra biểu đồ thiếu lịch sử, truy vết toàn chuỗi | 111–112 | PASS | nguyên nhân gốc ở frontend + hợp đồng API |
| G0-05 | Bản đồ trùng lặp bộ não, importer | 15, 69 | PASS | 3 hàm cỡ lệnh; ≥ 9 importer của engine cũ |
| G0-06 | Phân loại tái sử dụng module | 69 | PASS (đề xuất) | `V1_FORENSIC_BASELINE.md` §4; xác nhận lại ở G4 |
| G0-07 | Ba kiến trúc, tiêu chí đặt trước, đề xuất một | 85 | PASS (đề xuất) | `V2_ARCHITECTURE_DECISION.md`; chờ bạn duyệt |
| G0-08 | Chọn tác vụ ML V0 | 18–20, 29, 75–76 | PASS (đề xuất) | `V2_ML_RESEARCH_PROTOCOL.md`: ROLE A |
| G0-09 | Bảng so sánh V1 và V2 | 99 | PASS | `V1_VS_V2_EVIDENCE_COMPARISON.md` |

## B. Yêu cầu sản phẩm và UI

| ID | Yêu cầu | Mục | Trạng thái | Ghi chú |
|---|---|---|---|---|
| P-01 | Một route `/`, không điều hướng chính; ngăn kéo `#journal #evidence #data #model` | 7–8, 53, 103 | NOT_STARTED | G5 |
| P-02 | Một viewport lộ: MARKET, ACTION, WHY, NEXT, RISK, CHART, MTF | 7 | NOT_STARTED | G5 |
| P-03 | Vòng đời xác định L0–L6 (không phải xác suất) | 9 | NOT_STARTED | G4 |
| P-04 | Ngữ nghĩa màu + chữ + biểu tượng + ARIA (không chỉ màu) | 10 | NOT_STARTED | G5, test a11y |
| P-05 | Hợp đồng 5 giây của Human (8 câu hỏi) | 11 | NOT_STARTED | G5 |
| P-06 | Bảng sức khỏe tín hiệu (decisions, bias, watch, setup, trigger, plan, ready, blockers, near-miss) | 43–44 | NOT_STARTED | G4/G5 |
| P-07 | Biểu đồ: nến, khối lượng, M5/M15/H1, phiên, Entry/SL/TP/fill/exit, S/R do hệ thống tính; **bỏ** Fibonacci tay và bộ vẽ | 54 | NOT_STARTED | G5 |
| P-08 | Không trang legacy/control; không 503 do tính năng tắt | 53, 61, 103 | NOT_STARTED | G5 |
| P-09 | Nhãn bằng chứng luôn hiển thị (UNVALIDATED/RESEARCH/SHADOW/OOS_VALIDATED/FORWARD_VALIDATED) | 79 | NOT_STARTED | G4/G5 |
| P-10 | Không hiển thị "AI CONFIDENCE" trừ khi đủ 5 điều kiện (mục 78) | 78 | NOT_STARTED | G6/G7 |

## C. Biểu đồ và dữ liệu lịch sử (mục 111–118)

| ID | Yêu cầu | Mục | Trạng thái | Ghi chú |
|---|---|---|---|---|
| C-01 | API lịch sử theo khoảng/con trỏ + siêu dữ liệu (`oldest_available`, `has_more_*`, `data_version`) | 115 | NOT_STARTED | thiết kế ở ADR V2-004 |
| C-02 | Backfill lười khi kéo trái, prepend, **không nhảy**, **không trùng timestamp** | 116 | NOT_STARTED | G5 |
| C-03 | Độ sâu lịch sử theo kho chuẩn, không giới hạn bằng số nến UI; không tải hàng triệu nến | 117 | NOT_STARTED | |
| C-04 | Cửa sổ phía client: viewport + đệm; **đo ≥ 3 chiến lược trước khi chọn** | 118 | NOT_STARTED | S1/S2/S3 ở ADR |
| C-05 | Lịch sử và live gộp thành MỘT chuỗi có thứ tự | 114 | NOT_STARTED | |
| C-06 | Hành vi benchmark MT5 (cuộn dài, zoom mượt, đổi khung nhanh, nối live liền mạch) | 113 | NOT_STARTED | chỉ hành vi, không sao chép UI |

## D. Kiến trúc, dữ liệu, rủi ro

| ID | Yêu cầu | Mục | Trạng thái | Ghi chú |
|---|---|---|---|---|
| A-01 | Một đường quyết định duy nhất; không engine song song, không mã DEPRECATED | 14–15 | NOT_STARTED | |
| A-02 | Một hàm cho: cỡ lệnh, chi phí, trạng thái thị trường, hình học lệnh, kiểm tra rủi ro, hợp đồng quyết định, ý định thực thi | 15 | NOT_STARTED | |
| A-03 | Python sở hữu chiến lược; frontend chỉ hiển thị; không quy tắc nào chỉ nằm ở frontend | 13 | NOT_STARTED | |
| A-04 | Parquet bất biến + DuckDB/Polars; SQLite chỉ cho trạng thái giao dịch | 58 | NOT_STARTED | |
| A-05 | Chính sách giữ/nén tick; giám sát đĩa, log, tăng trưởng | 59 | NOT_STARTED | V1: ổ dữ liệu 81 GB, 0,93 MB/ngày tick |
| A-06 | Log có cấu trúc (timestamp, request_id, decision_id, model_version, data_timestamp, action, latency_ms, error_code), có xoay vòng | 60 | NOT_STARTED | |
| A-07 | Tính năng tắt ⇒ vắng mặt, 204 hoặc phản hồi "unavailable" có cấu trúc; **không 503** | 61 | NOT_STARTED | |
| A-08 | Chịu: MT5 rớt, collector kẹt, nến cũ, thiếu khung, quote xấu, spread rộng, model không khả dụng/timeout, đĩa cảnh báo, frontend reconnect ⇒ WAIT/UNAVAILABLE | 62 | NOT_STARTED | G8 |
| A-09 | Một lệnh khởi động; endpoint health kiểm dữ liệu, mô hình, lưu trữ, bộ máy quyết định | 63 | NOT_STARTED | |
| R-01 | Hàm cỡ lệnh duy nhất (equity, risk %, entry, SL, tick size/value, bước lot, lot tối thiểu, chi phí) | 49 | NOT_STARTED | tái dùng logic `trading/sizing.py` |
| R-02 | Chi phí: spread, trượt giá, hoa hồng, swap; có nguồn/đơn vị/thời kỳ/trạng thái xác minh; **không có giá trị 0 ngầm** | 46 | NOT_STARTED | |
| R-03 | Chi phí theo kỷ nguyên (giá, ATR, spread/ATR, swap, thực thi) | 47 | NOT_STARTED | V1 đo: chi phí/ATR giảm 4–7 lần 2018→2026 |
| R-04 | Mọi đánh giá có benchmark trung lập hướng và benchmark beta cùng thời gian vị thế | 48 | NOT_STARTED | |
| R-05 | Chỉ PAPER; không đường DEMO; không tiền thật | 50–52 | NOT_STARTED | giao diện `ExecutionPort` không có bản cài gửi lệnh |
| R-06 | Không bỏ phiếu mô hình; vai trò ngữ nghĩa rõ | 41 | NOT_STARTED | |
| R-07 | EV chỉ khi có xác suất đã hiệu chỉnh; R:R không phải xác suất | 42 | NOT_STARTED | |
| R-08 | Giải quyết "không có gì xảy ra cả ngày" mà không bịa lệnh; tần suất tín hiệu không phải edge | 43, 45 | NOT_STARTED | |

## E. ML và nghiên cứu

| ID | Yêu cầu | Mục | Trạng thái | Ghi chú |
|---|---|---|---|---|
| M-01 | Hệ thống ML vận hành thật: pipeline huấn luyện, schema đặc trưng/nhãn, walk-forward, hiệu chỉnh, registry, suy luận runtime, shadow log, health, version | 16 | NOT_STARTED | G6–G7 |
| M-02 | Thang thẩm quyền ML; không đường tắt | 17, 37 | NOT_STARTED | |
| M-03 | Chọn đúng một tác vụ V0 sau so ≥ 7 tác vụ | 18–20, 29 | PASS (đề xuất) | ROLE A: biên độ/biến động |
| M-04 | Mô hình cơ sở đơn giản (tuyến tính/GBM); không deep learning | 21 | NOT_STARTED | ridge/HAR mặc định |
| M-05 | Phân loại V1 ML: REUSE/REWRITE/REFERENCE/DELETE | 22 | PASS (đề xuất) | §4 forensic |
| M-06 | Hợp đồng đặc trưng (name, version, unit, source TF, lookback, available_at, missing, normalization, live, rationale) | 23 | NOT_STARTED | |
| M-07 | Bộ kiểm thử rò rỉ bắt buộc (8 loại) | 33 | NOT_STARTED | |
| M-08 | Chia dữ liệu theo thời gian, embargo, tôn trọng Test-H/holdout | 30–32 | NOT_STARTED | lát cắt G0 đã cắt ở 2021-12-31 |
| M-09 | Hiệu chỉnh + chỉ báo độ phủ; nếu hỏng ⇒ không hiển thị xác suất | 34 | NOT_STARTED | |
| M-10 | Shadow mode; lưu mọi bất đồng | 35 | NOT_STARTED | G7 |
| M-11 | Registry đầy đủ trường; trạng thái; không kích hoạt bằng thay file | 36–37 | NOT_STARTED | |
| M-12 | OOD/sức khỏe mô hình; fail-closed | 38 | NOT_STARTED | |
| M-13 | Cấm học trực tuyến/tự sửa luật | 82 | NOT_STARTED | |
| M-14 | Sổ cái K một nguồn; tiêu chí edge 7 điều kiện; Test-H/holdout khóa bằng mã | 71–73 | NOT_STARTED | cần bạn duyệt K = 44 |
| M-15 | Phân loại tri thức 75.md/ảnh: PROCESS RULE / DESCRIPTIVE FEATURE / TESTABLE / REJECTED / UNVERIFIED; không đưa Fibonacci, mẫu nến, EMA cắt, đỉnh đôi, RSI 70/30, bỏ phiếu chỉ báo vào production alpha | 25–28 | NOT_STARTED | bảng trong `V1_VS_V2_EVIDENCE_COMPARISON.md` §5 |
| M-16 | Nhật ký học: dự đoán + quyết định + kết quả PAPER + chi phí + bất đồng + vi phạm + benchmark beta | 80–81 | NOT_STARTED | |

## F. Kiểm thử, hiệu năng, vận hành

| ID | Yêu cầu | Mục | Trạng thái | Ghi chú |
|---|---|---|---|---|
| T-01 | Kim tự tháp kiểm thử (đơn vị, thuộc tính, tích hợp, replay, ML, API, trình duyệt, thị giác, độ tin cậy) | 64 | NOT_STARTED | |
| T-02 | Chrome DevTools MCP: console, network, performance, layout, a11y, responsive ở 6 khung | 65 | NOT_STARTED | **Chưa kiểm tra MCP này khả dụng**; Playwright MCP đã lỗi trình duyệt ở phiên này |
| T-03 | 14 trạng thái người dùng được kiểm thử | 66 | NOT_STARTED | |
| T-04 | So sánh hiệu năng V1/V2 cùng workload | 67, 100 | NOT_STARTED | baseline V1 đã có |
| T-05 | Soak ≥ 8 giờ (ưu tiên 24 giờ) | 68 | NOT_STARTED | G8 |
| T-06 | Tái dùng test hành vi của V1 làm test chấp nhận V2 | 70 | NOT_STARTED | `reference-v1/apps/dashboard/e2e/*` |
| T-07 | Rà soát độc lập và red-team theo vai trò khác người thiết kế | 95–96 | NOT_STARTED | |
| T-08 | Kích thước mã V2 nhỏ hơn đáng kể runtime V1; theo dõi riêng runtime/nghiên cứu/test/sinh tự động | 57 | NOT_STARTED | V1 runtime ~21,8k Python + 13,5k TS |
| T-09 | Ngân sách hiệu năng: API p95, render, FPS ≥ 55, long task ≤ 200 ms | 55–56 | NOT_STARTED | V1 đã đạt hầu hết |

## H. Cập nhật sau G2 (2026-10-12)

Bảng ở trên là baseline G0; các hàng sau đã đổi trạng thái (bằng chứng: `V2_G2_SKELETON_REPORT.md`, 36 test backend + 17 test trình duyệt).

| ID | Trạng thái mới | Ghi chú |
|---|---|---|
| P-01 | IN_PROGRESS | Một route `/` + ngăn kéo hash đã có (bộ khung); nội dung ngăn kéo/biểu đồ chưa triển khai |
| P-04 | IN_PROGRESS | axe WCAG 2 A/AA đạt cho trang và ngăn kéo; ngữ nghĩa màu BUY/SELL/HOLD/EXIT đã định nghĩa nhưng chưa có trạng thái thật để kiểm |
| P-05 | IN_PROGRESS | Hợp đồng 5 giây đạt ở mức bộ khung (nội dung là "KHÔNG KHẢ DỤNG") |
| P-08 | PASS (phạm vi bộ khung) | không trang legacy/control; không 503 do tính năng tắt (`WEB_NOT_BUILT` là 404 có cấu trúc) |
| P-09 | PASS (bộ khung) | nhãn bằng chứng bắt buộc trong hợp đồng và luôn hiện ở thanh trên |
| C-01 | IN_PROGRESS | `BarsResponse` (có `has_more_*`, `data_version`, bất biến thời gian tăng nghiêm ngặt) đã định nghĩa và test; endpoint ở G3 |
| A-04 | IN_PROGRESS | kho Parquet đọc chỉ-đọc, có test; SQLite chưa dùng |
| A-06 | PASS | nhật ký JSON đủ trường, xoay vòng; test |
| A-07 | PASS (bộ khung) | không có route trả 503; thiếu build web ⇒ 404 có cấu trúc |
| A-09 | IN_PROGRESS | `scripts/start.ps1` một lệnh + `/api/v2/health` (store, độ mới, đĩa, engine, model); engine/model còn `NOT_DEPLOYED` |
| R-05 | PASS | `mode` chỉ `PAPER` (hợp đồng + cấu hình + test); không có đường gửi lệnh (test quét mã) |
| M-14 | **BLOCKED** | chờ chủ dự án chốt chính sách K (ADR-V2-007); K = 44 **không** được kế thừa máy móc; V2 chưa đăng ký giả thuyết nào |
| T-01 | IN_PROGRESS | unit, API, hợp đồng, thuộc tính, trình duyệt đã có; còn replay, ML, độ tin cậy |
| T-02 | IN_PROGRESS | Chrome DevTools MCP **dùng được** (console/network/screenshot); chưa chạy đủ 6 khung/performance trace |
| T-04 | IN_PROGRESS | cổng G2 đã đo (không tệ hơn V1, ý nghĩa hạn chế); đo lại ở G5/G8 |
| T-06 | NOT_STARTED | test hành vi V1 chưa được chuyển |
| T-08 | IN_PROGRESS | theo dõi: V2 runtime Python 673 dòng, web 565 dòng (chưa có ý nghĩa) |
| ADR | cập nhật | ADR-V2-001/002/003/006/008 đã duyệt (002 có điều kiện), 007 mở |

## I. Cập nhật sau G3 (2026-10-12)

Bằng chứng: `V2_G3_DATA_PARITY_REPORT.md`; V2 commit `9501866` + các commit sau; 84 test backend, 17 test trình duyệt; parity với V1 chạy bằng `scripts/parity/parity.py`.

| ID | Trạng thái mới | Ghi chú |
|---|---|---|
| C-01 | PASS (backend) | `/api/v2/market/bars` theo `before` / `from`+`to`, trả `oldest_available`, `newest_available`, `has_more_before/after`, `data_version`; test phân trang không trùng/không hở |
| C-03 | PASS (backend) | độ sâu lấy từ kho chuẩn (M1 từ 2004), mỗi yêu cầu tối đa 5.000 nến; trình duyệt chỉ tải theo nhu cầu |
| C-05 | IN_PROGRESS | contract đảm bảo một chuỗi tăng nghiêm ngặt; việc gộp lịch sử + live nằm ở G5 |
| C-02, C-04, C-06 | NOT_STARTED | thuộc UI biểu đồ (G5) |
| A-04 | PASS (đọc) | kho nến, tick, live: chỉ đọc, có test không đổi tệp |
| R-02 | IN_PROGRESS | `SymbolInfo` từ broker (tick size/value, bước lot…) đã có; mô hình chi phí (spread/slippage/commission/swap có nguồn) ở G4 |
| G3-01 | PASS | bar parity vs V1 (xem báo cáo) |
| G3-02 | PASS | tick parity vs V1 |
| G3-03 | PASS | spread parity (cột `spread` của nến, quote) |
| G3-04 | PASS | symbol spec parity |
| G3-05 | PASS | clock/timezone/calendar parity (mọi mốc DST Mỹ + EU 2004–2026) |
| G3-06 | PASS | git init cho `xau-edge-v2` (repo lồng trong repo cha `AI-Harness`); commit local, chưa push |
| ML-FREEZE | PASS | `docs/ml/ml_v0_spec.json` đóng băng, băm bảo vệ có test; H-V2-01 RESEARCH_ONLY |
| M-14 | BLOCKED | chờ chính sách K của chủ dự án (không đổi) |

## J. Cập nhật sau G4 (2026-10-13)

Bằng chứng: `V2_G4_CORE_PARITY_REPORT.md`, `evidence/g4/*`; 650 test backend, 17 test trình duyệt; 353.369 phép kiểm golden với V1, 0 sai lệch.

| ID | Trạng thái mới | Ghi chú |
|---|---|---|
| G4-01 | PASS | lõi chuẩn `core/` thuần NumPy, không import V1, mypy strict sạch |
| G4-02 | PASS | parity chỉ báo/cấu trúc/regime/mẫu nến/SL/TP/cỡ lệnh (giống từng bit) |
| G4-03 | PASS | parity trạng thái thị trường từ nến thật (1.201 thời điểm, 30 tháng, ngoài Test-H/Holdout) |
| G4-04 | PASS (hạn chế) | parity quyết định: 53 MUA/BÁN thật so khớp; đường MUA/BÁN hiếm (1 trong lần chạy đầy đủ), phủ thêm bằng lần chạy nới cổng biến động |
| G4-05 | PASS | một hàm cỡ lệnh duy nhất (V1: ba); test thuộc tính chặn vượt trần rủi ro |
| G4-06 | PASS | mô hình chi phí có trạng thái từng thành phần (slippage/commission ASSUMED, swap có ngày đọc) |
| G4-07 | PASS | endpoint tick chỉ đọc (`/api/v2/market/ticks`), lỗi có mã |
| G4-08 | PASS | vòng đời 0..6 xác định; READY chỉ với BUY/SELL; cổng cứng chặn ở 5 |
| G4-09 | NOT_DONE (có chủ đích) | lifecycle v1.2.x, tuning chiến lược, ML, UI: ngoài phạm vi G4 |
| DATA | BLOCKED (chủ dự án) | collector V1 dừng từ 18:11 UTC 2026-10-12, `/state` đúng khi WAIT dữ liệu cũ |
| M-14 | BLOCKED | chờ chính sách K (không đổi) |

## K. Cập nhật sau G4.1 và G5 (2026-10-13)

Bằng chứng: `V2_G5_CHART_UI_REPORT.md`, `evidence/g41/*`, `evidence/g5/*`; 1.631 test backend, 24 test trình duyệt, 7 test đơn vị TS; golden synthetic 1.421.036 phép kiểm, 0 sai lệch.

| ID | Trạng thái mới | Ghi chú |
|---|---|---|
| G4.1 | PASS | 150.000 ca tổng hợp: 2.587 BUY, 2.487 SELL, mọi 21 mã từ chối, mọi biến thể kế hoạch; READY khi và chỉ khi BUY/SELL |
| C-01, C-03 | PASS (UI) | kéo trái nạp `before=` tới hết kho; không trần 400 nến; test mock 2.300 nến mỗi nến một lần |
| C-02 | PASS | đổi khung: phản hồi cũ không thắng; cả 6 khung nạp được |
| C-04 | PASS (hạn chế) | nến forming nối nến đóng, bản đóng thắng; chưa soak nhiều giờ |
| C-05 | PASS | một chuỗi tăng nghiêm ngặt (kiểm bằng `mergeBars` + test) |
| C-06 | NOT_DONE | vùng phiên chưa tô |
| UI-DECISION | PASS | Entry/SL/TP/R:R ròng/chi phí GIẢ ĐỊNH/cảnh báo/hạn hiệu lực/chuỗi lý do/thang 0..6/6 khung |
| WS | PASS | live/state/heartbeat, `seq` không hở trong 120 s live thật |
| LIVE-ACCEPT | PASS (hạn chế) | collector đã chạy lại; phiên 120 s sạch; chưa thấy MUA/BÁN thật trên biểu đồ |
| M-14 | BLOCKED | chính sách K (không đổi) |

## L. Cập nhật sau G7 (2026-10-13)

Bằng chứng: `V2_G7_PAPER_DESK_REPORT.md`, `evidence/g7/*`; 1.676 test backend, 29 test trình duyệt, 9 test TS; ADR-V2-007 (K khóa), ADR-V2-012.

| ID | Trạng thái mới | Ghi chú |
|---|---|---|
| M-14 | RESOLVED (chính sách) | K khóa theo họ: `K_V2_VOL_V0 = 2` nếu chỉ Ridge/HAR + LightGBM cùng tham gia selection trên confirmatory; không kế thừa 44; cơ chế ghi sổ làm ở G6 |
| G5 | PASS | chủ dự án duyệt; không chờ BUY/SELL tự nhiên |
| FWD-EVIDENCE | OPEN (yêu cầu riêng) | quan sát tín hiệu live tự nhiên; sổ PAPER đang rỗng, engine chạy |
| G7-01 | PASS | paper desk: mở/quản lý/đóng, SQLite riêng, nhật ký chỉ-thêm, một setup một lệnh |
| G7-02 | PASS | bộ kiểm soát V1 (ngưỡng giữ nguyên) nối vào quyết định; cắt lệnh khi lỗ ngày ≥ 3,5% |
| G7-03 | PASS (giới hạn) | khớp lệnh/SL/TP/swap là giả định có nhãn; nến mơ hồ → SL + cờ |
| G7-04 | PASS | HOLD khi đang giữ lệnh; marker và đường giá trên biểu đồ |
| G7-05 | PASS | hai POST duy nhất, chống Origin lạ, server tự tính mọi thứ |
| G7-06 | NOT_DONE | dời SL/trailing, nhiều lệnh, so mua-và-giữ, vi phạm kỷ luật, bất đồng ML |
| ORDER | CLOSED | Demo/MT5 order chưa mở; Desk không có đường gửi lệnh (test) |

## M. Cập nhật sau G6 (2026-10-13)

Bằng chứng: `V2_G6_ML_V0_REPORT.md`, `xau-edge-v2/docs/ml/runs/v0_dev_validation_run.json`; ADR-V2-007 (K khóa, được duyệt kèm làm rõ HAR/Ridge), ADR-V2-013.

| ID | Trạng thái mới | Ghi chú |
|---|---|---|
| G7 | PASS | chủ dự án duyệt; chấp nhận chưa có lệnh PAPER tự nhiên; auto PAPER mặc định BẬT |
| M-14 | RESOLVED + IMPLEMENTED | sổ cái K `docs/ml/k_ledger.json` (họ K_V2_VOL_V0, K=2, gắn băm đặc tả); lần nhìn ghi trước khi đọc dữ liệu |
| ML-SPEC | AMENDED 1.1.0 | chỉ `k_accounting`; 1.0.0 giữ nguyên + test chứng minh |
| ML-01 | PASS | đặc trưng/nhãn đúng đặc tả; không rò rỉ (cắt, đổi tương lai, phá nhãn năm kiểm tra); parity `live_row` |
| ML-02 | PASS | walk-forward theo năm, embargo 25, hiệu chỉnh dải; chạy lại giống hệt từng bit |
| ML-03 | DONE (kết quả: không đạt một tiêu chí) | Kiểm định: +9,6%, CI>0, độ phủ 76,9%; **dương 2/3 năm < 75%**; Phát triển đạt cả |
| ML-04 | PASS | LightGBM không hơn ridge (CI chứa 0): ridge mặc định |
| ML-LOCK | PASS | Test-H/Holdout khóa bằng mã (tệp duyệt + sổ cái + một lần); chưa mở |
| ML-REG | PASS | registry RESEARCH/NONE, thăng từng bước có bằng chứng |
| ML-UI | PASS | ngăn Mô hình: trạng thái, khóa, tiêu chí đạt/không đạt; không có dự báo |
| ML-STATUS | RESEARCH | chưa VALIDATED_OFFLINE; không SHADOW; không thẩm quyền |
| ML-MON | NOT_DONE | giám sát vận hành/fail-closed: điều kiện của SHADOW |
| TEST-H | CHỜ CHỦ DỰ ÁN | khuyến nghị chưa mở (mục 5 báo cáo G6) |
| WS-RACE | FIXED | mốc đầu sự kiện `paper` lấy trước vân tay quyết định |

## N. Cập nhật sau quyết định ML và G8 (2026-10-13)

Bằng chứng: `V2_G8_RELIABILITY_FORWARD_REPORT.md`, `evidence/g8/*`; ADR-V2-007 (làm rõ một phía), ADR-V2-013 (kết cục), ADR-V2-014; `docs/forward/FORWARD_EVIDENCE_PROTOCOL.md`.

| ID | Trạng thái mới | Ghi chú |
|---|---|---|
| ML-V0 | REJECTED tại Kiểm định | giữ nguyên tiêu chí đăng ký trước; Test-H KHÔNG mở; registry RETIRED (authority NONE); họ `K_V2_VOL_V0` ĐÓNG, K không bị tiêu |
| K-ONE-SIDED | CLARIFIED | K=2, α=0,05 Bonferroni: cận dưới MỘT PHÍA 97,5% (bách phân vị 2,5) cho phát biểu "cải thiện > 0"; thay câu chữ "two-sided 97.5%" ở spec 1.1.0 cho các họ sau; không kết quả nào đổi |
| G8-01 | PASS | nhật ký quyết định theo nến M5 đã đóng (một dòng/nến, dòng đầu thắng) + phễu quyết định |
| G8-02 | PASS | độ phủ quan sát + liệt kê khoảng trống |
| G8-03 | PASS | giao thức forward đăng ký trước: kết luận cần ≥100 lệnh, ≥60 ngày, độ phủ ≥95% và giả thuyết do chủ dự án duyệt; mặc định `claim_allowed=false` |
| G8-04 | PASS | kiểm tra toàn vẹn khi khởi động, sao lưu trực tuyến hằng ngày (giữ 14), watchdog vòng nền, cảnh báo lệnh mở + dữ liệu M1 cũ |
| G8-05 | PASS | bằng chứng sập tiến trình: giết giữa giao dịch (không còn nửa nào) và sau commit (đủ cả hai) |
| G8-06 | PASS | soak 12 phút trên dịch vụ thật: 2.366 yêu cầu, 0 lỗi, bộ nhớ không rò, 0 khoảng hở `seq` |
| G8-07 | PASS (hạn chế) | giết cứng dịch vụ thật và khởi động lại: dữ liệu còn nguyên, khoảng trống hiện ra trong độ phủ |
| FWD-EVIDENCE | ĐANG TÍCH LŨY | chưa có giả thuyết forward được duyệt; chưa có lệnh PAPER tự nhiên |
| OPS-BACKUP | CHỜ CHỦ DỰ ÁN | sao lưu cùng ổ đĩa; cần bản sao ra ổ khác |
| OPS-AUTOSTART | CHỜ CHỦ DỰ ÁN | dịch vụ không tự chạy khi máy khởi động lại |

## P. Cập nhật sau G8.1 (2026-10-13)

Bằng chứng: `V2_G8_1_RELIABILITY_HARDENING_REPORT.md`; ADR-V2-015; `docs/ops/RUNBOOK.md`; 1.763 pytest.

| ID | Trạng thái mới | Ghi chú |
|---|---|---|
| OPS-AUTOSTART | DONE | tác vụ Task Scheduler (đăng nhập) + người giám sát; giết dịch vụ ⇒ chạy lại sau 12 s (kiểm trên máy thật); chưa thử khởi động máy |
| OPS-WATCHDOG | DONE | watchdog ngoài mỗi 2 phút (kết quả tác vụ 0); chỉ vận hành |
| OPS-ALERT-TG | BUILT, CHƯA GỬI THẬT | kênh Telegram kiểm bằng máy chủ giả; thiếu token + chat id (chủ dự án) |
| OPS-BACKUP-MIRROR | DONE | bản sao thứ hai D: kiểm sha256 + integrity; bắt kịp khi ổ quay lại |
| OPS-BACKUP | BLOCKED (chủ dự án) | CHƯA có bản sao ngoài thiết bị: máy chỉ có một SSD vật lý; OneDrive chưa đồng bộ; `/health` báo WARN |
| OPS-RESTORE | DONE (test đơn vị) | công cụ khôi phục có hoàn tác; chưa làm trên sổ thật |
| K-FWD | KHÔNG MỞ | chưa có giả thuyết forward đủ cụ thể (quyết định chủ dự án) |
| NEXT | CHỜ PHẠM VI | Human Decision Layer → M1 Execution Intelligence: cần chủ dự án xác nhận phạm vi |

## Q. Cập nhật sau G9 + G10 (2026-10-13)

Bằng chứng: `V2_G9_G10_HUMAN_DECISION_AND_M1_EXECUTION_REPORT.md`; `reports/evidence/g9_g10/`; 1.812 pytest + 46 Playwright.

| ID | Trạng thái mới | Ghi chú |
|---|---|---|
| G9 | PASS | lớp HỆ THỐNG / CON NGƯỜI / AUTO PAPER tách biệt; nhật ký `human_decisions` chỉ thêm; CHẤP NHẬN không gửi lệnh |
| G10 | PASS | `core/execution.py` + `core/advice.py`; M1 không bao giờ đảo hướng; tất định |
| STRATEGY-LOCK | PASS | `tests/unit/test_strategy_lock.py` khóa sha256 + hằng số |
| NO-BROKER | PASS | OpenAPI chỉ 3 POST; quét AST; 0 `order_send` |
| NEXT | CHỜ | bằng chứng forward; mục chủ dự án (Telegram, sao lưu ngoài) ngoài phạm vi |

## G. Kết quả cuối (mục 98, 108)

Chấm **riêng** các chiều: UX sản phẩm, kiến trúc, độ tin cậy dữ liệu, độ đơn giản mã, hiệu năng, ổn định vận hành, hạ tầng ML, chất lượng thống kê ML, an toàn rủi ro, vòng đời PAPER; và **riêng**: SOFTWARE COMPLETE / ML PIPELINE COMPLETE / EDGE VALIDATED / PAPER READY / DEMO READY. Không bắt buộc có edge để tuyên bố phần mềm hoàn tất.
