# V2 · Kiến trúc lớp tình báo thị trường (đã cài đặt)

Ngày: 2026-10-13 · Mã: `xau-edge-v2/src/xau_edge_v2/core/intelligence/`, `api/intelligence.py`, `domain/intelligence.py`.

## 1. Sơ đồ chạy thật
```
BarStore (đóng nến) ─► MultiFrames.as_of(at)  ── chỉ nến đã đóng
        │
        ├─► build_market_state ─► decide()  ───────────────► Decision (V1 v1.1.0, BẤT BIẾN)
        │                                   │
        │              ungated_decision()  ◄┘  (chạy lại decide với cổng/giới hạn tắt, chỉ để HỎI)
        │                       │
        │                       ▼
        │          funnel.build_authorization ─► Authorization { chain_verdict, gates, system_hold, funnel[11] }
        │
        └─► intelligence.observe ─► TimeframeView[H4,H1,M15,M5,M1] + Levels + Events + Scenarios[5] + Changes
                                      (price_action · structure_events · volatility, cache theo nến đóng)
        │
        ▼
 GET /api/v2/intelligence  (authority = NONE)      engine_tick ─► decision_events (SQLite, theo sự kiện)
        │
        ▼
 UI: SystemPanel (3 dòng lý do tách lớp)  +  ngăn "Thị trường" (quan sát · kịch bản · phễu · thay đổi)
```
Bốn lớp tách bạch: **Quan sát thị trường** → **Đánh giá kịch bản** → **Ủy quyền chiến lược** (V1) → **Hành động của người** (HumanPanel, không đổi).

## 2. Hợp đồng và bất biến
| Bất biến | Cách thực thi | Test |
|---|---|---|
| Mô tả không có quyền | `authority: Literal["NONE"]`, `descriptive_only: Literal[True]`; không có route ghi | `test_the_document_is_descriptive_and_has_no_authority`, e2e "never offers an action" (0 nút) |
| CONTROL không đổi | `ungated_decision` dùng `dataclasses.replace` trên **bản sao**; `decide()` không sửa | `test_asking_the_question_does_not_change_the_answer`, test khóa chiến lược V1 xanh, API: `/state` trước/sau gọi `/intelligence` bằng nhau |
| Ứng viên V2 không hoạt động | `candidate_active: Literal[False]` | API test; `test_no_live_module_imports_the_research_families` |
| Không nhìn trước | mọi sự kiện: `known_at = available_us[index]` | test tham số hóa theo seed (price action 4, cấu trúc 3+2, họ B/C/D 3×3); trên dữ liệu thật DEV': 0 sai lệch trong 25 điểm cắt ngẫu nhiên × 2 bộ phát hiện × 2 khung |
| Quyền trình bày hợp lệ | đồng nhất lý do: `(BUY/SELL) ⇔ chain OK ∧ không cổng ∧ không giữ` | hypothesis property, 300 ví dụ |

## 3. Ngữ nghĩa thời gian (một nơi duy nhất)
- Swing xác nhận tại đóng nến `i + 3` (`known_at`), swing tạm thời gắn cờ `confirmed=false`, **có thể biến mất**.
- BOS/CHoCH: `known_at` = đóng nến đóng vượt swing; mức bị phá = swing còn hiệu lực trước nến đó.
- Phá vỡ thất bại: `known_at` = đóng nến làm mất lại mức (≤3 nến sau).
- Nén/mở rộng/phá hộp: dựa nến đóng cuối; `known_at` = đóng nến đó.
- Nến đang hình thành **không** vào lớp này (chỉ chart vẽ).

## 4. Kịch bản (mô tả có điều kiện, không phải xác suất)
| Khóa | Điều kiện hoạt động | Xác nhận | Vô hiệu |
|---|---|---|---|
| CONTINUATION | H1 có hướng và M15 cùng chiều (+ nhịp hồi ⇒ THEO DÕI) | M5 đóng vượt swing M5 | M15 đóng thủng swing M15 |
| BREAKOUT | hộp nén hợp lệ / đã đóng ngoài hộp | M15 đóng ngoài hộp | đóng lại trong hộp ≤3 nến |
| REVERSAL | CHoCH/quét thất bại **ngược** H1 (H1 trung lập: chỉ M15) | M15 BOS hướng mới | vượt cực trị bị quét |
| RANGE | M15 RANGE/LOW_VOL, có S/R | nến từ chối tại biên | M15 đóng ngoài biên |
| NO_TRADE | SHOCK, dữ liệu cũ, đóng cửa, chi phí xấu | điều kiện hết | — |
Khi thiếu M15, các kịch bản tương ứng hiện `INACTIVE: thiếu dữ liệu` (không bịa).

## 5. Hiệu năng
`GET /intelligence` p50 6,6 ms, p95 42 ms, p99 69 ms (200 lần, cache 1 s dùng chung với `/state`); tính một lần ~28 ms gồm phân tích (~17 ms) + lớp mô tả ~10 ms; lần đầu 103 ms. Cache theo (khung, số nến, nến cuối): nến đóng không đổi. Dịch vụ rảnh: 2,7% một lõi, 149 MB (trước 112 MB).

## 6. Không làm
Không đặt lệnh, không đổi ngưỡng, không đổi rủi ro, không dự đoán nến kế tiếp, không dùng ML.
