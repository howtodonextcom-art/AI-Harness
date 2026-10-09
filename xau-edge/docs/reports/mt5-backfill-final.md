# Báo cáo backfill lịch sử MT5 (cuối cùng)

Sinh bởi `scripts/backfill_mt5.py` lúc 2026-10-09T10:49:22+00:00. Máy chủ: FTMO-Demo, symbol broker: XAUUSD, `Max bars in chart` của terminal: 10000000.

| Khung | Yêu cầu từ | Broker trả về sớm nhất | Local sớm nhất | Local mới nhất | Số nến | Trạng thái | Đủ? |
|---|---|---|---|---|---|---|---|
| M1 | 2003-01-01 | 2004-06-11T04:18:00+00:00 | 2004-06-11T04:18:00+00:00 | 2026-10-09T10:47:00+00:00 | 7064072 | BROKER_LIMITED | có |
| M5 | 2003-01-01 | 2004-06-11T04:15:00+00:00 | 2004-06-11T04:15:00+00:00 | 2026-10-09T10:40:00+00:00 | 1499955 | BROKER_LIMITED | có |
| M15 | 2003-01-01 | 2004-06-11T04:15:00+00:00 | 2004-06-11T04:15:00+00:00 | 2026-10-09T10:30:00+00:00 | 515609 | BROKER_LIMITED | có |
| M30 | 2003-01-01 | 2004-06-11T04:00:00+00:00 | 2004-06-11T04:00:00+00:00 | 2026-10-09T10:00:00+00:00 | 260713 | BROKER_LIMITED | có |
| H1 | 2003-01-01 | 2004-06-11T04:00:00+00:00 | 2004-06-11T04:00:00+00:00 | 2026-10-09T09:00:00+00:00 | 132226 | BROKER_LIMITED | có |
| H4 | 2003-01-01 | 2004-06-11T01:00:00+00:00 | 2004-06-11T01:00:00+00:00 | 2026-10-09T05:00:00+00:00 | 34232 | BROKER_LIMITED | có |

## Lý do và khoảng trống lớn nhất

* **M1** — the cap is not binding and nothing older is served: the broker has no earlier bars
  * khoảng trống 109.3 giờ: 2005-11-23T17:16:00+00:00 → 2005-11-28T06:36:00+00:00
  * khoảng trống 102.1 giờ: 2006-11-22T17:00:00+00:00 → 2006-11-26T23:07:00+00:00
  * khoảng trống 86.2 giờ: 2006-02-17T16:23:00+00:00 → 2006-02-21T06:36:00+00:00
  * khoảng trống 86.0 giờ: 2005-02-18T16:49:00+00:00 → 2005-02-22T06:52:00+00:00
  * khoảng trống 86.0 giờ: 2010-11-11T09:03:00+00:00 → 2010-11-14T23:05:00+00:00
* **M5** — the cap is not binding and nothing older is served: the broker has no earlier bars
  * khoảng trống 109.3 giờ: 2005-11-23T17:15:00+00:00 → 2005-11-28T06:35:00+00:00
  * khoảng trống 102.1 giờ: 2006-11-22T17:00:00+00:00 → 2006-11-26T23:05:00+00:00
  * khoảng trống 86.2 giờ: 2006-02-17T16:20:00+00:00 → 2006-02-21T06:35:00+00:00
  * khoảng trống 86.1 giờ: 2005-02-18T16:45:00+00:00 → 2005-02-22T06:50:00+00:00
  * khoảng trống 86.1 giờ: 2010-11-11T09:00:00+00:00 → 2010-11-14T23:05:00+00:00
* **M15** — the cap is not binding and nothing older is served: the broker has no earlier bars
  * khoảng trống 109.2 giờ: 2005-11-23T17:15:00+00:00 → 2005-11-28T06:30:00+00:00
  * khoảng trống 102.0 giờ: 2006-11-22T17:00:00+00:00 → 2006-11-26T23:00:00+00:00
  * khoảng trống 86.2 giờ: 2006-02-17T16:15:00+00:00 → 2006-02-21T06:30:00+00:00
  * khoảng trống 86.0 giờ: 2005-02-18T16:45:00+00:00 → 2005-02-22T06:45:00+00:00
  * khoảng trống 86.0 giờ: 2010-11-11T09:00:00+00:00 → 2010-11-14T23:00:00+00:00
* **M30** — the cap is not binding and nothing older is served: the broker has no earlier bars
  * khoảng trống 109.5 giờ: 2005-11-23T17:00:00+00:00 → 2005-11-28T06:30:00+00:00
  * khoảng trống 102.0 giờ: 2006-11-22T17:00:00+00:00 → 2006-11-26T23:00:00+00:00
  * khoảng trống 86.5 giờ: 2006-02-17T16:00:00+00:00 → 2006-02-21T06:30:00+00:00
  * khoảng trống 86.0 giờ: 2004-09-03T15:30:00+00:00 → 2004-09-07T05:30:00+00:00
  * khoảng trống 86.0 giờ: 2004-12-23T16:30:00+00:00 → 2004-12-27T06:30:00+00:00
* **H1** — the cap is not binding and nothing older is served: the broker has no earlier bars
  * khoảng trống 109.0 giờ: 2005-11-23T17:00:00+00:00 → 2005-11-28T06:00:00+00:00
  * khoảng trống 102.0 giờ: 2006-11-22T17:00:00+00:00 → 2006-11-26T23:00:00+00:00
  * khoảng trống 86.0 giờ: 2004-09-03T15:00:00+00:00 → 2004-09-07T05:00:00+00:00
  * khoảng trống 86.0 giờ: 2004-12-23T16:00:00+00:00 → 2004-12-27T06:00:00+00:00
  * khoảng trống 86.0 giờ: 2005-02-18T16:00:00+00:00 → 2005-02-22T06:00:00+00:00
* **H4** — the cap is not binding and nothing older is served: the broker has no earlier bars
  * khoảng trống 112.0 giờ: 2005-11-23T14:00:00+00:00 → 2005-11-28T06:00:00+00:00
  * khoảng trống 104.0 giờ: 2006-11-22T14:00:00+00:00 → 2006-11-26T22:00:00+00:00
  * khoảng trống 88.0 giờ: 2004-07-02T13:00:00+00:00 → 2004-07-06T05:00:00+00:00
  * khoảng trống 88.0 giờ: 2004-09-03T13:00:00+00:00 → 2004-09-07T05:00:00+00:00
  * khoảng trống 88.0 giờ: 2004-12-23T14:00:00+00:00 → 2004-12-27T06:00:00+00:00

Trạng thái: `COMPLETE_AVAILABLE_HISTORY` (đủ), `BROKER_LIMITED` (broker không có sớm hơn; đủ theo định nghĩa), `TERMINAL_LIMITED` (terminal chặn: cần hành động của chủ dự án), `INCOMPLETE` (chạy lại), `UNKNOWN`.
Khoảng trống lớn là nến broker không có trong khung đó (cuối tuần/ngày lễ/giờ nghỉ là bình thường; xem `docs/MT5_DATA_PLATFORM.md`). Không có nến nào bị bịa từ khung khác.
