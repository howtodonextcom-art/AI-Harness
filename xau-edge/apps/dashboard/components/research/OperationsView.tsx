"use client";

import { useCallback } from "react";
import { StatusBadge } from "@/components/research/StatusBadge";
import { Bar, Gate, Panel, RefreshButton, ResearchShell, SourceNote, TableWrap, Txt, Warning, td, th, useLoad } from "@/components/research/ui";
import { type CalibrationView, type RolloutView, type SoakView, fmt, research } from "@/lib/research";

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

function Rollout({ r }: { r: RolloutView }) {
  const dash = (v: number | null | undefined, suffix = "") => (typeof v === "number" ? `${v}${suffix}` : "KHÔNG RÕ");
  return (
    <Panel title="Rollout theo tier">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
        <span>Tier hiện tại:</span>
        <StatusBadge tone="unknown">{r.current_tier === null ? r.current_tier_state || "KHÔNG RÕ" : `${r.current_tier} (${r.current_tier_state})`}</StatusBadge>
        <span className="text-xs text-slate-500">
          <Txt>{r.current_tier_reason}</Txt>
        </span>
      </div>
      <TableWrap label="Bảng tier rollout">
        <table className="w-full min-w-[820px] text-sm">
          <caption className="sr-only">Các tier rollout: gửi lệnh, giới hạn lot, rủi ro, điều kiện lên bậc và tiến độ</caption>
          <thead>
            <tr>
              {["Tier", "Tên", "Gửi lệnh", "Lot tối đa", "Rủi ro %", "Cần VALIDATED", "Điều kiện thoát tier", "Tiến độ"].map((c) => (
                <th key={c} className={th} scope="col">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {r.tiers.map((t) => (
              <tr key={String(t.tier)} className="border-t border-slate-300/50 align-top dark:border-slate-700">
                <th scope="row" className={`${td} text-left font-mono font-semibold`}>
                  {String(t.tier)}
                </th>
                <td className={td}>
                  <Txt>{t.name}</Txt>
                </td>
                <td className={td}>
                  <StatusBadge tone={t.send_orders ? "warn" : "neutral"}>{t.send_orders ? "CÓ GỬI LỆNH (khi được cho phép)" : "không gửi lệnh"}</StatusBadge>
                </td>
                <td className={`${td} font-mono`}>{dash(t.lot_cap)}</td>
                <td className={`${td} font-mono`}>{dash(t.risk_pct)}</td>
                <td className={td}>{t.requires_validated ? "có" : "không"}</td>
                <td className={`${td} text-xs`}>
                  <ul>
                    <li>ngày giao dịch tối thiểu: {dash(t.exit?.min_trading_days)}</li>
                    <li>lệnh tối thiểu: {dash(t.exit?.min_orders)}</li>
                    <li>bị từ chối/không rõ tối đa: {dash(t.exit?.max_rejected_or_unknown)}</li>
                    <li>tuần tối thiểu: {dash(t.exit?.min_weeks)}</li>
                  </ul>
                </td>
                <td className={td}>
                  <StatusBadge tone="unknown">{t.progress || "KHÔNG RÕ"}</StatusBadge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
      <p className="mt-2 text-sm font-semibold">
        <Txt>{r.note}</Txt>
      </p>
      <SourceNote source={r.source} />
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
      <Panel title="Luật tài khoản chưa xác minh">
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
  const rolloutLoader = useCallback((s: AbortSignal) => research.rollout(s), []);
  const rollout = useLoad(rolloutLoader);
  const soak = useLoad(soakLoader);
  return (
    <ResearchShell current="/research/operations" title="Vận hành và hiệu chuẩn thực thi" subtitle="Chi phí giả định so với đo được, tiến độ soak, bar trùng và các luật tài khoản còn chờ xác minh (chỉ đọc).">
      <div className="flex justify-end">
        <RefreshButton
          onClick={() => {
            cal.reload();
            soak.reload();
            rollout.reload();
          }}
        />
      </div>
      <p className="rounded-md border-2 border-red-600 bg-red-500/10 p-2 text-sm font-semibold text-red-800 dark:text-red-200">funded vẫn bị chặn: console không bật funded và không gửi lệnh.</p>
      <Gate result={cal.result} what="hiệu chuẩn chi phí" partial={(c) => <Calibration cal={c} />}>
        {(c) => <Calibration cal={c} />}
      </Gate>
      <Gate result={rollout.result} what="rollout theo tier" partial={(r) => (Array.isArray(r.tiers) ? <Rollout r={r} /> : null)}>
        {(r) => <Rollout r={r} />}
      </Gate>
      <Gate result={soak.result} what="tiến độ soak">
        {(s) => <Soak soak={s} />}
      </Gate>
    </ResearchShell>
  );
}
