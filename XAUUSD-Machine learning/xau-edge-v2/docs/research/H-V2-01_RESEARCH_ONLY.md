# H-V2-01: xếp hạng chất lượng setup (RESEARCH-ONLY)

Ngày: 2026-10-12 · Trạng thái: **RESEARCH_ONLY. Chưa đăng ký, không tiêu K, không dùng Test-H.** Duyệt: chủ dự án ("H-V2-01: giữ research-only, không dùng Test-H ngay").

## Ý tưởng (giả thuyết, chưa phải kết quả)

Với setup xu hướng + chạm EMA50 + nến xác nhận (định nghĩa ở báo cáo ảnh, mục H–I), một mô hình đơn giản (logistic) trên vài đặc trưng (vị trí trong biên độ 50 nến hướng theo lệnh, phân vị ATR, giờ trong ngày, thân nến tín hiệu) có thể xếp hạng setup tốt/xấu.

## Vì sao KHÔNG được coi là bằng chứng

- Quan sát đến từ lát cắt G0 trên Dev/Val (Class D): AUC 0,66 (Dev) và 0,67 (Val), qua các kiểm soát (nhãn hoán vị, chỉ hướng, chỉ r/ATR, giãn mẫu, đuôi 72 nến), nhưng **tôi đã nhìn kết quả**, định nghĩa setup đã được chọn/phân tích nhiều lần, sự kiện tập trung theo thời gian, **chưa có chi phí**, chưa so benchmark beta.
- Mâu thuẫn bề mặt: setup không phân biệt có E[R] ≈ 0 trong khi nhóm trên 20% phải đạt E[R] lớn; điều này đáng ngờ trước hơn 44 giả thuyết đã thất bại ở V1.
- Các phép đo trước đó của tôi trên lịch sử đầy đủ **đã chạm Test-H và holdout** (xem `V1_FORENSIC_BASELINE.md` mục 5): với các giả thuyết sinh từ đó, Test-H không còn sạch.

## Được phép (không tiêu K, không tạo bằng chứng)

- Đọc, mô tả, vẽ biểu đồ khám phá trên dữ liệu ≤ 2021-12-31 (Class D).
- Viết đặc tả máy đọc được và danh sách đặc trưng để **sau này** đăng ký.

## Không được phép cho đến khi chủ dự án duyệt chính sách K (ADR-V2-007) và một đăng ký trước bằng văn bản

- Chạy trên Test-H (2022-01-01..2025-04-30) hoặc Holdout (2026-05-01..2026-10-07).
- Đưa vào đường quyết định, hiển thị cho người dùng, hay dùng làm thẩm quyền ML.
- Gọi nó là "phát hiện" hoặc "lợi thế".

## Con đường tới bằng chứng sạch

1. Bạn duyệt chính sách K; 2. đăng ký trước (định nghĩa, đặc trưng, chi phí theo kỷ nguyên, benchmark beta, tiêu chí) **trước khi** nhìn dữ liệu mới; 3. hoặc dữ liệu *forward* tích lũy từ ngày đăng ký, hoặc Test-H chạy **một lần**; 4. so với benchmark trung lập hướng và beta; 5. chỉ khi qua mới thăng cấp qua thang bằng chứng.
