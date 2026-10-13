# V1 so với V2: tương đương chức năng và khác biệt thực chất

Ngày: 2026-10-13 · Phân loại: **A** cải thiện thật · **B** chỉ kỹ thuật/độ tin cậy · **C** chỉ UI · **D** cùng logic V1 · **E** thoái lui · **F** chưa triển khai.

## 1. Đường quyết định (Q2) và bộ não live
Market data (V1 collector → `live.json` ~1 Hz + kho Parquet) → `load_frames` (`store.tail(tf,450)`) → `build_market_state` → `decide` (`core/decision.py`) → `assess_execution` (M1) → governor chèn RISK_LIMIT/COOLDOWN/DAILY_LIMIT → BUY/SELL/WAIT → người (tùy chọn) → PAPER.

Chuỗi chiến lược: H4 regime (chỉ veto) → H1 xu hướng (**chủ sở hữu hướng duy nhất**) → M15 cấu trúc/pullback → M5 trigger động lượng → M1 thực thi (chỉ chặn) → hard gate (percentile spread, spread/ATR5 0,15, biến động thấp/cao, SHOCK/HIGH_VOL) → room ≥1 ATR → stop lai ≤3 ATR → R=2, net R:R ≥1,5 → sizing 0,25%.

- **Strategy hiển thị:** `strategy_version = 1.1.0` trong `/api/v2/state` (VERIFIED IN RUNTIME). Đó là baseline V1 v1.1.0.
- **Candidate V2 có chạy live không?** KHÔNG. `core/candidate.py` không được tham chiếu trong `src/` ngoài nghiên cứu (VERIFIED, grep). Trạng thái: IMPLEMENTED + TESTED, RESEARCH ONLY.
- **Kết luận Q2:** V2 live = V1 brain. Điểm khác: ưu tiên hard gate trong đầu ra; M1 advisory; governor chèn vào lý do.
- Tương đương V1↔V2 của lõi quyết định: có test parity G4 (`V2_G4_CORE_PARITY_REPORT.md`); em **không** chạy lại so khớp theo thời gian thực trong audit này (NOT MEASURED trong P0).

## 2. Bảng V1 vs V2
| Chiều | V1 | V2 | Khác biệt thực | Bằng chứng | Phân loại / Verdict |
|---|---|---|---|---|---|
| Chiến lược lõi | baseline v1.1.0 | cùng v1.1.0 | không | `core/decision.py`, G4 | **D** |
| Candidate (C1/C2/C3/C7) | không có | có, 14 biến thể | chưa nối live, chưa có outcome | `core/candidate.py`, 0 ref live | **F** (live) / RESEARCH ONLY |
| Hard gate precedence | chuỗi báo lý do theo từng tầng | hard gate đè chuỗi | che độ sâu chuỗi (SPREAD_TOO_WIDE khi H1 NEUTRAL) | `decision.py` | **E** nhẹ |
| Nguồn dữ liệu | kho thô FTMO (có bar giả) | kho sạch có hash + `CleanBarStore` | tách và chứng minh dữ liệu | manifest 997d73f8…, 190 tháng PASS | **A** (nghiên cứu) / **B** |
| Replay tất định | không | có, restore = chạy liên tục từng bit | tái lập | `research/replay.py`, 10 test | **A** (nghiên cứu) |
| Cold start | n/a | RESTORE_PENDING ⇒ WAIT | an toàn khi mất trạng thái (chỉ candidate) | ADR-V2-020 | **B** |
| PAPER ledger | có | SQLite WAL, governor, journal, decision_log | mạnh hơn, có kiểm thử | `paper.sqlite3`, G7 | **B** |
| Lớp quyết định người | không | `human_decisions` + panel | ghi nhận quyết định + lý do | `HumanPanel.tsx`, POST /human/decision | **A** nhẹ / **C** |
| M1 execution | không (ghi nhận) | G10 advisory (chặn) | chưa đo giá trị | `core/execution.py` | **B** (UNVALIDATED) |
| ML | models V1 (800 LOC) | ML V0 | gắn CONTAMINATED, không live | register | **F** |
| Mẫu nến/pattern | `features/candles.py`, `trading/patterns.py`, `structure/*` (≈3,1k LOC có thể dùng) | chỉ `core/execution.py` | V2 **ít hơn** V1 về thư viện; V1 baseline cũng không gọi `patterns` trong quyết định (grep baseline: 0) | grep | **F** (cả hai); **E** nếu tính tài sản V1 |
| Chart | UI cũ | Vite/React, forming bar, positions overlay | UI mới tốt hơn | `ChartPanel.tsx` | **C** |
| Thang sẵn sàng | cockpit/arming/setup_machine | `readiness_level/6` ở ChartPanel; SystemPanel không có `next_condition` | giảm chi tiết so với V1 `arming`/`setup_alerts` | `SystemPanel.tsx` | **E** |
| Hợp đồng API | REST | pydantic → OpenAPI → TS types, WS có `seq` | tin cậy giao diện | OpenAPI | **B** |
| Độ trễ / hiệu năng | 1,5% CPU API | 3,6% 1 lõi / 112 MB | đo được | tiến trình | **B** |
| Quan sát / độ tươi | live.json | freshness/health endpoint, age_seconds | có số đo | `/market/quote`, `/health` | **B** |
| Kiểm thử | lớn | 1.925 pass, ruff, mypy --strict | nghiêm ngặt hơn | B3 | **B** |
| Governance nghiên cứu | rải rác | spec hash, contamination ledger, status register | kỷ luật | `docs/research/*` | **A** (nghiên cứu) |
| Alert/Telegram | có (V1) | không (ngoài phạm vi) | OOS | | n/a |
| Backtest | V1 research | clean-store backtest, bootstrap | chưa có outcome hợp lệ | `research/backtest.py` | **B** |

## 3. Nhận định tổng hợp
- **A (cải thiện thật về năng lực):** chủ yếu nằm ở *nghiên cứu và nền tảng bằng chứng*, không ở *chất lượng tín hiệu giao dịch*.
- **B/C chiếm đa số**: kỹ thuật và UI.
- **D:** toàn bộ quyết định giao dịch live.
- **E:** mất `next_condition`/arming chi tiết; hard gate che chuỗi; thư viện mẫu nến của V1 không được mang sang.
- **F:** Candidate live, ML live, nhận diện cấu trúc/thanh khoản live.

**Verdict thẳng:** V2 không phải "giao diện hào nhoáng quanh V1" theo nghĩa hẹp (nó có kho dữ liệu, replay, governance thật), nhưng **về trí tuệ giao dịch, nó là V1**. Trader chỉ nhìn thấy A ở UI qua *độ tin cậy*, không qua *nhiều cơ hội hơn hay giải thích sâu hơn*.

## 4. Chưa xác minh
So sánh trực tiếp tính năng UI `/trade` của V1 theo từng nút/panel; đo tỉ lệ BUY/SELL của V1 vs V2 trên cùng khoảng thời gian thực (cần chạy song song, nằm ngoài P0).
