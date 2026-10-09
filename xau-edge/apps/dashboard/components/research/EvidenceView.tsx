"use client";

import { useCallback, useState } from "react";
import { EvidenceBadge } from "@/components/research/EvidenceBadge";
import { StatusBadge, type Tone } from "@/components/research/StatusBadge";
import { Gate, Panel, RefreshButton, ResearchShell, SourceNote, TableWrap, Txt, td, th, useLoad } from "@/components/research/ui";
import { type GatesView, type Stage1Variant, type Stage1View, fmt, pct, research, shortId } from "@/lib/research";

/** A number from the API: "KHÔNG RÕ" when absent, never an implicit zero. */
function n(v: unknown, digits = 3): string {
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "KHÔNG RÕ";
}

function ci(v: number[] | null | undefined): string {
  return Array.isArray(v) && v.length === 2 && v.every((x) => Number.isFinite(x)) ? `[${v[0].toFixed(3)}; ${v[1].toFixed(3)}]` : "KHÔNG RÕ";
}

const STATUS_TONE: Record<string, Tone> = {
  DEPENDENCE_STABLE: "neutral",
  INTRABAR_ROBUST: "neutral",
  UNKNOWN: "unknown",
};

function StatusText({ value }: { value: string | null | undefined }) {
  if (!value) return <StatusBadge tone="unknown">KHÔNG RÕ</StatusBadge>;
  return <StatusBadge tone={STATUS_TONE[value] ?? "warn"}>{value === "UNKNOWN" ? "KHÔNG RÕ (UNKNOWN)" : value}</StatusBadge>;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="min-w-0 rounded-lg border border-slate-300/60 p-3 dark:border-slate-700">
      <h3 className="mb-1 text-sm font-semibold">{title}</h3>
      {children}
    </section>
  );
}

