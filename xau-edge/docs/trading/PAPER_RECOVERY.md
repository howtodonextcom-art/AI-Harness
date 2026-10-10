# An toàn trạng thái PAPER: ghi nhật ký trước, fail-closed, khôi phục

Mục tiêu: bàn paper không bao giờ **âm thầm** mất, nhân đôi hay làm lại một lệnh. Khi nghi ngờ, nó dừng mở lệnh mới và nói rõ.

## 1. Thiết kế (commit-log)

`paper_journal.jsonl` là nguồn sự thật (chỉ thêm, `fsync` từng dòng). `paper_desk.json` chỉ là ảnh chụp (ghi nguyên tử: file tạm → `replace`) để khởi động nhanh.

Thứ tự khi mở lệnh: `paper.pending` (ý định) → khớp lệnh trong bộ nhớ → `paper.open` (mang `broker_position`) → ghi ảnh chụp. Khi đóng: `paper.close` (mang `broker_closed`) → ảnh chụp.

Lúc khởi động bàn **đối chiếu** ảnh chụp với journal:

| Tình huống | Kết quả |
|---|---|
| Khớp | `PAPER DESK READY` |
| `pending` mồ côi (sập trước khi khớp, không có gì để khôi phục) | Tự ghi `paper.abort` (`CRASH_BEFORE_COMMIT`), lệnh thành CANCELLED, không tính là vị thế |
| Journal có `open`/`close` mà ảnh chụp thiếu hoặc khác (sập giữa journal và ảnh chụp) | **FAIL CLOSED**: `PAPER_STATE_ERROR` cho tới khi chạy khôi phục (mục 3); không tự sửa âm thầm |
| Ảnh chụp hỏng/không đọc được | **FAIL CLOSED** như trên; file hỏng được giữ lại `paper_desk.json.corrupt-<giờ>` |

Khi FAIL CLOSED mọi thao tác mở lệnh mới bị từ chối, giao diện báo lỗi đỏ.

Các kiểm thử cắm lỗi (`tests/unit/trading/test_paper_safety.py`) giả lập sập ở từng khe: trước/sau `pending`, trước/sau khớp, trước/sau `open`, trước/sau ghi ảnh chụp, trước/sau `close`.

## 2. Một tiến trình ghi duy nhất

`data/trade/writer.lock` là khóa **cấp hệ điều hành** (msvcrt/fcntl) kèm metadata `{pid, role, host, started_at, code_version}`. Tiến trình thứ hai không lấy được khóa thì chạy ở chế độ **chỉ đọc**: không ghi journal/telemetry/alert, hero hiện `DECISION UNAVAILABLE` + `WRITER_LOCK`, không mở được lệnh. Khóa tự nhả khi tiến trình chết (không có khóa "mồ côi" chặn mãi); metadata cũ được báo là stale.

## 3. Khôi phục

Kiểm tra (không thay đổi gì):

```
uv run python scripts/paper_recover.py
```

In `OK` nếu ảnh chụp và journal khớp; nếu không, liệt kê từng khác biệt và mã thoát 1.

Áp dụng (dựng lại ảnh chụp từ journal):

1. Dừng stack: `scripts\stop_market_stack.ps1` (lệnh `--apply` cần khóa ghi, sẽ từ chối nếu API còn chạy).
2. `uv run python scripts/paper_recover.py --apply`
3. Ảnh chụp cũ được giữ `paper_desk.json.bak-<giờ>`, một dòng `paper.recovered` được ghi vào journal.
4. Khởi động lại stack.

Nó từ chối (không đụng gì) nếu chính journal không đáng tin (định dạng cũ, dòng không đọc được).

## 4. Giới hạn đã biết

* Tiến độ MFE/MAE giữa hai lần lưu và `last_bar` không phục hồi được từ journal; sau khôi phục chúng được tính lại từ nến kế tiếp (có thể lạc quan/bi quan nhẹ cho phần đã qua).
* Chỉ bảo vệ **bàn paper**. Chưa có đối chiếu vị thế MT5 (không có lệnh thật); đó là yêu cầu của sprint DEMO sau này.
* Quy tắc cuối tuần/đóng cửa: mặc định `BLOCK_NEW_NEAR_CLOSE` (chặn mở mới sát giờ đóng cửa, lý do hiện trên nút); `HOLD_ACROSS_CLOSE` và `CLOSE_BEFORE_CLOSURE` cấu hình được.
