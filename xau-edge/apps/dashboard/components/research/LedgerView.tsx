"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { StatusBadge } from "@/components/research/StatusBadge";
import { Gate, Panel, RefreshButton, ResearchShell, SourceNote, TableWrap, Warning, card, td, th, useLoad } from "@/components/research/ui";
import { type LedgerView as Ledger, type PowerView, type Result, fmt, research } from "@/lib/research";

const input = "w-full rounded-md border border-slate-400 bg-transparent px-2 py-1 font-mono text-sm";

function McdeChart({ power }: { power: PowerView }) {
  const W = 480;
  const H = 220;
  const pad = { l: 44, r: 12, t: 12, b: 28 };
  const pts = [...power.curve];
  if (!pts.some((p) => p.n === power.n)) pts.push({ n: power.n, mde: power.mde });
  pts.sort((a, b) => a.n - b.n);
  const xMax = Math.max(...pts.map((p) => p.n));
  const yMax = Math.max(0.3, ...pts.map((p) => p.mde)) * 1.05;
  const x = (n: number) => pad.l + (n / xMax) * (W - pad.l - pad.r);
  const y = (v: number) => H - pad.b - (v / yMax) * (H - pad.t - pad.b);
  const path = pts.map((p, i) => `${i === 0 ? "M" : "L"}${x(p.n).toFixed(1)},${y(p.mde).toFixed(1)}`).join(" ");
  const limit = power.underpowered_threshold;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Đường MDE theo n, K = ${power.k}, sd = ${power.sd}`} className="h-auto w-full max-w-full">
      <rect x={pad.l} y={pad.t} width={W - pad.l - pad.r} height={H - pad.t - pad.b} fill="none" stroke="currentColor" strokeOpacity="0.2" />
      <line x1={pad.l} x2={W - pad.r} y1={y(limit)} y2={y(limit)} stroke="#dc2626" strokeDasharray="4 3" />
      <text x={W - pad.r - 2} y={y(limit) - 3} textAnchor="end" fontSize="10" fill="#dc2626">
        ngưỡng {limit.toFixed(2)} R
      </text>
      <path d={path} fill="none" stroke="#0284c7" strokeWidth="2" />
      {pts.map((p) => (
        <circle key={p.n} cx={x(p.n)} cy={y(p.mde)} r={p.n === power.n ? 5 : 2.5} fill={p.n === power.n ? (power.underpowered_by_design ? "#dc2626" : "#16a34a") : "#0284c7"} />
      ))}
      {[0, 0.1, 0.2, 0.3].filter((v) => v <= yMax).map((v) => (
        <text key={v} x={pad.l - 4} y={y(v) + 3} textAnchor="end" fontSize="10" fill="currentColor" fillOpacity="0.6">
          {v.toFixed(1)}
        </text>
      ))}
      {pts.map((p) => (
        <text key={`x${p.n}`} x={x(p.n)} y={H - 10} textAnchor="middle" fontSize="9" fill="currentColor" fillOpacity="0.6">
          {p.n}
        </text>
      ))}
      <text x={pad.l} y={9} fontSize="10" fill="currentColor" fillOpacity="0.6">
        MDE (R)
      </text>
    </svg>
  );
}

function PowerCalculator({ defaultK }: { defaultK: number | null }) {
  const [k, setK] = useState(String(defaultK ?? 21));
  const [n, setN] = useState("500");
  const [sd, setSd] = useState("1.3");
  const [result, setResult] = useState<Result<PowerView> | null>(null);
  const kn = Number(k);
  const nn = Number(n);
  const sdn = Number(sd);
  const valid = Number.isInteger(kn) && kn >= 1 && kn <= 1000 && Number.isInteger(nn) && nn >= 1 && nn <= 1_000_000 && sdn > 0.05 && sdn <= 10;

  useEffect(() => {
    if (!valid) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      research
        .power(kn, nn, sdn, controller.signal)
        .then(setResult)
        .catch(() => undefined);
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [valid, kn, nn, sdn]);

  return (
    <Panel title="Máy tính MDE (K, n, sd)">
      <div className="grid grid-cols-3 gap-2 text-sm">
        <label>
          K
          <input className={input} inputMode="numeric" value={k} onChange={(e) => setK(e.target.value)} aria-label="K (số biến thể đã thử)" />
        </label>
        <label>
          n
          <input className={input} inputMode="numeric" value={n} onChange={(e) => setN(e.target.value)} aria-label="n (số lệnh)" />
        </label>
        <label>
          sd (R)
          <input className={input} inputMode="decimal" value={sd} onChange={(e) => setSd(e.target.value)} aria-label="sd (độ lệch chuẩn R)" />
        </label>
      </div>
      {!valid && <Warning>Giá trị ngoài miền hợp lệ: K 1..1000, n 1..1.000.000, 0,05 &lt; sd ≤ 10. Chưa tính.</Warning>}
      {valid && (
        <div className="mt-3">
          <Gate result={result} what="phép tính MDE">
            {(p) => (
              <div className="space-y-2">
                <p className="text-sm">
                  alpha = 0,05 / {p.k} = <span className="font-mono">{p.alpha.toFixed(5)}</span> · MDE ={" "}
                  <strong className="font-mono">{p.mde.toFixed(3)} R</strong>{" "}
                  {p.underpowered_by_design ? (
                    <StatusBadge tone="fail">underpowered by design</StatusBadge>
                  ) : (
                    <StatusBadge tone="ok">đủ công suất cho ngưỡng {p.underpowered_threshold.toFixed(2)} R</StatusBadge>
                  )}
                </p>
                <McdeChart power={p} />
                <p className="text-xs text-slate-500">
                  Số lệnh cần để phát hiện: {Object.entries(p.trades_needed).map(([e, t]) => `${e} R → ${t}`).join(" · ")}
                </p>
                <p className="break-words text-[11px] text-slate-500">{p.formula}</p>
                <SourceNote source={p.source} />
              </div>
            )}
          </Gate>
        </div>
      )}
    </Panel>
  );
}

function Filters({ ledger, onChange }: { ledger: Ledger; onChange: (f: { h: string; p: string; s: string }) => void }) {
  const [h, setH] = useState("");
  const [p, setP] = useState("");
  const [s, setS] = useState("");
  const opts = (key: "hypothesis" | "period" | "scenario") => [...new Set(ledger.runs.map((r) => r[key]))].sort();
  const select = (label: string, key: "h" | "p" | "s", value: string, set: (v: string) => void, values: string[]) => (
    <label className="text-sm">
      {label}
      <select
        className={input}
        value={value}
        onChange={(e) => {
          set(e.target.value);
          onChange({ h, p, s, [key]: e.target.value });
        }}
      >
        <option value="">tất cả</option>
        {values.map((v) => (
          <option key={v} value={v}>
            {v}
          </option>
        ))}
      </select>
    </label>
  );
  return (
    <div className="mb-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
      {select("Giả thuyết", "h", h, setH, opts("hypothesis"))}
      {select("Giai đoạn", "p", p, setP, opts("period"))}
      {select("Kịch bản", "s", s, setS, opts("scenario"))}
    </div>
  );
}

function RunsTable({ ledger }: { ledger: Ledger }) {
  const [f, setF] = useState({ h: "", p: "", s: "" });
  const rows = useMemo(
    () => ledger.runs.filter((r) => (!f.h || r.hypothesis === f.h) && (!f.p || r.period === f.p) && (!f.s || r.scenario === f.s)),
    [ledger.runs, f],
  );
  return (
    <Panel title={`Mọi lần chạy (${rows.length}/${ledger.total_runs})`}>
      <Filters ledger={ledger} onChange={setF} />
      <TableWrap label="Bảng các lần chạy trong ledger">
        <table className="w-full min-w-[760px] text-sm">
          <thead>
            <tr>
              {["#", "Thời gian", "Biến thể", "Giai đoạn", "Kịch bản", "Số lệnh (n)", "Mean net R cơ sở", "Mean net R bi quan", "Kết quả", "Registry id"].map((c) => (
                <th key={c} className={th} scope="col">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.number} className="border-t border-slate-300/50 dark:border-slate-700">
                <td className={td}>{r.number}</td>
                <td className={`${td} whitespace-nowrap text-xs`}>{r.time ?? "KHÔNG RÕ"}</td>
                <td className={`${td} font-mono`}>{r.variant}</td>
                <td className={td}>{r.period}</td>
                <td className={td}>{r.scenario}</td>
                <td className={td}>{r.trades ?? "chưa có"}</td>
                <td className={`${td} font-mono`}>{fmt(r.mean_net_r_base, 4)}</td>
                <td className={`${td} font-mono`}>{fmt(r.mean_net_r_pessimistic, 4)}</td>
                <td className={td}>
                  {r.verdict === "PASS" ? (
                    <StatusBadge tone="ok">PASS (giai đoạn)</StatusBadge>
                  ) : r.verdict === "FAIL" ? (
                    <StatusBadge tone="fail">FAIL</StatusBadge>
                  ) : (
                    <StatusBadge tone="unknown">KHÔNG RÕ</StatusBadge>
                  )}
                </td>
                <td className={`${td} font-mono text-xs`}>{r.registry_id}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td className={td} colSpan={10}>
                  Không có lần chạy khớp bộ lọc.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </TableWrap>
      <SourceNote source={ledger.source} />
    </Panel>
  );
}

function LedgerBody({ ledger }: { ledger: Ledger }) {
  const alpha = ledger.k ? 0.05 / ledger.k : null;
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-3">
        <Panel title="Bộ đếm K (chương trình này)">
          <p className="font-mono text-2xl">
            K = {ledger.k ?? "KHÔNG RÕ"}
            {ledger.k_cap ? ` / ${ledger.k_cap}` : ""}
          </p>
          <p className="text-sm">
            alpha = 0,05 / K = <span className="font-mono">{alpha === null ? "KHÔNG RÕ" : alpha.toFixed(6)}</span>
            {ledger.alpha !== null && alpha !== null && Math.abs(ledger.alpha - alpha) > 1e-4 && (
              <StatusBadge tone="warn">ledger ghi {ledger.alpha}</StatusBadge>
            )}
          </p>
          {ledger.malformed_rows > 0 && <Warning>{ledger.malformed_rows} dòng ledger hỏng, bị bỏ qua.</Warning>}
          <SourceNote source={ledger.source} />
        </Panel>
        <Panel title="K legacy (chỉ đọc)">
          <ul className="text-sm">
            <li>Baselines: {ledger.legacy_k.baselines}</li>
            <li>Programme 1: {ledger.legacy_k.programme_1 ?? "không áp dụng"}</li>
          </ul>
          <p className="mt-1 text-xs text-slate-500">K của V2 là bộ đếm riêng (xem ledger V2). Mọi số này do mã nghiên cứu ghi, console không sửa.</p>
        </Panel>
        <Panel title="Tổng kết">
          <ul className="text-sm">
            {Object.entries(ledger.verdicts).map(([v, c]) => (
              <li key={v}>
                {v}: <span className="font-mono">{c}</span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
      <RunsTable ledger={ledger} />
    </div>
  );
}

export function LedgerView() {
  const [programme, setProgramme] = useState<"v1" | "v2">("v1");
  const loader = useCallback((s: AbortSignal) => research.ledger(programme, s), [programme]);
  const { result, reload } = useLoad(loader);
  const k = result?.kind === "ok" ? result.data.k : null;
  return (
    <ResearchShell current="/research/ledger" title="Ledger & K" subtitle="Mọi lần chạy (kể cả thất bại), bộ đếm K, alpha = 0,05/K và công suất thống kê (MDE).">
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Chương trình">
        {(["v1", "v2"] as const).map((p) => (
          <button
            key={p}
            type="button"
            aria-pressed={programme === p}
            onClick={() => setProgramme(p)}
            className={`rounded-md border px-3 py-1 text-sm ${programme === p ? "border-sky-600 bg-sky-500/15 font-semibold" : "border-slate-400"}`}
          >
            Chương trình {p.toUpperCase()}
          </button>
        ))}
        <RefreshButton onClick={reload} />
      </div>
      <Gate key={programme} result={result} what={`ledger ${programme.toUpperCase()}`}>
        {(ledger) => <LedgerBody ledger={ledger} />}
      </Gate>
      <PowerCalculator defaultK={k} />
      <div className={card}>
        <p className="text-xs text-slate-500">
          MDE = hiệu ứng nhỏ nhất có thể phát hiện (công suất 80%, đã hiệu chỉnh theo K). Khi MDE lớn hơn 0,20 R, phép thử bị coi là underpowered by design:
          kết quả âm khi đó không chứng minh được là không có edge.
        </p>
      </div>
    </ResearchShell>
  );
}
