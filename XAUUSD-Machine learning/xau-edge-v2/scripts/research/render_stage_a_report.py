"""Render the Stage A reports (Markdown) from the JSON the research scripts wrote: no hand-copied numbers.

uv run python scripts/research/render_stage_a_report.py <reports dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "research"


def pct(a: float, b: float) -> str:
    return "n/a" if not b else f"{100 * a / b:.1f}%"


def table(rows: list[list[object]], head: list[str]) -> str:
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def dist(d: dict[str, object]) -> str:
    return f"{d['p10']} / {d['p50']} / {d['p90']} (n={d['n']})"


def main(out_dir: Path) -> None:  # noqa: PLR0915 - one section per report block
    mf = json.loads((DOCS / "multifamily_stage_a_dev.json").read_text(encoding="utf-8"))
    core = json.loads((DOCS / "core_stage_a_dev.json").read_text(encoding="utf-8"))
    fams = mf["families"]
    lines: list[str] = [
        "# V2 · Stage A signal-only: CAND_V2_CORE_1.1.0 và MULTIFAMILY_RESEARCH_0.1.0 (DEV')",
        "",
        "Viết cho: chủ dự án. **Không có outcome, không PnL, không mở Validation/Confirm-C/Test-H/Holdout, "
        "không chỉnh ngưỡng.** Số liệu được kết xuất tự động từ "
        "`docs/research/multifamily_stage_a_dev.json` và `docs/research/core_stage_a_dev.json`.",
        "",
        f"Dữ liệu: kho sạch (manifest `{str(mf['manifest_sha256'])[:12]}…`), tháng PASS của DEV' 2005-11..2018-12; "
        f"M15: {mf['bars_scored_m15']:,} nến (~{mf['approx_trading_years']} năm giao dịch).",
        "",
        "## 1. MULTIFAMILY_RESEARCH_0.1.0 (spec đóng băng `multifamily_0.1.0.spec.json`, hash `multifamily_0.1.0.sha256`)",
        "",
        "### 1.1 Phễu (mỗi episode bị chặn ở cổng ĐẦU TIÊN nó vi phạm)",
    ]
    rows = []
    for n, f in fams.items():
        s = f["funnel_survivors"]
        rows.append([
            n, s["RAW"], s["EPISODES"], s["AFTER_CLEARANCE"], s["AFTER_STOP"], s["AFTER_TARGET"],
            s["AFTER_COST"], f["accepted_without_overlap"]["n"],
        ])  # fmt: skip
    lines.append(
        table(
            rows,
            [
                "Họ",
                "Raw",
                "Episode",
                "Sau CLEARANCE",
                "Sau STOP",
                "Sau TARGET",
                "Sau COST (= chấp nhận)",
                "Không chồng (96 nến)",
            ],
        )
    )
    lines += ["", "Cổng đầu tiên chặn episode:", ""]
    rows = []
    for n, f in fams.items():
        r = f["first_refusal_of_episodes"]
        e = f["episodes"]["n"]
        rows.append(
            [n]
            + [
                f"{r.get(g, 0)} ({pct(r.get(g, 0), e)})"
                for g in ("CLEARANCE", "STOP", "TARGET", "COST", "ACCEPTED")
            ]
        )
    lines.append(table(rows, ["Họ", "CLEARANCE", "STOP", "TARGET", "COST", "ACCEPTED"]))
    lines += ["", "### 1.2 Cân bằng hướng (mua / bán)", ""]
    rows = []
    for n, f in fams.items():
        rows.append([n, f"{f['raw_eligibility']['buy']}/{f['raw_eligibility']['sell']}",
                     f"{f['episodes']['buy']}/{f['episodes']['sell']}",
                     f"{f['accepted_signals']['buy']}/{f['accepted_signals']['sell']}"])  # fmt: skip
    lines.append(table(rows, ["Họ", "Raw", "Episode", "Chấp nhận"]))
    lines += ["", "### 1.3 Chế độ và phiên (của tín hiệu chấp nhận)", ""]
    for n, f in fams.items():
        lines.append(
            f"- **{n}** chế độ M15: `{json.dumps(f['regime_of_accepted'], ensure_ascii=False)}`; phiên: `{json.dumps(f['session_of_accepted'], ensure_ascii=False)}`"
        )
    lines += ["", "### 1.4 Khả thi hình học", ""]
    rows = []
    for n, f in fams.items():
        g = f["geometry_feasibility"]
        rows.append([n, f"{100 * g['episodes_with_valid_stop_share']:.1f}%", dist(g["risk_atr_of_valid_stops"]),
                     f"{100 * g['with_target_share_of_valid_stops']:.1f}%",
                     f"{100 * g['target_capped_by_structure_share']:.1f}%", dist(g["net_rr_of_valid_targets"]),
                     dist(g["cost_r_of_valid_orders"])])  # fmt: skip
    lines.append(
        table(
            rows,
            [
                "Họ",
                "Episode có stop hợp lệ (≤3 ATR)",
                "Rủi ro ATR p10/50/90",
                "Có target hợp lệ (trong số có stop)",
                "Target bị cản chặn",
                "Net R:R p10/50/90",
                "cost_R p10/50/90",
            ],
        )
    )
    lines += ["", "### 1.5 Chồng lấn giữa các họ (tín hiệu chấp nhận, ±6 nến M15)", ""]
    rows = [
        [
            k,
            v[next(x for x in v if x.endswith("accepted"))],
            v["same_side_within_6_bars"],
            v["opposite_side_within_6_bars"],
        ]
        for k, v in mf["overlap_between_families"].items()
    ]
    lines.append(table(rows, ["Cặp", "Số tín hiệu của họ đầu", "Cùng phía", "Ngược phía"]))
    if "overlap_core_vs_multifamily" in core:
        lines += ["", "Core giao họ mới (CORE episode, ±1 giờ):", ""]
        rows = [
            [k, v["core_episodes"], v["same_side_within_1h"], v["opposite_side_within_1h"]]
            for k, v in core["overlap_core_vs_multifamily"].items()
        ]
        lines.append(table(rows, ["Họ", "Core episodes", "Cùng phía", "Ngược phía"]))
    lines += ["", "### 1.6 Ước lượng công suất nghiên cứu (không phải kết quả)", ""]
    rows = []
    for n, f in fams.items():
        p = f["research_power"]
        rows.append([n, f["accepted_without_overlap"]["n"], p["n_required_for_0.20R"], p["n_required_for_0.30R"],
                     p["years_to_reach_n_for_0.20R"], p["years_to_reach_n_for_0.30R"]])  # fmt: skip
    lines.append(
        table(
            rows,
            [
                "Họ",
                "Tín hiệu không chồng trong DEV'",
                "n cần (0,20R)",
                "n cần (0,30R)",
                "Năm để đủ n (0,20R)",
                "Năm để đủ n (0,30R)",
            ],
        )
    )
    lines += [
        "",
        "## 2. CAND_V2_CORE_1.1.0 (spec đóng băng `cand_v2_spec.json`, hash `cand_v2_spec.sha256`)",
        "",
    ]
    lines.append(
        f"Tháng đã xử lý: **{core['months_processed']}** ({core['first_month']} → {core['last_month']}); "
        f"hoàn tất toàn DEV': **{core['complete']}**. Nến M5 đánh giá: {core['m5_bars_evaluated']:,}; "
        f"bị bỏ qua vì thiếu trạng thái (H1 UNKNOWN hoặc thiếu M1): {core['m5_bars_skipped_no_state']:,} "
        f"({pct(core['m5_bars_skipped_no_state'], core['m5_bars_evaluated'])}); "
        f"nến mà chuỗi CONTROL đủ điều kiện khi TẮT cổng (raw eligibility giả định): "
        f"{core['raw_eligibility_chain_ok_bars_gates_off']:,}."
    )
    lines += [
        "",
        "Tín hiệu sau cổng chi phí/cấu trúc (mọi biến thể, episode = chuỗi cùng phía cách nhau ≤60 phút):",
        "",
    ]
    rows = []
    for name, v in core["variants"].items():
        rows.append([name, v["signals_after_gates"], v["episodes"], json.dumps(v["direction"]),
                     v["research_power"]["episodes_per_year"], v["research_power"]["years_to_reach_n_for_0.20R"]])  # fmt: skip
    lines.append(
        table(
            rows, ["Biến thể", "Tín hiệu", "Episode", "Hướng", "Episode/năm", "Năm để đủ n (0,20R)"]
        )
    )
    core_v = core["variants"].get("CORE")
    if core_v:
        lines += ["", f"CORE: chế độ H4 `{core_v['regime_h4']}`; chế độ M15 `{core_v['regime_m15']}`; phiên `{core_v['session']}`; "
                  f"hình học rủi ro ATR {dist(core_v['geometry']['risk_atr'])}; net R:R {dist(core_v['geometry']['net_rr'])}."]  # fmt: skip
    lines += [
        "",
        "Giới hạn: số liệu Core phụ thuộc vào việc replay đã chạy hết DEV' chưa (`complete`).",
    ]
    (out_dir / "V2_STAGE_A_SIGNAL_ONLY_REPORT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    d = mf["family_D_study"]
    rr = d["range_runs"]
    dl = [
        "# V2 · Family D (tương tác biên RANGE): tính bền RANGE, nhân quả của biên, khả năng tạo lệnh",
        "",
        "Dữ liệu: DEV' 2005-11..2018-12, M15 sạch. **Không outcome.** Nhãn SAU nến tín hiệu chỉ dùng để mô tả độ bền của nhãn "
        "trong báo cáo này, không bao giờ đi vào tín hiệu. Không chọn D vì kỳ vọng lợi nhuận.",
        "",
        "## 1. Tính bền của RANGE",
        f"- Tỉ lệ nến mang nhãn RANGE: **{100 * d['range_label_share']:.1f}%**.",
        f"- {rr['n_runs']:,} đoạn RANGE liên tiếp: độ dài p25 / trung vị / p75 = **{rr['p25_bars']} / {rr['median_bars']} / {rr['p75_bars']} nến**.",
        f"- {100 * rr['share_of_runs_ge_12_bars']:.1f}% số đoạn dài ≥12 nến; {100 * rr['share_of_runs_ge_24_bars']:.1f}% ≥24 nến; "
        f"nhưng {100 * rr['share_of_range_bars_in_runs_ge_24']:.1f}% số nến RANGE nằm trong các đoạn ≥24 nến (nhãn bền tập trung ở ít đoạn dài).",
        f"- Tuổi của đoạn RANGE tại nến tín hiệu D (p10/p50/p90): **{d['range_age_at_signal_bars']['p10']} / {d['range_age_at_signal_bars']['p50']} / {d['range_age_at_signal_bars']['p90']} nến**: "
        "một phần đáng kể tín hiệu D xảy ra khi nhãn RANGE còn rất non.",
        f"- Nhãn RANGE còn nguyên sau tín hiệu: **{100 * d['range_persists_after_signal']['next_6_bars']:.1f}%** (6 nến), "
        f"**{100 * d['range_persists_after_signal']['next_12_bars']:.1f}%** (12 nến), **{100 * d['range_persists_after_signal']['next_24_bars']:.1f}%** (24 nến).",
        "",
        "## 2. Nhân quả và độ ổn định của mức biên",
        "- Biên = đỉnh/đáy của **20 nến TRƯỚC** nến tín hiệu (nhân quả theo cấu tạo; test cắt lịch sử `tests/unit/test_multifamily.py::test_the_contract_is_causal` và `test_families_are_causal_*`).",
        f"- Độ rộng biên (ATR) p10/p50/p90: **{d['boundary_width_atr']['p10']} / {d['boundary_width_atr']['p50']} / {d['boundary_width_atr']['p90']}**.",
        f"- Biên còn NGUYÊN SAU 6 nến chỉ **{100 * d['boundary_unchanged_6_bars_later_share']:.1f}%**: biên cuốn chiếu 20 nến trượt liên tục; không phải mức giá cố định. Đây là hạn chế của định nghĩa hiện tại, không sửa sau khi xem số.",
        f"- Số lần chạm cạnh biên (trong 0,25 ATR) trong 20 nến trước: p10/p50/p90 = {d['prior_touches_of_the_edge_within_0.25_atr']['p10']} / {d['prior_touches_of_the_edge_within_0.25_atr']['p50']} / {d['prior_touches_of_the_edge_within_0.25_atr']['p90']}.",
        "",
        "## 3. Khả năng hình thành lệnh hợp lệ",
        f"- Episode D: {d['d_episode_heads']:,}; có lệnh hợp lệ (qua mọi cổng) **{100 * d['valid_order_share_of_heads']:.1f}%**.",
        f"- Cổng đầu tiên chặn: `{json.dumps(d['first_refusal_of_heads'])}`.",
        "- Stop luôn là sàn 1,25 ATR của CONTROL (biên rủi ro 0,8 ATR nhỏ hơn sàn); cổng TARGET (net R:R ≥ 1,5 với mức đối diện là biên đối diện) và COST (cost_R ≤ 0,15) chặn nhiều nhất.",
        "",
        "## 4. Kết luận có kiểm soát",
        "- D là họ duy nhất có đủ số tín hiệu không chồng trong DEV' để chạm cỡ mẫu 0,20R (xem báo cáo Stage A), nhưng **nhãn RANGE không bền** và biên trượt: luận điểm 'biên ổn định' chưa được dữ liệu ủng hộ. Bộ lọc độ bền (vd. tuổi RANGE tối thiểu) là biến thể mới (K+1) và **không** được thêm sau khi xem số liệu này.",
        "- Trạng thái: **INCONCLUSIVE / NOT_TESTED** về edge; đây là kiểm tra khả thi và độ bền của nhãn, không phải kết quả giao dịch.",
    ]
    (out_dir / "V2_FAMILY_D_RANGE_REPORT.md").write_text("\n".join(dl) + "\n", encoding="utf-8")
    print("rendered")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
