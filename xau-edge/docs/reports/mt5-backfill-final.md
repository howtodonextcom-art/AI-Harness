# Báo cáo backfill lịch sử MT5 (cuối cùng)

Sinh bởi `scripts/backfill_mt5.py` lúc 2026-10-09T09:32:42+00:00. Máy chủ: FTMO-Demo, symbol broker: XAUUSD, `Max bars in chart` của terminal: 100000.

| Khung | Yêu cầu từ | Broker trả về sớm nhất | Local sớm nhất | Local mới nhất | Số nến | Trạng thái | Đủ? |
|---|---|---|---|---|---|---|---|
| M1 | 2003-01-01 | 2026-06-29T15:03:00+00:00 | 2026-06-29T15:03:00+00:00 | 2026-10-09T09:31:00+00:00 | 100309 | TERMINAL_LIMITED | chưa |
| M5 | 2003-01-01 | 2025-05-08T08:40:00+00:00 | 2025-05-08T08:40:00+00:00 | 2026-10-09T09:25:00+00:00 | 100048 | TERMINAL_LIMITED | chưa |
| M15 | 2003-01-01 | 2022-07-18T18:00:00+00:00 | 2022-07-18T18:00:00+00:00 | 2026-10-09T09:15:00+00:00 | 100016 | TERMINAL_LIMITED | chưa |
| M30 | 2003-01-01 | 2018-05-11T16:00:00+00:00 | 2018-05-11T16:00:00+00:00 | 2026-10-09T09:00:00+00:00 | 100008 | TERMINAL_LIMITED | chưa |
| H1 | 2003-01-01 | 2010-02-05T00:00:00+00:00 | 2010-02-05T00:00:00+00:00 | 2026-10-09T08:00:00+00:00 | 100003 | TERMINAL_LIMITED | chưa |
| H4 | 2003-01-01 | 2004-06-11T01:00:00+00:00 | 2004-06-11T01:00:00+00:00 | 2026-10-09T05:00:00+00:00 | 34232 | BROKER_LIMITED | có |

## Lý do và khoảng trống lớn nhất

* **M1** — the terminal's 'Max bars in chart' (100000) caps the history it can serve; raise it, restart the terminal and rerun
  * khoảng trống 53.1 giờ: 2026-07-03T16:59:00+00:00 → 2026-07-05T22:05:00+00:00
  * khoảng trống 49.3 giờ: 2026-07-10T20:49:00+00:00 → 2026-07-12T22:05:00+00:00
  * khoảng trống 49.3 giờ: 2026-07-17T20:49:00+00:00 → 2026-07-19T22:05:00+00:00
  * khoảng trống 49.3 giờ: 2026-07-24T20:49:00+00:00 → 2026-07-26T22:05:00+00:00
  * khoảng trống 49.3 giờ: 2026-07-31T20:49:00+00:00 → 2026-08-02T22:05:00+00:00
* **M5** — the terminal's 'Max bars in chart' (100000) caps the history it can serve; raise it, restart the terminal and rerun
  * khoảng trống 73.3 giờ: 2026-04-02T20:45:00+00:00 → 2026-04-05T22:05:00+00:00
  * khoảng trống 53.2 giờ: 2025-07-04T16:55:00+00:00 → 2025-07-06T22:05:00+00:00
  * khoảng trống 53.2 giờ: 2026-06-19T16:55:00+00:00 → 2026-06-21T22:05:00+00:00
  * khoảng trống 53.2 giờ: 2026-07-03T16:55:00+00:00 → 2026-07-05T22:05:00+00:00
  * khoảng trống 51.4 giờ: 2025-11-28T19:40:00+00:00 → 2025-11-30T23:05:00+00:00
