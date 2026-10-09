"use client";

import { useCallback } from "react";
import { StatusBadge, type Tone } from "@/components/research/StatusBadge";
import { Gate, Panel, RefreshButton, ResearchShell, SourceNote, TableWrap, Txt, td, th, useLoad } from "@/components/research/ui";
import { type HypothesesView as View, type Preregistration, fmt, research } from "@/lib/research";

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

function Body({ view }: { view: View }) {
  return (
    <div className="space-y-4">
      {view.violations.length > 0 && (
        <p role="alert" className="rounded-xl border-2 border-red-600 bg-red-500/10 p-3 text-sm font-semibold text-red-800 dark:text-red-200">
          VI PHẠM ĐĂNG KÝ TRƯỚC: {view.violations.join(", ")}. Kết quả của các giả thuyết này không được tin.
        </p>
      )}
      <Panel title={`Giả thuyết đã đăng ký (${view.hypotheses.length})`}>
        <TableWrap label="Bảng giả thuyết">
          <table className="w-full min-w-[820px] text-sm">
            <thead>
              <tr>
                {["ID", "Chương trình", "Giả thuyết", "Đăng ký trước", "Kết quả (n lần chạy)", "MDE / n dự kiến", "Lưới biến thể"].map((c) => (
                  <th key={c} className={th} scope="col">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {view.hypotheses.map((h) => (
                <tr key={`${h.programme}-${h.id}`} className="border-t border-slate-300/50 align-top dark:border-slate-700">
                  <td className={`${td} font-mono font-semibold`}>{h.id}</td>
                  <td className={td}>{h.programme}</td>
                  <td className={`${td} min-w-[10rem]`} title={h.path}>
                    <Txt>{h.title}</Txt>
                    <p className="text-[11px] text-slate-500">
                      <Txt>{h.registered}</Txt>
                    </p>
                    <p className="break-all font-mono text-[10px] text-slate-500">{h.path}</p>
                  </td>
                  <td className={td}>
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
                  <td className={`${td} text-xs text-slate-500`}>chưa có trong file đăng ký; xem máy tính MDE ở trang Ledger</td>
                  <td className={`${td} text-xs`}>
                    <Txt>{h.grid?.replaceAll("**", "").replaceAll("`", "") ?? "KHÔNG RÕ"}</Txt>
                  </td>
                </tr>
              ))}
              {view.hypotheses.length === 0 && (
                <tr>
                  <td className={td} colSpan={7}>
                    Không đọc được file giả thuyết nào.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </TableWrap>
        <SourceNote source={view.source} />
      </Panel>
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
