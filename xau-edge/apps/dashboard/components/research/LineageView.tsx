"use client";

import { useCallback, useState } from "react";
import { StatusBadge } from "@/components/research/StatusBadge";
import { Gate, Panel, RefreshButton, ResearchShell, SourceNote, Txt, useLoad } from "@/components/research/ui";
import { type LineageNode, type LineageView as View, research, shortId } from "@/lib/research";

function Field({ k, v, mono = true }: { k: string; v: string | null | undefined; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] text-slate-500">{k}</dt>
      <dd className={`break-words text-xs [overflow-wrap:anywhere] ${mono ? "font-mono" : ""}`}>{v ? <Txt>{v}</Txt> : <span className="text-amber-800 dark:text-amber-300">KHÔNG RÕ</span>}</dd>
    </div>
  );
}

function Hash({ k, v }: { k: string; v: string | null | undefined }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] text-slate-500">{k}</dt>
      <dd className="font-mono text-xs [overflow-wrap:anywhere]" title={v ?? undefined}>
        {v ? `${v.slice(0, 16)}${v.length > 16 ? "…" : ""}` : <span className="text-amber-800 dark:text-amber-300">KHÔNG RÕ</span>}
      </dd>
    </div>
  );
}

function Node({ node, onJump }: { node: LineageNode; onJump: (id: string) => void }) {
  const detail = node.detail && Object.keys(node.detail).length > 0 ? JSON.stringify(node.detail) : null;
  return (
    <li id={`node-${node.id}`} className="min-w-0 scroll-mt-4 rounded-lg border border-slate-300/60 p-3 dark:border-slate-700">
      <p className="text-sm font-semibold [overflow-wrap:anywhere]">
        <Txt>{node.label}</Txt>
      </p>
      <p className="mt-0.5 text-xs">
        id{" "}
        <span className="font-mono" title={node.id} aria-label={`mã ${node.id}`}>
          {shortId(node.id, 8)}
        </span>
        {" · cha: "}
        {node.parents.length === 0 ? (
          <span className="text-slate-500">gốc (không có cha)</span>
        ) : (
          node.parents.map((p, i) => (
            <span key={p}>
              {i > 0 && ", "}
              <a
                href={`#node-${p}`}
                onClick={(e) => {
                  e.preventDefault();
                  onJump(p);
                }}
                title={p} aria-label={`nút cha ${p}`} className="font-mono underline">
                {shortId(p, 8)}
              </a>
            </span>
          ))
        )}
      </p>
      <dl className="mt-2 grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-2">
        <Field k="nguồn" v={node.source} />
        <Field k="broker" v={node.broker} mono={false} />
        <Field k="symbol / timeframe" v={[node.symbol, node.timeframe].filter(Boolean).join(" / ") || null} />
        <Field k="múi giờ" v={node.timezone} mono={false} />
        <Field k="đồng hồ broker" v={node.broker_clock} mono={false} />
        <Field k="timestamp đầu" v={node.first_timestamp} />
        <Field k="timestamp cuối" v={node.last_timestamp} />
        <Field k="lấy lúc" v={node.fetched_at} />
        <Hash k="raw_hash" v={node.raw_hash} />
        <Hash k="parent_hash" v={node.parent_hash} />
        <Field k="biến đổi" v={node.transformation} mono={false} />
        <Field k="phiên bản biến đổi" v={node.transform_version} />
        <Field k="kết quả validator" v={node.validator_result} mono={false} />
        <Field k="chi tiết" v={detail} />
      </dl>
    </li>
  );
}

const PREVIEW = 3;

