# Đối chiếu nền tảng nghiên cứu (RI-01)

Ngày: 2026-10-09. Mục đích: rút ra **ý tưởng dùng lại được** cho XAU EDGE từ các hệ thống nghiên cứu/giao dịch
đã có tên tuổi, không thêm phụ thuộc nặng. Nguyên tắc: *lấy mẫu thiết kế, không lấy phần mềm*.

Nguồn đã đọc (tài liệu chính thức, 2026-10-09): DVC (doc.dvc.org, Experiment Management), MLflow
(mlflow.org, Tracking), Qlib (qlib.readthedocs.io, Recorder), NautilusTrader (nautilustrader.io, Overview),
Freqtrade (freqtrade.io, Lookahead analysis). Trang tài liệu LEAN (lean.io) trả lỗi HTTP 500 và URL còn lại
trả 404 vào ngày đọc, nên **dòng LEAN dưới đây dựa trên hiểu biết có sẵn, không trích dẫn trang mới**.

| Hệ thống | Năng lực liên quan | Cách hoạt động | Hữu ích cho XAU EDGE? | Quyết định | Lý do | Mục tiêu triển khai |
|---|---|---|---|---|---|---|
| DVC Experiments | Định danh thí nghiệm gắn code + dữ liệu + tham số | Mỗi thí nghiệm là một tham chiếu git ẩn gắn với commit gốc; tham số, metric, plot đọc từ file có cấu trúc (YAML/JSON/CSV); tên tự sinh | Có: nguồn gốc dữ liệu, mã, tham số phải cùng một danh tính | **Adapt** | Không cần DVC; đã có git và registry. Lấy ý "danh tính = băm của (code, data, params)" | `research/identity.py`: băm chuẩn tắc, `experiment_id` tất định |
| MLflow Tracking | Run, params, metrics, artifacts, datasets, lineage model | `log_param/metric`, `log_input` gắn dataset với run, registry có vòng đời và phiên bản | Có: mô hình dữ liệu run, gắn dataset với run, vòng đời | **Adapt** | Server và DB quá nặng cho một kho local; mô hình dữ liệu thì phù hợp | `research/manifest.py`, vòng đời đã có (ADR-0024) |
| Qlib Recorder | Experiment → Recorder → run; lưu object/artifact, tải lại, so sánh | `log_params/metrics`, `save_objects`, `search_records` trả bảng so sánh | Có: tải lại artifact theo tên, so sánh nhiều run | **Adapt** | Pickle không tương thích môi trường: **từ chối pickle**, dùng JSON chuẩn tắc + băm | Manifest JSON bất biến, băm đầu ra |
| QuantConnect LEAN | Tách module nghiên cứu / backtest / live, cùng một thuật toán | Handler cắm được (data feed, fill, result), một thuật toán chạy ở cả hai chế độ | Có: tách quyết định khỏi môi trường chạy | **Adapt** (chưa xác minh bằng trang mới) | Đã có `signals` dùng chung backtest/live; cần thêm kiểm thử tương đương | Kiểm thử parity RI-12 |
| NautilusTrader | Tương đương nghiên cứu/live, xác định, event-sourcing | Cùng mã chiến lược cho backtest và live; lõi xác định theo sự kiện; message bus | Có: replay xác định, nhật ký sự kiện kiểm toán | **Adapt** | Không đổi engine; thêm lược đồ sự kiện và replay trên nhật ký hiện có | `research/events.py`, replay test, nhật ký tiên nghiệm |
| Freqtrade | Phát hiện nhìn trước (lookahead/recursive analysis), dry-run | Chạy backtest đầy đủ rồi chạy lại từng cặp/cắt cụt, so tín hiệu có đổi không | Có: kiểm thử cắt cụt và "rác tương lai" cho tín hiệu | **Adopt (ý tưởng)** | Là đúng kiểm thử rò rỉ mà ta cần cho máy trạng thái sự kiện | Test truncation/repaint/future-garbage RI-07 |
| Weights & Biases | Theo dõi thí nghiệm dạng dịch vụ | SaaS | Không | **Reject** | Gửi dữ liệu ra ngoài, vi phạm nguyên tắc cục bộ | — |

## Không áp dụng

* Không thêm `dvc`, `mlflow`, `qlib`, `lean`, `nautilus_trader`, `wandb` làm phụ thuộc (quy tắc 37 của prompt).
* Không dùng pickle làm định dạng artifact.
* Không dựng tracking server; kho là file trong git và `experiments/`.

## Hệ quả thiết kế

1. Danh tính thí nghiệm là **băm chuẩn tắc** của các trường định danh; cùng đầu vào cho cùng `experiment_id`.
2. Manifest bất biến, tạo mới theo phiên bản, không ghi đè.
3. Nhật ký tiên nghiệm là chuỗi băm chỉ thêm vào cuối (kiểu event-sourcing).
4. Kiểm thử cắt cụt kiểu Freqtrade được dùng làm bất biến của mọi bộ phát hiện sự kiện.
