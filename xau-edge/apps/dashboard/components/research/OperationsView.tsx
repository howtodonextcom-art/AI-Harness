"use client";

import { useCallback } from "react";
import { StatusBadge } from "@/components/research/StatusBadge";
import { Bar, Gate, Panel, RefreshButton, ResearchShell, SourceNote, TableWrap, Txt, Warning, td, th, useLoad } from "@/components/research/ui";
import { type CalibrationView, type SoakView, fmt, research } from "@/lib/research";

const COST_LABEL: Record<string, string> = {
  slippage_points: "Slippage (points)",
  commission_per_lot_per_side: "Commission / lot / chiều",
  swap_long_points: "Swap mua (points)",
  swap_short_points: "Swap bán (points)",
};

function Calibration({ cal }: { cal: CalibrationView }) {
  const measured = cal.measured;
  const extra = measured ? Object.keys(measured).filter((k) => !(k in cal.assumed)) : [];
  return (
    <Panel title="Chi phí: giả định so với đo được">
      {measured === null && (
        <Warning>
          KHÔNG RÕ: <Txt>{cal.message ?? "chưa đo chi phí thật"}</Txt> Các số bên dưới là GIẢ ĐỊNH của mô hình chi phí, chưa được kiểm chứng.
        </Warning>
      )}
      <TableWrap label="Bảng chi phí giả định và đo được">
        <table className="mt-2 w-full min-w-[420px] text-sm">
          <thead>
            <tr>
              {["Khoản", "Giả định", "Đo được", "Lệch"].map((c) => (
                <th key={c} className={th} scope="col">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(cal.assumed).map(([key, a]) => {
              const m = measured?.[key];
              const num = typeof m === "number" ? m : null;
              const drift = num !== null && a !== 0 ? (num - a) / Math.abs(a) : null;
              return (
                <tr key={key} className="border-t border-slate-300/50 dark:border-slate-700">
                  <td className={td}>{COST_LABEL[key] ?? key}</td>
                  <td className={`${td} font-mono`}>
                    {fmt(a, 2)} <StatusBadge tone="warn">GIẢ ĐỊNH</StatusBadge>
                  </td>
                  <td className={`${td} font-mono`}>{measured === null ? "KHÔNG RÕ" : fmt(num ?? m, 2)}</td>
                  <td className={`${td} font-mono`}>
                    {drift === null ? "—" : (
                      <span className={Math.abs(drift) > 0.5 ? "font-semibold text-red-700 dark:text-red-300" : ""}>{`${(drift * 100).toFixed(0)}%`}</span>
                    )}
                  </td>
                </tr>
              );
            })}
            {extra.map((key) => (
              <tr key={key} className="border-t border-slate-300/50 dark:border-slate-700">
                <td className={td}>{key}</td>
                <td className={`${td} font-mono`}>—</td>
                <td className={`${td} font-mono`}>{fmt(measured?.[key], 3)}</td>
                <td className={td}>—</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
      <SourceNote source={cal.source} />
    </Panel>
  );
}

function Soak({ soak }: { soak: SoakView }) {
  const t = soak.target ?? { soak_days: 14, uptime_min: 0.99, duplicates_max: 0, demo_weeks: 4 };
  const days = soak.days_covered ?? null;
  const uptime = soak.uptime_m15 ?? null;
  const dup = soak.duplicate_bars ?? null;
  const rules = soak.funded_rules;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Panel title="Soak 14 ngày và uptime M15">
        <div className="space-y-3 text-sm">
          <div>
            <div className="flex justify-between gap-2">
              <span>Tiến độ soak</span>
              <strong className="font-mono">{days === null ? "KHÔNG RÕ" : `${days.toFixed(2)} / ${t.soak_days} ngày`}</strong>
            </div>
            <Bar value={days ?? 0} max={t.soak_days} label="Tiến độ soak (ngày)" />
          </div>
          <div>
            <div className="flex justify-between gap-2">
              <span>Uptime M15 (mục tiêu ≥ {(t.uptime_min * 100).toFixed(0)}%)</span>
              <strong className="font-mono">{uptime === null ? "KHÔNG RÕ" : `${(uptime * 100).toFixed(1)}%`}</strong>
            </div>
            <Bar value={(uptime ?? 0) * 100} max={100} label="Uptime M15 (%)" tone={uptime === null ? "warn" : uptime >= t.uptime_min ? "ok" : "fail"} />
            {days !== null && days < t.soak_days && <p className="text-xs text-slate-500">Mới phủ {days.toFixed(2)} ngày: chưa đủ để kết luận uptime.</p>}
          </div>
          <div>
            <div className="flex justify-between gap-2">
              <span>Bar trùng (mục tiêu ≤ {t.duplicates_max})</span>
              <strong className={`font-mono ${dup !== null && dup > t.duplicates_max ? "text-red-700 dark:text-red-300" : ""}`}>{dup ?? "KHÔNG RÕ"}</strong>
            </div>
            <Bar value={dup ?? 0} max={Math.max(1, soak.decided_bars ?? 1)} label="Bar trùng" tone={dup !== null && dup > t.duplicates_max ? "fail" : "ok"} />
          </div>
          <p className="text-xs text-slate-500">
            {soak.cycles ?? "?"} chu kỳ · {soak.decided_bars ?? "?"} bar đã quyết định / {soak.expected_bars ?? "?"} bar dự kiến · cảnh báo ghi: {soak.alerts ? soak.alerts.lines : "KHÔNG RÕ"} · demo mục tiêu {t.demo_weeks} tuần
          </p>
        </div>
        <SourceNote source={soak.source} />
      </Panel>
      <Panel title="Rollout và luật tài khoản chưa xác minh">
        <p className="mb-2 text-sm">
          Rollout theo tier: <StatusBadge tone="unknown">KHÔNG RÕ</StatusBadge> <span className="text-xs text-slate-500">(chưa có nguồn dữ liệu cho tiến độ rollout)</span>
        </p>
        {rules?.status === "ok" && rules.pending ? (
          <>
            <p className="text-sm">
              <strong className="font-mono">
                {rules.pending.length} / {rules.total}
              </strong>{" "}
              luật chưa xác minh (chỉ đọc, không có nút sửa).
            </p>
            <ul className="mt-2 grid gap-1 text-xs sm:grid-cols-1">
              {rules.pending.map((r) => (
                <li key={r} className="break-all font-mono">
                  {r}
                </li>
              ))}
            </ul>
            <SourceNote source={rules.source} />
          </>
        ) : (
          <Warning>
            KHÔNG RÕ: không đọc được luật tài khoản. <Txt>{rules?.reason}</Txt>
          </Warning>
        )}
      </Panel>
    </div>
  );
}

export function OperationsView() {
  const calLoader = useCallback((s: AbortSignal) => research.calibration(s), []);
  const soakLoader = useCallback((s: AbortSignal) => research.soak(s), []);
  const cal = useLoad(calLoader);
  const soak = useLoad(soakLoader);
  return (
    <ResearchShell current="/research/operations" title="Vận hành và hiệu chuẩn thực thi" subtitle="Chi phí giả định so với đo được, tiến độ soak, bar trùng và các luật tài khoản còn chờ xác minh (chỉ đọc).">
      <div className="flex justify-end">
        <RefreshButton
          onClick={() => {
            cal.reload();
            soak.reload();
          }}
        />
      </div>
      <Gate result={cal.result} what="hiệu chuẩn chi phí" partial={(c) => <Calibration cal={c} />}>
        {(c) => <Calibration cal={c} />}
      </Gate>
      <Gate result={soak.result} what="tiến độ soak">
        {(s) => <Soak soak={s} />}
      </Gate>
    </ResearchShell>
  );
}
