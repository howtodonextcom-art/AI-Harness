# V2 · Phản hồi Owner Decision (CONDITIONAL APPROVAL): báo cáo nộp

Ngày: 2026-10-13 · Viết cho: chủ dự án. **Dừng trước mọi outcome backtest và trước khi promote Candidate.** Không tuyên bố trading edge; không sửa V1 CONTROL; không đổi giới hạn rủi ro; không kích hoạt broker; không mở Validation'/Confirm-C/Test-H/Holdout; không sửa RAW; không đổi cửa sổ khóa.

## Trạng thái một dòng
A (ba lỗi kỹ thuật): **XONG, có test**. B (tách hai nhánh + hợp đồng): **XONG, đã đóng băng có hash**. C (Stage A): **MULTIFAMILY XONG; CORE ĐANG CHẠY** (xem mục 3, 158 tháng DEV', bốn worker ưu tiên thấp). D (Family D), E (ML M0/M1 hạ tầng), F (ADR hai nguồn: bản nháp, A1: chờ anh đăng nhập): xong phần được phép.

## Danh mục nộp (tiêu chí G)
| # | Yêu cầu | Tài liệu / bằng chứng |
|---|---|---|
| 1 | Báo cáo sửa ba lỗi + regression test | `V2_OWNER_DECISION_TECHNICAL_FIXES_REPORT.md` |
| 2 | Spec riêng cho Core và B/C/D | `docs/research/cand_v2_spec.json` (+ `CAND_V2_CORE_1.1.0_CONTRACT.md`, hash `cand_v2_spec.sha256`); `docs/research/multifamily_0.1.0.spec.json` (hash `multifamily_0.1.0.sha256`); `cand_v2_spec_1.0.0.json` lưu lại bản cũ |
| 3 | Stage A signal-only | `V2_STAGE_A_SIGNAL_ONLY_REPORT.md` (sinh tự động từ JSON) |
| 4 | Family D và độ bền RANGE | `V2_FAMILY_D_RANGE_REPORT.md` |
| 5 | Event logging khi UI tắt / nhiều client | báo cáo 1, mục 1 (test + đo sống: 30 GET, 1115→1115 dòng) |
| 6 | UI 1440×900 và 1152×720 | `reports/evidence/intel/intel_{1440x900,1152x720}_{fold,full,market_drawer}.png`; e2e **52 passed** |
| 7 | CPU/RAM, latency, giới hạn chưa đo | mục 4 dưới đây |
| 8 | Giả thuyết còn INCONCLUSIVE | mục 5 dưới đây |
| + | ML M0/M1 hạ tầng | `V2_ML_M0_M1_INFRASTRUCTURE_REPORT.md` |
| + | ADR-V2-019 hai nguồn (nháp) | `docs/adr/ADR-V2-019-rev2-two-source-evidence.PROPOSED.md` |

## 1. Phân tách hai nhánh (B)
`CAND_V2_CORE_1.1.0` (C1/C2/C3) và `MULTIFAMILY_RESEARCH_0.1.0` (B/C/D) là **hai spec, hai mã, hai báo cáo**; chồng lấn chỉ được **báo cáo** (không gộp, không thêm biến thể của nhánh này vào nhánh kia, `variants_allowed = 0`). Hợp đồng đủ: entry quote, stop, target, net R:R, cost, expiry, overlapping position, ablation (Core: `CAND_V2_CORE_1.1.0_CONTRACT.md`; B/C/D: spec JSON + `research/multifamily.py`, test 10 + 3). Hình học của B/C/D **dùng đúng hàm stop/target của CONTROL** (`compute_stop`, `compute_targets`), không tham số mới. Spec 1.1.0 của Core được đóng băng (1.0.0 lưu lại); nội dung không đổi so với bản đề xuất, chỉ trạng thái và ngày; freeze gate (hash khớp) kiểm bằng test trước khi chạy.

## 2. Freeze gate và Stage A (C)
- Freeze gate: `test_cand_freeze`, `test_clean_store_manifest`, `test_multifamily_spec` xanh; `cand_replay.py` đọc đúng `cand_v2_spec.sha256` và chỉ nhận tháng PASS của DEV'/VALIDATION'/RESERVED.
- Stage A **chỉ tạo tín hiệu**: không simulator, không PnL. Đã xác minh chạy `cand_replay.py` sau khi thêm số liệu bổ sung (phiên, chế độ, đếm raw eligibility) cho ra **đúng digest cũ** của F6 (2011-03: `8fd7a48e…`, 2011-04: `aa455662…`).
- Báo cáo riêng: raw eligibility, episode, tín hiệu sau cổng chi phí/cấu trúc, cân bằng hướng, chế độ/phiên, chồng lấn giữa các họ, khả thi hình học, ước lượng công suất: trong báo cáo Stage A.
- **Multifamily**: chạy hai lần trên toàn DEV' (300.922 nến M15, ~12 năm) cho JSON **giống hệt** (tất định).
- **Core**: một tiến trình liên tục cho DEV' ước 3–4 giờ; để nằm trong giới hạn 4 worker ưu tiên thấp em chia DEV' thành **4 đoạn liền kề** (2005-11..2009-02, 2009-03..2012-06, 2012-07..2015-10, 2015-11..2018-12). Trong mỗi đoạn bộ nhớ vòng đời **liên tục**; tại 3 ranh giới (2009-03, 2012-07, 2015-11) bộ nhớ C1 bắt đầu rỗng (C1 chỉ nhớ 6 nến M5 nên ảnh hưởng ≤ vài nến). Mã Core đã chạy: tất cả số liệu Core trong báo cáo Stage A ghi rõ `complete`; khi `complete = true` mới là toàn DEV'. Em chỉ nộp số liệu Core đã hoàn tất khi nó hoàn tất; hiện tại báo cáo là **một phần** và được gắn nhãn như vậy.

### Phát hiện Stage A (không phải kết quả giao dịch)
1. **Hình học là nút thắt của B và C**, không phải thiếu sự kiện: chỉ **31%** (B) và **27%** (C) episode có stop hợp lệ (≤ 3 ATR); rủi ro trung vị ~2,5 ATR; sau cổng TARGET chỉ **9,0%** (B) và **6,1%** (C) episode thành lệnh hợp lệ. D có stop hợp lệ 99% (sàn 1,25 ATR của CONTROL), và 40,2% episode thành lệnh hợp lệ; cổng chặn lớn nhất là TARGET (42%) và COST (17%).
2. **Công suất**: tín hiệu không chồng trong DEV': B 434, C 234, D 849 so với n cần 663 (0,20R) / 295 (0,30R). Chỉ **D** đủ cho 0,20R ngay trong DEV'; B đủ cho 0,30R; C không đủ cho cả hai. (Ước lượng, chưa phải kết quả; "không chồng" theo giả định giữ vị thế tối đa 96 nến.)
3. **Chồng lấn giữa họ thấp** (cùng phía ±6 nến: B×C 67/519, B×D 8/519, C×D 8/272): ba họ phần lớn là các tập tín hiệu khác nhau.
4. **B tập trung vào phiên Á** (266/519 tín hiệu chấp nhận) và OFF_HOURS 138: sự nén tiền phá vỡ hình thành ở phiên yên; liên quan tới chi phí/spread thực thi lúc đó chưa đo bằng outcome.
5. Core (một phần): chuỗi CONTROL đủ điều kiện khi tắt cổng chỉ ở **67 nến M5 / 188.892** đã đánh giá (≈ 1 trên 2.800); 20,7% nến M5 bị bỏ qua vì thiếu trạng thái (H1 UNKNOWN hoặc thiếu M1; cao nhất ở giai đoạn đầu: 43% trong 9 tháng đầu 2005-11..2006-07): độ phủ M1 của DEV' sớm là một giới hạn dữ liệu cần ghi nhận. Nhất quán với V1 (2 tín hiệu / 16.270 quyết định).

## 3. Family D (D)
Chi tiết: `V2_FAMILY_D_RANGE_REPORT.md`. Tóm tắt trung thực: nhãn RANGE **không bền** (trung vị 11 nến/đoạn, chỉ 22% còn nguyên sau 24 nến kể từ tín hiệu; tuổi RANGE trung vị lúc tín hiệu 14 nến, p10 chỉ 2 nến); biên 20 nến **nhân quả theo cấu tạo** nhưng **trượt** (chỉ 4,9% còn nguyên sau 6 nến); lệnh hợp lệ hình thành được (40,2%). D được xem trước vì khả thi mẫu và độ bền nhãn, **không vì kỳ vọng lợi nhuận**; B/C vẫn trong sổ giả thuyết với phân tích khả thi độc lập.

## 4. Tài nguyên, độ trễ, giới hạn chưa đo (7)
| Chỉ số | Giá trị (đo hôm nay) |
|---|---|
| `GET /api/v2/intelligence` (200 lần) | p50 3,0 ms, p95 40,2 ms, p99 63,9 ms, 19 KB |
| `GET /api/v2/state` | p50 3,2 ms, p95 40,2 ms, p99 66,4 ms |
| Dịch vụ V2 | 3,6% một lõi, 154 MB (60 s, trong lúc bốn replay Stage A chạy); CPU toàn máy ~33% (<60%) |
| Stage A | 4 worker ưu tiên thấp; mỗi tiến trình ~85% một lõi, ~135 MB; collector V1 và PAPER không bị chạm (chỉ đọc kho; CPU collector không đo riêng) |
| Quote MT5→V2 | p50 0,47 s / p95 3,78 s / p99 10,9 s (P0, chưa lặp lại) |
| **NOT MEASURED** | độ trễ render trình duyệt, WS→DOM; nhiều client > 8 luồng trên dịch vụ sống; đuôi p99 của quote ở collector; hành vi khi collector chết; tải qua các phiên Á/Âu/Mỹ; phục hồi từ backup thực tế |

## 5. Giả thuyết còn INCONCLUSIVE / NOT_TESTED
- HB1, HC1, HD1: chưa có outcome; về **công suất DEV'**: B đủ cho 0,30R nhưng không cho 0,20R; C không đủ; D đủ cho 0,20R.
- Core C1, C2, C3a, C3b, C7: chưa có outcome (Stage A signal-only); công suất Core thấp (xem báo cáo Stage A khi hoàn tất).
- M1 advisory (G10): giá trị chưa đo. Candidate V1 v1.2 (vòng đời): chưa chạy.
- Hai bài toán ML (pha biến động, mất mức BOS): chưa có mô hình hay đường cơ sở; chỉ có hạ tầng.
- Dữ liệu: 2021-02..09 vẫn **quarantine** (ADR hai nguồn ở dạng nháp; 2021-03 là ngoại lệ cần đối sánh offset); A1 terminal portable vẫn **chờ anh đăng nhập** (terminal chưa chạy).

## 6. Hợp đồng trạng thái cuối
| Mục | Giá trị |
|---|---|
| Git HEAD trước | root `4f306d9`; repo lồng `cbfceca` |
| Git HEAD sau | repo lồng `449020b` (+ commit báo cáo); root: hash trong tin nhắn bàn giao |
| Test | pytest **2019 passed**; e2e **52 passed**; `ruff` sạch; `mypy --strict` 71 tệp sạch |
| Dữ liệu đã truy cập | kho sạch DEV' 2005-11..2018-12 (PASS, hash kiểm), qua `CleanBarStore`; kho trực tiếp chỉ-đọc cho runtime |
| Dữ liệu bảo vệ không truy cập | VALIDATION', Confirm-C, Test-H, Holdout, quarantine 2021-02..09, RESERVED; **outcome: không** |
| Bất biến | V1 CONTROL `1.1.0` không đổi; `candidate_active=false`; PAPER-only; giới hạn rủi ro không đổi; không broker |
| Cổng kế tiếp của chủ dự án | (1) xem Stage A Core khi hoàn tất, (2) cho phép bước kế (ablation/VALIDATION' một lần) hay không, (3) A1 đăng nhập, (4) duyệt ADR-V2-019 rev2 |