function Dl({ rows }: { rows: [string, React.ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-0.5 text-xs">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-slate-500">{k}</dt>
          <dd className="text-right font-mono">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function Basis({ v }: { v: Stage1Variant }) {
  return (
    <p className="mb-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
      <EvidenceBadge cls={v.evidence_class} />
      <span>
        n = <span className="font-mono">{n(v.n_events, 0)}</span> (hiệu dụng <span className="font-mono">{n(v.n_effective, 0)}</span>) · K = <span className="font-mono">{n(v.k, 0)}</span>
      </span>
    </p>
  );
}

function Labels({ v }: { v: Stage1Variant }) {
  const labels = v.labels;
  return (
    <Section title="Quyền gắn nhãn (labels)">
      {labels ? (
        <TableWrap label="Quyền gắn nhãn của biến thể">
          <table className="w-full min-w-[420px] text-xs">
            <caption className="sr-only">Mỗi nhãn có được phép hiển thị hay không, kèm lý do từ chối</caption>
            <thead>
              <tr>
                {["Nhãn", "Quyết định", "Lý do"].map((c) => (
                  <th key={c} className={th} scope="col">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(labels).map(([name, d]) => (
                <tr key={name} className="border-t border-slate-300/50 align-top dark:border-slate-700">
                  <th scope="row" className={`${td} text-left font-mono`}>
                    {name}
                  </th>
                  <td className={td}>
                    {d.allowed ? <StatusBadge tone="info">ĐƯỢC PHÉP GẮN NHÃN</StatusBadge> : <StatusBadge tone="fail">TỪ CHỐI</StatusBadge>}
                  </td>
                  <td className={td}>
                    {d.reasons.length === 0 ? (
                      d.allowed ? "—" : "KHÔNG RÕ (API không nêu lý do)"
                    ) : (
                      <ul className="list-disc pl-4">
                        {d.reasons.map((r) => (
                          <li key={r}>
                            <Txt>{r}</Txt>
                          </li>
                        ))}
                      </ul>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      ) : (
        <p className="text-sm">KHÔNG RÕ: API không trả quyền gắn nhãn.</p>
      )}
    </Section>
  );
}

function VariantDetail({ v }: { v: Stage1Variant }) {
  if (v.status === "TOO_FEW_EVENTS") {
    return (
      <Panel title={`Chi tiết ${v.variant}`}>
        <StatusBadge tone="warn">TOO_FEW_EVENTS</StatusBadge> <span className="text-sm">Quá ít sự kiện để phân tích; không có số liệu.</span>
      </Panel>
    );
  }
  const a = v.attribution;
  const p = v.placebo;
  return (
    <Panel title={`Chi tiết ${v.variant}`}>
      <div className="grid gap-3 lg:grid-cols-2">
        <Section title="Edge Attribution">
          <Basis v={v} />
          {a ? (
            <>
              <Dl
                rows={[
                  ["mean net R quan sát", n(a.observed_mean_r)],
                  ["direction edge", n(a.direction_edge)],
                  ["timing edge", n(a.timing_edge)],
                  ["drift exposure", n(a.drift_exposure)],
                ]}
              />
              <TableWrap label="Đối chứng (counterfactuals)">
                <table className="mt-2 w-full min-w-[420px] text-xs">
                  <caption className="sr-only">Các đối chứng của phân rã edge: trung bình, chênh lệch, khoảng tin cậy</caption>
                  <thead>
                    <tr>
                      {["Đối chứng", "mean R", "chênh R", "CI", "effect size"].map((c) => (
                        <th key={c} className={th} scope="col">
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {a.counterfactuals.map((c) => (
                      <tr key={c.name} className="border-t border-slate-300/50 dark:border-slate-700">
                        <th scope="row" className={`${td} text-left font-normal`}>
                          <Txt>{c.name}</Txt>
                        </th>
                        <td className={`${td} font-mono`}>{n(c.mean_r)}</td>
                        <td className={`${td} font-mono`}>{n(c.incremental_r)}</td>
                        <td className={`${td} font-mono`}>{ci([c.ci_low as number, c.ci_high as number])}</td>
                        <td className={`${td} font-mono`}>{n(c.effect_size)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
              <p className="mt-1 text-[11px] text-slate-500">
                <Txt>{a.note ?? "mô tả, không phải khẳng định nhân quả"}</Txt>
              </p>
            </>
          ) : (
            <p className="text-sm">KHÔNG RÕ: chưa có phân rã edge.</p>
          )}
        </Section>
        <Section title="Placebo Comparison">
          <Basis v={v} />
          {p ? (
            <>
              <Dl
                rows={[
                  ["thật (mean net R)", n(p.real)],
                  ["placebo trung vị", n(p.median)],
                  ["placebo p95", n(p.p95)],
                  ["placebo p99", n(p.p99)],
                  ["phân vị thực nghiệm", n(p.empirical_percentile)],
                  ["số lần rút", n(p.draws, 0)],
                ]}
              />
              <p className="mt-1 text-[11px] text-slate-500">
                <Txt>{p.kind ?? "KHÔNG RÕ"}</Txt>
              </p>
            </>
          ) : (
            <p className="text-sm">KHÔNG RÕ: chưa có so sánh placebo.</p>
          )}
        </Section>
        <Section title="Dependence Sensitivity">
          <Basis v={v} />
          <Dl
            rows={[
              ["trạng thái", <StatusText key="s" value={v.dependence_status} />],
              ["n thô", n(v.n_events, 0)],
              ["n hiệu dụng", n(v.n_effective, 0)],
              ["số ngày khác nhau", n(v.unique_days, 0)],
              ["CI95 net base", ci(v.ci95_net_base)],
            ]}
          />
          <p className="mt-1 text-[11px] text-slate-500">CI theo khối 1/2/5 ngày: chưa có trong API.</p>
        </Section>
        <Section title="Power">
          <Basis v={v} />
          <Dl
            rows={[
              ["K", n(v.k, 0)],
              ["alpha Bonferroni (0.05/K)", n(v.alpha_bonferroni, 4)],
              ["MDE hiệu dụng", `${n(v.mde_effective)} R`],
              ["đủ công suất?", v.adequately_powered === null || v.adequately_powered === undefined ? "KHÔNG RÕ" : v.adequately_powered ? "có (theo MDE)" : "KHÔNG"],
            ]}
          />
        </Section>
        <Section title="Intrabar Ambiguity">
          <Basis v={v} />
          <Dl rows={[["trạng thái", <StatusText key="s" value={v.intrabar_status} />]]} />
        </Section>
        <Section title="Structural Stability (era)">
          <Basis v={v} />
          <Dl rows={[["trạng thái", <StatusText key="s" value={v.era_status} />]]} />
          {v.by_year && typeof v.by_year === "object" ? (
            <TableWrap label="Kết quả theo năm">
              <table className="mt-2 w-full min-w-[260px] text-xs">
                <caption className="sr-only">Số sự kiện và mean net R theo năm</caption>
                <thead>
                  <tr>
                    {["Năm", "n", "mean net R"].map((c) => (
                      <th key={c} className={th} scope="col">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(v.by_year as Record<string, { n?: number; mean_net_base_r?: number }>).map(([year, row]) => (
                    <tr key={year} className="border-t border-slate-300/50 dark:border-slate-700">
                      <th scope="row" className={`${td} text-left font-mono font-normal`}>
                        {year}
                      </th>
                      <td className={`${td} font-mono`}>{n(row?.n, 0)}</td>
                      <td className={`${td} font-mono`}>{n(row?.mean_net_base_r)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
          ) : (
            <p className="mt-1 text-xs">KHÔNG RÕ: chưa có kết quả theo năm.</p>
          )}
        </Section>
        <Section title="Cost Distribution">
          <p className="text-sm">
            <StatusBadge tone="unknown">CHƯA CÓ: cần dữ liệu demo</StatusBadge>
          </p>
          <p className="mt-1 text-xs text-slate-500">Chưa có nguồn đo phân phối chi phí thật (spread, slippage, swap); không suy ra từ giả định.</p>
        </Section>
        <Section title="Provenance">
          <Dl
            rows={[
              ["experiment_id", <span key="e" className="break-all" title={v.experiment_id ?? ""}>{shortId(v.experiment_id, 12)}</span>],
              ["code commit", <span key="c" className="break-all" title={v.code_commit_sha ?? ""}>{v.code_commit_sha ? v.code_commit_sha.slice(0, 12) : "KHÔNG RÕ"}</span>],
              ["manifest_verified", v.manifest_verified === true ? "có" : v.manifest_verified === false ? "KHÔNG" : "KHÔNG RÕ"],
              ["provenance", v.provenance ?? "KHÔNG RÕ"],
              ["ghi lúc", v.recorded_at ?? "KHÔNG RÕ"],
            ]}
          />
          <p className="mt-2 text-xs text-slate-500">Dataset ids</p>
          <ul className="text-xs">
            {v.dataset_ids && Object.keys(v.dataset_ids).length > 0 ? (
              Object.entries(v.dataset_ids).map(([tf, id]) => (
                <li key={tf} className="break-all font-mono" title={id}>
                  {tf}: {id}
                </li>
              ))
            ) : (
              <li>KHÔNG RÕ</li>
            )}
          </ul>
        </Section>
      </div>
      <div className="mt-3">
        <Labels v={v} />
      </div>
    </Panel>
  );
}

function Detail({ variant }: { variant: string }) {
  const loader = useCallback((s: AbortSignal) => research.stage1Variant(variant, s), [variant]);
  const { result } = useLoad(loader);
  return (
    <Gate result={result} what={`chi tiết Stage 1 của ${variant}`}>
      {(d) => <VariantDetail v={d.variant} />}
    </Gate>
  );
}

function Table({ view, degraded }: { view: Stage1View; degraded: boolean }) {
  const [selected, setSelected] = useState<string | null>(null);
  const current = selected ?? view.variants.find((v) => v.status !== "TOO_FEW_EVENTS")?.variant ?? view.variants[0]?.variant ?? null;
  return (
    <div className="space-y-4">
      {!degraded && view.survivors.length === 0 && view.variants.length > 0 && (
        <div role="status" className="rounded-xl border-2 border-slate-500 bg-slate-500/10 p-3 text-sm font-semibold">
          Không có biến thể nào sống sót Stage 1 (K = {n(view.k, 0)}, {view.variants.length} biến thể). Stage 1 chỉ là sàng lọc; Test-H và holdout chưa được dùng.
        </div>
      )}
      {!degraded && view.survivors.length > 0 && (
        <div role="status" className="rounded-xl border-2 border-dashed border-amber-600 bg-amber-500/10 p-3 text-sm">
          {view.survivors.length} biến thể qua sàng lọc Stage 1: <span className="font-mono">{view.survivors.join(", ")}</span>. Đây chỉ là sàng lọc (SCREENING), chưa phải bằng chứng.
        </div>
      )}
      <Panel title={`Stage 1 trên Development-2 (${view.variants.length} biến thể)`}>
        <p className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <EvidenceBadge cls={view.evidence_class ?? "SCREENING"} /> mean net R bên dưới là kết quả sàng lọc: không có cột đạt/không đạt kiểu PASS. K = {n(view.k, 0)} cho cả họ.
        </p>
        <TableWrap label="Bảng biến thể Stage 1">
          <table className="w-full min-w-[1300px] text-xs [&_td]:!text-xs [&_th]:!text-[11px]">
            <caption className="sr-only">Biến thể Stage 1: lớp bằng chứng, n thô, n hiệu dụng, K, mean R gộp, CI95, p một phía, MDE, độ phụ thuộc, provenance</caption>
            <thead>
              <tr>
                {[
                  "Biến thể",
                  "Lớp bằng chứng",
                  "n thô",
                  "n hiệu dụng",
                  "Ngày duy nhất",
                  "K",
                  "mean gross mid R",
                  "mean net base R",
                  "mean net pess R",
                  "CI95 net base",
                  "p một phía (alpha)",
                  "MDE hiệu dụng",
                  "Đủ công suất",
                  "Phụ thuộc",
                  "Sống sót Stage 1",
                  "Provenance",
                  "Chi tiết",
                ].map((c) => (
                  <th key={c} className={th} scope="col">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {view.variants.map((v) => (
                <tr key={v.variant} className={`border-t border-slate-300/50 align-top dark:border-slate-700 ${current === v.variant ? "bg-sky-500/10" : ""}`}>
                  <th scope="row" className={`${td} text-left font-mono font-semibold`}>
                    {v.variant}
                  </th>
                  {v.status === "TOO_FEW_EVENTS" ? (
                    <td className={td} colSpan={14}>
                      <StatusBadge tone="warn">TOO_FEW_EVENTS</StatusBadge> quá ít sự kiện, không có số liệu
                    </td>
                  ) : (
                    <>
                      <td className={td}>
                        <EvidenceBadge cls={v.evidence_class} />
                      </td>
                      <td className={`${td} font-mono`}>{n(v.n_events, 0)}</td>
                      <td className={`${td} font-mono`}>{n(v.n_effective, 0)}</td>
                      <td className={`${td} font-mono`}>{n(v.unique_days, 0)}</td>
                      <td className={`${td} font-mono`}>{n(v.k, 0)}</td>
                      <td className={`${td} font-mono`}>{n(v.mean_gross_mid_r)}</td>
                      <td className={`${td} font-mono`}>{n(v.mean_net_base_r)}</td>
                      <td className={`${td} font-mono`}>{n(v.mean_net_pess_r)}</td>
                      <td className={`${td} font-mono`}>{ci(v.ci95_net_base)}</td>
                      <td className={`${td} font-mono`}>
                        {n(v.p_value_one_sided, 4)}
                        <span className="block text-[11px] text-slate-500">α = {n(v.alpha_bonferroni, 4)}</span>
                      </td>
                      <td className={`${td} font-mono`}>{n(v.mde_effective)} R</td>
                      <td className={td}>
                        {v.adequately_powered === null || v.adequately_powered === undefined ? (
                          <StatusBadge tone="unknown">KHÔNG RÕ</StatusBadge>
                        ) : (
                          <StatusBadge tone="neutral">{v.adequately_powered ? "đủ (theo MDE)" : "KHÔNG đủ"}</StatusBadge>
                        )}
                      </td>
                      <td className={td}>
                        <StatusText value={v.dependence_status} />
                      </td>
                      <td className={td}>
                        {v.survivor === null || v.survivor === undefined ? (
                          <StatusBadge tone="unknown">KHÔNG RÕ</StatusBadge>
                        ) : v.survivor ? (
                          <StatusBadge tone="warn">SỐNG SÓT (chỉ sàng lọc)</StatusBadge>
                        ) : (
                          <StatusBadge tone="neutral">không sống sót</StatusBadge>
                        )}
                      </td>
                      <td className={td}>
                        {v.manifest_verified ? <StatusBadge tone="neutral">REPRODUCIBLE (manifest khớp)</StatusBadge> : <StatusBadge tone="unknown">KHÔNG RÕ</StatusBadge>}
                      </td>
                    </>
                  )}
                  <td className={td}>
                    <button
                      type="button"
                      aria-label={`Xem chi tiết ${v.variant}`}
                      aria-pressed={current === v.variant}
                      onClick={() => setSelected(v.variant)}
                      className="rounded-md border border-slate-400 px-2 py-0.5 text-xs"
                    >
                      Chi tiết
                    </button>
                  </td>
                </tr>
              ))}
              {view.variants.length === 0 && (
                <tr>
                  <td className={td} colSpan={17}>
                    CHƯA CÓ kết quả Stage 1.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </TableWrap>
        {view.problems && view.problems.length > 0 && (
          <ul className="mt-2 list-disc pl-5 text-xs">
            {view.problems.map((p) => (
              <li key={p}>
                <Txt>{p}</Txt>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-2 text-xs text-slate-500">
          <Txt>{view.note ?? ""}</Txt>
        </p>
        <SourceNote source={view.source} />
      </Panel>
      {current && <Detail key={current} variant={current} />}
    </div>
  );
}

const CLASS_TONE: Record<string, Tone> = {
  SUPPORTED: "info",
  CONSERVATIVE: "warn",
  "OVER-STRICT": "warn",
  "UNDER-STRICT": "fail",
  UNVERIFIED: "unknown",
};

const EFFECTS = ["0.00R", "0.05R", "0.10R", "0.20R"];
const MODELS: [string, string][] = [
  ["independent", "độc lập"],
  ["clustered", "gom cụm"],
  ["overlapping", "chồng lấn"],
];

function GatesBody({ g }: { g: GatesView }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="Hiệu chuẩn cổng robustness (chiến lược trồng sẵn)">
        <p className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <EvidenceBadge cls={g.evidence_class ?? "DESCRIPTIVE"} /> Tỉ lệ qua cổng theo hiệu ứng thật gắn vào dữ liệu mô phỏng (seed {n(g.seed, 0)}); 0.00R là chiến lược không có edge.
        </p>
        <TableWrap label="Tỉ lệ qua cổng theo hiệu ứng">
          <table className="w-full min-w-[560px] text-sm">
            <caption className="sr-only">Tỉ lệ qua mỗi cổng ứng với hiệu ứng 0.00R, 0.05R, 0.10R, 0.20R và phân loại</caption>
            <thead>
              <tr>
                <th className={th} scope="col">
                  Cổng
                </th>
                {EFFECTS.map((e) => (
                  <th key={e} className={th} scope="col">
                    qua @ {e}
                  </th>
                ))}
                <th className={th} scope="col">
                  Phân loại
                </th>
              </tr>
            </thead>
            <tbody>
              {g.gates.map((x) => (
                <tr key={x.gate} className="border-t border-slate-300/50 align-top dark:border-slate-700">
                  <th scope="row" className={`${td} text-left font-semibold`}>
                    {x.gate}
                  </th>
                  {EFFECTS.map((e) => (
                    <td key={e} className={`${td} font-mono`}>
                      {pct(x.pass_rate?.[e])}
                    </td>
                  ))}
                  <td className={td}>
                    <StatusBadge tone={CLASS_TONE[x.classification] ?? "unknown"}>{CLASS_TONE[x.classification] ? x.classification : `KHÔNG RÕ (${x.classification})`}</StatusBadge>
                    <p className="mt-0.5 text-xs text-slate-500">
                      <Txt>{x.reason}</Txt>
                    </p>
                    {/overfit|no-edge|không có edge/i.test(x.reason) && (
                      <p className="mt-0.5 text-xs font-semibold">Cổng này không phải bộ lọc overfitting: nó cho qua cả chiến lược không có edge.</p>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </Panel>
      <Panel title="Công suất của phép thử chính">
        <p className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <EvidenceBadge cls={g.evidence_class ?? "DESCRIPTIVE"} /> Xác suất phát hiện hiệu ứng thật, theo ba mô hình phụ thuộc.
        </p>
        <TableWrap label="Công suất theo hiệu ứng và mô hình phụ thuộc">
          <table className="w-full min-w-[420px] text-sm">
            <caption className="sr-only">Công suất ứng với từng hiệu ứng giả định, theo mô hình độc lập, gom cụm và chồng lấn</caption>
            <thead>
              <tr>
                <th className={th} scope="col">
                  Hiệu ứng
                </th>
                {MODELS.map(([, label]) => (
                  <th key={label} className={th} scope="col">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(g.power).map(([effect, row]) => (
                <tr key={effect} className="border-t border-slate-300/50 dark:border-slate-700">
                  <th scope="row" className={`${td} text-left font-mono font-semibold`}>
                    {effect}
                  </th>
                  {MODELS.map(([m]) => (
                    <td key={m} className={`${td} font-mono`}>
                      {pct(row?.[m])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
        <h3 className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Giả định (n, K, sd)</h3>
        <ul className="mt-1 space-y-0.5 text-xs">
          {Object.entries(g.assumptions).map(([k, v]) => (
            <li key={k} className="break-words">
              <span className="font-mono">{k}</span>: <Txt>{typeof v === "string" ? v : fmt(v)}</Txt>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-slate-500">
          <Txt>{g.note}</Txt>
        </p>
      </Panel>
    </div>
  );
}

export function EvidenceView() {
  const sLoader = useCallback((s: AbortSignal) => research.stage1(s), []);
  const gLoader = useCallback((s: AbortSignal) => research.gates(s), []);
  const s1 = useLoad(sLoader);
  const gates = useLoad(gLoader);
  return (
    <ResearchShell current="/research/evidence" title="Bằng chứng" subtitle="Stage 1 (SCREENING) của Batch A trên Development-2, quyền gắn nhãn, hiệu chuẩn cổng và công suất. Chỉ đọc.">
      <div className="flex justify-end">
        <RefreshButton
          onClick={() => {
            s1.reload();
            gates.reload();
          }}
        />
      </div>
      <Gate result={s1.result} what="kết quả Stage 1" partial={(v) => (Array.isArray(v.variants) ? <Table view={{ ...v, survivors: v.survivors ?? [] }} degraded /> : null)}>
        {(view) =>
          view.status === "empty" ? (
            <p role="status" className="rounded-xl border-2 border-dashed border-slate-500 p-3 text-sm">
              CHƯA CÓ kết quả Stage 1 (chưa chạy Batch A). Đây không phải kết luận rằng không có edge.
            </p>
          ) : (
            <Table view={view} degraded={false} />
          )
        }
      </Gate>
      <h2 className="text-lg font-semibold">Hiệu chuẩn cổng &amp; công suất</h2>
      <Gate result={gates.result} what="hiệu chuẩn cổng và công suất">
        {(g) => <GatesBody g={g} />}
      </Gate>
    </ResearchShell>
  );
}
