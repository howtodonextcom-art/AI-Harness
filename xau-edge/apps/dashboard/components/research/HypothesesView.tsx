"use client";

import { useCallback, useState } from "react";
import { EvidenceBadge } from "@/components/research/EvidenceBadge";
import { StatusBadge, type Tone } from "@/components/research/StatusBadge";
import { Gate, Panel, RefreshButton, ResearchShell, SourceNote, TableWrap, Txt, td, th, useLoad } from "@/components/research/ui";
import { type CommitInfo, type HypothesesView as View, type HypothesisRow, type Preregistration, type Registration, fmt, research } from "@/lib/research";

function PreReg({ p }: { p: Preregistration }) {
  const map: Record<Preregistration["state"], [Tone, string]> = {
    OK: ["ok", "ĐĂNG KÝ TRƯỚC: OK"],
    VIOLATION: ["fail", "VI PHẠM ĐĂNG KÝ TRƯỚC"],
    NO_RESULTS: ["neutral", "CHƯA CÓ KẾT QUẢ"],
    UNKNOWN: ["unknown", "KHÔNG RÕ"],
  };
  const [tone, text] = map[p.state] ?? ["unknown", "KHÔNG RÕ"];
  return (
    <div className="space-y-0.5">
      <StatusBadge tone={tone}>{text}</StatusBadge>
      <p className="text-xs text-slate-500">
        <Txt>{p.detail}</Txt>
      </p>
      {p.registered_at && <p className="font-mono text-[11px] text-slate-500">commit đăng ký {p.registered_at}</p>}
      {p.first_run_at && <p className="font-mono text-[11px] text-slate-500">lần chạy đầu {p.first_run_at}</p>}
    </div>
  );
}

const MECH: Record<string, [Tone, string]> = {
  HYPOTHESIZED: ["warn", "HYPOTHESIZED (chỉ là giả thuyết)"],
  PARTIALLY_SUPPORTED: ["info", "PARTIALLY_SUPPORTED"],
  OBSERVED_PROXY: ["info", "OBSERVED_PROXY"],
  DIRECTLY_OBSERVED: ["info", "DIRECTLY_OBSERVED"],
};

function Mechanism({ status }: { status: string | null | undefined }) {
  const [tone, text] = (status && MECH[status]) || (["unknown", "KHÔNG RÕ"] as [Tone, string]);
  return <StatusBadge tone={tone}>{text}</StatusBadge>;
}

function num(v: number | null | undefined, digits = 0): string {
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "KHÔNG RÕ";
}

/** Registration cells of one row. Legacy V1 rows keep the old note; unknown is KHÔNG RÕ, never blank. */
function regCells(r: Registration | null | undefined): React.ReactNode[] {
  if (r?.status === "ok") {
    const n = r.variant_count ?? r.variant_ids?.length ?? null;
    const dropped = r.dropped_variants ?? [];
    return [
      <span key="n" className="font-mono">
        {num(r.expected_event_count)}
      </span>,
      <span key="ne" className="font-mono">
        {num(r.effective_event_count_estimate)}
      </span>,
      <span key="m" className="font-mono">
        {num(r.mde_raw, 3)} / {num(r.mde_effective, 3)} R
      </span>,
      <span key="k" className="font-mono">
        {num(r.k_at_registration)}
      </span>,
      r.underpowered_by_design === null || r.underpowered_by_design === undefined ? (
        <StatusBadge key="u" tone="unknown">
          KHÔNG RÕ
        </StatusBadge>
      ) : r.underpowered_by_design ? (
        <StatusBadge key="u" tone="warn">
          UNDERPOWERED BY DESIGN
        </StatusBadge>
      ) : (
        <StatusBadge key="u" tone="neutral">
          đủ công suất theo thiết kế
        </StatusBadge>
      ),
      <span key="v">
        <span className="font-mono">{num(n)}</span> biến thể
        {dropped.length > 0 && (
          <span className="block text-xs text-slate-500">
            bỏ {dropped.length}: {dropped.join(", ")}
          </span>
        )}
      </span>,
      <Mechanism key="mech" status={r.mechanism_status} />,
    ];
  }
  const text =
    r?.status === "legacy" ? (
      <span className="text-xs text-slate-500">chưa có trong file đăng ký (legacy V1)</span>
    ) : (
      <StatusBadge tone="unknown" title={r?.reason}>
        KHÔNG RÕ
      </StatusBadge>
    );
  return Array.from({ length: 7 }, (_, i) => <span key={i}>{i === 0 ? text : "—"}</span>);
}

