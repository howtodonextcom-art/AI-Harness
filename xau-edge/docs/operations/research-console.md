# Research console (web)

Trang `/research` của dashboard giúp chủ dự án theo dõi chương trình nghiên cứu trong
`docs/PROFITABILITY_ROADMAP.md` **mà không thể tự lừa mình**. ADR-0024. Nó chỉ **hiển thị**: không chạy
thí nghiệm, không mở Test-H hay holdout, không bật funded, không gửi lệnh. Thao tác duy nhất là **hạ
trạng thái** một chiến lược (WATCH, DEGRADED, DISABLED); không bao giờ nâng bậc từ web.

## Chạy

```powershell
uv run python scripts/serve_api.py          # API chỉ nghe 127.0.0.1:8000, có /research và /lifecycle
cd apps/dashboard; npm run build; npm run start   # http://localhost:3000/research
```

Nút "Hạ trạng thái" cần `XAU_EDGE_WEB_CONTROL=true` (control plane, ADR-0023: token, Host, Origin,
gõ chữ `DEMOTE`). Không bật thì phần đọc vẫn dùng được.

## Nguồn dữ liệu của từng trang (mọi con số truy ngược được tới file)

| Trang | Nội dung | Nguồn |
|---|---|---|
| `/research` | kết luận (B), K, ngân sách giả thuyết, điều kiện dừng, quyết định D-1..D-5 | `docs/research/edge-program/{final-verdict,ledger}.md`, `docs/research/edge-program-v2/STATE.json`, Phụ lục A của roadmap |
| `/research/ledger` | từng lần chạy, bộ đếm K, alpha, MDE | `ledger.md` (V1) và `edge-program-v2/ledger.md` (V2), công thức mục 5.1 của roadmap |
| `/research/hypotheses` | H01..H14, đăng ký trước hay chưa | `hypotheses/H*.md`, ledger, `git log` (chỉ đọc) |
| `/research/candidates` | 7 tiêu chí, gross-mid so với net, 4 cổng robustness | `experiments/edge_program*/**.json`, `experiments/edge_program_v2/robustness/<biến thể>.json` |
| `/research/data` | bảng dữ liệu, chứng nhận giờ broker theo năm, khóa dữ liệu | `data-manifest.json`, `edge-program-v2/clock-certificate.json`, `experiments/runs` |
| `/research/forward` | vòng đời chiến lược, kỳ vọng so với thực tế, gợi ý suy giảm | `data/execution/lifecycle.jsonl`, `data/forward/<id>/summary.json`, `configs/research/decay.yaml` |
| `/research/operations` | chi phí giả định so với đo được, soak, luật funded còn chờ | `data/execution/{calibration.json,cycles.jsonl,alerts.jsonl}`, `configs/prop/ftmo_funded.yaml` |

## Ý nghĩa các nhãn

* **KHÔNG RÕ**: nguồn thiếu hoặc hỏng. Không bao giờ được hiểu là "ổn".
* **NGUYÊN VẸN / ĐÃ DÙNG** (Test-H, holdout): NGUYÊN VẸN chỉ hiện khi sổ đăng ký thí nghiệm đọc được
  trọn vẹn và không có lần dùng nào.
* **CHƯA CHẠY** (cổng robustness): chưa có kết quả; không phải PASS.
* **VI PHẠM ĐĂNG KÝ TRƯỚC**: file giả thuyết được commit sau lần chạy đầu tiên của nó.
* **KHÔNG KẾT LUẬN**: forward dưới 100 lệnh.
* **GIẢ ĐỊNH**: chi phí chưa được đo trên tài khoản demo (sprint P12).
* **CHƯA CHỨNG NHẬN** (năm): giờ broker của năm đó chưa được xác minh; giả thuyết theo phiên bị chặn.

## `STATE.json` của Edge Program V2 (chủ dự án hoặc code nghiên cứu ghi, web chỉ đọc)

```json
{"sprint": "P0", "k_declared": 0, "k_cap": 48, "hypotheses_used": 0, "hypotheses_budget": 8,
 "decisions": {"D-1": "approved"}}
```

Chưa có file này nghĩa là "chưa bắt đầu V2"; các quyết định hiện là `pending` cho đến khi bạn ghi.

## An toàn

Đường dẫn chỉ được nằm trong `docs/research`, `docs/evals`, `docs/reports`, `docs/operations`,
`experiments`, `data/execution`, `data/forward`, `configs`; không đọc `.env*`, cơ sở dữ liệu, khóa hay
token; không có đường dẫn tuyệt đối trong câu trả lời; mọi route `/research` và `/lifecycle` chỉ GET.
Có test cho từng điều trên (`tests/unit/research/`).
