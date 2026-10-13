# V2 · Pháp y nguồn gốc dữ liệu XAUUSD (Cổng B)

Ngày: 2026-10-13 · Phạm vi: chỉ dữ liệu giá (không có outcome chiến lược nào được xem) · Bằng chứng: `reports/evidence/data_forensics/`

> **ĐÍNH CHÍNH (Gate B3, 2026-10-13):** lần "tải lại từ broker" trong báo cáo này đã đi qua **terminal MetaQuotes mặc định** (`C:\Program Files\MetaTrader 5`, máy chủ **MetaQuotes-Demo**), **không phải terminal FTMO** đã cấp dữ liệu cho kho. Hệ quả: (1) nguồn đối chiếu là một **nhà cung cấp khác** (mạnh hơn "cùng broker"); (2) kết luận "terminal hôm nay không còn phục vụ bar giả" **chỉ đúng với MetaQuotes**. Terminal FTMO hôm nay **vẫn phục vụ đúng các bar giả** ở M1, M5, M15, M30, H1, H4 (giống kho 100%, kiểm tra 3 tuần mẫu: `docs/research/ftmo_terminal_probe.json`). Vậy nguồn gốc là **lịch sử trên máy chủ FTMO**, không phải V1 và không phải nhập liệu. Xem `V2_A1_PROVENANCE_REPORT.md`. Số bar giả là **2.216** (không phải 2.205): thêm 11 bar ngày lễ/ngày đóng cửa có volume thấp.


## 0. Kết luận (và thu hồi chẩn đoán trước)
1. **Chẩn đoán trước của em là SAI.** Em đã kết luận "lỗi nguồn cấp, nhiễu làm tự tương quan −0,33" và đề xuất luật |autocorr| ≤ 0,10. Đó chỉ là triệu chứng, không phải nguyên nhân. Chủ dự án đã cảnh báo đúng. ADR-V2-018 bị **rút lại**.
2. **Nguyên nhân thật, đã chứng minh:** từ **2012-06-26 21:00 UTC đến 2021-01-20 22:00 UTC**, mỗi ngày giao dịch có **một "pseudo-bar"** đóng dấu đúng phút rollover (21:00 UTC mùa hè, 22:00 mùa đông), `spread = 0`, tick volume cỡ cả ngày (36.000–190.000, bình thường 15–2.000), và **mang OHLC của PHIÊN GIAO DỊCH KẾ TIẾP**. Cùng một bar có mặt trong M1, M5, M15, M30, H1 và bị **gộp** vào bar H4 chứa nó. Tổng cộng **2.205 bar** trong **104 tháng**.
3. **Hệ quả: nhìn trước (look-ahead) tới 24 giờ.** Một mô hình coi bar này là bar đã đóng sẽ "biết" cao/thấp/đóng của ngày mai. Đây là nguồn của edge giả +0,68R ở Stage B. Tự tương quan −0,33 chỉ là hệ quả: bar này nằm sát các khoảng nghỉ phiên, nên các cặp lợi suất "xuyên khoảng nghỉ" đảo dấu.
4. Phần còn lại của dữ liệu trong giai đoạn đó **đúng**: bỏ các pseudo-bar đi thì H1 giống 100% với một lần tải lại mới từ broker (2009-09 → 2020-12) và M1 tổng hợp lên H1 khớp ≈ 100%.
5. **Nguồn gốc chính xác của pseudo-bar chưa xác định được** (mục 5). Có bằng chứng rằng nó **không còn được broker phục vụ hôm nay**, nên có đường phục hồi tại nguồn (cần hành động của chủ dự án).