function CommitLine({ label, c }: { label: string; c: CommitInfo | null | undefined }) {
  const sha = c?.commit;
  return (
    <p className="text-xs">
      <span className="text-slate-500">{label}: </span>
      {sha ? (
        <span className="break-all font-mono" title={sha}>
          {sha.slice(0, 8)} · {c?.time ?? "KHÔNG RÕ"}
        </span>
      ) : (
        <span className="font-semibold text-amber-800 dark:text-amber-300">KHÔNG RÕ{c?.unknown_reason ? ` (${c.unknown_reason})` : ""}</span>
      )}
    </p>
  );
}

function Detail({ h }: { h: HypothesisRow }) {
  const r = h.registration;
  return (
    <Panel title={`Chi tiết ${h.id}: ${h.title}`}>
      <div className="mb-3 grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Toàn vẹn đăng ký trước</h3>
          <PreReg p={h.preregistration} />
          <CommitLine label="commit đăng ký" c={h.registration_commit} />
          <CommitLine label="commit kết quả đầu tiên" c={h.first_result_commit} />
        </div>
        <div className="space-y-1">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Điều kiện bác bỏ</h3>
          <p className="text-sm">{r?.status === "ok" && r.falsification_condition ? <Txt>{r.falsification_condition}</Txt> : "KHÔNG RÕ"}</p>
        </div>
      </div>
      {r?.status === "ok" ? (
        <div className="grid gap-3 md:grid-cols-2">
          <section aria-label="Đã quan sát (thống kê)" className="min-w-0 rounded-lg border-2 border-slate-500 bg-slate-500/5 p-3">
            <h3 className="flex flex-wrap items-center gap-2 text-sm font-semibold">
              Đã quan sát (thống kê) <EvidenceBadge cls={r.evidence_class ?? "DESCRIPTIVE"} />
            </h3>
            <p className="mt-1 break-words text-sm">
              <Txt>{r.observed_pattern ?? "KHÔNG RÕ"}</Txt>
            </p>
            <dl className="mt-2 grid grid-cols-2 gap-x-2 gap-y-0.5 text-xs">
              <dt className="text-slate-500">n sự kiện dự kiến (thô)</dt>
              <dd className="font-mono">{num(r.expected_event_count)}</dd>
              <dt className="text-slate-500">n hiệu dụng (ước tính)</dt>
              <dd className="font-mono">{num(r.effective_event_count_estimate)}</dd>
              <dt className="text-slate-500">K lúc đăng ký</dt>
              <dd className="font-mono">{num(r.k_at_registration)}</dd>
              <dt className="text-slate-500">sd kỳ vọng / power mục tiêu</dt>
              <dd className="font-mono">
                {num(r.expected_sd, 2)} / {num(r.power_target, 2)}
              </dd>
              <dt className="text-slate-500">MDE thô / hiệu dụng</dt>
              <dd className="font-mono">
                {num(r.mde_raw, 3)} / {num(r.mde_effective, 3)} R
              </dd>
              <dt className="text-slate-500">N hiệu dụng cần cho mục tiêu</dt>
              <dd className="font-mono">{num(r.required_effective_n_for_target)}</dd>
            </dl>
            <p className="mt-2 text-[11px] text-slate-500">MDE do API tính; giao diện không tự tính.</p>
          </section>
          <section aria-label="Giải thích được giả thuyết (HYPOTHESIZED)" className="min-w-0 rounded-lg border-2 border-dashed border-amber-600 bg-amber-500/5 p-3">
            <h3 className="flex flex-wrap items-center gap-2 text-sm font-semibold">
              Giải thích được giả thuyết (HYPOTHESIZED) <Mechanism status={r.mechanism_status} />
            </h3>
            <p className="mt-1 break-words text-sm">
              <Txt>{r.hypothesized_explanation ?? "KHÔNG RÕ"}</Txt>
            </p>
            <h4 className="mt-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Lý do kinh tế</h4>
            <p className="break-words text-sm">
              <Txt>{r.economic_rationale ?? "KHÔNG RÕ"}</Txt>
            </p>
            <p className="mt-2 text-[11px] text-slate-500">Phần này chưa được kiểm chứng trực tiếp; không phải kết quả thống kê.</p>
          </section>
        </div>
      ) : (
        <p className="text-sm text-slate-500">
          {r?.status === "legacy" ? (
            "Chương trình V1: chưa có trong file đăng ký có cấu trúc (legacy)."
          ) : (
            <>
              KHÔNG RÕ: không đọc được đăng ký có cấu trúc. <Txt>{r?.reason}</Txt>
            </>
          )}
        </p>
      )}
      {r?.status === "ok" && r.problems && r.problems.length > 0 && (
        <ul role="alert" className="mt-2 list-disc rounded-md border-2 border-dashed border-amber-500 p-2 pl-6 text-xs">
          {r.problems.map((p) => (
            <li key={p}>
              <Txt>{p}</Txt>
            </li>
          ))}
        </ul>
      )}
      {r?.status === "ok" && r.parameter_grid && <p className="mt-2 break-words font-mono text-[11px] text-slate-500">lưới: {JSON.stringify(r.parameter_grid)}</p>}
    </Panel>
  );
}

