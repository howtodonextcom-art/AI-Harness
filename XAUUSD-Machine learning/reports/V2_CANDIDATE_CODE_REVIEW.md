# V2 · Rà soát mã Candidate V2 (`core/candidate.py`, `research/*`, Stage A/B)

Ngày: 2026-10-13 · Phương pháp: đọc từng nhánh, viết kiểm thử đặc trưng cho từng nghi vấn, sửa chỉ những lỗi không đổi ngữ nghĩa spec · Không chạy lại outcome.

## 0. Kết luận
- **Không có lỗi nhìn trước trong mã.** Mọi đầu vào của `candidate_step` là trạng thái đã đóng; lỗi nhìn trước nằm ở **dữ liệu** (pseudo-bar), xem báo cáo pháp y.
- **Tìm ra 3 lỗi đã sửa** (kiểm toán và nguồn chi phí), **1 lỗi MỞ cần sửa spec** (tính tất định khi khởi động lại), 2 điểm nhỏ, và **thiếu một chốt chặn dữ liệu** trong pipeline (đã thêm). Chiến lược gốc V1 không đổi (test khóa xanh).
- Mọi lỗi có kiểm thử hồi quy. Lỗi mở được ghim bằng `xfail(strict=True)`: khi ai đó sửa, test chuyển đỏ và buộc phải cập nhật.

## 1. Bảng phát hiện
| # | Hạng mục | Mức | Phát hiện | Trạng thái |
|---|---|---|---|---|
| F1 | C1: "trạng thái thô và trạng thái bị thay" | Cao (kiểm toán) | Khi trí nhớ C1 thay nhãn M15, `Decision.state` chứa nhãn **đã thay** (V1 `decide` đóng gói `state=work`). UI, nhật ký, `advice` sẽ hiển thị "M15 pullback" mà thị trường không có | **ĐÃ SỬA**: `decision.state` luôn là trạng thái thô; thêm dòng lý do "C1: setup remembered (armed at bar …), raw M15 …" |
| F2 | C2: nguồn spread của màn lọc chi phí | Trung bình | Màn `cost_R` đọc `state.spread` (bar M5 cuối), trong khi lệnh được vào ở **quote M1 thực thi** (spec: execution_timing). Quote rộng hơn bar M5 vẫn qua; ngược lại bị loại oan | **ĐÃ SỬA**: `quote_spread_points(ctx, state)`: dùng (ask − bid) khi ngữ cảnh có quote, ngược lại spread của trạng thái. Chỉ khác kết quả đúng ở các trường hợp lỗi |
| F3 | C2: tránh tính đôi | Thông tin | Đã kiểm: `net_rr` (cổng kế hoạch của control, giữ nguyên), `cost_R` (màn lọc), PnL thực (kế toán) là ba thứ riêng; chỉ PnL thực vào endpoint. **Phát hiện thêm:** `net_rr` của control trừ spread dù BUY đã vào ở ask ⇒ bảo thủ cho BUY. Đã ghi trong spec, không sửa (bất biến) | Không lỗi; ghi chú |
| F4 | C2: early return | Thấp | Nhánh `elif cfg.c2` chỉ chạy khi guard SHOCK không bắn, nên `StepInfo.cost_r` bị bỏ trống khi SHOCK chặn. Không đổi quyết định | Chấp nhận, ghi chú |
| F5 | C3b: `StepInfo.guard` | Thấp | Nhãn guard còn được đặt ở nhánh WAIT dù guard không đổi quyết định ⇒ nhật ký gây hiểu lầm | **ĐÃ SỬA**: guard chỉ ghi khi nó đã đổi quyết định |
| F6 | C1: tính tất định khi khởi động lại | **Cao (spec)** | `planned_stop` được tính tại **bar bắt đầu arm** (đúng spec). Một setup "armed" liên tục lâu hơn đoạn phát lại sẽ có `planned_stop` **khác nhau** tùy bắt đầu phát lại từ đâu. Stage A phát lại 40 bar đầu mỗi tháng; live khởi động lại cũng vậy. Bất biến hóa chỉ bởi `STOP_LEVEL` | **MỞ.** Cần amend spec (xem §3). Test `xfail(strict)` chứng minh khác biệt |
| F7 | C7 | Thấp | Cô lập: cờ mặc định tắt, biến thể `X_*` không thuộc `CORE_TIER`, test khẳng định không có trong ứng viên đóng băng. Rủi ro: C7 thay **cả hai** khoảng cách và có thể bỏ "không có cản" ⇒ không giới hạn TP | Chấp nhận (exploratory, ghi rõ) |
| F8 | Pipeline: chốt chặn dữ liệu | **Cao** | Stage A/B không từ chối tháng có pseudo-bar, nên đã chạy trên dữ liệu nhìn trước | **ĐÃ THÊM**: `require_clean()` trong `cand_signals`, `funnel_audit`, `cand_evaluate` (từ chối trừ khi `XAU_ALLOW_DEFECTIVE=1`), test thật chạy trên tháng lỗi 2016-05 thấy `DataDefectError` |
| F9 | Stage A | Thấp | Một lần chạy "smoke test" nhầm tháng Validation 2019-02 (không outcome, đã xóa kết quả) | Ghi trong sổ nhiễm; Stage A từ chối cửa sổ ngoài DEV nếu thiếu `--confirm` |