* **M15** — the terminal's 'Max bars in chart' (100000) caps the history it can serve; raise it, restart the terminal and rerun
  * khoảng trống 73.2 giờ: 2022-12-23T21:45:00+00:00 → 2022-12-26T23:00:00+00:00
  * khoảng trống 73.2 giờ: 2022-12-30T21:45:00+00:00 → 2023-01-02T23:00:00+00:00
  * khoảng trống 73.2 giờ: 2023-04-06T20:45:00+00:00 → 2023-04-09T22:00:00+00:00
  * khoảng trống 73.2 giờ: 2023-12-22T21:45:00+00:00 → 2023-12-25T23:00:00+00:00
  * khoảng trống 73.2 giờ: 2023-12-29T21:45:00+00:00 → 2024-01-01T23:00:00+00:00
* **M30** — the terminal's 'Max bars in chart' (100000) caps the history it can serve; raise it, restart the terminal and rerun
  * khoảng trống 75.5 giờ: 2020-12-24T18:30:00+00:00 → 2020-12-27T22:00:00+00:00
  * khoảng trống 73.5 giờ: 2021-04-01T20:30:00+00:00 → 2021-04-04T22:00:00+00:00
  * khoảng trống 73.5 giờ: 2021-12-23T21:30:00+00:00 → 2021-12-26T23:00:00+00:00
  * khoảng trống 73.5 giờ: 2022-04-14T20:30:00+00:00 → 2022-04-17T22:00:00+00:00
  * khoảng trống 73.5 giờ: 2022-12-23T21:30:00+00:00 → 2022-12-26T23:00:00+00:00
* **H1** — the terminal's 'Max bars in chart' (100000) caps the history it can serve; raise it, restart the terminal and rerun
  * khoảng trống 86.0 giờ: 2010-11-11T09:00:00+00:00 → 2010-11-14T23:00:00+00:00
  * khoảng trống 83.0 giờ: 2011-04-21T18:00:00+00:00 → 2011-04-25T05:00:00+00:00
  * khoảng trống 80.0 giờ: 2010-12-10T20:00:00+00:00 → 2010-12-14T04:00:00+00:00
  * khoảng trống 78.0 giờ: 2015-12-24T16:00:00+00:00 → 2015-12-27T22:00:00+00:00
  * khoảng trống 78.0 giờ: 2015-12-31T16:00:00+00:00 → 2016-01-03T22:00:00+00:00
* **H4** — the cap is not binding and nothing older is served: the broker has no earlier bars
  * khoảng trống 112.0 giờ: 2005-11-23T14:00:00+00:00 → 2005-11-28T06:00:00+00:00
  * khoảng trống 104.0 giờ: 2006-11-22T14:00:00+00:00 → 2006-11-26T22:00:00+00:00
  * khoảng trống 88.0 giờ: 2004-07-02T13:00:00+00:00 → 2004-07-06T05:00:00+00:00
  * khoảng trống 88.0 giờ: 2004-09-03T13:00:00+00:00 → 2004-09-07T05:00:00+00:00
  * khoảng trống 88.0 giờ: 2004-12-23T14:00:00+00:00 → 2004-12-27T06:00:00+00:00

Trạng thái: `COMPLETE_AVAILABLE_HISTORY` (đủ), `BROKER_LIMITED` (broker không có sớm hơn; đủ theo định nghĩa), `TERMINAL_LIMITED` (terminal chặn: cần hành động của chủ dự án), `INCOMPLETE` (chạy lại), `UNKNOWN`.
Khoảng trống lớn là nến broker không có trong khung đó (cuối tuần/ngày lễ/giờ nghỉ là bình thường; xem `docs/MT5_DATA_PLATFORM.md`). Không có nến nào bị bịa từ khung khác.

**OWNER_ACTION_REQUIRED:** close FTMO MT5 completely, run `uv run python scripts/mt5_set_max_bars.py --value 10000000 --apply`, reopen FTMO MT5 and wait for login/synchronisation, then rerun `uv run --extra mt5 python scripts/backfill_mt5.py --write-report`