function Body({ view, degraded }: { view: View; degraded: boolean }) {
  const known = new Set(view.stages);
  const extra = view.nodes.filter((n) => !known.has(n.stage));
  const emptyDeclared = new Set(view.empty_stages);
  const [open, setOpen] = useState<Set<string>>(new Set());
  const jump = (id: string) => {
    const target = view.nodes.find((n) => n.id === id);
    if (target) setOpen((o) => new Set(o).add(target.stage));
    setTimeout(() => document.getElementById(`node-${id}`)?.scrollIntoView({ block: "center" }), 50);
  };
  return (
    <div className="space-y-4">
      {view.problems.length > 0 && (
        <div role="alert" className="rounded-xl border-2 border-red-600 bg-red-500/10 p-3 text-sm">
          <p className="font-semibold text-red-800 dark:text-red-200">Vấn đề toàn vẹn của lineage ({view.problems.length})</p>
          <ul className="mt-1 list-disc pl-5 text-xs [overflow-wrap:anywhere]">
            {view.problems.map((p) => (
              <li key={p}>
                <Txt>{p}</Txt>
              </li>
            ))}
          </ul>
        </div>
      )}
      {degraded && <p className="text-xs text-slate-500">Dưới đây là phần lineage đọc được; vì trạng thái KHÔNG RÕ nên không dùng làm bằng chứng nguồn gốc dữ liệu.</p>}
      <Panel title={`Chuỗi nguồn gốc dữ liệu: ${view.stages.length} bước, ${view.nodes.length} nút`}>
        <ol className="space-y-4">
          {view.stages.map((stage, i) => {
            const nodes = view.nodes.filter((n) => n.stage === stage);
            const empty = nodes.length === 0;
            return (
              <li key={stage} className="min-w-0">
                <h3 className="flex flex-wrap items-center gap-2 text-sm font-semibold">
                  <span className="font-mono text-slate-500">{i + 1}.</span> <span data-stage={stage}>{stage}</span>
                  {empty ? (
                    <StatusBadge tone="unknown">TRỐNG: chưa có</StatusBadge>
                  ) : (
                    <StatusBadge tone="neutral">{nodes.length} nút</StatusBadge>
                  )}
                  {empty && !emptyDeclared.has(stage) && <StatusBadge tone="warn">API không khai báo bước trống này</StatusBadge>}
                </h3>
                {!empty && (
                  <>
                    <ul className="mt-2 grid gap-2 lg:grid-cols-2">
                      {(open.has(stage) ? nodes : nodes.slice(0, PREVIEW)).map((n) => (
                        <Node key={n.id} node={n} onJump={jump} />
                      ))}
                    </ul>
                    {nodes.length > PREVIEW && (
                      <button
                        type="button"
                        aria-expanded={open.has(stage)}
                        onClick={() =>
                          setOpen((o) => {
                            const next = new Set(o);
                            if (next.has(stage)) next.delete(stage);
                            else next.add(stage);
                            return next;
                          })
                        }
                        className="mt-2 rounded-md border border-slate-400 px-3 py-1 text-xs"
                      >
                        {open.has(stage) ? `Thu gọn ${stage}` : `Hiện tất cả ${nodes.length} nút của ${stage}`}
                      </button>
                    )}
                  </>
                )}
              </li>
            );
          })}
        </ol>
      </Panel>
      {extra.length > 0 && (
        <Panel title="Nút thuộc bước không rõ">
          <ul className="grid gap-2 lg:grid-cols-2">
            {extra.map((n) => (
              <Node key={n.id} node={n} onJump={jump} />
            ))}
          </ul>
        </Panel>
      )}
      <SourceNote source={view.source} />
    </div>
  );
}

export function LineageView() {
  const loader = useCallback((s: AbortSignal) => research.lineage(s), []);
  const { result, reload } = useLoad(loader);
  return (
    <ResearchShell current="/research/lineage" title="Lineage dữ liệu" subtitle="Từ nguồn thô đến thực thi: mỗi nút có id, cha, băm và kết quả validator. Chỉ đọc; hash dài được rút gọn (đầy đủ trong title).">
      <div className="flex justify-end">
        <RefreshButton onClick={reload} />
      </div>
      <Gate result={result} what="lineage dữ liệu" partial={(v) => (
        <Body view={{ ...v, stages: v.stages ?? [], problems: v.problems ?? [], nodes: v.nodes ?? [], empty_stages: v.empty_stages ?? [] }} degraded />
      )}>
        {(view) => <Body view={view} degraded={false} />}
      </Gate>
    </ResearchShell>
  );
}
