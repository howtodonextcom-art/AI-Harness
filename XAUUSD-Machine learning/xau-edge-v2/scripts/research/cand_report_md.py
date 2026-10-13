"""Render ``summary.json`` of ``cand_evaluate.py`` as the eight separated sections of the report.

uv run python scripts/research/cand_report_md.py data/research/cand_eval/summary.json > report.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def fmt(v: Any, nd: int = 3) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def table(head: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(fmt(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def main() -> None:
    s = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    v = s["variants"]
    names = list(v)
    parts = [
        f"# Candidate evaluation, window {s['window']}",
        f"spec sha256 `{s['spec_sha256'][:16]}...` | code `{s['git_sha'][:10]}` | {s['years']:.2f} years | {s['bars']} M5 bars | {s['armed_episodes']} ARMED setups of the control (episodes)",
        "",
        "## 1. Structural reachability (no outcome)",
        table(
            [
                "variant",
                "changes",
                "episodes",
                "per year",
                "reachability = episodes / armed setups",
            ],
            [
                [
                    n,
                    "+".join(v[n]["changes"]) or "-",
                    v[n]["episodes"],
                    v[n]["episodes_per_year"],
                    v[n]["episodes"] / max(1, s["armed_episodes"]),
                ]
                for n in names
            ],
        ),
        "",
        "## 2. Episode frequency and 3. Executed PAPER trades",
        table(
            [
                "variant",
                "episodes",
                "attempted",
                "refused by governor",
                "unresolved",
                "executed",
                "per year",
                "BUY",
                "SELL",
            ],
            [
                [
                    n,
                    v[n]["episodes"],
                    v[n]["attempted"],
                    json.dumps(v[n]["refused"]),
                    v[n]["unresolved"],
                    v[n]["executed"],
                    v[n]["executed_per_year"],
                    v[n]["buy"],
                    v[n]["sell"],
                ]
                for n in names
            ],
        ),
        "",
        "## 4. Expectancy after costs (R per trade) and 5. Statistical uncertainty",
        table(
            ["variant", "N", "months", "E", "lower 97.5%", "upper 97.5%", "status", "reason"],
            [
                [
                    n,
                    v[n]["executed"],
                    v[n]["months_with_trades"],
                    v[n]["E"],
                    v[n]["E_lower"],
                    v[n]["E_upper"],
                    v[n]["status"],
                    v[n]["status_reason"],
                ]
                for n in names
            ],
        ),
        "",
        "Power (design): " + json.dumps(s["power"]),
        "",
        "Cost decomposition per executed trade (R): price path (already contains the spread mechanics and slippage), swap, planned spread, planned slippage",
        table(
            [
                "variant",
                "mean price R",
                "mean swap R",
                "planned spread R",
                "planned slippage R",
                "win rate",
                "false positives",
            ],
            [
                [
                    n,
                    v[n]["mean_r_price"],
                    v[n]["mean_r_swap"],
                    v[n]["mean_r_spread_plan"],
                    v[n]["mean_r_slip_plan"],
                    v[n]["win_rate"],
                    v[n]["false_positive_rate"],
                ]
                for n in names
            ],
        ),
        "",
        "## 6. Safety violations",
        table(
            [
                "variant",
                "signals",
                "net_rr<1.5",
                "stop>3ATR",
                "risk!=0.25",
                "cost_R>cap",
                "spike",
                "on SHOCK bar",
                "gap through stop",
                "ambiguous bars",
                "horizon exits",
                "MDD R",
                "worst month R",
                "caps hold",
            ],
            [
                [
                    n,
                    *[
                        s["violations"][n][k]
                        for k in (
                            "signals",
                            "net_rr_below_1_5",
                            "stop_above_3_atr",
                            "risk_not_0_25",
                            "cost_r_above_cap",
                            "spread_spike",
                            "on_shock_bar",
                        )
                    ],
                    v[n]["gap_through_stop"],
                    v[n]["ambiguous_bars"],
                    v[n]["horizon_exits"],
                    v[n]["mdd_R"],
                    v[n]["worst_month_R"],
                    v[n]["caps_hold"],
                ]
                for n in names
            ],
        ),
    ]
    if "incremental" in s:
        inc = s["incremental"]
        parts += [
            "",
            "## 7. Candidate versus control (incremental trades: present in the variant, absent in its parent)",
            table(
                ["variant", "parent", "N", "E", "lower", "upper", "status", "reason"],
                [
                    [
                        i["variant"],
                        i["parent"],
                        i["n"],
                        i["E"],
                        i["lower"],
                        i["upper"],
                        i["status"],
                        i["reason"],
                    ]
                    for i in inc.values()
                ],
            ),
        ]
        sel = s["selection"]
        parts += [
            "",
            "## 8. Preregistered selection rule and INCONCLUSIVE findings",
            table(
                [
                    "change",
                    "S structural",
                    "V safety",
                    "O not refuted",
                    "caps",
                    "statuses",
                    "enters",
                    "flag",
                ],
                [
                    [
                        c,
                        d["S_structural"],
                        d["V_safety"],
                        d["O_not_refuted"],
                        d["caps"],
                        ", ".join(d["statuses"]),
                        d["enters"],
                        d["flag"],
                    ]
                    for c, d in sel["changes"].items()
                ],
            ),
            "",
            f"Included changes: {sel['included']}; frozen candidate: **{sel['frozen_candidate']}**; no candidate: {sel['no_candidate']}",
        ]
    by_year = [
        [n]
        + [
            fmt(v[n]["by_year"].get(str(y), {}).get("n", 0))
            + "/"
            + fmt(v[n]["by_year"].get(str(y), {}).get("E"))
            for y in range(2011, 2019)
        ]
        for n in names
    ]
    parts += ["", "Trades/E by year", table(["variant", *map(str, range(2011, 2019))], by_year)]
    print("\n".join(parts))


if __name__ == "__main__":
    main()
