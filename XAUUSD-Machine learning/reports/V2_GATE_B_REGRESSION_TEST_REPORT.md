# V2 · Báo cáo kiểm thử hồi quy Gate B

Ngày: 2026-10-13 · Kết quả toàn bộ: **1.891 passed, 1 xfailed** (trước Gate B: 1.872) · `ruff` sạch · `mypy --strict` 58 tệp sạch · test khóa chiến lược V1 xanh · OpenAPI không đổi (3 POST) · spec hash không đổi.

## Kiểm thử mới theo lỗi
| Lỗi / yêu cầu | Test | Khẳng định |
|---|---|---|
| F1 trạng thái bị "rửa" bởi C1 | `test_defect_a_substituted_setup_must_not_launder_the_state_of_the_decision` | `decision.state is raw`, `m15_pullback == "NONE"`, có dòng lý do "C1: setup remembered …" |
| F1 (nhánh veto) | `test_defect_a_veto_keeps_the_raw_state_too` | `decision.state is state` khi guard biến BUY thành WAIT |
| F2 spread của màn chi phí | `test_defect_cost_screen_must_use_the_executable_quote_spread` | quote rộng ⇒ `COST_TOO_HIGH` dù bar M5 êm; quote hẹp ⇒ BUY dù bar M5 rộng |
| F2 (cập nhật các test C2 cũ) | `test_c2_prices_cost_against_risk_…`, `test_c2_refuses_when_cost_is_a_large_share_of_the_risk`, test thuộc tính bất biến | dùng `quote_spread_points` |
| F5 tên guard | `test_guard_info_only_names_a_guard_that_changed_the_decision` | `info.guard is None` khi control đã WAIT; `SHOCK_GUARD` khi guard đổi quyết định |
| Parity mọi cờ tắt | `test_parity_holds_for_every_context_shape_and_with_memory_carried` (4 tham số) | `decision == decide(...)` và `Memory()` rỗng; 400 trạng thái × 4 hình dạng ngữ cảnh |
| F6 khởi động lại (MỞ) | `test_open_defect_planned_stop_depends_on_the_replay_start` | `xfail(strict=True)`: `planned_stop` khác nhau giữa chạy liên tục và phát lại 40 bar |
| Phần tất định của khởi động lại | `test_a_restart_that_replays_more_than_the_memory_window_is_identical_when_the_setup_is_not_armed` | bộ nhớ cuối giống hệt, bằng `Memory()` |
| Cô lập PAPER/broker của gói nghiên cứu | `test_research_modules_have_no_broker_network_or_process_path` | không import MetaTrader5/requests/socket/subprocess…; không `order_send`/`open_position` |
| Pseudo-bar: phát hiện | `tests/unit/test_clean_view.py` (9 test) | bar 2013-05-14 bị bắt; bar đầu sau khoảng nghỉ (2021, vài nghìn tick) **không** bị bắt; đủ 3 điều kiện chữ ký; giờ mùa đông 22:00; `strip` trả bản sao và số bar; `require_clean` ném `DataDefectError` |
| Pseudo-bar: nguyên nhân tự tương quan | `test_the_pseudo_bar_creates_the_mean_reversion_and_removing_it_removes_it` | chuỗi bước ngẫu nhiên + 1 bar giả/ngày ⇒ tự tương quan toàn chuỗi < −0,25; bỏ bar ⇒ |·| < 0,1 |
| F8 chốt chặn pipeline | chạy thật `cand_signals.py` trên 2016-05 | `DataDefectError: 2016-05 M1: 25 daily pseudo-bar(s)` (không có test đơn vị vì cần kho thật) |

## Kiểm thử đã có từ trước và vẫn xanh
`test_candidate.py` (đối xứng BUY/SELL từng biến thể, bất biến an toàn qua 2.400 bước ngẫu nhiên, không bao giờ trái hướng H1, tất định, spec khớp mã, C1–C3b–C7 từng nhánh), `test_research_backtest.py` (luật fill PAPER, governor, bootstrap, trạng thái, bảng công suất), `test_cand_freeze.py` (băm spec, cửa sổ khóa), `test_strategy_lock.py` (sha256 7 tệp chiến lược + hằng số).

## Không được kiểm bằng test đơn vị (nêu rõ)
- Phát hiện pseudo-bar trên kho thật: chạy bằng `scripts/research/data_forensics.py` (kết quả trong `docs/research/data_forensics_xauusd.json`, 104 tháng, 2.205 bar, 0 bar ngoài giai đoạn).
- Tái lập pháp y: `terminal_dump.py` cần terminal MT5 đang mở; đã chạy một lần, dữ liệu tải được lưu nén cùng băm.
- Công suất mô phỏng (Monte Carlo): `scripts/research/power.py --mc`, không phải test.
- Tính tất định end-to-end của Stage A giữa các lần chạy: chưa kiểm (phụ thuộc F6).
