# Nghiệm thu vòng đời paper (PAPER_LIFECYCLE_ACCEPTANCE)

Câu hỏi: một quyết định thật có đi hết `decision → mở lệnh paper → giá chạy → thoát SL/TP/thời gian → journal → MFE/MAE → marker` đúng không? Đây **không** chứng minh thực thi live và **không** là bằng chứng edge.

Trạng thái tổng: **Acceptance Replay ĐẠT; Forward live: `FORWARD_ACCEPTANCE_PENDING`** (chưa có setup thật nào xuất hiện từ khi bàn paper chạy; không giả lập tín hiệu live).

## 1. Bốn lớp bằng chứng

| Lớp | Nội dung | Kết quả |
|---|---|---|
| Test tổng hợp (đơn vị) | `test_paper_desk.py` (20 test), `test_engine_alerts_lock.py`, `test_ui_contract.py` | đạt: mở ở ask+slippage, một lệnh/setup, thoát SL/TP (SL thắng khi chạm cả hai), TIME_EXIT, đóng tay không lặp, sống qua restart, MFE/MAE tại thời điểm thoát |
| Acceptance Replay (dữ liệu đã đốt) | `scripts/trade_acceptance_replay.py`: `ReplayMarketSource → TradeEngine → decision_core → PaperDesk → journal`, AUTO_PAPER bật cục bộ, không logic riêng | đạt (mục 2) |
| Hợp đồng UI ↔ bản ghi thật | `test_ui_contract.py` + e2e dùng bản ghi desk THẬT (`e2e/fixtures/real_paper_trade.json`) | đạt; phát hiện và sửa lệch tên trường (mục 4) |
| Forward live | bàn paper chạy trong API, theo dõi mỗi nến M1 đóng | **PENDING** (mục 5) |

## 2. Acceptance Replay (dữ liệu đã đốt: E1 2025-08-04→09-01, E2 2025-12-01→12-29)

| Run | Quyết định | Lệnh paper | BUY/SELL | Thoát | Journal (pending/open/close) | Vấn đề |
|---|---|---|---|---|---|---|
| v1.1.0 E1 | 5 460 | 4 | 1 / 3 | STOP_LOSS 2, TAKE_PROFIT 1, TIME_EXIT 1 | 4/4/4 | 0 |
| v1.2.0 E1 | 5 460 | 3 | 1 / 2 | STOP_LOSS 3 | 3/3/3 | 0 |
| v1.2.0 E2 | 5 149 | 4 | 3 / 1 | TAKE_PROFIT 1, STOP_LOSS 3 | 4/4/4 | 0 |

Đã xác minh: có cả BUY và SELL; có đủ SL, TP và TIME_EXIT; mỗi lệnh có dòng `paper.pending`, `paper.open`, `paper.close`; không mở trùng một setup (0); mọi lệnh đóng có `exit_reason`, `exit_price`, `net_pnl`, `r_multiple`, `mfe_r`, `mae_r`, `duration_minutes`; SL/TP đúng phía; lệnh dính SL có R ≈ −1.00 (cộng chi phí) và MAE = 1.00R; lệnh chạm TP có MFE = 1.98R (không vượt mục tiêu).

Kết quả mô phỏng (THĂM DÒ, rất nhỏ): v1.1 4 lệnh −0.47R; v1.2 7 lệnh −4.05R (1 TP, 6 SL). Không tối ưu, không dùng để chọn cấu hình; edge validation = 0%.

## 3. Sai sót đo được tìm thấy nhờ nghiệm thu (đã sửa)

1. **MAE/MFE tính cả phần sau thời điểm thoát**: lệnh dính SL có MAE tới 3.28R và MFE của nến chạm SL vẫn được ghi, trong khi lệnh bị cắt ở −1.0R. Nay `PaperDesk._settled_excursions` chốt MFE/MAE tại lúc thoát (SL: MAE ≤ khoảng cách thoát, MFE không tính nến chạm SL vì SL được xét trước; TP: MFE ≤ mục tiêu). 3 test mới.
2. **Lệch tên trường UI ↔ backend**: UI và API markers đọc `initial_tp`, nhưng bản ghi desk ghi `tp` (và `sl` hiện hành), nên lệnh paper thật sẽ hiện TP "—" và không có đường TP trên biểu đồ; mock e2e che lỗi này. Đã sửa (`tp`, `sl`, `decision`), thêm test hợp đồng trên bản ghi thật và e2e dùng bản ghi thật.

## 4. Journal và provenance

Mỗi bản ghi có `code_version`, `strategy_version`, `strategy_id`, `evidence_status`, ảnh chụp `decision` đầy đủ, `market` (phiên, H4/H1/M30/M15/M5/M1, volume_type TICK_VOLUME, spread, ATR, biến động, tin tức, tuổi dữ liệu, `setup_phase`), `quote` lúc vào, `planned_entry` so với `fill_price`. Journal chỉ thêm (append-only) và đọc lại được sau restart.

## 5. Forward live (FORWARD_ACCEPTANCE_PENDING)

Bàn paper chạy liên tục trong API (`EngineRunner`, bước mỗi 5 s, tính lại khi có nến M1 đóng). Ghi mọi quyết định mỗi phút (`data/trade/decisions-YYYYMMDD.jsonl`), log tín hiệu hành động (`signals-YYYYMMDD.jsonl`), cảnh báo `*_SETUP_READY` mỗi setup một lần (Telegram nếu cấu hình, nếu không file). Soak 40 phút ngày 2026-10-09: 477 lần poll, 0 lỗi, 0 flicker, 0 vi phạm, 100% WAIT. Từ khi chạy bản mới (15:08 UTC) chưa có setup. Theo tần suất đo được (0.1–0.23 setup/ngày), có thể mất vài ngày đến vài tuần.

Điều kiện đạt forward: một setup thật → owner bấm PAPER BUY/SELL → vị thế thoát bằng SL/TP/thời gian/đóng tay → journal và marker đúng. **Chưa đạt, không giả lập.** Mặc định vẫn là xác nhận thủ công; `XAU_EDGE_AUTO_PAPER=true` là tùy chọn cục bộ chỉ chạm bàn paper (không thể tới `order_send`).
