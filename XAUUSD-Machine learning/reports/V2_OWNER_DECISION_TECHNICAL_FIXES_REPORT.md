# V2 · Sửa ba vấn đề kỹ thuật theo Owner Decision (CONDITIONAL APPROVAL)

Ngày: 2026-10-13 · Phân loại: ENGINEERING_IMPROVEMENT / DATA_CORRECTNESS_IMPROVEMENT. Không đổi V1 CONTROL, rủi ro, ngưỡng; không mở dữ liệu bảo vệ.

## 1. GET không còn ghi `decision_events` (A.1)
**Lỗi cũ (do em):** `GET /api/v2/intelligence` gọi hàm vừa tính vừa so sánh với "trạng thái trước" vừa ghi DB. Nhiều client hoặc UI mở/tắt làm đổi cái được ghi (và trạng thái so sánh bị chia giữa các lần gọi). Bằng chứng trên DB sống trước khi sửa: 1.115 dòng, chủ yếu `GATES` (439) và `SCENARIO` (432), do spread/biến động nhấp nháy giữa các lần poll của các client.

**Sau sửa:**
- `view_intelligence` (GET) chỉ **tính mô tả và đọc** lịch sử từ DB; không ghi, không đổi trạng thái.
- `record_intelligence` là **người ghi duy nhất**, chỉ được `engine_tick` gọi; so sánh với trạng thái trước **của engine**; khoá `_ENGINE_LOCK`.
- `IntelMemo` có khoá luồng (trang và engine dùng chung từ hai luồng).

| Kiểm tra | Test / bằng chứng |
|---|---|
| Engine ghi khi **không ai mở UI** | `test_the_engine_records_state_transitions_without_a_viewer`: một `engine_tick`, không GET nào, DB có `ENGINE_START` đủ ID |
| **Multi-client**: 5 GET tuần tự + 24 GET từ 8 luồng song song không thêm một dòng nào | `test_a_get_never_writes_however_many_clients` |
| Sống: 30 GET vào dịch vụ đang chạy: 1115 → 1115 dòng | đo trực tiếp sau khi khởi động lại |
| **Idempotency**: ghi cùng ảnh chụp hai lần = một dòng; thử lại cùng khoá không nhân đôi | `test_recording_the_same_snapshot_twice_is_one_row` |
| **Restart**: lịch sử còn nguyên, mở lại có `ENGINE_START` thứ hai, ID khác, không ghi đè | `test_a_restart_keeps_history_and_starts_a_new_observation` |
| Nâng cấp DB cũ tại chỗ (thêm cột, giữ dòng cũ) | `test_an_old_database_is_migrated_in_place` |

## 2. Ngữ nghĩa `ungated_decision`: chẩn đoán giả định, có NOT_EVALUABLE (A.2)
**Lỗi ngữ nghĩa cũ:** kết quả "chuỗi nói gì khi tắt cổng" được trình bày như lý do của thị trường thật, kể cả khi dữ liệu cũ/thiếu hoặc thị trường đóng (khi đó cổng DATA bị tắt giả định làm chuỗi trông "đủ sức trả lời").

**Sau sửa:**
- `counterfactual_chain` trả `Counterfactual(evaluable, reason, decision)`. **NOT_EVALUABLE** khi: `MARKET_STATUS_UNKNOWN`, `MARKET_CLOSED`, `FEED_DISCONNECTED`, `SYMBOL_SPEC_UNKNOWN`, `STALE_DATA` (chất lượng dữ liệu hoặc khung chuỗi H4/H1/M15/M5 cũ), `TIMEFRAMES_MISSING` (thiếu H1 hoặc H4).
- Hợp đồng API: `Authorization.chain_basis = "COUNTERFACTUAL_GATES_OFF"`, `chain_evaluable`, `chain_not_evaluable_reason`; `chain_verdict = "NOT_EVALUABLE"`; các bước chuỗi trong phễu là `NOT_APPLICABLE`; UI hiện "không đánh giá được (lý do)" và ghi chú "chẩn đoán giả định tắt cổng".
- Quyết định CONTROL **không đổi**: test so sánh `decide()` trước/sau, test khoá chiến lược V1 xanh, `/state` trước/sau gọi `/intelligence` giống nhau.

| Kiểm tra | Test |
|---|---|
| 10 tình huống dữ liệu/thị trường không tin cậy ⇒ NOT_EVALUABLE, đúng lý do, không đoán | `test_the_counterfactual_says_not_evaluable_instead_of_guessing` (10 ca) |
| Trạng thái khoẻ ⇒ evaluable và gắn nhãn counterfactual | `test_a_healthy_state_is_evaluable_and_marked_counterfactual` |
| Nhất quán với chiến lược (300 ví dụ hypothesis) | `test_authorization_is_consistent_with_the_strategy` |
| Hỏi không làm đổi câu trả lời thật | `test_asking_the_question_does_not_change_the_answer` |

## 3. Truy xuất sự kiện (A.3)
Bảng `decision_events` nay có, cho **mỗi** chuyển trạng thái: `id`, `event_id` (UUIDv5 ổn định từ khoá), `event_key` (băm của loại, nội dung, thời điểm, phiên bản; UNIQUE), `at`, `strategy_version`, `dataset_version` (phiên bản kho dữ liệu lúc ghi), `decision_id`, `setup_id`, `paper_position_id` (vị thế PAPER đang mở khi có). Lệnh PAPER do **engine** mở/đóng ghi thêm `PAPER_OPEN` / `PAPER_CLOSE` gắn `paper_position_id`. Việc ghi **không** phụ thuộc UI (mục 1).
- Test: `test_a_paper_order_is_in_the_trail_with_its_ids` (vị thế PAPER thật mở bằng desk: sự kiện mang decision_id, setup_id, strategy/dataset version, event_id; thử lại không nhân đôi), `test_events_are_linked_to_the_open_paper_position`, `test_the_view_shows_the_stored_history_with_ids`.
- Giới hạn: lệnh PAPER mở/đóng **bằng tay qua API** (POST) chưa ghi `PAPER_*` vào `decision_events` (chúng đã có trong `journal`); các sự kiện cũ (1.115 dòng trước sửa) không có `event_id` (bảng append-only, không sửa); spread nhấp nháy vẫn sinh nhiều dòng `GATES`/`SCENARIO` (ghi đúng thực tế; chưa chống rung).

## 4. Hồi quy
`pytest` toàn bộ: **2019 passed** (trước đợt này 1978; +41), `ruff` và `mypy --strict` (71 tệp) sạch, `docs/openapi.json` + `schema.d.ts` tái sinh, test hợp đồng OpenAPI xanh. e2e xem báo cáo cuối.
