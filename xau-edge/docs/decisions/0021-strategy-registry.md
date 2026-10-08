# ADR-0021: Strategy registry và evidence gate theo strategy_id + config hash + dataset hash

Status: accepted (2026-10-08). Bổ sung (không thay thế) ADR-0017.

**Bối cảnh.** ADR-0017 gắn evidence gate với đúng một cấu hình: Baseline C (`evidence_params()`
trong `signals/engine.py`). Baseline C đã FAIL, nên tín hiệu luôn `WAIT`; nhưng về cấu trúc, một
chiến lược mới PASS cả Dev/Val/Test cũng không thể mở gate vì gate chỉ nhìn Baseline C
(`00-diagnosis.md`, mục 5, rào cản hạ tầng).

**Quyết định.**

* Mới `signals/strategy_registry.py`: `StrategySpec(strategy_id, family, params)`, `config_hash`
  (hash của params, bất kể thứ tự khóa), `dataset_hash` (hash của `{timeframe: dataset_id}`),
  `StrategyRegistry` (đăng ký/tra cứu theo id) và `default_strategy()` = Baseline C.
* `signals/evidence.py`: `evidence_for_strategy(registry, spec, dataset=None)`. VALIDATED chỉ khi,
  cho record mới nhất của mỗi giai đoạn development/validation/test: `params["strategy"] ==
  strategy_id`, config hash khớp spec, cả ba chạy trên cùng dataset, cây git sạch, cả ba PASS, và
  (nếu truyền `dataset`) dataset hash bằng giá trị yêu cầu. Thay đổi bất kỳ tham số nào là một danh
  tính khác, không thừa hưởng evidence. `evidence_status(family, params)` cũ giữ nguyên (API, test).
* `generate_signal(..., strategy=None, dataset=None)`: mặc định Baseline C, nên hành vi hiện tại
  không đổi. `EVIDENCE_FAMILY` và `evidence_params()` giữ lại cho `api/app.py`.

**Bất biến giữ nguyên.** Không có strategy VALIDATED thì quyết định luôn là WAIT
(`NO_VALIDATED_EDGE`); schema vẫn cấm BUY/SELL khi không có evidence; Test vẫn khóa theo
`evaluation/periods.py` và `run_backtest.py`. Registry chỉ đặt tên, không bao giờ cấp evidence.

**Chưa làm (cố ý).** Engine vẫn dựng input từ analogue (Baseline C). Một strategy khác muốn lái
BUY/SELL cần bộ dựng input riêng + ADR ủy quyền riêng + test parity backtest-vs-engine; việc đó
chỉ làm khi có strategy PASS (Edge Program, T1.6 nhánh A).

**Hệ quả.** Mỗi strategy mới được ủy quyền bằng ADR riêng; thêm strategy vào registry không đủ để
trade.