## 1. Chuỗi truy vết dữ liệu (RAW → … → BACKTEST)
| Bước | Bằng chứng | Phát hiện |
|---|---|---|
| Nguồn thô | `xau-edge/data/market/XAUUSD/events.jsonl`, `docs/MT5_DATA_PLATFORM.md`, `history_backfill.py` | Toàn bộ lịch sử lấy **native** từ terminal MT5 `FTMO-Demo` (`copy_rates_from`), "không bịa nến". Ngày 2026-10-09 terminal bị giới hạn 100.000 bar; chủ dự án đã nâng "Max bars" rồi backfill M1 (từ 2004-06), M5, M15, M30, H1 (từ 2004-06), H4 (từ 2004-06). Hiện terminal lại là `maxbars = 100000` |
| Import | `data/raw/` (chỉ 2025-05→), `data/research_history/` (`mt5-ftmo-demo-history`: H1 2010-01→2025-04, H4 2004→2025-04, M15 2022-07→) | Kho nghiên cứu H1/H4 **cũng chứa pseudo-bar** (tải ngày 2026-10-08 từ cùng terminal) |
| Chuẩn hóa | `bar-manifest.json`, `parity-audit.json`: "8/8 cặp EXACT, kể cả toàn bộ lịch sử" | Parity chỉ chứng minh **kho = terminal tại lúc tải**, không chứng minh terminal đúng |
| Resampling | `market_data/resampling.py` | V1 chỉ resample khi cần; M1→…→H1 trong kho khớp tuyệt đối với M5 (kiểm: M5 close = M1 close phút thứ 4 = 100% trên mọi tháng mẫu) |
| Parquet / V2 reader | `BarStore`, `frame_from_polars` | Không biến đổi giá; `as_of` đúng quy tắc "chỉ bar đã đóng" (open + độ dài khung) |
| MarketState / Candidate / Backtest | `core/market_state.py`, `core/candidate.py`, `research/backtest.py` | Mã không có lỗi nhìn trước; **dữ liệu** có. Pseudo-bar "đã đóng" lúc 21:05 (M5) / 22:00 (H1) nên đi vào EMA, cấu trúc, ATR cho hàng trăm bar sau đó |

## 2. Bằng chứng về pseudo-bar
**Định nghĩa phát hiện** (`research/clean_view.py`): phút 0 của giờ 21 hoặc 22 UTC, `spread == 0`, `tick_volume ≥ max(20.000, 20 × trung vị)`. Bar đầu tiên sau khoảng nghỉ bình thường cũng có spread 0 nhưng chỉ vài nghìn tick (2021: 1.500–4.700), nên không bị bắt (có test).

| Bằng chứng | Kết quả |
|---|---|
| Số bar, thời gian | 2.205 bar M1, một mỗi ngày giao dịch (20–23/tháng), **2012-06-26 → 2021-01-20**, 104 tháng liên tục; 0 bar ngoài giai đoạn này |
| Nội dung | Ngày D 21:00: O=1425,13 H=1430,57 L=**1388,37** C=**1392,36**, vol 187.530; bar thật cùng giờ chỉ biên độ ≈ $0,3 |
| Nó là gì | OHLC khớp **phiên kế tiếp** trong ≥ 95% số ngày (|H|, |L|, |C| ≤ $1; sai số trung vị 0,03–0,27), chỉ ≈ 7% khớp phiên trước (2013, 2016, 2019). Nó **gần giống** nến D1 của terminal (ví dụ 2013-05-15: H 1430,80 / L 1388,37 / C 1392,86 / vol 281.001) nhưng **không trùng**: H 1430,57, C 1392,36, vol 187.530 |
| Lan truyền | Cùng bar có trong M1, M5, M15, M30, H1. H4 bị **gộp**: kho H4 21:00 UTC = O 1425,13 / H 1430,80 / **L 1388,37** / C 1425,74 / vol **195.680** = bar thật (L 1423,62, vol 8.150) cộng pseudo-bar (187.530 + 8.150 = 195.680) |
| Triệu chứng | tự tương quan lag-1 **toàn chuỗi** −0,29…−0,38 ở M1/M5/H1; **khi chỉ xét cặp trong cùng phiên** ≈ −0,02 (bình thường); **99–100% hiệp phương sai âm đến từ các cặp sát khoảng nghỉ**; bỏ pseudo-bar ⇒ −0,03…+0,02 trên mọi tháng thử (2012-06, 2013-05, 2016-05, 2019-05, 2020-12, 2021-01) |
| Tác động lên trạng thái | trên bar quyết định 22:00–04:00 UTC: **82–87%** trạng thái đổi nhãn khi bỏ pseudo-bar (M15 structure 55–62%, vol regime 49–55%, H1 trend 12–24%); ATR15 phình trung vị ×1,4–1,5 |

