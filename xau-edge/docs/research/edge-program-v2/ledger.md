# Sổ thí nghiệm Edge Program V2 (chỉ thêm vào cuối, không sửa, không xóa)

Ngày mở: 2026-10-09. Sổ này sở hữu K của V2. Sổ lịch sử (Programme 0 và Programme 1) nằm ở
`docs/research/edge-program/ledger.md` và chỉ đọc.

* Biến thể đã khai báo (Batch A, sau khi loại biến thể underpowered-by-design): H07 6 + H08 2 + H09 6 + H10 6 = **20**.
* **K = 0 + 20 = 20; trần K cap = 24.** alpha = 0.05 / 20 = 0.0025. (Số 0 là K cũ không cộng dồn vào V2: K cũ nằm ở sổ lịch sử.)
* Sàng lọc Stage 1: Holm-Bonferroni family-wise 0.10 trên 20 biến thể (xem từng file giả thuyết). Stage 1 là SCREENING: không tạo bằng chứng.
* Biến thể bị loại theo quy tắc underpowered-by-design (MDE > +0.20R tại K đã đăng ký): `H08-PD-e0`, `H08-PD-e0.25`, `H08-PD-e0.5`, `H08-ASIA-e0.5`. Không chạy, không tính K.
* Test-H (2022-01-01..2025-04-30) và Holdout (2026-05-01..2026-10-07) **không bị chạm**. Mọi lần chạy bên dưới là Development-2 (2011-01-01..2018-12-31).
* Chạy chẩn đoán trên dữ liệu đã dùng (Class D) không tính K và không là bằng chứng: xem `docs/research/edge-program-v2/`.

## Bảng chạy

| # | Thời gian | Giả thuyết/biến thể | Giai đoạn | Kịch bản | Ghi chú | Registry id |
|---|---|---|---|---|---|---|
