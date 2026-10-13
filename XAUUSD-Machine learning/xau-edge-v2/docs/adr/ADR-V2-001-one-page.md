# ADR-V2-001: một route `/` và các ngăn kéo

Trạng thái: **ĐÃ DUYỆT** (2026-10-12, chủ dự án) · Nguồn: kiểm toán V1 (chỉ `/trade` giúp ra quyết định).

Quyết định: giao diện là **một trang**. Ngăn kéo (`#journal`, `#evidence`, `#data`, `#model`) là tab trong cùng trang, chia sẻ được bằng hash. Không có điều hướng chính, không trang research/legacy/control.
Hệ quả: mọi tính năng phải có giá trị quyết định trực tiếp; không có trang mồ côi. Ngăn kéo chưa triển khai phải **ghi rõ "chưa triển khai"**, không giả vờ có dữ liệu.