## 3. Tái tải từ MetaQuotes-Demo (nhà cung cấp KHÁC FTMO; hôm nay, 2026-10-13)
`scripts/research/terminal_dump.py` (chỉ `copy_rates_range`, không hàm giao dịch, không thông tin tài khoản) tải H1 (từ 2009-09), H4 (từ 2004-06), D1.
- **H1, 2009-09 → 2020-12: 100% bar giống hệt kho** (OHLC ≤ $0,005), kể cả 2012-06→2020-12; kho chỉ **thừa đúng các pseudo-bar**.
- **H4, 2004-06 → 2012-05: 100% giống;** 2012-06 → 2020: 83,3% (5/6 bar giống; bar 21:00 UTC khác do bị gộp).
- Terminal hiện **không phục vụ** bar H1 lúc 00:00 giờ server (21:00 UTC); H4 lúc đó có giá trị bình thường. Nghĩa là **nguồn hôm nay sạch hơn kho** cho H1/H4.
- Từ **2021-02**: tải lại ≠ kho (khác biệt vài cent tới hàng chục cent; `spread` 4 so với 45; tick volume khác). Ranh giới trùng thời điểm các pseudo-bar chấm dứt (2021-01-20). Kết luận: dữ liệu terminal **bị sửa/xây lại** giữa hai lần tải ở giai đoạn gần đây; so khớp tuyệt đối với tải lại **không còn ý nghĩa** từ 2021-02.

## 4. Các kiểm tra khác yêu cầu
| Kiểm tra | Kết quả |
|---|---|
| Loại giá | **BID**. Tick bid tổng hợp thành M1 khớp kho trong 2 cent ở 94–100% bar (2021-11: 100%; 2026-06: 100%); mid và ask lệch 0,06–0,47 |
| Timestamp/múi giờ/DST | Kho = **UTC**. Giờ server = UTC+2 mùa đông, +3 mùa hè theo lịch DST của Mỹ; offset khớp mọi tháng 2009–2020 (67 tháng chuyển mùa có cả hai offset), H1 giống hệt sau khi quy đổi. Không phát hiện lệch múi giờ |
| OHLC hợp lệ, trùng lặp, thứ tự | 0 bar sai OHLC, 0 trùng timestamp, 0 bar sai thứ tự trong cả 269 tháng M5 |
| Khoảng nghỉ phiên | khoảng nghỉ hằng ngày 21:00–22:00 UTC và cuối tuần bình thường; số khoảng nghỉ/tháng 15–23 |
| Spread và real_volume | `spread` = 0 toàn bộ 2004→2010 (không ghi nhận); 2011: 60–70; 2013: 30–40; 2019: 20; 2024: 13; 2026: 40–50. `real_volume` ≠ 0 chỉ ở H1/H4 2012-03-28 → 2018-02-09 (V1 đã ghi chú, không dùng). Đổi nguồn tick volume (15 → 115 → 20) trùng các mốc 2012-04 và 2018-02 |
| Phân phối lợi suất, jump | kurtosis cao (12–200), 3–35 bar > 8σ/tháng. Trong giai đoạn lỗi 20–35/tháng là pseudo-bar; ngoài ra sự kiện thật (ví dụ 2021-08-09: sập chớp nhoáng mở cửa Chủ nhật 1.763 → 1.684, **thật**, được xác nhận bởi công khai) |
| Độc lập khoảng nghỉ | tự tương quan tách khoảng nghỉ: 2004-06..09 và 2005-03..05 vẫn ≈ −0,18…−0,36 ⇒ **SUSPECT** (spread không ghi, M1 thưa, có thể bid-ask bounce; chưa giải thích) |
| Đối chiếu sự kiện công khai (yếu, theo trí nhớ, không phải nguồn độc lập có giấy phép) | sau khi bỏ pseudo-bar: đỉnh 1920,61 (9/2011), đáy 1046,23 (12/2015), đỉnh 2074,87 (8/2020), 1682,99 (8/2021) khớp các mốc đã biết; bản thô có 1388,37 làm "đáy" 14/5/2013 |
| Nguồn độc lập bên thứ ba | **không có sẵn, chưa dùng.** Không tải dữ liệu có giấy phép chưa rõ. Mọi "VERIFIED_VALID" dưới đây nghĩa là "khớp bằng chứng cùng broker", không phải bên thứ ba |

