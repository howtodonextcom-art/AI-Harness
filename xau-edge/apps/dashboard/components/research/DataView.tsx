"use client";

import { useCallback } from "react";
import { StatusBadge, type Tone } from "@/components/research/StatusBadge";
import { Gate, Panel, RefreshButton, ResearchShell, SourceNote, TableWrap, Txt, Warning, td, th, useLoad } from "@/components/research/ui";
import { type DataView as Data, type LocksView, research } from "@/lib/research";

const date = (iso: string | null) => (iso ? iso.slice(0, 10) : "chưa có");

function Frames({ data }: { data: Data }) {
  return (
    <Panel title="Khung dữ liệu theo timeframe">
      <TableWrap label="Bảng khung dữ liệu">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr>
              {["TF", "Số hàng", "Ngày đầu", "Ngày cuối", "Dataset id", "Validator", "Lỗi ERROR", "Cảnh báo"].map((c) => (
                <th key={c} className={th} scope="col">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.frames.map((f) => (
              <tr key={f.timeframe} className="border-t border-slate-300/50 align-top dark:border-slate-700">
                <td className={`${td} font-semibold`}>{f.timeframe}</td>
                <td className={`${td} font-mono`}>{f.rows ?? "chưa có"}</td>
                <td className={td}>{date(f.first)}</td>
                <td className={td}>{date(f.last)}</td>
                <td className={`${td} font-mono text-xs`}>{f.dataset_id ?? "chưa có"}</td>
                <td className={td}>
                  {f.validation_passed === true ? (
                    <StatusBadge tone="ok">ĐẠT</StatusBadge>
                  ) : f.validation_passed === false ? (
                    <StatusBadge tone="fail">KHÔNG ĐẠT</StatusBadge>
                  ) : (
                    <StatusBadge tone="unknown">{f.rows === 0 ? "KHÔNG CÓ DỮ LIỆU" : "KHÔNG RÕ"}</StatusBadge>
                  )}
                </td>
                <td className={`${td} text-xs`}>
                  {f.errors.length === 0 ? "—" : f.errors.map((e) => (
                    <div key={e.code} className="text-red-700 dark:text-red-300">
                      {e.code} × {e.count}
                    </div>
                  ))}
                </td>
                <td className={`${td} text-xs`}>
                  {f.warnings.length === 0 ? "—" : f.warnings.map((e) => (
                    <div key={e.code}>
                      {e.code} × {e.count}
                    </div>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
      <SourceNote source={data.source} />
    </Panel>
  );
}

function Clock({ data }: { data: Data }) {
  const c = data.clock_certificate;
  return (
    <Panel title="Chứng nhận giờ broker theo năm">
      {!c.present && <Warning>KHÔNG RÕ: chưa có file chứng nhận giờ broker; mọi năm đều CHƯA CHỨNG NHẬN và giả thuyết theo phiên bị chặn.</Warning>}
      <p className="my-2 text-sm">
        <Txt>{c.message}</Txt>
        {c.session_hypotheses_blocked_years.length > 0 && (
          <>
            {" "}
            <StatusBadge tone="warn">{c.session_hypotheses_blocked_years.length} năm bị chặn</StatusBadge>
          </>
        )}
      </p>
      <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8" aria-label="Chứng nhận giờ theo năm">
        {c.years.map((y) => (
          <li
            key={y.year}
            className={`rounded-md border px-2 py-1 text-center text-xs ${
              y.certified ? "border-green-600 bg-green-500/10" : "border-red-600 bg-red-500/15 font-semibold text-red-800 dark:text-red-200"
            }`}
            data-blocked={y.certified ? "false" : "true"}
          >
            <div className="font-mono text-sm">{y.year}</div>
            <div>{y.state}</div>
            {y.offset !== null && <div className="font-mono">offset {y.offset}</div>}
          </li>
        ))}
      </ul>
      <SourceNote source={c.source} />
    </Panel>
  );
}

const LOCK_TONE: Record<string, Tone> = {
  "NGUYÊN VẸN": "ok",
  "ĐÃ DÙNG": "fail",
  "KHÔNG RÕ": "unknown",
  "ĐÃ DÙNG THIẾT KẾ": "warn",
  "ĐANG TÍCH LŨY": "info",
};

const OUTCOME_TONE: Record<string, Tone> = {
  PASS: "info",
  FAIL: "fail",
  INCONCLUSIVE: "warn",
  LOCKED: "neutral",
  UNKNOWN: "unknown",
};

/** null => "—" (not a confirmatory split); an unrecognised value is KHÔNG RÕ, never an implicit result. */
function Outcome({ state }: { state: string | null | undefined }) {
  if (state === null || state === undefined) return <span aria-label="không áp dụng">—</span>;
  if (!(state in OUTCOME_TONE)) return <StatusBadge tone="unknown">KHÔNG RÕ ({state})</StatusBadge>;
  return <StatusBadge tone={OUTCOME_TONE[state]}>{state === "UNKNOWN" ? "KHÔNG RÕ (UNKNOWN)" : state}</StatusBadge>;
}

function Locks({ locks }: { locks: LocksView }) {
  const rows = locks.locks.filter((l) => ["dev2", "val2", "testH", "holdout", "forward"].includes(l.id));
  return (
    <Panel title="Trạng thái khóa dữ liệu">
      <TableWrap label="Bảng khóa dữ liệu">
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr>
              {["Giai đoạn", "Từ", "Đến", "Mục đích", "Trạng thái", "Kết quả (outcome)"].map((c) => (
                <th key={c} className={th} scope="col">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((l) => (
              <tr key={l.id} className="border-t border-slate-300/50 dark:border-slate-700">
                <td className={`${td} font-semibold`}>{l.name}</td>
                <td className={td}>{l.from}</td>
                <td className={td}>{l.to ?? "đang chạy"}</td>
                <td className={td}>
                  <Txt>{l.use}</Txt>
                </td>
                <td className={td}>
                  <StatusBadge tone={LOCK_TONE[l.state] ?? "unknown"}>{l.state}</StatusBadge>
                  {l.burned && <span className="ml-1 text-xs text-slate-500">(burned)</span>}
                </td>
                <td className={td}>
                  <Outcome state={l.outcome_state} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
      <p className="mt-2 text-xs text-slate-500">
        {locks.registry_records} bản ghi registry đã đọc, {locks.unreadable_records} không đọc được · freeze record:{" "}
        {locks.freeze_records.length === 0 ? "chưa có" : locks.freeze_records.join(", ")}. Console chỉ hiển thị, không mở khóa.
      </p>
      <SourceNote source={locks.source} />
    </Panel>
  );
}

export function DataView() {
  const dataLoader = useCallback((s: AbortSignal) => research.data(s), []);
  const lockLoader = useCallback((s: AbortSignal) => research.locks(s), []);
  const d = useLoad(dataLoader);
  const l = useLoad(lockLoader);
  return (
    <ResearchShell current="/research/data" title="Dữ liệu, chứng nhận giờ và khóa" subtitle="Khung dữ liệu và lỗi validator, chứng nhận giờ broker theo năm, trạng thái khóa Dev-2 / Val-2 / Test-H / Holdout / Forward.">
      <div className="flex justify-end">
        <RefreshButton
          onClick={() => {
            d.reload();
            l.reload();
          }}
        />
      </div>
      <Gate result={d.result} what="manifest dữ liệu" dataAt={(x) => x.generated_at} partial={(x) => <Frames data={x} />}>
        {(data) => (
          <div className="space-y-4">
            <Frames data={data} />
            <Clock data={data} />
          </div>
        )}
      </Gate>
      <Gate result={l.result} what="trạng thái khóa dữ liệu" partial={(x) => <Locks locks={x} />}>
        {(locks) => <Locks locks={locks} />}
      </Gate>
    </ResearchShell>
  );
}
