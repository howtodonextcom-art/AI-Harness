# V2 · Báo cáo triển khai và xác minh (Master Directive: phá trần trí tuệ V1)

Ngày: 2026-10-13 · Viết cho: chủ dự án. Đây là báo cáo cuối của đợt; các báo cáo chi tiết: `V2_BRAIN_RECONSTRUCTION_REPORT.md`, `V1_ALGORITHM_ASSET_REGISTRY.md`, `V2_MARKET_INTELLIGENCE_ARCHITECTURE.md`, `V2_REGIME_AND_STRUCTURE_ENGINE.md`, `V2_PRICE_ACTION_INTELLIGENCE.md`, `V2_MULTI_STRATEGY_RESEARCH_PROTOCOL.md`, `V2_ML_RESEARCH_ROADMAP.md`, `V2_UI_UX_RECONSTRUCTION_REPORT.md`, `V2_REALTIME_PERFORMANCE_REPORT.md`.

## A. Hợp đồng trạng thái cuối
| Mục | Giá trị |
|---|---|
| Git HEAD trước | root (GitHub `main`) `b492db3`; repo lồng `xau-edge-v2` `02b7e95` |
| Git HEAD sau | repo lồng `cbfceca`; root: commit đẩy lên `main` (hash trong tin nhắn bàn giao, vì báo cáo này nằm trong chính commit đó) |
| Tệp thay đổi | 36 tệp mã/test/UI/script trong `xau-edge-v2` (21 tệp mới: `core/intelligence` 7, `api`, `domain`, UI, test, script), 10 báo cáo, bằng chứng `reports/evidence/intel/` |
| Thuật toán tái dùng | `analyse_structure`, `classify_regime`, `decide()` (V1 v1.1.0), chỉ báo ATR/ADX |
| Thuật toán mới | 10 mô tả nến, swing xác nhận/tạm thời + BOS/CHoCH/phá vỡ thất bại có `known_at`, pha biến động + hộp nén, 5 kịch bản, diff thay đổi, phễu 11 bước, họ B/C/D (research only) |
| Nối vào runtime | `GET /api/v2/intelligence`, `decision_events` (ghi bởi `engine_tick`), SystemPanel (3 dòng lý do), ngăn "Thị trường" |
| Không nối vào runtime | họ B/C/D, Candidate V2, ML (test cấm import) |
| UI chứng minh | `reports/evidence/intel/*.png` (1440×900 và 1152×720: màn hình đầu, ngăn Thị trường); e2e 51 pass |
| Độ trễ | xem `V2_REALTIME_PERFORMANCE_REPORT.md`: REST p50 6,6 ms / p95 42 ms / p99 69 ms; MT5→V2 p50 0,47 s / p95 3,78 s / p99 10,9 s (P0); render trình duyệt **NOT MEASURED** |
| Test | **pytest 1978 passed** (trước 1925, +53); **e2e 51 passed** (+5); `ruff` sạch; `mypy --strict` 69 tệp sạch; pre-commit qua |
| Dữ liệu nghiên cứu đã truy cập | kho sạch DEV' 2016-01..2018-12 (+ warm-up 45 ngày, các tháng PASS), chỉ qua `CleanBarStore` (manifest `997d73f8…`, hash từng tệp); kho trực tiếp chỉ-đọc cho runtime; sổ PAPER của chính V2 |
| Dữ liệu bảo vệ **không** truy cập | Test-H, Holdout, Confirm-C, VALIDATION', các tháng quarantine, RESERVED; **không** có outcome nào được đọc (`outcomes_read: false`) |
| Bất biến CONTROL/rủi ro | V1 CONTROL không đổi; `strategy_version 1.1.0`; `candidate_active=false`; giới hạn rủi ro, ngưỡng, sizing, governor không đổi; PAPER-only; không broker thật; collector không bị chạm |
| Lỗi còn lại | xem mục D |
| Câu hỏi nghiên cứu còn lại | xem mục E |
| Cổng chủ dự án kế tiếp | mục F |