## 5. Nguồn gốc pseudo-bar: đã biết và chưa biết
Đã biết: (a) có mặt trong kho `research_history` tải ngày 2026-10-08 trực tiếp từ terminal; (b) V1 không tạo bar (backfill chỉ ghi nến native); (c) tải lại H1/H4 hôm nay không có; (d) bar giống nhưng không trùng nến D1 của broker.
Chưa biết: vì sao terminal phục vụ chúng ngày 10-08/09 (đang "Max bars = Unlimited", terminal xây lại lịch sử?) mà hôm nay không. Giả thuyết: (H1) máy chủ broker đã sửa lịch sử giữa các lần tải; (H2) chế độ "unlimited" khiến terminal dựng lại khung thấp từ một bản ghi hàng ngày; (H3) tài khoản/server khác nhau. **Thí nghiệm phân biệt (cần chủ dự án):** nâng Max bars trên một bản terminal riêng, tải M1 một ngày 2016, kiểm pseudo-bar (xem `V2_DATA_RECOVERY_OPTIONS.md`).

## 6. Phân loại tháng (269 tháng XAUUSD M5)
Định nghĩa. **VERIFIED_VALID:** (≤2021-01) H1 (từ 2009-09) hoặc H4 (trước đó) **giống hệt** tải lại mới (≥99,5%), M1 tổng hợp khớp bucket (≥97%), vệ sinh sạch, không pseudo-bar, tự tương quan trong phiên |·| ≤ 0,15; (≥2021-10) M1 khớp tick thu độc lập (≥97% trong 10 cent) và vệ sinh sạch. **INVALID:** ≥ 5 pseudo-bar (dữ liệu nhìn trước); *recoverable* nếu bỏ chúng thì H1 giống hệt tải lại và M1 khớp. **SUSPECT:** bất thường chưa giải thích hoặc khớp kém. **INSUFFICIENT_EVIDENCE:** không có nguồn đối chiếu.
| Giai đoạn | Lớp | Số tháng |
|---|---|---|
| 2004-06 → 2004-09 | SUSPECT (mean reversion trong phiên, spread không ghi) | 4 |
| 2004-10 → 2005-02 | VERIFIED_VALID (mức H4) | 5 |
| 2005-03 → 2005-05 | SUSPECT | 3 |
| 2005-06 → 2012-05 | VERIFIED_VALID (H4 trước 2009-09; H1 sau) | 84 |
| 2012-06 | SUSPECT (3 pseudo-bar, tháng bắt đầu) | 1 |
| 2012-07 → 2020-12 | **INVALID, recoverable** (trừ 2020-10 không đạt điều kiện recoverable do 5 bar H1 lệch) | 101 (+1) |
| 2021-01 | INVALID (13 pseudo-bar tới 01-20, phần sau khác tải lại) | 1 |
| 2021-02 → 2021-09 | INSUFFICIENT_EVIDENCE (không tick, tải lại đã khác) | 8 |
| 2021-10 → 2026-10 | VERIFIED_VALID 53 tháng; SUSPECT 8 tháng: 2022-01..03 (khớp tick 54–86%), 2023-10, 2024-01, 2024-07, 2024-08, 2025-10 (96–97%) | 61 |
Tổng: VERIFIED_VALID 142, SUSPECT 16, INVALID (recoverable) 101, INVALID 2, INSUFFICIENT_EVIDENCE 8. Bảng từng tháng: `reports/evidence/data_forensics/months.csv`.
**Lưu ý:** ngưỡng 97% khớp tick là chọn theo kinh nghiệm, các tháng 96–97% rất gần ngưỡng; **2022-01..03 (khớp 54–86%, chênh tới $7,8) là bất thường thật cần điều tra trước khi Test-H được mở**.

## 7. Giới hạn
Chưa có nguồn bên thứ ba; mẫu tick chỉ 3 ngày/tháng; ngưỡng phân loại do em chọn (đã nêu); không xác định được nguyên nhân gốc pseudo-bar; không tải lại M1/M5/M15/M30 cho 2012–2021 vì terminal đang giới hạn 100.000 bar. Em chỉ **đọc** dữ liệu giá của Test-H và Holdout để kiểm tính toàn vẹn (không outcome chiến lược), ghi trong sổ nhiễm.
