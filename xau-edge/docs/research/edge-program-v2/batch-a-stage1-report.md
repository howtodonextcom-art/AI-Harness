# Batch A, Stage 1 (Development-2): báo cáo kết quả

Ngày chạy: 2026-10-09 (UTC). Evidence class: **SCREENING**. Mã: `scripts/run_batch_a.py`, commit `09cc128`
(cây sạch, đăng ký H07-H10 commit `f83782d` trước khi tính bất kỳ kết quả nào). Dữ liệu: bộ nghiên cứu H1/H4
đúng như lưu (hash trong từng file kết quả), cửa sổ Development-2 2011-01-01..2018-12-31. **Test-H và Holdout
không bị chạm.** Kết quả gốc: `experiments/edge_program_v2_stage1/*.json`; sổ: `ledger.md` (20 dòng).

## Kết luận

**Không có biến thể nào sống sót Stage 1.** Holm-Bonferroni (family-wise 0.10, 20 biến thể) không bác bỏ H0
cho biến thể nào, và mean net R bi quan âm ở cả 20. Theo Gate A của roadmap: *không có survivor trên
Development-2*. Đây là kết quả khoa học hợp lệ: **NO EDGE FOUND trong Batch A (K = 20)**. Không có gì được
thăng cấp lên Validation-2 hay Test-H.

## Bảng kết quả (mean R mỗi sự kiện; gross-mid là giá giữa không phí)

| Biến thể | N | Gross-mid | Net base | Net bi quan | p (một phía) | Kết quả |
|---|---|---|---|---|---|---|
| H07-PD-e0 | 1608 | -0.598 | -0.700 | -0.714 | 1.0000 | FAIL |
| H07-PD-e0.25 | 1524 | -0.617 | -0.718 | -0.732 | 1.0000 | FAIL |
| H07-PD-e0.5 | 1404 | -0.614 | -0.715 | -0.729 | 1.0000 | FAIL |
| H07-ASIA-e0 | 2142 | -0.144 | -0.282 | -0.299 | 1.0000 | FAIL |
| H07-ASIA-e0.25 | 1719 | -0.162 | -0.302 | -0.319 | 1.0000 | FAIL |
| H07-ASIA-e0.5 | 1324 | -0.168 | -0.309 | -0.325 | 1.0000 | FAIL |
| H08-ASIA-e0 | 777 | -0.059 | -0.209 | -0.226 | 1.0000 | FAIL |
| H08-ASIA-e0.25 | 640 | -0.071 | -0.223 | -0.239 | 1.0000 | FAIL |
| H09-ASIA_LONDON-t0.2 | 752 | +0.074 | -0.053 | -0.070 | 0.8429 | FAIL |
| H09-ASIA_LONDON-t0.3 | 1206 | +0.065 | -0.059 | -0.077 | 0.9248 | FAIL |
| H09-ASIA_LONDON-t0.4 | 1598 | +0.071 | -0.055 | -0.072 | 0.9362 | FAIL |
| H09-LONDON_NY-t0.2 | 625 | -0.024 | -0.165 | -0.183 | 0.9984 | FAIL |
| H09-LONDON_NY-t0.3 | 1086 | +0.027 | -0.112 | -0.130 | 0.9952 | FAIL |
| H09-LONDON_NY-t0.4 | 1497 | +0.034 | -0.105 | -0.123 | 0.9978 | FAIL |
| H10-c0.8-L20 | 661 | -0.143 | -0.295 | -0.315 | 1.0000 | FAIL |
| H10-c0.8-L50 | 661 | +0.025 | -0.129 | -0.149 | 0.9900 | FAIL |
| H10-c0.8-L100 | 661 | +0.025 | -0.128 | -0.148 | 0.9896 | FAIL |
| H10-c0.9-L20 | 1230 | -0.103 | -0.244 | -0.263 | 1.0000 | FAIL |
| H10-c0.9-L50 | 1230 | -0.001 | -0.142 | -0.161 | 0.9998 | FAIL |
| H10-c0.9-L100 | 1230 | +0.009 | -0.133 | -0.152 | 0.9995 | FAIL |

Đọc đúng: ở H09 và H10 gross-mid gần 0 hoặc dương nhẹ nhưng chi phí (spread tối thiểu 30 points, slippage,
swap theo giá trị terminal hiện tại, một anachronism bi quan) kéo net xuống âm. Độ nhạy swap là chẩn đoán Class D
và **không** được dùng để cứu một biến thể.

## Công suất và phụ thuộc

Mọi biến thể đều "đủ công suất" theo MDE hiệu dụng (0.12-0.18R tại K = 20, sd giả định 1.3R), nên các khoảng
tin cậy day-block loại trừ edge lớn hơn khoảng +0.05R net ở H09-ASIA_LONDON (ví dụ CI 95% của t0.2:
[-0.155, +0.049]), chứ không chỉ "không thấy". Mọi biến thể DEPENDENCE_STABLE (1, 2, 5 ngày). Đa số
INTRABAR_ROBUST; H08-ASIA-e0 và H10-c0.9-L50 là INTRABAR_SENSITIVE (cần dữ liệu khung nhỏ hơn nếu từng được xét).
Kỷ nguyên: Development-2 chỉ có giai đoạn trước 2021 nên báo cáo kỷ nguyên là UNKNOWN (không giả vờ).

## Chẩn đoán Class D: nhánh đối chứng PD (KHÔNG phải bằng chứng, KHÔNG phải giả thuyết đã đăng ký)

Phân rã attribution của H07-PD cho thấy hướng *đảo chiều* thua nặng (net -0.70R, percentile placebo 0.0) trong khi
cùng các mốc thời gian đó nhưng **theo chiều cú quét** có mean net +0.48R. 85% sự kiện PD xảy ra ở 1-2 giờ đầu
của ngày giao dịch (21:00-23:00 UTC, quanh rollover 17:00 New York). Đây là một *gợi ý* về tính tiếp diễn quanh
rollover, trên đúng dữ liệu đã dùng để thiết kế (Development-2).

Quy tắc áp dụng:

* Không có biến thể "tiếp diễn sau quét PD" nào được đăng ký, nên **không thể được chạy hay thăng cấp**; chạy
  nó trên Development-2 sau khi đã thấy con số này sẽ là chọn giả thuyết theo kết quả (forking paths).
* Muốn kiểm tra, phải đăng ký một giả thuyết mới (tính vào K, cần quyết định của chủ dự án vì Batch B của
  roadmap không có giả thuyết này) và chỉ được đánh giá trên **dữ liệu chưa xem** (Validation-2 theo luật
  của roadmap, rồi Test-H), không phải trên Development-2.
* Nó được ghi vào sổ bậc tự do (`design-ledger.jsonl`) như tri thức đã biết, để mọi giả thuyết sau này phải
  khai báo.
* Cảnh báo giải thích: sự kiện tập trung ở giờ rollover nơi spread, thanh khoản và cách ghi giá bar khác
  thường; một hiệu ứng như vậy cần kiểm chứng bằng dữ liệu tick/M1 và broker thứ hai trước khi tin.

## Trạng thái cổng

| Cổng | Trạng thái |
|---|---|
| Gate A (survivor Stage 1 trên Development-2) | **KHÔNG**. Dừng hoặc P8 (Batch B) |
| Batch B (H11-H14) | **OWNER_ACTION_REQUIRED**: prompt hiện tại chỉ cho phép H07-H10 |
| Stage 2 / Validation-2 | Không chạy (không có survivor) |
| Test-H, Holdout | **Không mở** |