## B. Trước / sau (mỗi thay đổi)
| Thay đổi | Trước | Sau | Test | An toàn / rollback |
|---|---|---|---|---|
| Lý do WAIT tách lớp | WAIT hiển thị SPREAD_TOO_WIDE dù H1 không hướng (đo sống trong P0 và lặp lại hôm nay: `NO_DIRECTION` + cổng spread) | `chain_verdict` + `gates` + `system_hold`; phễu 11 bước | `test_a_hard_gate_no_longer_hides_a_missing_direction`, `..._governor_is_not_a_market_statement`, property 300 ví dụ, e2e deterministic | không đổi `decide()`; `ungated_decision` dùng bản sao; xóa router/UI là gỡ |
| `next_condition` hiển thị | API có, UI không | "Thị trường chặn … cần: …" | e2e | gỡ dòng UI |
| Mất sự kiện giữa hai M5 close | `decision_log` chỉ mỗi M5 close, bỏ sót lệnh AUTO 07:43 | `decision_events` ghi mọi chuyển trạng thái, độc lập khi không có người xem | `test_the_engine_records_state_transitions_without_a_viewer` | bảng mới `CREATE IF NOT EXISTS`; restore chịu bảng thiếu |
| Độ tươi và provenance | tuổi nến từng khung | + "dựa nến đã đóng, M5 đóng lúc, giá cách N s" + "v1.1.0 UNVALIDATED, ứng viên V2 không hoạt động" | e2e | — |
| Mô tả thị trường | không | 5 khung, mức, sự kiện, kịch bản, thay đổi | 34 + 5 + 14 + 5 e2e | `authority NONE`, 0 nút |

