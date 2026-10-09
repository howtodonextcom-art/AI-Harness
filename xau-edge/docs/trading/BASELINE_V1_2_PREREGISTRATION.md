# Pre-đăng ký baseline v1.2.0 (viết TRƯỚC khi chạy bất kỳ kết quả ứng viên nào)

Trạng thái: **đăng ký trước**. Commit chứa tài liệu này phải đứng trước commit cài đặt v1.2. Không có kết quả của v1.2 nào tồn tại tại thời điểm viết.

Nhãn bằng chứng không đổi: `UNVALIDATED_OPERATIONAL_BASELINE`. Mục tiêu là *sử dụng được về logic*, không phải lợi nhuận. Không có phần trăm tin cậy, không tuyên bố edge.

## 1. Vấn đề (đã đo, không phỏng đoán)

Dữ liệu chẩn đoán: 3 cửa sổ đã đốt (2025-06-02→06-30, 2025-11-03→12-01, 2026-02-02→03-02), 16 270 quyết định M5, phiên bản v1.1.0, `scripts/signal_funnel_dump.py`. Kết quả: 2 BUY, 16 268 WAIT. Số liệu then chốt:

| Phát hiện | Số liệu |
|---|---|
| Cổng spread + biến động loại bỏ phần lớn *thời gian quyết định* nhưng gần như không loại tín hiệu | còn 45.4% quyết định sau 3 cổng; gỡ TẤT CẢ cổng ngữ cảnh (spread, 2 biến động, M1 quiet, H4) chỉ nâng 2 → 10 tín hiệu |
| M15 setup và M5 trigger trên cùng một nến | 156 lần (46/46/64 theo cửa sổ) so với 304 nếu độc lập: **tương quan âm** (pullback là nhịp ngược xu hướng, trigger là động lượng quay lại) |
| Nếu cho phép trigger sau setup trong N nến M5 | N=3: 294, N=6: 411, N=12: 591 nến trigger có setup sẵn sàng (so với 156 cùng nến) |
| Hình học kế hoạch tại 156 nến setup+trigger | stop = 1.47 ATR(M15) (trung vị) trong khi ATR(M5)/ATR(M15) = 0.53; chỗ trống tới mức M15 đối diện = 1.15 ATR(M15) so với cần 2.21 ATR(M15) cho R/R ròng 1.5 ⇒ **90% thiếu chỗ**; chỉ 11/156 qua `rr_ok` |
| `clearance_ok` (≥1 ATR) và `rr_ok` | `rr_ok` luôn chặt hơn (cần ≈1.9 ATR); tại 91 nến qua clearance chỉ 11 qua RR ⇒ clearance không có tác dụng độc lập (bị RR bao hàm) |
| Cổng biến động | nhãn LOW/HIGH là phân vị cuốn chiếu 200 nến ATR(M15): LOW 22–36%, HIGH 15–24% tùy cửa sổ. ATR(M15) tuyệt đối trung vị khi nhãn LOW = 7.06 USD, khi HIGH = 8.79, toàn bộ = 7.65 ⇒ nhãn phản ánh *tương đối với 2 ngày gần nhất*, không phải biến động bất thường tuyệt đối |

Nguyên nhân gốc (xếp theo tác động lên tín hiệu): (1) **hình học kế hoạch không nhất quán thang thời gian** — vào lệnh ở M5 nhưng stop/đệm/ATR-floor đo ở M15 trong khi mục tiêu bị chặn ở mức M15 gần nhất ⇒ R/R ≥ 1.5 gần như không thể với pullback; (2) **đòi hỏi đồng thời** pullback M15 và trigger M5 trên cùng một nến trong khi hai điều kiện có tương quan âm theo định nghĩa; (3) cổng biến động tương đối cứng; ảnh hưởng nhỏ lên số tín hiệu nhưng che 50% trạng thái. Không phải: lỗi tính toán (không có mức hỗ trợ/kháng cự sai phía; tính lại độc lập khớp), không phải timeframe không thể đồng thời thỏa (156 trường hợp cùng nến tồn tại).

## 2. Giả thuyết

