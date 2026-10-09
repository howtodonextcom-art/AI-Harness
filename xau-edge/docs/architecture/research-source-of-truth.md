# Hợp đồng nguồn sự thật của Research Console

Nguyên tắc: **BẰNG CHỨNG > UI**. Mỗi trường hiển thị đi theo một đường duy nhất:

```
ARTEFACT NGUỒN -> PARSER ĐÃ KIỂM CHỨNG -> MÔ HÌNH MIỀN -> API (GET) -> UI
```

Không có đường ngược lại: một trạng thái UI, một file JSON nhập tay hay một ô nhập không bao giờ là sự thật
khoa học. Một trường hiển thị mà không có dòng trong bảng dưới đây là **lỗi**. Mọi nguồn thiếu, hỏng hay
mâu thuẫn trả `status: "unknown"` (KHÔNG RÕ), không bao giờ ngầm thành đạt.

Mọi phản hồi `/research/*` và `/lifecycle/*` có khối `provenance` (`generated_at`, `code_commit` rút gọn)
cộng `source` của chính view. Không phản hồi nào chứa đường dẫn tuyệt đối, bí mật hay số tài khoản đầy đủ.

## Bảng nguồn

| Trường hiển thị | Nguồn sự thật | Parser / kiểm chứng | Trạng thái khi thiếu hoặc sai |
|---|---|---|---|
| K, alpha, trần K của V1 | `docs/research/edge-program/ledger.md` (chỉ thêm) | `research/ledger.parse_ledger` (regex nghiêm, đếm dòng lỗi) | unknown |
| K của V2 | `docs/research/edge-program-v2/ledger.md` | như trên; K lấy từ ledger, không từ STATE.json | unknown |
| Trạng thái quyết định D-1..D-5 | Phụ lục A của roadmap + `STATE.json` | `service._decisions` | pending |
| Đăng ký giả thuyết (rationale, cơ chế, sai khi nào) | `hypotheses/H*.md` + `H*.registration.json` | `integrity.registration.HypothesisRegistration` (pydantic, extra=forbid) | registration: unknown |
| MDE, N kỳ vọng, underpowered | **tính lại** từ đầu vào của đăng ký (`registration.derive`), không lưu | `integrity.power2.power_report` | unknown |
| Commit và thời điểm đăng ký, commit kết quả đầu | lịch sử git (`git log`, chỉ đọc) | `research/hypotheses.commit_info`, `first_commit_mentioning` | unknown_reason (clone nông, file chưa commit) |
| Toàn vẹn đăng ký trước | thời điểm commit cuối của file so với dòng ledger đầu | `hypotheses.preregistration_check` | UNKNOWN / VIOLATION |
| Kết quả Stage 1 | `experiments/edge_program_v2_stage1/*_dev2.json` | `integrity_views.stage1` + manifest | unknown (cấu trúc sai) |
| Danh tính thí nghiệm | `manifests/<id>.json` (tên file = hash nội dung) | `integrity.identity.RunManifest` | provenance = KHÔNG RÕ |
| Nhãn VALIDATED, ADEQUATELY_POWERED, REPRODUCIBLE | **chỉ** `integrity.evidence.can_display(label, proof)` | một hàm duy nhất | allowed=false + lý do |
| Khóa Test-H và Holdout | `experiments/runs`, file kết quả, ledger, freeze | `service.locks` (nhiều nguồn) | KHÔNG RÕ; chỉ NGUYÊN VẸN khi mọi nguồn đọc được và đối soát khớp |
| Kết quả Test-H / Holdout | `experiments/edge_program_v2/{testH,holdout}-outcome.json` **và** freeze record | `service._outcome_state` | LOCKED / UNKNOWN (kết quả không có freeze là UNKNOWN) |
| Ứng viên sống sót Stage 2 | file kết quả có 2 giai đoạn dev/val | `service._variants`, `_is_survivor` | unknown nếu trùng hay lỗi file |
| Cổng robustness | `experiments/edge_program_v2/robustness/<variant>.json` | `service._gates` | CHƯA CHẠY / KHÔNG RÕ |
| Hiệu chuẩn cổng và công suất | `edge-program-v2/gate-calibration.json` (từ mô phỏng, có seed) | `integrity_views.gate_calibration` | unknown |
| Dòng dõi dữ liệu | `edge-program-v2/lineage.json` (từ `scripts/build_lineage.py`) | `integrity.lineage.verify` + id băm lại | unknown; giai đoạn rỗng hiện TRỐNG |
| Chứng nhận đồng hồ theo năm | `edge-program-v2/clock-certificate.json` | `forensics.clock` | CHƯA CHỨNG NHẬN |
| Chất lượng dữ liệu | `data-manifest.json`, `data-quality-by-year.json` | `service.data` | unknown |
| Bằng chứng tiên nghiệm | `data/forward/prospective.jsonl` (chuỗi băm) | `integrity.prospective.verify` | NO PROSPECTIVE EVIDENCE YET / PROVENANCE INVALID / KHÔNG RÕ |
| Sẵn sàng forward | `data/forward/<id>/summary.json` | `integrity.forward_power.readiness` (N hiệu dụng, lịch, chế độ) | INCONCLUSIVE khi thiếu đầu vào |
| Bảng vòng đời | seed từ kết quả + `data/execution/lifecycle.jsonl` | `research.lifecycle.LifecycleStore` | lỗi file = unknown (fail closed) |
| Gợi ý suy giảm edge | `configs/research/decay.yaml` + tóm tắt forward | `research.decay.evaluate_decay` | UNKNOWN; `advisory_only` khi chưa kết luận |
| Chi phí giả định / đo | `CostModel` mặc định / `data/execution/calibration.json` | `service.calibration` | GIẢ ĐỊNH; EXECUTION_VALIDATED bị từ chối khi thiếu |
| Soak, uptime | `data/execution/cycles.jsonl`, `alerts.jsonl` | `service.soak` (cửa sổ tới hiện tại) | unknown |
| Luật funded | `configs/prop/ftmo_funded.yaml` | `funded.rules` | unknown |
| Tier rollout (định nghĩa) | `configs/execution/rollout.yaml` | `funded.rollout.RolloutConfig` | unknown |
| Tier rollout hiện tại | cơ sở dữ liệu trạng thái funded (console **không mở**) | không có | KHÔNG RÕ theo thiết kế |

## Quy tắc

1. **Một hàm quyết định nhãn.** Giao diện không tự suy ra "VALIDATED", "adequately powered", "reproducible",
   "sealed before outcome", "execution-validated": chúng đến từ `can_display` hoặc `prospective.verify`.
2. **Số suy ra không được lưu.** MDE, số biến thể, cờ underpowered luôn tính lại từ đầu vào.
3. **Lớp bằng chứng** (`DESCRIPTIVE .. EXECUTION`) đi cùng mọi số liệu thống kê; không lớp nào tự nâng cấp.
4. **Chỉ đọc.** Ngoại lệ duy nhất là hạ trạng thái chiến lược xuống WATCH/DEGRADED/DISABLED (ADR-0024).
5. **Artefact sinh ra là bất biến và có băm**: manifest (tên file = hash), lineage (id = hash nội dung),
   ledger tiên nghiệm (chuỗi băm), sổ bậc tự do (chuỗi băm). Sửa một byte bị phát hiện.
