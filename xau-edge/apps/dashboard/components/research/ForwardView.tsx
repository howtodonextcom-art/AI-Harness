"use client";

import { useCallback, useState } from "react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { EvidenceBadge } from "@/components/research/EvidenceBadge";
import { LifecycleBadge, ValidationBadge } from "@/components/research/LifecycleBadge";
import { StatusBadge } from "@/components/research/StatusBadge";
import { Gate, Panel, RefreshButton, ResearchShell, SourceNote, TableWrap, Txt, Warning, td, th, useLoad } from "@/components/research/ui";
import { ControlRequestError, newIdempotencyKey, postDemote } from "@/lib/control";
import { type ForwardView as Forward, type ProspectiveView, type Readiness, type StrategiesView, type StrategyRow, evidenceLabel, fmt, research } from "@/lib/research";

type Target = "WATCH" | "DEGRADED" | "DISABLED";

/** Only states strictly below the current one (the server enforces it again and never accepts a raise). */
function targetsFor(state: string): Target[] {
  if (state === "WATCH") return ["DEGRADED", "DISABLED"];
  if (state === "DEGRADED") return ["DISABLED"];
  return ["WATCH", "DEGRADED", "DISABLED"];
}

const field = "w-full rounded-md border border-slate-400 bg-transparent px-2 py-1 text-sm";