## C. Mười câu hỏi cuối
1. **Giả định V1 nào gây trần?** (a) đường duy nhất `decide()` với H1 độc quyền hướng và pullback+trigger cùng nến (V1 đã đo: 2 tín hiệu/16.270 quyết định); (b) nhãn BOS/CHoCH và chế độ **không bền** (48% mất mức ≤3 nến; chế độ đổi mỗi ~5 nến, DEV'); (c) cổng đứng trước chuỗi che lý do thật. Chưa đổi quy tắc nào.
2. **Tài sản V1 bị bỏ sót:** vòng đời setup v1.2 (`baseline_v12.py`, `setup_machine.py`, pre-đăng ký), thang `arming`/`setup_alerts`, thư viện nến `trading/patterns.py` (không vào quyết định baseline). Sổ: `V1_ALGORITHM_ASSET_REGISTRY.md`.
3. **Năng lực mới đang chạy:** lớp quan sát (nến, cấu trúc có `known_at`, pha biến động, kịch bản, diff), phễu tách lớp, nhật ký sự kiện, ngăn Thị trường.
4. **Mô tả hay dự đoán?** Toàn bộ là **mô tả**. Không thành phần nào được chứng minh dự đoán (họ B/C/D `NOT_TESTED`, ML không hoạt động).
5. **Khác gì ở đầu ra runtime?** Cùng quyết định, nhưng kèm `chain_verdict`, `gates`, `system_hold`, 5 kịch bản, mức quan trọng, sự kiện có giờ biết, danh sách thay đổi.
6. **Trader hiểu được gì hôm nay mà hôm qua không?** "H1 không hướng, cần H1 tăng/giảm; spread đang rộng là chuyện riêng; tài khoản không bị giữ"; kịch bản đảo chiều đang theo dõi vì M15 vừa quét đáy; mức nào xác nhận/vô hiệu.
7. **Độ trễ dữ liệu→UI đo được:** MT5→V2 p50 0,47 / p95 3,78 / p99 10,9 s (P0); REST 6,6/42/69 ms; mô tả cập nhật theo sự kiện `state` hoặc poll 4 s; **render trình duyệt chưa đo**.
8. **Giải thích mọi WAIT độc lập với rủi ro/governor?** Có ở tầng dữ liệu/API: khi không có cổng và không có giữ, `chain_verdict` bằng đúng lý do đầu của chiến lược (property test); khi chuỗi OK mà vẫn WAIT, lý do nằm ở `gates` hoặc `system_hold`. Giới hạn: cổng "RISK_LIMIT do không cỡ lệnh được" tính vào giữ tài khoản.
9. **Giả thuyết giao dịch chưa kiểm chứng:** tất cả (HB1, HC1, HD1; Candidate C1/C2/C3/C7; v1.2; M1 advisory). Chiến lược live là `UNVALIDATED`.
10. **Bằng chứng để Candidate V2 thay CONTROL:** spec 1.1.0 duyệt và băm; Stage A trên DEV'; VALIDATION' **một lần** `SUPPORTED` (cận dưới bootstrap theo tháng 97,5% > 0 sau chi phí, đủ cỡ mẫu theo `research/stats.py`) mà không `REFUTED_HARM` theo kiểm soát khớp; Confirm-C một lần; forward PAPER đủ mẫu; chạy shadow song song CONTROL; kế hoạch rollback; **phê duyệt của chủ dự án**. Hiện không có mục nào đạt.

**Câu hỏi chốt:** "Nếu V2 vẫn như V1 với giao diện đẹp hơn thì quyết định kiến trúc nào chịu trách nhiệm?" → xem `V2_BRAIN_RECONSTRUCTION_REPORT.md` §1: đường duy nhất `decide()` + đầu ra ba trạng thái làm toàn bộ giao diện của trí tuệ. Thay đổi đã cài: tách mô tả khỏi ủy quyền, chuỗi điều kiện đầy đủ, kịch bản độc lập. **Quyết định giao dịch vẫn là V1.** Để thực sự đổi hành vi giao dịch cần Giai đoạn 3 (nghiên cứu có cổng).

## D. Lỗi và hạn chế còn lại
1. Nhãn EXPANSION 28% (M15) chưa mang thông tin; nhãn chế độ không bền (trung vị 5 nến): cần tiền đăng ký lại, không chỉnh sau kết quả.
2. 1152×720: thẻ Hệ thống vẫn phải cuộn để thấy Entry/SL/TP (bố cục cũ).
3. Chưa có chú thích sự kiện trên biểu đồ; chưa có timeline vòng đời setup.
4. Đuôi p99 10,9 s của quote chưa điều tra (nằm ở collector).
5. Render trình duyệt và nhiều client chưa đo; poll mô tả 4 s.
6. `test-results/paper-e2e.sqlite3-*` bị theo dõi bởi git ở repo lồng và bị e2e sửa: nên bỏ theo dõi (vệ sinh repo, chưa làm).
7. `intel_descriptive` chỉ 2016–2018 và 2 khung (H1, M15); H4/M5/M1 chưa đo.
8. Chưa kiểm khả dụng với người dùng thật.

## E. Câu hỏi nghiên cứu còn lại
Thông tin gia tăng của mỗi nhãn/họ so với kiểm soát khớp (cần outcome); hình học stop/target của B/C (rủi ro 2,7–2,8 ATR); persistence filter cho RANGE; tiền đăng ký lại pha biến động; hiệu quả vòng đời v1.2/C1 trên DEV'; bài toán ML #1–#2 (nhãn không PnL).

## F. Cổng phê duyệt tiếp theo của chủ dự án
1. Duyệt **spec 1.1.0** và hình học stop/target của họ B/C/D (trước khi có bất kỳ outcome).
2. Cho phép **Stage A** (tín hiệu, không outcome) trên DEV' (≈4–8 giờ một lõi, ưu tiên thấp, ≤4 worker).
3. Phạm vi ML M0–M1 (nhãn không PnL).
4. Cửa sổ bảo trì + kế hoạch rollback nếu muốn điều tra đuôi p99 ở collector.
5. Các mục Gate B3 còn treo: A1 (đăng nhập portable), 2021-02..09, ADR-V2-019 hai nguồn.