H-A: pullback là nhịp ngược xu hướng và trigger là sự quay lại; mô hình tuần tự `ARMED → TRIGGERED` phản ánh đúng khái niệm giao dịch hơn confluence cùng nến.
H-B: stop và đệm phải đo theo thang thời gian của trigger (ATR(M5)) để R/R so với mức cấu trúc M15 có thể đạt được; `clearance_ok` là cổng thừa.
H-C: nhãn biến động phân vị cuốn chiếu là chỉ báo ngữ cảnh, không phải điều kiện cấm tuyệt đối; bảo vệ cứng còn lại là spread/M1 bất thường/H4 SHOCK|HIGH_VOLATILITY/stop tối đa 3 ATR.

## 3. Thay đổi chính xác (tối đa 3, không đổi bất kỳ ngưỡng số nào)

**A. Vòng đời setup (stateless, tất yếu từ nến đã đóng).** Với 36 lần đóng M5 gần nhất kết thúc tại thời điểm quyết định:
`NONE → ARMED` khi H1 có hướng và M15 setup (structure cùng hướng + pullback, định nghĩa v1.1 giữ nguyên) sẵn sàng; `ARMED` tồn tại tối đa **N = 6 nến M5** (= 2 nến M15, định trước, không chỉnh); `ARMED → TRIGGERED` ở lần đóng M5 đầu tiên mà M5 momentum cùng hướng (định nghĩa v1.1 giữ nguyên); `→ EXPIRED` khi quá N nến; `→ INVALIDATED` khi H1 đổi hướng hoặc M15 structure chuyển ngược hướng. Chỉ nến M5 *hiện tại* mới tạo tín hiệu (TRIGGERED tại nến hiện tại). Mỗi lần armed chỉ cho **một** tín hiệu; arm lại chỉ sau khi M15 setup hết sẵn sàng rồi sẵn sàng lại (pullback mới). Mặc định nếu setup đã sẵn sàng từ đầu cửa sổ 36 nến: coi như ARMED từ nến đầu cửa sổ. Setup cùng nến (v1.1) là trường hợp con.

**B. Hình học kế hoạch nhất quán.** `compute_stop` và `compute_targets` dùng ATR(M5) (khung trigger) thay cho ATR(M15) cho: sàn ATR (`atr_k` 1.25), đệm cấu trúc (0.1), stop tối đa (3.0), đệm mục tiêu (0.1). Giữ nguyên: mọi hệ số, `min_net_rr` = 1.5, mục tiêu 2R bị chặn bởi mức M15 đối diện, swing M5 làm tham chiếu cấu trúc. **Bỏ** cổng `clearance_ok` (bị RR bao hàm); mức kháng cự/hỗ trợ vẫn giới hạn mục tiêu như cũ.

**C. Biến động: từ veto sang cảnh báo.** Nhãn `LOW`/`HIGH` không tạo `VOLATILITY_TOO_LOW/HIGH`; thay vào đó `warnings` + `entry_quality = "CAUTION"` + hiển thị. Giữ veto cứng: `exec_quality POOR` (spread/ATR hoặc phân vị spread hoặc M1 ABNORMAL), H4 regime ∈ {SHOCK, HIGH_VOLATILITY}, M1 `VOLATILE`, stop > 3 ATR(M5). M1 quiet/noisy giữ nguyên là veto (không phải nút thắt: gỡ chúng thêm 0 tín hiệu ở v1.1) — xem 6.

Không thay đổi: H1 là nguồn hướng duy nhất; H4 chỉ chặn; M30 chỉ hiển thị; M1 chỉ chặn; tick volume chỉ xác nhận hoạt động; rủi ro/lot; hết hạn 3 nến M5 từ nến trigger; `allow_unknown_news` cho paper.

## 4. Phiên bản

`STRATEGY_VERSION` 1.2.0 cho hành vi mới; v1.1.0 vẫn tái lập được bằng `BaselineConfig(version="1.1.0")` (test chốt hash replay). Mặc định sản xuất chỉ chuyển sang 1.2.0 nếu qua mục 7.

## 5. Dữ liệu được phép