## 2. Các mục yêu cầu rà soát
| Yêu cầu | Kết quả |
|---|---|
| C1 lifecycle & invalidation | 9 điều kiện vô hiệu được kiểm từng cái (H1 đổi hướng/trung tính, H4 phủ quyết, M15 ngược/REVERSAL, SHOCK, dữ liệu cũ, thị trường đóng, M5 đóng ngoài mức stop dự kiến). Bộ nhớ hết hạn đúng sau 6 bar. F1 và F6 là lỗi ở đây |
| Raw versus substituted state | F1 (đã sửa). Bất biến mới: nhãn thay chỉ khi H1 vẫn cùng phía và bộ nhớ còn hiệu lực |
| C2 cost gate, early returns, double counting | F2, F3, F4 |
| C3a/C3b guards | C3a chỉ bỏ cổng LOW; C3b thay HIGH + H4 HIGH_VOLATILITY bằng SHOCK (H4 SHOCK vẫn chặn); guard SHOCK thuộc C3b, không ở C3a (test). F5 |
| C7 isolation | F7 |
| Parity khi mọi cờ tắt | **Đúng từng bit** trên 1.500 trạng thái ngẫu nhiên × 4 hình dạng ngữ cảnh (quote đầy đủ, không quote, không equity, thiếu ask) × bộ nhớ mang qua bar; `Memory()` luôn rỗng khi C1 tắt |
| Closed-bar-only & no-lookahead | Mã: đạt (hàm thuần, đầu vào đã đóng; `Observation` tính từ `as_of`). Dữ liệu: **không đạt** do pseudo-bar. M1 quote lấy từ bar đóng đúng phút quyết định |
| Replay / restart determinism | F6 (mở). Phần tất định được chứng minh: sau khi setup tắt hơn cửa sổ nhớ + 1 bar, mọi lần khởi động lại cho cùng `Memory()` |
| PAPER-only & broker isolation | `core/candidate.py` và `research/*` không import broker/mạng/tiến trình, không có `order_send`, `open_position` (test AST). OpenAPI vẫn 3 POST. `terminal_dump.py` nằm ngoài gói V2, chỉ `copy_rates_range` |

## 3. Lỗi mở F6: đề xuất sửa (cần chủ dự án duyệt vì đổi ngữ nghĩa spec)
1. **Làm mới mức vô hiệu theo bar armed gần nhất** (đề xuất): `planned_stop` = stop tính tại bar armed **gần nhất**, không phải bar đầu. Bộ nhớ chỉ phụ thuộc ≤ 7 bar cuối ⇒ phát lại 40 bar là đủ, đồng nhất live/backtest. Đổi ngữ nghĩa: mức vô hiệu "trượt" theo swing M5.
2. **Lưu bộ nhớ bền** (SQLite) và phát lại từ điểm lưu: giữ ngữ nghĩa spec nhưng chỉ cho live; backtest theo tháng vẫn sai nếu không chạy liên tục.
3. **Chạy backtest liên tục không cắt tháng** (không có warm-up) + live lưu bền: đúng spec nhưng phụ thuộc hạ tầng.
Khuyến nghị: (1). Tới khi được duyệt, mọi kết quả Stage A có thể phụ thuộc điểm cắt tháng ở một số setup hiếm.

## 4. Ảnh hưởng của các sửa lên Stage A/B cũ
Các số Stage A/B hiện tại **vô hiệu vì dữ liệu**, nên các sửa F1/F2/F5 không làm thay đổi kết luận. Khi chạy lại trên dữ liệu đã làm sạch, F2 có thể thay đổi tập tín hiệu C2 ở các bar mà quote M1 rộng hơn spread M5.

## 5. Kiểm thử
Xem `V2_GATE_B_REGRESSION_TEST_REPORT.md`. `tests/unit/test_candidate.py` (+12 test hồi quy, 1 xfail), `tests/unit/test_clean_view.py` (9 test).
