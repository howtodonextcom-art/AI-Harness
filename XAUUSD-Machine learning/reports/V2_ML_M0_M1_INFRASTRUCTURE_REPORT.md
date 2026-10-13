# V2 · ML M0 và hạ tầng M1 (chỉ nghiên cứu): schema, đặc trưng nhân quả, hợp đồng nhãn, kiểm tra rò rỉ

Ngày: 2026-10-13 · Mã: `src/xau_edge_v2/ml/m0_contract.py` · Test: `tests/unit/test_ml_m0_contract.py` (10 test). **Không huấn luyện, không suy luận, không triển khai; quyền hạn NONE.** ML V0 vẫn CONTAMINATED và không hồi sinh.

## 1. Hợp đồng nhãn (không dùng PnL, không dùng kết quả lệnh)
| Nhãn | Định nghĩa | Biết khi nào |
|---|---|---|
| `vol_expansion_12.v1` | y_t = 1 nếu trong 12 nến SAU t có nến range ≥ 1,5 × ATR14_t | đóng nến t+12 (`label_known_idx = t+12`) |
| `break_failed_3.v1` | với mỗi BOS/CHoCH tại nến j: y = 1 nếu mức bị phá bị mất lại bằng một nến đóng trong ≤3 nến | đóng nến j+3; sự kiện mà cửa sổ chưa khép **không** có nhãn |

## 2. Đặc trưng (12, mỗi cái có nguồn và độ sâu lùi; tất cả nhân quả)
`atr14_rel, atr_ratio, recent_range_atr, last_range_atr, body_share, close_pos, ema_dist_atr, adx14, spread_atr, hour_sin, hour_cos, regime_code`. Hàng t chỉ dùng nến ≤ t, **biết tại đóng nến t**; 260 nến đầu là khởi động (không hợp lệ). Không điền khuyết.

## 3. Lược đồ dữ liệu và manifest
`dataset_manifest`: schema `m0-1`, nhãn, danh sách đặc trưng + nguồn, số hàng, khung, mốc đầu/cuối, **sha256** của (mốc thời gian, X, y), `authority: NONE`, `pnl_in_labels: false`; tất định (test).

## 4. Kiểm tra rò rỉ (đều đã có test)
| Kiểm tra | Cách | Test |
|---|---|---|
| Đặc trưng tại t không phụ thuộc nến sau t | thay toàn bộ nến sau t bằng giá trị khác ⇒ X[:t+1] không đổi (3 điểm t) | `test_features_at_t_do_not_depend_on_any_later_bar` |
| Bộ kiểm tra thật sự BẮT được rò rỉ | đặc trưng cố ý nhìn trước 1 nến ⇒ phép so sánh thất bại | `test_the_harness_detects_a_leaky_feature` |
| Nhãn chỉ đọc tương lai và biết đúng lúc | `known - t = 12`; nhãn tại t ≤ cut−12 không đổi khi đổi nến sau cut | `test_volatility_label_is_future_only_and_known_at_t_plus_h` |
| Nhãn không nằm trong đặc trưng | |tương quan| lớn nhất < 0,6 | `test_the_label_is_not_derivable_from_the_features_at_t` |
| Nhãn cấu trúc ổn định khi thêm nến | nhãn cũ không đổi khi nối dữ liệu | `test_break_failed_labels_are_known_only_after_the_window` |
| Purge + embargo | train chỉ gồm hàng có cửa sổ nhãn kết thúc trước (khối test − embargo); k-fold: hàng sau khối cách ≥ embargo | `test_the_purge_removes_every_row_whose_label_touches_the_test_block` |
| Provenance đủ | mỗi đặc trưng có nguồn, độ sâu, cờ nhân quả | `test_every_feature_has_provenance_and_is_causal` |

## 5. Giới hạn
- Bài toán #3 (xác suất kết quả) cần outcome nên **không** nằm ở M0/M1.
- Chưa có công suất cho từng nhãn (nhãn #1 có một hàng cho mỗi nến M15; nhãn #2 ước khoảng 20 nghìn sự kiện BOS/CHoCH trên DEV' M15, suy từ ~5 nghìn sự kiện của 2016–2018, chưa đếm trên toàn DEV'; phân tích công suất chính thức là bước M0 tiếp theo).
- Chưa có hiệu chuẩn, drift, registry mô hình cho mô hình mới (chưa có mô hình).
- Tương quan nhãn-đặc trưng < 0,6 chỉ là kiểm tra thô trên dữ liệu mô phỏng, không phải bằng chứng không rò rỉ trên dữ liệu thật.

## 6. Bước kế (cần duyệt)
Xây tập dữ liệu M0 trên kho sạch DEV' (hai nhãn), báo cáo tần suất nền và công suất, đường cơ sở tất định; chưa huấn luyện cho tới khi đường cơ sở và công suất được duyệt.
