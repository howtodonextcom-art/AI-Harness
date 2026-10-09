"use client";

import { useCallback, useState } from "react";
import { EvidenceBadge } from "@/components/research/LifecycleBadge";
import { StatusBadge, type Tone } from "@/components/research/StatusBadge";
import { Gate, Panel, RefreshButton, ResearchShell, SourceNote, TableWrap, Txt, Warning, td, th, useLoad } from "@/components/research/ui";
import { type CandidateDetail, type CandidatesView as View, type GateMap, type GateState, fmt, research } from "@/lib/research";

const CRITERIA: Record<string, { label: string; op: string }> = {
  min_trades: { label: "Số lệnh tối thiểu (n)", op: "≥" },
  ci_lower_above_zero: { label: "Cận dưới CI của mean net R", op: ">" },
  profit_factor: { label: "PF (hệ số lãi/lỗ)", op: "≥" },
  max_drawdown_r: { label: "Max drawdown (R)", op: "≤" },
  positive_folds: { label: "Số fold dương", op: "≥" },
  robust_to_best_trades: { label: "Mean net R sau khi loại best 5% lệnh", op: ">" },
  no_concentration: { label: "Tập trung theo phiên/chế độ (tối đa)", op: "≤" },
};

const GATE_LABEL: Record<string, string> = {
  cost_stress: "Cost Stress",
  parameter_stability: "Parameter stability",
  temporal_stability: "Temporal stability",
  broker_robustness: "Broker robustness",
};

/** PASS and FAIL are shown only when the file says so; anything else is NOT RUN / UNKNOWN, never a pass. */
export function GateBadge({ state }: { state: GateState | string }) {
  const map: Record<string, [Tone, string]> = {
    PASS: ["ok", "PASS"],
    FAIL: ["fail", "FAIL"],
    "CHƯA CHẠY": ["neutral", "CHƯA CHẠY"],
    "KHÔNG RÕ": ["unknown", "KHÔNG RÕ"],
  };
  const [tone, text] = map[state] ?? ["unknown", "KHÔNG RÕ"];
  return <StatusBadge tone={tone}>{text}</StatusBadge>;
}

function Gates({ gates }: { gates: GateMap }) {
  return (
    <ul className="grid gap-2 sm:grid-cols-2" aria-label="Bốn cổng robustness">
      {Object.keys(GATE_LABEL).map((g) => (
        <li key={g} className="flex items-center justify-between gap-2 rounded-md border border-slate-300/60 px-2 py-1 text-sm dark:border-slate-700">
          <span>{GATE_LABEL[g]}</span>
          <GateBadge state={gates[g]?.state ?? "KHÔNG RÕ"} />
        </li>
      ))}
    </ul>
  );
}

