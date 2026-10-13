# ADR-V2-004: lịch sử theo khoảng + sự kiện live

Trạng thái: đề xuất (hợp đồng đã định nghĩa ở G2, triển khai ở G3/G5).
`GET /api/v2/market/bars?timeframe&from&to&limit&before` trả `bars, oldest_available, newest_available, has_more_before, has_more_after, data_version`. Sự kiện live qua WebSocket có `seq` để phát hiện lỡ. Một chuỗi có thứ tự duy nhất; thời điểm nến phải tăng nghiêm ngặt (không trùng) — đã là ràng buộc của hợp đồng (`BarsResponse`).
Nguyên nhân V1 chỉ có 400 nến: frontend khóa cứng, không dùng `before` (`V1_FORENSIC_BASELINE.md` §2).
