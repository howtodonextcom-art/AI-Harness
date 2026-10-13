# V2 · Kho dữ liệu sạch (ADR-V2-019): xây dựng, kiểm chứng, chốt chặn

Ngày: 2026-10-13 · Mã: `src/xau_edge_v2/research/clean_store.py`, `clean_view.py`; `scripts/research/build_clean_store.py` · Manifest: `docs/research/clean_store_manifest.json` (sha256 `997d73f8…`) · Danh sách bar bị loại: `docs/research/dropped_pseudo_bars.csv`

## 1. Kết quả
| Cửa sổ (quyết định Gate B2) | Tháng | PASS | Quarantine | Ghi chú |
|---|---|---|---|---|
| DEV' 2005-06 → 2018-12 | 163 | **163** | 0 | 84 tháng đầu (2005-06 → 2012-05) không có gì để làm sạch và ra **giống hệt bản thô** |
| VALIDATION' 2019-01 → 2021-01 | 25 | **24** | 1 | 2021-01 loại: lịch sử nguồn đổi từ 2021-01-21 nên H4 khác nguồn đối chiếu |
| QUARANTINE 2021-02 → 2021-09 | 8 | 0 | 8 | theo quyết định của chủ dự án |
| RESERVED 2021-10 → 2021-12 | 3 | **3** | 0 | giữ riêng; kiểm bằng tick (100%) |
Không có tháng nào của Confirm-C, Test-H, Holdout được đọc hay xây dựng.

Đã làm sạch: **2.216 bar M1** (+ các bản sao ở M5/M15/M30/H1), **2.182 bar H4 khôi phục** từ MetaQuotes-Demo, 21 bar H4 chỉ chứa bar giả (ngày đóng cửa/lễ) bị loại, và **5 bucket** M15/M30/H1 (tháng 2020-10, tuần lệch DST Âu/Mỹ) có bar thật trộn bar giả nên được **dựng lại từ M1 sạch** rồi kiểm lại với H1 nguồn đối chiếu.

## 2. Bất biến đã kiểm
| Yêu cầu của chủ dự án | Cách thực hiện | Kết quả |
|---|---|---|
| Giữ nguyên RAW | băm sha256 mọi tệp thô trước và sau khi xây; khác ⇒ **dừng** | không đổi; test `test_the_raw_files_are_not_touched` |
| Kho sạch riêng | `data/clean_store/XAUUSD/<TF>/<tháng>.parquet`, cùng bố cục `BarStore` | 190 tháng × 6 khung |
| Loại pseudo-bar | quy tắc 2 tầng (`clean_view`): tầng 1 mọi ngày (rollover, spread 0, volume cỡ ngày), tầng 2 trong kỷ nguyên 2012-06-26..2021-01-20 (rollover, spread 0, bất kể volume) áp cho M1; bar thô ở khung lớn bị loại theo **bản sinh đôi M1** và phải **trùng bar giả** (nếu trộn với bar thật thì dựng lại từ M1) | bar giả còn lại **0** ở mọi tháng PASS |
| H4 từ nguồn đã kiểm chứng | thay mọi bar H4 khác nguồn đối chiếu, **chỉ** khi bucket chứa bar giả | H4 trùng nguồn đối chiếu **100%** ở 187 tháng PASS |
| Manifest + SHA256 | mỗi tệp, mỗi đầu vào thô, danh sách bar loại, nguồn đối chiếu, mã hash của chính manifest (không tính giờ xây) | **xây hai lần ⇒ 1.140 tệp và manifest giống từng bit** |
| Đồng bộ M1/H1/H4 | M1→M5, M5→M15/M30/H1 (OHLC ≤ nửa cent), H1→H4 theo bucket của chính bar H4 | **100%** ở cả 190 tháng PASS, ngưỡng đạt 99,5% |
| Giống nguồn đối chiếu | H1 ≥ 99,9% (từ 2009-09), H4 100% (≤ 2021-01); tick ≥ 97% cho RESERVED | H1 min 100% (136 tháng); H4 min 100%; tick 100% |
| Vệ sinh | không bar sai OHLC, không trùng, không ngược thứ tự | 0 vi phạm |
| Ngăn dữ liệu lỗi lọt vào backtest | `CleanBarStore`: kiểm hash manifest khi mở, kiểm sha256 **từng tệp trước khi đọc**, chỉ phục vụ tháng PASS, **không bỏ qua im lặng** tháng quarantine/chưa liệt kê, từ chối khoảng ngoài kho; pipeline thêm `require_clean` (từ chối tháng có bar giả) và `cand_signals.py` từ chối chạy kiểu chia tháng | test: sửa 1 tệp, sửa manifest, tháng quarantine giữa khoảng, khoảng ngoài kho đều bị từ chối |
Một tháng không chứng minh được thì **không có tệp dữ liệu**, chỉ có lý do trong manifest (cơ chế giúp bắt 17 tháng ở các vòng thử đầu: ngày lễ chỉ có bar giả, bucket trộn, ngưỡng volume sót bar giả ngày lễ; tất cả đã xử lý bằng quy tắc chứ không hạ ngưỡng).

## 3. Phát hiện trong lúc xây (đã sửa)
1. **Ngưỡng volume sót 11 bar giả ngày lễ/đóng cửa** (volume 1–19.000): dùng quy tắc kỷ nguyên cho M1. Số bar giả M1 là **2.216**, không phải 2.205.
2. **Bar thô ở khung lớn tại phút rollover có thể là bar THẬT** có trường spread = 0 (tuần lệch DST 2016-10, 2014-03): quy tắc tầng 2 không áp cho khung lớn; khớp theo bản sinh đôi M1.
3. **Tuần lệch DST Âu/Mỹ (2020-10)**: bucket M15/M30/H1 tại 21:00 UTC có bar thật trộn bar giả; dựng lại từ M1 sạch, đối chiếu với H1 nguồn đối chiếu.
4. **H4 cuối tháng** chứa H1 của tháng sau: bỏ qua bucket vượt cuối tháng khi đối chiếu H1→H4.

## 4. Giới hạn
- Nguồn đối chiếu là **máy chủ MetaQuotes-Demo** (khác nhà cung cấp, nhưng có thể chung nguồn gốc lịch sử cũ): "VERIFIED" ≠ "chân lý".
- M1/M5/M15/M30 cũ không có nguồn đối chiếu trực tiếp; được kiểm bằng đồng bộ hóa nội bộ với H1/H4 đã khớp.
- Ngày bắt đầu quyết định hiệu dụng của DEV' là **2005-11** (chỉ báo cần ≈ 150 ngày lịch sử, kho bắt đầu 2005-06).
- 2021-02..09: có bằng chứng chéo nhà cung cấp (trung vị 0,06 USD, p95 0,18–0,46) tương đương các tháng đã kiểm; **không** tự mở khóa, chờ chủ dự án.
- Bản dẫn xuất sạch **không** thay thế raw; mỗi lần xây mới phải ra manifest cùng hash.