Chỉ dữ liệu ĐÃ ĐỐT (2025-05-01..2026-04-30). Cửa sổ đã dùng để chẩn đoán/thiết kế (KHÔNG dùng để chấp nhận): W1 2025-11-03→12-01, W2 2025-06-02→06-30, W3 2026-02-02→03-02. Cửa sổ chấp nhận (chưa từng được xem): **E1 2025-08-04→2025-09-01, E2 2025-12-01→2025-12-29**. Dự trữ chưa chạm: 2026-03-02→2026-04-30. Test-H (2022-01..2025-04) và Holdout (2026-05..2026-10) KHÔNG được mở.

## 6. Chỉ số được xem

Chính (khả thi vận hành): số quyết định, số BUY/SELL, số setup riêng biệt trên ngày giao dịch, phân bố theo phiên và giờ, tỉ lệ nến ARMED/TRIGGERED/EXPIRED/INVALIDATED, phễu cổng đầy đủ, hợp lệ kế hoạch (100% theo bất biến), tính xác định, parity, không rò rỉ tương lai, trùng lặp tín hiệu. Phụ (thăm dò, ghi rõ "burned data, exploratory"): thống kê kết quả mô phỏng R, MFE/MAE, tỉ lệ thoát — **không** dùng để chọn cấu hình.

Phân tích loại trừ (chỉ để quy trách nhiệm, báo cáo tất cả, không chọn theo kết quả): none (v1.1), A, B, C, A+B, A+B+C.

## 7. Tiêu chí chấp nhận / loại bỏ (định trước)

v1.2 thay v1.1 vận hành chỉ khi TẤT CẢ đúng, đo trên E1 và E2:

1. Nhân quả: quyết định tại t không đổi khi cắt bỏ mọi nến sau t (test); không dùng nến đang hình thành.
2. Xác định: hai lần replay → hash `comparable()` giống hệt; parity toàn lịch sử vs đuôi live = 0 khác biệt.
3. Kế hoạch hợp lệ 100%: SL/TP đúng phía, lot ≥ `volume_min` và đúng bước, rủi ro ≤ 0.5% vốn, R/R ròng ≥ 1.5, stop ≥ mức tối thiểu của broker.
4. Khả đạt: số setup riêng biệt trên ngày giao dịch gộp E1+E2 nằm trong dải **[0.25, 8]** (≥1 setup mỗi 4 ngày để vòng đời paper được dùng trong sử dụng bình thường; ≤8/ngày vì governor tối đa 6 lệnh/ngày và nhiều hơn là dấu hiệu tín hiệu tầm thường). Dải là kiểm tra lành mạnh kỹ thuật, KHÔNG phải mục tiêu để chỉnh.
5. Không bùng nổ/trùng lặp: tối đa một tín hiệu mỗi lần ARMED; không hai tín hiệu cùng hướng cùng nến M15; mỗi tín hiệu có giải thích khớp (phễu).
6. Mỗi quy tắc giải thích được bằng một câu (xem tài liệu OPERATIONAL_BASELINE).

Nếu (4) thấp hơn 0.25: v1.2 BỊ LOẠI, ghi nhận; thay đổi tiếp theo cần tài liệu tiền đăng ký mới (v1.3), không chỉnh ngưỡng tại chỗ. Nếu cao hơn 8: loại, điều tra trùng lặp. Kết quả mô phỏng R xấu **không** là lý do loại và **không** được giấu.

## 8. Hành động bị cấm

Quét lưới tham số liên tục; chỉnh N, `atr_k`, `min_net_rr`, ngưỡng phân vị, ngưỡng RSI/ROC; chọn cấu hình theo PnL/Sharpe/winrate/profit factor; dùng E1/E2 để thiết kế rồi chấp nhận trên chính chúng; xem Test-H/Holdout; thêm chỉ báo hoặc bỏ phiếu.

## 9. Ghi nhận

Tài liệu này được commit trước khi cài đặt v1.2. Số liệu chẩn đoán ở mục 1 nằm trong `docs/reports/SIGNAL_FUNNEL_ANALYSIS.md`.