function DemoteForm({ strategy, onDone }: { strategy: StrategyRow; onDone: () => void }) {
  const options = targetsFor(strategy.state);
  const [to, setTo] = useState<Target>(options[0]);
  const [reason, setReason] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  async function submit() {
    setConfirming(false);
    setBusy(true);
    setMessage(null);
    try {
      const { event } = await postDemote({ strategy_id: strategy.strategy_id, to, reason: reason.trim(), confirm: "DEMOTE" }, newIdempotencyKey());
      setMessage({ ok: true, text: `Đã hạ ${event.strategy_id}: ${event.from_state} → ${event.to_state}.` });
      setReason("");
      onDone();
    } catch (error) {
      const text = error instanceof ControlRequestError ? `${error.info.code}: ${error.info.message}` : "không gửi được yêu cầu";
      setMessage({ ok: false, text: `Thất bại (${text}). Trạng thái không đổi.` });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title={`Hạ trạng thái: ${strategy.strategy_id}`}>
      <form
        className="space-y-3"
        aria-label="Hạ trạng thái chiến lược"
        onKeyDown={(e) => {
          if (e.key === "Escape" && !busy) {
            setReason("");
            setMessage(null);
          }
        }}
        onSubmit={(e) => {
          e.preventDefault();
          if (reason.trim().length > 0) setConfirming(true);
        }}
      >
        <p className="text-xs text-slate-500">
          Chỉ HẠ bậc (WATCH, DEGRADED, DISABLED); không nâng bậc, không đụng vị thế. Nâng bậc chỉ qua ledger, ADR và CLI.
        </p>
        <label className="block text-sm">
          Hạ xuống
          <select className={field} value={to} onChange={(e) => setTo(e.target.value as Target)}>
            {options.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          Lý do (bắt buộc, tối đa 200 ký tự)
          <textarea className={field} rows={2} maxLength={200} required value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>
        <button
          type="submit"
          disabled={busy || reason.trim().length === 0}
          className="rounded-md border border-amber-600 bg-amber-500/20 px-3 py-1 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-40"
        >
          Hạ trạng thái
        </button>
        {message && (
          <p role="status" className={`text-sm ${message.ok ? "text-green-700 dark:text-green-300" : "text-red-700 dark:text-red-300"}`}>
            {message.text}
          </p>
        )}
      </form>
      {confirming && (
        <ConfirmDialog
          title={`Hạ ${strategy.strategy_id} xuống ${to}`}
          word="DEMOTE"
          tone="danger"
          points={[
            `Trạng thái chuyển từ ${strategy.state} xuống ${to}; không thể nâng lại từ web.`,
            "Không đóng hay sửa vị thế nào; không gửi lệnh.",
            "Thao tác được ghi vào journal cùng lý do của bạn.",
          ]}
          onConfirm={() => void submit()}
          onCancel={() => setConfirming(false)}
        />
      )}
    </Panel>
  );
}

const EXPECTED_ROWS: [string, string, string, number][] = [
  ["Tần suất tín hiệu / tuần", "signals_per_week_expected", "signals_per_week_realised", 2],
  ["Mean net R", "mean_r_expected", "mean_r_realised", 3],
  ["MFE", "mfe_expected", "mfe_realised", 3],
  ["MAE", "mae_expected", "mae_realised", 3],
  ["Spread", "spread_assumed", "spread_observed", 2],
  ["Slippage", "slippage_assumed", "slippage_observed", 2],
];

function dec(v: number | null | undefined, digits = 0): string {
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "KHÔNG RÕ";
}

/** Never states CONSISTENT / INCONSISTENT unless the effective N is known and reaches the requirement. */
function Conclusion({ r }: { r: Readiness | null | undefined }) {
  const c = r?.conclusion;
  if (!c) return <StatusBadge tone="unknown">KHÔNG RÕ (thiếu readiness)</StatusBadge>;
  if (c === "INCONCLUSIVE") return <StatusBadge tone="warn">INCONCLUSIVE: chưa đủ để kết luận</StatusBadge>;
  const eff = r?.effective_n;
  const need = r?.required_effective_n;
  const enough = typeof eff === "number" && typeof need === "number" && eff >= need;
  if ((c === "CONSISTENT" || c === "INCONSISTENT") && enough) {
    return <StatusBadge tone={c === "CONSISTENT" ? "info" : "fail"}>{c}</StatusBadge>;
  }
  return <StatusBadge tone="unknown">KHÔNG RÕ (API báo {c} nhưng N hiệu dụng chưa đạt hoặc thiếu)</StatusBadge>;
}

function ReadinessCard({ fwd }: { fwd: Forward }) {
  const r = fwd.readiness;
  const rows: [string, string, string][] = [
    ["N thô (số lệnh)", dec(r?.raw_n ?? fwd.n_trades), "chỉ mô tả, không dùng để kết luận"],
    ["N hiệu dụng", dec(r?.effective_n, 1), "đã trừ phụ thuộc theo ngày"],
    ["N hiệu dụng cần", dec(r?.required_effective_n), "theo effect mục tiêu và power"],
    ["Số ngày lịch", dec(r?.calendar_days, 0), `tối thiểu ${dec(r?.minimum_calendar_days, 0)}`],
    ["Chế độ thị trường đã thấy", dec(r?.regimes_seen), `cần ${dec(r?.regimes_required)}`],
    ["Power ước tính", typeof r?.power_estimate === "number" ? `${(r.power_estimate * 100).toFixed(0)}%` : "KHÔNG RÕ", "xác suất phát hiện effect mục tiêu"],
  ];
  return (
    <div className="space-y-2" aria-label="Mức sẵn sàng kết luận forward" role="group">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span>Kết luận:</span>
        <Conclusion r={r} />
      </div>
      <TableWrap label="Mức sẵn sàng kết luận forward">
        <table className="w-full min-w-[420px] text-sm">
          <caption className="sr-only">N thô, N hiệu dụng so với N cần, số ngày, chế độ thị trường và power</caption>
          <thead>
            <tr>
              {["Đại lượng", "Giá trị", "Ghi chú"].map((c) => (
                <th key={c} className={th} scope="col">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, value, note]) => (
              <tr key={label} className="border-t border-slate-300/50 dark:border-slate-700">
                <th scope="row" className={`${td} text-left font-normal`}>
                  {label}
                </th>
                <td className={`${td} font-mono`}>{value}</td>
                <td className={`${td} text-xs text-slate-500`}>{note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
      {r?.reasons && r.reasons.length > 0 && (
        <ul className="list-disc pl-5 text-xs">
          {r.reasons.map((x) => (
            <li key={x}>
              <Txt>{x}</Txt>
            </li>
          ))}
        </ul>
      )}
      {typeof fwd.legacy_reference_trades === "number" && (
        <p className="text-[11px] text-slate-500">{fwd.legacy_reference_trades} lệnh: mốc tham chiếu cũ, không đủ để kết luận.</p>
      )}
    </div>
  );
}

function ForwardBody({ fwd, state, k }: { fwd: Forward; state: string; k: string }) {
  const settled = fwd.readiness?.conclusion === "CONSISTENT" || fwd.readiness?.conclusion === "INCONSISTENT";
  const e = fwd.expected_vs_realised;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span>
          n = <strong className="font-mono">{fwd.n_trades}</strong> lệnh · K = <strong className="font-mono">{k}</strong>
        </span>
        <EvidenceBadge cls="EXECUTION" />
        <ValidationBadge label={evidenceLabel(state)} />
      </div>
      <ReadinessCard fwd={fwd} />
      <TableWrap label="So sánh kỳ vọng và thực tế">
        <table className="w-full min-w-[480px] text-sm">
          <thead>
            <tr>
              {["Đại lượng", "Kỳ vọng / giả định", "Thực tế"].map((c) => (
                <th key={c} className={th} scope="col">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {EXPECTED_ROWS.map(([label, a, b, digits]) => (
              <tr key={a} className="border-t border-slate-300/50 dark:border-slate-700">
                <td className={td}>{label}</td>
                <td className={`${td} font-mono`}>{fmt(e[a], digits)}</td>
                <td className={`${td} font-mono`}>{fmt(e[b], digits)}</td>
              </tr>
            ))}
            <tr className="border-t border-slate-300/50 dark:border-slate-700">
              <td className={td}>Độ trễ (ms)</td>
              <td className={`${td} font-mono`}>—</td>
              <td className={`${td} font-mono`}>{fmt(e["latency_ms"], 0)}</td>
            </tr>
          </tbody>
        </table>
      </TableWrap>
      {!settled && <Warning>INCONCLUSIVE: mẫu forward chưa đủ N hiệu dụng, thời gian hoặc chế độ thị trường; các số trên chỉ mô tả, không dùng để đánh giá edge.</Warning>}
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Gợi ý suy giảm (decay)</h3>
        {fwd.decay ? (
          <div className="mt-1 space-y-1 text-sm">
            <p>
              Gợi ý: <strong>{fwd.decay.suggestion}</strong>
              {fwd.decay.max_drawdown_r !== null && <span className="text-slate-500"> · max drawdown {fmt(fwd.decay.max_drawdown_r, 2)} R</span>}
            </p>
            <ul className="list-disc pl-5 text-xs">
              {fwd.decay.reasons.map((r) => (
                <li key={r}>
                  <Txt>{r}</Txt>
                </li>
              ))}
            </ul>
            <p className="text-xs text-slate-500">
              Chỉ là gợi ý: người dùng quyết định có hạ hay không.
              {fwd.decay.advisory_only ? " (advisory_only: mẫu chưa đủ để kết luận, gợi ý chỉ mang tính tham khảo.)" : ""}
            </p>
          </div>
        ) : (
          <p className="mt-1 text-sm text-slate-500">Chưa đánh giá: cần đủ mẫu forward và cận dưới khoảng tin cậy kỳ vọng.</p>
        )}
      </div>
      <SourceNote source={fwd.source} />
    </div>
  );
}

const PROSPECTIVE_LABEL: Record<string, string> = {
  ok: "SEALED BEFORE OUTCOME",
  empty: "NO PROSPECTIVE EVIDENCE YET",
  invalid: "PROVENANCE INVALID",
  unknown: "KHÔNG RÕ",
};

/** The label is derived from `status`; "SEALED BEFORE OUTCOME" is only ever shown when status is ok. */
function ProspectiveCard({ p }: { p: ProspectiveView }) {
  const expected = PROSPECTIVE_LABEL[p.status] ?? "KHÔNG RÕ";
  const label = p.label === expected ? expected : "KHÔNG RÕ";
  const tone = label === "SEALED BEFORE OUTCOME" ? "info" : label === "NO PROSPECTIVE EVIDENCE YET" ? "neutral" : label === "PROVENANCE INVALID" ? "fail" : "unknown";
  return (
    <Panel title="Bằng chứng tiền cứu (prospective)">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {label === "SEALED BEFORE OUTCOME" && <EvidenceBadge cls="PROSPECTIVE" />}
        <StatusBadge tone={tone}>{label}</StatusBadge>
        <span>
          tín hiệu = <strong className="font-mono">{p.signals ?? "KHÔNG RÕ"}</strong> · kết quả = <strong className="font-mono">{p.outcomes ?? "KHÔNG RÕ"}</strong>
        </span>
      </div>
      {p.problems && p.problems.length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-xs [overflow-wrap:anywhere]">
          {p.problems.map((x) => (
            <li key={x}>
              <Txt>{x}</Txt>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-xs text-slate-500">Nhãn chỉ là niêm phong trước kết quả khi chuỗi băm của sổ tiền cứu được xác minh.</p>
      <SourceNote source={p.source} />
    </Panel>
  );
}

function Selected({ strategy, k, onDone }: { strategy: StrategyRow; k: string; onDone: () => void }) {
  const loader = useCallback((s: AbortSignal) => research.forward(strategy.strategy_id, s), [strategy.strategy_id]);
  const { result } = useLoad(loader);
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title={`Expected vs realised: ${strategy.strategy_id}`}>
        <p className="mb-2 flex items-center gap-2 text-sm">
          Vòng đời: <LifecycleBadge state={strategy.state} />
        </p>
        <Gate result={result} what={`mẫu forward của ${strategy.strategy_id}`} dataAt={(f) => f.updated_at}>
          {(f) => <ForwardBody fwd={f} state={strategy.state} k={k} />}
        </Gate>
      </Panel>
      {strategy.web_demotable ? (
        <DemoteForm key={strategy.strategy_id} strategy={strategy} onDone={onDone} />
      ) : (
        <Panel title="Hạ trạng thái">
          <p className="text-sm text-slate-500">
            Chiến lược này không thể hạ từ web (trạng thái {strategy.state}). Từ web chỉ hạ được PAPER, DEMO, VALIDATED, FUNDED, WATCH hoặc DEGRADED.
          </p>
        </Panel>
      )}
    </div>
  );
}

function StrategiesBody({ view, k, reload }: { view: StrategiesView; k: string; reload: () => void }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = view.strategies.find((s) => s.strategy_id === selectedId) ?? null;
  return (
    <div className="space-y-4">
      <Panel title={`Vòng đời chiến lược (${view.strategies.length})`}>
        <p className="mb-2 text-xs text-slate-500">
          <Txt>{view.web_rule}</Txt>
        </p>
        <div className="max-h-80 overflow-y-auto">
          <TableWrap label="Bảng vòng đời chiến lược">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr>
                  {["Chiến lược", "Trạng thái", "Nhãn", "Lịch sử", "Từ web", "Forward"].map((c) => (
                    <th key={c} className={th} scope="col">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {view.strategies.map((s) => (
                  <tr key={s.strategy_id} className={`border-t border-slate-300/50 dark:border-slate-700 ${selectedId === s.strategy_id ? "bg-sky-500/10" : ""}`}>
                    <td className={`${td} font-mono`}>{s.strategy_id}</td>
                    <td className={td}>
                      <LifecycleBadge state={s.state} />
                    </td>
                    <td className={td}>
                      <ValidationBadge label={evidenceLabel(s.state)} />
                    </td>
                    <td className={`${td} text-xs`}>{s.history.length === 0 ? "—" : `${s.history.length} sự kiện, gần nhất ${s.history[s.history.length - 1].at.slice(0, 10)}`}</td>
                    <td className={`${td} text-xs`}>{s.web_demotable ? "có thể hạ" : "không"}</td>
                    <td className={td}>
                      <button
                        type="button"
                        aria-label={`Chọn ${s.strategy_id}`}
                        aria-pressed={selectedId === s.strategy_id}
                        onClick={() => setSelectedId(s.strategy_id)}
                        className="rounded-md border border-slate-400 px-2 py-0.5 text-xs"
                      >
                        Chọn
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        </div>
        <SourceNote source={view.source} />
      </Panel>
      {selected ? <Selected key={selected.strategy_id} strategy={selected} k={k} onDone={reload} /> : <p className="text-sm text-slate-500">Chọn một chiến lược để xem forward và (nếu được phép) hạ trạng thái.</p>}
    </div>
  );
}

export function ForwardView() {
  const loader = useCallback((s: AbortSignal) => research.strategies(s), []);
  const overviewLoader = useCallback((s: AbortSignal) => research.overview(s), []);
  const { result, reload } = useLoad(loader);
  const overview = useLoad(overviewLoader).result;
  const prospectiveLoader = useCallback((s: AbortSignal) => research.prospective(s), []);
  const prospective = useLoad(prospectiveLoader);
  const k = overview?.kind === "ok" && overview.data.v1.k != null ? String(overview.data.v1.k) : overview === null ? "…" : "KHÔNG RÕ";
  return (
    <ResearchShell current="/research/forward" title="Forward và vòng đời" subtitle="Vòng đời chiến lược, kỳ vọng so với thực tế, gợi ý suy giảm. Thao tác duy nhất của console: hạ trạng thái.">
      <div className="flex justify-end">
        <RefreshButton onClick={reload} />
      </div>
      <Gate result={prospective.result} what="sổ bằng chứng tiền cứu">
        {(p) => <ProspectiveCard p={p} />}
      </Gate>
      <Gate result={result} what="vòng đời chiến lược">
        {(view) => <StrategiesBody view={view} k={k} reload={reload} />}
      </Gate>
    </ResearchShell>
  );
}
