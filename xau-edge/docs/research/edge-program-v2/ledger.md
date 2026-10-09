# Sổ thí nghiệm Edge Program V2 (chỉ thêm vào cuối, không sửa, không xóa)

Ngày mở: 2026-10-09. Sổ này sở hữu K của V2. Sổ lịch sử (Programme 0 và Programme 1) nằm ở
`docs/research/edge-program/ledger.md` và chỉ đọc.

* Biến thể đã khai báo (Batch A, sau khi loại biến thể underpowered-by-design): H07 6 + H08 2 + H09 6 + H10 6 = **20**.
* **K = 0 + 20 = 20; trần K cap = 24.** alpha = 0.05 / 20 = 0.0025. (Số 0 là K cũ không cộng dồn vào V2: K cũ nằm ở sổ lịch sử.)
* Sàng lọc Stage 1: Holm-Bonferroni family-wise 0.10 trên 20 biến thể (xem từng file giả thuyết). Stage 1 là SCREENING: không tạo bằng chứng.
* Biến thể bị loại theo quy tắc underpowered-by-design (MDE > +0.20R tại K đã đăng ký): `H08-PD-e0`, `H08-PD-e0.25`, `H08-PD-e0.5`, `H08-ASIA-e0.5`. Không chạy, không tính K.
* Test-H (2022-01-01..2025-04-30) và Holdout (2026-05-01..2026-10-07) **không bị chạm**. Mọi lần chạy bên dưới là Development-2 (2011-01-01..2018-12-31).
* **Quy tắc bảo thủ cho Stage 2 và Test-H (thêm sau review độc lập):** vì Development-2 và Validation-2 đã bị 21 biến thể của Programme 1 dùng, mọi biến thể V2 tới Stage 2 phải được đánh giá với K_tổng = K_V2 + 21 = 41 (alpha = 0.05 / 41), trừ khi chủ dự án quyết định khác bằng văn bản có phiên bản. K = 20 ở trên chỉ áp dụng cho sàng lọc Stage 1.
* Chạy chẩn đoán trên dữ liệu đã dùng (Class D) không tính K và không là bằng chứng: xem `docs/research/edge-program-v2/`.

## Bảng chạy