function Detail({ detail }: { detail: CandidateDetail }) {
  const periods = Object.entries(detail.periods);
  const allPass = periods.length > 0 && periods.every(([, p]) => p.stage_pass);
  return (
    <div className="space-y-4" aria-label={`Chi tiết ${detail.variant}`}>
      <p className="text-sm">
        <strong className="font-mono">{detail.variant}</strong> ({detail.hypothesis ?? "?"}) <EvidenceBadge label={allPass ? "UNVALIDATED" : "REJECTED"} />
        <span className="ml-2 text-xs text-slate-500">
          {allPass ? "qua cả hai giai đoạn nhưng cần Test-H và cổng robustness (chưa phải VALIDATED)" : "không qua đủ 7 tiêu chí ở mọi giai đoạn"}
        </span>
      </p>
      {periods.map(([name, p]) => (
        <Panel key={name} title={`Giai đoạn ${name}: ${p.criteria_passed}/${p.criteria_total} tiêu chí đạt`}>
          <p className="mb-2 text-xs text-slate-500">
            n = {p.trades ?? "chưa có"} · K = {p.variants_k ?? "chưa có"} · alpha = {fmt(p.alpha, 5)} · mean net R cơ sở {fmt(p.mean_net_r_base, 4)} / bi quan{" "}
            {fmt(p.mean_net_r_pessimistic, 4)}
          </p>
          <TableWrap label={`Bảng 7 tiêu chí, giai đoạn ${name}`}>
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr>
                  {["Tiêu chí", "Giá trị", "Ngưỡng", "Kết quả"].map((c) => (
                    <th key={c} className={th} scope="col">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(p.criteria).map(([key, c]) => {
                  const meta = CRITERIA[key] ?? { label: key, op: "" };
                  return (
                    <tr key={key} className="border-t border-slate-300/50 dark:border-slate-700">
                      <td className={td}>{meta.label}</td>
                      <td className={`${td} font-mono`}>{fmt(c.value, 3)}</td>
                      <td className={`${td} font-mono`}>
                        {meta.op} {fmt(c.threshold, 2)}
                      </td>
                      <td className={td}>{c.passed ? <StatusBadge tone="ok">ĐẠT</StatusBadge> : <StatusBadge tone="fail">KHÔNG ĐẠT</StatusBadge>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </TableWrap>
          <SourceNote source={detail.sources} />
        </Panel>
      ))}
      <div className="grid gap-4 md:grid-cols-2">
        <Panel title="Gross-at-mid so với net R">
          <p className="text-sm">
            gross-mid R: <strong>{detail.gross_mid_r === null ? "chưa có" : fmt(detail.gross_mid_r)}</strong>
          </p>
          <p className="text-xs text-slate-500">
            <Txt>{detail.gross_mid_note}</Txt>
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Đường vốn: <Txt>{detail.equity_note}</Txt>
          </p>
        </Panel>
        <Panel title="Bốn cổng robustness">
          <Gates gates={detail.gates} />
          <p className="mt-2 text-xs text-slate-500">CHƯA CHẠY nghĩa là chưa có bằng chứng, không phải đã đạt.</p>
        </Panel>
      </div>
    </div>
  );
}

function DetailLoader({ variant }: { variant: string }) {
  const loader = useCallback((s: AbortSignal) => research.candidate(variant, s), [variant]);
  const { result } = useLoad(loader);
  return (
    <Gate result={result} what={`chi tiết ${variant}`}>
      {(d) => <Detail detail={d} />}
    </Gate>
  );
}

function Body({ view }: { view: View }) {
  const [selected, setSelected] = useState<string | null>(null);
  return (
    <div className="space-y-4">
      {view.survivors.length === 0 ? (
        <p role="status" className="rounded-xl border-2 border-red-600 bg-red-500/10 p-3 text-sm font-semibold text-red-800 dark:text-red-200">
          Không có biến thể nào sống sót qua cả hai giai đoạn: tất cả đều REJECTED.
        </p>
      ) : (
        <Warning>Ứng viên sống sót: {view.survivors.join(", ")}. Vẫn UNVALIDATED cho đến khi Test-H và bốn cổng robustness đạt.</Warning>
      )}
      <Panel title={`Mọi biến thể (${view.variants.length})`}>
        <p className="mb-2 text-xs text-slate-500">
          <Txt>{view.note}</Txt>
        </p>
        <TableWrap label="Bảng biến thể">
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr>
                {["Biến thể", "Sống sót", "Nhãn", "Giai đoạn (n, tiêu chí đạt)", "Cổng robustness", "Chi tiết"].map((c) => (
                  <th key={c} className={th} scope="col">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {view.variants.map((v) => (
                <tr key={v.variant} className={`border-t border-slate-300/50 dark:border-slate-700 ${selected === v.variant ? "bg-sky-500/10" : ""}`}>
                  <td className={`${td} font-mono`}>{v.variant}</td>
                  <td className={td}>{v.survivor ? <StatusBadge tone="warn">CÓ (ứng viên)</StatusBadge> : <StatusBadge tone="fail">KHÔNG</StatusBadge>}</td>
                  <td className={td}>
                    <EvidenceBadge label={v.survivor ? "UNVALIDATED" : "REJECTED"} />
                  </td>
                  <td className={`${td} text-xs`}>
                    {Object.entries(v.periods).map(([name, p]) => (
                      <div key={name}>
                        {name}: n = {p.trades ?? "?"}, {p.criteria_passed}/{p.criteria_total}, R bi quan {fmt(p.mean_net_r_pessimistic, 3)}
                      </div>
                    ))}
                  </td>
                  <td className={td}>
                    <div className="flex flex-wrap gap-1">
                      {Object.keys(GATE_LABEL).map((g) => (
                        <span key={g} title={GATE_LABEL[g]}>
                          <GateBadge state={v.gates[g]?.state ?? "KHÔNG RÕ"} />
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className={td}>
                    <button
                      type="button"
                      onClick={() => setSelected(selected === v.variant ? null : v.variant)}
                      aria-expanded={selected === v.variant}
                      aria-label={`Xem chi tiết ${v.variant}`}
                      className="whitespace-nowrap rounded-md border border-slate-400 px-2 py-0.5 text-xs"
                    >
                      {selected === v.variant ? "Ẩn" : "Xem"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
        <SourceNote source={view.source} />
      </Panel>
      {selected && <DetailLoader key={selected} variant={selected} />}
    </div>
  );
}

export function CandidatesView() {
  const loader = useCallback((s: AbortSignal) => research.candidates(s), []);
  const { result, reload } = useLoad(loader);
  return (
    <ResearchShell current="/research/candidates" title="Ứng viên và cổng robustness" subtitle="Bảng 7 tiêu chí cho từng biến thể, gross-mid so với net R, và bốn cổng robustness (chỉ đọc).">
      <div className="flex justify-end">
        <RefreshButton onClick={reload} />
      </div>
      <Gate result={result} what="danh sách ứng viên">
        {(view) => <Body view={view} />}
      </Gate>
    </ResearchShell>
  );
}
