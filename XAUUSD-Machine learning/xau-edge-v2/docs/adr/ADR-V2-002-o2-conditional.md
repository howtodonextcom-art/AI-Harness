# ADR-V2-002: kiến trúc O2 (SPA tĩnh + một dịch vụ Python), CÓ ĐIỀU KIỆN

Trạng thái: **ĐÃ DUYỆT CÓ ĐIỀU KIỆN** (2026-10-12). Điều kiện: bộ khung G2 phải **không tệ hơn V1** ở các cổng đã đặt trước (xem `reports/V2_G2_SKELETON_REPORT.md`). Thua cổng nào ⇒ quay lại phương án O1 (tiến hóa V1) và sửa ADR này.

Quyết định: Vite + React + TypeScript build thành tệp tĩnh, FastAPI phục vụ cùng gốc; một tiến trình Python chứa API REST + WebSocket (về sau: Decision Governor, suy luận ML, PAPER, journal). Collector là tiến trình riêng (hiện dùng collector của V1, chỉ đọc kho dữ liệu). Huấn luyện ML ngoại tuyến, không bao giờ trong tiến trình phục vụ.