const key = (h: HypothesisRow) => `${h.programme}-${h.id}`;

function Body({ view }: { view: View }) {
  const firstV2 = view.hypotheses.find((h) => h.programme === "V2");
  const [selected, setSelected] = useState<string | null>(null);
  const current = view.hypotheses.find((h) => key(h) === selected) ?? firstV2 ?? view.hypotheses[0];
  return (
    <div className="space-y-4">
      {view.violations.length > 0 && (
        <p role="alert" className="rounded-xl border-2 border-red-600 bg-red-500/10 p-3 text-sm font-semibold text-red-800 dark:text-red-200">
          VI PHẠM ĐĂNG KÝ TRƯỚC: {view.violations.join(", ")}. Kết quả của các giả thuyết này không được tin.
        </p>
      )}
      <Panel title={`Giả thuyết đã đăng ký (${view.hypotheses.length})`}>
        <p className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <EvidenceBadge cls="DESCRIPTIVE" /> Expected N, MDE và K là số tính từ đăng ký trước kết quả (API tính), không phải kết quả thực nghiệm.
        </p>
        <TableWrap label="Bảng giả thuyết">
          <table className="w-full min-w-[1280px] text-sm">
            <caption className="sr-only">Giả thuyết đã đăng ký, số mẫu kỳ vọng, MDE, K lúc đăng ký và trạng thái cơ chế</caption>
            <thead>
              <tr>
                {[
                  "ID",
                  "Giả thuyết",
                  "Đăng ký trước",
                  "Kết quả (n lần chạy)",
                  "Expected N",
                  "Effective N (est.)",
                  "MDE thô / hiệu dụng",
                  "K lúc đăng ký",
                  "Underpowered",
                  "Biến thể (bỏ)",
                  "Cơ chế",
                  "Chi tiết",
                ].map((c) => (
                  <th key={c} className={th} scope="col">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {view.hypotheses.map((h) => {
                const cells = regCells(h.registration);
                return (
                  <tr key={key(h)} className={`border-t border-slate-300/50 align-top dark:border-slate-700 ${current && key(current) === key(h) ? "bg-sky-500/10" : ""}`}>
                    <th scope="row" className={`${td} text-left font-mono font-semibold`}>
                      {h.id}
                      <span className="block text-[11px] font-normal text-slate-500">{h.programme}</span>
                    </th>
                    <td className={`${td} min-w-[12rem]`} title={h.path}>
                      <Txt>{h.title}</Txt>
                      <p className="text-[11px] text-slate-500">
                        <Txt>{h.registered}</Txt>
                      </p>
                      <p className="break-all font-mono text-[10px] text-slate-500">{h.path}</p>
                      <p className="mt-0.5 text-[11px] text-slate-500">
                        lưới: <Txt>{h.grid?.replaceAll("**", "").replaceAll("`", "") ?? "KHÔNG RÕ"}</Txt>
                      </p>
                    </td>
                    <td className={`${td} min-w-[10rem]`}>
                      <PreReg p={h.preregistration} />
                    </td>
                    <td className={td}>
                      <p>
                        {h.results.runs} lần chạy / {h.results.variants} biến thể
                      </p>
                      <StatusBadge tone={h.results.runs === 0 ? "neutral" : h.results.any_pass ? "warn" : "fail"}>
                        {h.results.runs === 0 ? "UNVALIDATED" : h.results.any_pass ? "UNVALIDATED (có PASS giai đoạn)" : "REJECTED"}
                      </StatusBadge>
                      {h.results.best_pessimistic_min && (
                        <p className="mt-1 text-xs text-slate-500">
                          tốt nhất (bi quan, tối thiểu 2 giai đoạn): <span className="font-mono">{h.results.best_pessimistic_min.variant}</span>{" "}
                          {fmt(h.results.best_pessimistic_min.value, 4)} R
                        </p>
                      )}
                    </td>
                    {cells.map((c, i) => (
                      <td key={i} className={td}>
                        {c}
                      </td>
                    ))}
                    <td className={td}>
                      <button
                        type="button"
                        aria-label={`Xem chi tiết ${h.id}`}
                        aria-pressed={current ? key(current) === key(h) : false}
                        onClick={() => setSelected(key(h))}
                        className="rounded-md border border-slate-400 px-2 py-0.5 text-xs"
                      >
                        Chi tiết
                      </button>
                    </td>
                  </tr>
                );
              })}
              {view.hypotheses.length === 0 && (
                <tr>
                  <td className={td} colSpan={12}>
                    Không đọc được file giả thuyết nào.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </TableWrap>
        <SourceNote source={view.source} />
      </Panel>
      {current && <Detail h={current} />}
      <Panel title={`Dự kiến, chưa đăng ký (${view.planned.length})`}>
        <ul className="grid gap-1 text-sm sm:grid-cols-2">
          {view.planned.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center gap-2">
              <span className="font-mono font-semibold">{p.id}</span>
              <span className="min-w-0 break-words">{p.name}</span>
              <StatusBadge tone="neutral">Batch {p.batch}: CHƯA ĐĂNG KÝ</StatusBadge>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-slate-500">Cần quyết định D-1 trước khi V2 bắt đầu; console không đăng ký hay chạy giả thuyết.</p>
      </Panel>
    </div>
  );
}

export function HypothesesView() {
  const loader = useCallback((s: AbortSignal) => research.hypotheses(s), []);
  const { result, reload } = useLoad(loader);
  return (
    <ResearchShell current="/research/hypotheses" title="Giả thuyết" subtitle="H01..H14: đăng ký trước, kết quả, lưới biến thể. Đăng ký phải có trước kết quả (kiểm bằng git).">
      <div className="flex justify-end">
        <RefreshButton onClick={reload} />
      </div>
      <Gate result={result} what="danh sách giả thuyết">
        {(view) => <Body view={view} />}
      </Gate>
    </ResearchShell>
  );
}
