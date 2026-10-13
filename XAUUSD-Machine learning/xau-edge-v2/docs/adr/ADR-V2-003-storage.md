# ADR-V2-003: lưu trữ

Trạng thái: đề xuất, chấp thuận ngầm theo O2.
Parquet bất biến cho dữ liệu thị trường (đọc bằng Polars/DuckDB); SQLite chỉ cho trạng thái giao dịch (paper, journal, registry). Không thêm cơ sở dữ liệu khác khi chưa có lý do.
**Kho dữ liệu thị trường dùng chung với V1, CHỈ ĐỌC** (quyết định 2026-10-12): V2 không bao giờ ghi vào `xau-edge\data\market`. Có test chứng minh mô-đun đọc kho không thay đổi tệp nào.
