"use client";

import { useCallback } from "react";
import { StatusBadge } from "@/components/research/StatusBadge";
import { Bar, Gate, Panel, RefreshButton, ResearchShell, SourceNote, Txt, Warning, useLoad } from "@/components/research/ui";
import { type Overview, research } from "@/lib/research";

function Counter({ label, used, cap, tone }: { label: string; used: number | null | undefined; cap: number | null | undefined; tone?: "fail" }) {
  const known = typeof used === "number" && typeof cap === "number";
  return (
    <div>
      <div className="flex justify-between gap-2 text-sm">
        <span>{label}</span>
        <strong className="font-mono">{known ? `${used} / ${cap}` : "KHÔNG RÕ"}</strong>
      </div>
      {known ? <Bar value={used} max={cap} label={label} tone={tone ?? "info"} /> : <Warning>Không đọc được {label}.</Warning>}
    </div>
  );
}

function Programme({ name, data }: { name: string; data: Overview }) {
  const v = name === "V1" ? data.v1 : data.v2;
  const k = name === "V1" ? (data.v1.k ?? null) : (data.v2.k_declared ?? null);
  const kCap = v.k_cap ?? null;
  const hyp = name === "V1" ? data.v1.hypotheses_used : data.v2.hypotheses_used;
  const hypCap = v.hypotheses_budget ?? null;
  const v2Idle = name === "V2" && !data.v2.started;
  return (
    <Panel title={`Chương trình ${name}`}>
      {v.status !== "ok" ? (
        <Warning>
          KHÔNG RÕ: <Txt>{"reason" in v ? v.reason : "không đọc được nguồn"}</Txt>
        </Warning>
      ) : v2Idle ? (
        <div className="space-y-2 text-sm">
          <StatusBadge tone="neutral">CHƯA BẮT ĐẦU</StatusBadge>
          <p>
            <Txt>{data.v2.message}</Txt>
          </p>
          <p className="font-mono text-xs">
            K = 0 / {data.v2.k_cap ?? "?"} · giả thuyết 0 / {data.v2.hypotheses_budget ?? "?"}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <Counter label="K đã dùng / trần" used={k} cap={kCap} tone={k !== null && kCap !== null && k >= kCap ? "fail" : undefined} />
          <Counter label="Ngân sách giả thuyết" used={hyp} cap={hypCap} tone={hyp != null && hypCap != null && hyp >= hypCap ? "fail" : undefined} />
          {name === "V1" && data.v1.alpha != null && (
            <p className="text-xs text-slate-500">
              alpha hiệu chỉnh = 0,05 / K = <span className="font-mono">{data.v1.alpha}</span> · {data.v1.runs} lần chạy ghi trong ledger
              {data.v1.malformed_rows ? ` · ${data.v1.malformed_rows} dòng hỏng` : ""}
            </p>
          )}
        </div>
      )}
      <SourceNote source={v.source} />
    </Panel>
  );
}

function Content({ data }: { data: Overview }) {
  return (
    <div className="space-y-4">
      {data.banner ? (
        <div role="status" aria-label="Kết luận chương trình" className="rounded-xl border-2 border-red-600 bg-red-500/10 p-4 text-lg font-semibold text-red-800 dark:text-red-200">
          <Txt>{data.banner}</Txt>
          <p className="mt-1 text-sm font-normal">Chưa chiến lược nào ở trạng thái VALIDATED hay FUNDED; bot sẽ WAIT.</p>
        </div>
      ) : (
        <Panel title="Chiến lược đã kiểm định">
          <p className="text-sm">{data.validated_strategies.join(", ") || "không có"}</p>
        </Panel>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <Panel title="Kết luận chương trình trước">
          {data.verdict.status === "ok" ? (
            <p className="text-xl font-semibold">
              <Txt>{data.verdict.label}</Txt>
            </p>
          ) : (
            <Warning>
              KHÔNG RÕ: <Txt>{data.verdict.reason}</Txt>
            </Warning>
          )}
          <p className="mt-1 text-xs text-slate-500">Nhãn bằng chứng: UNVALIDATED (không có ứng viên qua cả hai giai đoạn).</p>
          <SourceNote source={data.verdict.source} />
        </Panel>
        <Programme name="V1" data={data} />
        <Programme name="V2" data={data} />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Panel title="Điều kiện dừng đã đạt">
          {data.stop_conditions_reached.length === 0 ? (
            <p className="text-sm">Chưa đạt điều kiện dừng nào (theo các nguồn đọc được).</p>
          ) : (
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {data.stop_conditions_reached.map((s) => (
                <li key={s}>
                  <Txt>{s}</Txt>
                </li>
              ))}
            </ul>
          )}
          <SourceNote source={[data.v1.source, data.v2.source]} />
        </Panel>
        <Panel title="Quyết định chủ dự án đang chờ (D-1..D-5)">
          {data.decisions.length === 0 ? (
            <Warning>KHÔNG RÕ: không đọc được danh sách quyết định.</Warning>
          ) : (
            <ul className="space-y-2 text-sm">
              {data.decisions.map((d) => (
                <li key={d.id} className="flex flex-wrap items-start gap-2">
                  <strong className="font-mono">{d.id}</strong>
                  <StatusBadge tone={d.state === "pending" ? "warn" : "ok"}>{d.state === "pending" ? "ĐANG CHỜ" : d.state.toUpperCase()}</StatusBadge>
                  <span className="min-w-0 flex-1 break-words">
                    <Txt>{d.text.replaceAll("**", "")}</Txt> <span className="text-slate-500">(đề xuất: {d.recommended})</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
          <SourceNote source={data.sources.at(-1)} />
        </Panel>
      </div>
      <SourceNote source={data.sources} label="các nguồn của trang" />
    </div>
  );
}

export function OverviewView() {
  const loader = useCallback((s: AbortSignal) => research.overview(s), []);
  const { result, reload } = useLoad(loader);
  return (
    <ResearchShell current="/research" title="Research Console: chúng ta đang ở đâu?" subtitle="Trạng thái chương trình nghiên cứu edge, K, ngân sách và quyết định đang chờ.">
      <div className="flex justify-end">
        <RefreshButton onClick={reload} />
      </div>
      <Gate result={result} what="tổng quan chương trình" dataAt={(d) => d.generated_at} partial={(d) => <Content data={d} />}>
        {(data) => <Content data={data} />}
      </Gate>
    </ResearchShell>
  );
}