| # | Thời gian | Giả thuyết/biến thể | Giai đoạn | Kịch bản | Ghi chú | Registry id |
|---|---|---|---|---|---|---|
| 1 | 2026-10-09 01:51:56 UTC | H07-PD-e0 | dev2-2 | base + bi quan | 1608 lệnh, mean net R -0.7002 / bi quan -0.7140; gross-mid -0.5982; p=1.0000; FAIL | `330d97a35464d3ad` |
| 2 | 2026-10-09 01:51:56 UTC | H07-PD-e0.25 | dev2-2 | base + bi quan | 1524 lệnh, mean net R -0.7178 / bi quan -0.7317; gross-mid -0.6169; p=1.0000; FAIL | `7a27e6f1cf219c4d` |
| 3 | 2026-10-09 01:51:56 UTC | H07-PD-e0.5 | dev2-2 | base + bi quan | 1404 lệnh, mean net R -0.7149 / bi quan -0.7288; gross-mid -0.6144; p=1.0000; FAIL | `4a67a4c0a8b42f09` |
| 4 | 2026-10-09 01:51:56 UTC | H07-ASIA-e0 | dev2-2 | base + bi quan | 2142 lệnh, mean net R -0.2821 / bi quan -0.2993; gross-mid -0.1439; p=1.0000; FAIL | `d30011eeb50ed435` |
| 5 | 2026-10-09 01:51:56 UTC | H07-ASIA-e0.25 | dev2-2 | base + bi quan | 1719 lệnh, mean net R -0.3017 / bi quan -0.3187; gross-mid -0.1620; p=1.0000; FAIL | `f51bc1069da2164d` |
| 6 | 2026-10-09 01:51:56 UTC | H07-ASIA-e0.5 | dev2-2 | base + bi quan | 1324 lệnh, mean net R -0.3085 / bi quan -0.3252; gross-mid -0.1685; p=1.0000; FAIL | `518fbf7a3ffb594b` |
| 7 | 2026-10-09 01:51:56 UTC | H08-ASIA-e0 | dev2-2 | base + bi quan | 777 lệnh, mean net R -0.2093 / bi quan -0.2255; gross-mid -0.0586; p=1.0000; FAIL | `ff5e72e6fe581891` |
| 8 | 2026-10-09 01:51:56 UTC | H08-ASIA-e0.25 | dev2-2 | base + bi quan | 640 lệnh, mean net R -0.2229 / bi quan -0.2389; gross-mid -0.0708; p=1.0000; FAIL | `efce6c34acd4a67b` |
| 9 | 2026-10-09 01:51:56 UTC | H09-ASIA_LONDON-t0.2 | dev2-2 | base + bi quan | 752 lệnh, mean net R -0.0526 / bi quan -0.0698; gross-mid +0.0736; p=0.8429; FAIL | `e6269da6e5602d15` |
| 10 | 2026-10-09 01:51:56 UTC | H09-ASIA_LONDON-t0.3 | dev2-2 | base + bi quan | 1206 lệnh, mean net R -0.0594 / bi quan -0.0765; gross-mid +0.0655; p=0.9248; FAIL | `85d34e05e2420084` |
| 11 | 2026-10-09 01:51:56 UTC | H09-ASIA_LONDON-t0.4 | dev2-2 | base + bi quan | 1598 lệnh, mean net R -0.0547 / bi quan -0.0719; gross-mid +0.0714; p=0.9362; FAIL | `c2cfe5f3d80a9aac` |
| 12 | 2026-10-09 01:51:56 UTC | H09-LONDON_NY-t0.2 | dev2-2 | base + bi quan | 625 lệnh, mean net R -0.1653 / bi quan -0.1833; gross-mid -0.0244; p=0.9984; FAIL | `62930b5130999c47` |
| 13 | 2026-10-09 01:51:56 UTC | H09-LONDON_NY-t0.3 | dev2-2 | base + bi quan | 1086 lệnh, mean net R -0.1122 / bi quan -0.1300; gross-mid +0.0272; p=0.9952; FAIL | `054716d6313ec456` |
| 14 | 2026-10-09 01:51:56 UTC | H09-LONDON_NY-t0.4 | dev2-2 | base + bi quan | 1497 lệnh, mean net R -0.1052 / bi quan -0.1230; gross-mid +0.0336; p=0.9978; FAIL | `e7899a42453dcede` |
| 15 | 2026-10-09 01:51:56 UTC | H10-c0.8-L20 | dev2-2 | base + bi quan | 661 lệnh, mean net R -0.2946 / bi quan -0.3147; gross-mid -0.1432; p=1.0000; FAIL | `6dba5bd6f5085475` |
| 16 | 2026-10-09 01:51:56 UTC | H10-c0.8-L50 | dev2-2 | base + bi quan | 661 lệnh, mean net R -0.1287 / bi quan -0.1488; gross-mid +0.0248; p=0.9900; FAIL | `8c50cf2389acfd1b` |
| 17 | 2026-10-09 01:51:56 UTC | H10-c0.8-L100 | dev2-2 | base + bi quan | 661 lệnh, mean net R -0.1279 / bi quan -0.1480; gross-mid +0.0255; p=0.9896; FAIL | `af3049174203d959` |
| 18 | 2026-10-09 01:51:56 UTC | H10-c0.9-L20 | dev2-2 | base + bi quan | 1230 lệnh, mean net R -0.2438 / bi quan -0.2628; gross-mid -0.1031; p=1.0000; FAIL | `622bb42d5d50481e` |
| 19 | 2026-10-09 01:51:56 UTC | H10-c0.9-L50 | dev2-2 | base + bi quan | 1230 lệnh, mean net R -0.1424 / bi quan -0.1613; gross-mid -0.0006; p=0.9998; FAIL | `bd2c59e475c1c67b` |
| 20 | 2026-10-09 01:51:56 UTC | H10-c0.9-L100 | dev2-2 | base + bi quan | 1230 lệnh, mean net R -0.1331 / bi quan -0.1520; gross-mid +0.0089; p=0.9995; FAIL | `c48a8ba4394df543` |
