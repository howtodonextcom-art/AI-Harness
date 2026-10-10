"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { formatInZone, type DisplayZone } from "@/lib/time";
import { ZoneSelect, useDisplayZone } from "@/lib/useZone";
import {
  type ActionName,
  type ActionState,
  type CheckStatus,
  type ControlStatus,
  type Job,
  type JournalEvent,
  type PreflightReport,
  ControlRequestError,
  getControl,
  newIdempotencyKey,
  postControl,
} from "@/lib/control";

/** the proxy answers these when the API runs without web control: nothing to poll, nothing to show */
const DISABLED_CODES = new Set(["CONTROL_UNAVAILABLE", "HTTP_404"]);
const isDisabled = (e: unknown) => e instanceof ControlRequestError && DISABLED_CODES.has(e.info.code);

const STATUS_POLL_MS = 3000;
const JOURNAL_POLL_MS = 5000;

const CHECK_STYLE: Record<CheckStatus, string> = {
  ok: "border-green-600 bg-green-500/10 text-green-800 dark:text-green-300",
  warn: "border-amber-500 bg-amber-500/10 text-amber-800 dark:text-amber-300",
  fail: "border-red-600 bg-red-500/10 text-red-800 dark:text-red-300",
  unknown: "border-slate-400 bg-slate-500/10 text-slate-600 dark:text-slate-300",
};

const CHECK_TEXT: Record<CheckStatus, string> = { ok: "OK", warn: "CẢNH BÁO", fail: "LỖI", unknown: "CHƯA RÕ" };

const JOB_TEXT: Record<Job["status"], string> = {
  RUNNING: "đang chạy",
  SUCCEEDED: "xong",
  FAILED: "thất bại",
  REFUSED: "bị từ chối",
};

type Pending = { kind: "mode_demo" | "smoke" | "flatten" } | null;

const card = "rounded-xl border border-slate-300/60 bg-white/60 p-4 dark:border-slate-700 dark:bg-slate-900/60";
const heading = "mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500";

function Reasons({ action }: { action: ActionState | undefined }) {
  if (!action || action.allowed) return null;
  return (
    <ul className="mt-1 space-y-0.5 text-xs text-slate-500" aria-label="Lý do không khả dụng">
      {action.blockers.map((b) => (
        <li key={b.code}>
          <span className="font-mono">{b.code}</span>: {b.message}
        </li>
      ))}
    </ul>
  );
}

function ActionButton({
  label,
  action,
  busy,
  onClick,
  tone = "default",
}: {
  label: string;
  action: ActionState | undefined;
  busy: boolean;
  onClick: () => void;
  tone?: "default" | "warning" | "danger";
}) {
  const disabled = busy || !action?.allowed;
  const style =
    tone === "danger"
      ? "border-red-700 bg-red-600 text-white"
      : tone === "warning"
        ? "border-amber-600 bg-amber-500/20"
        : "border-slate-400";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={action && !action.allowed ? action.blockers.map((b) => b.message).join("; ") : undefined}
      className={`rounded-md border px-3 py-1 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-40 ${style}`}
    >
      {label}
    </button>
  );
}

function ResultRows({ result }: { result: Record<string, unknown> }) {
  const entries = Object.entries(result).filter(([, v]) => v !== null && v !== undefined && typeof v !== "object");
  if (entries.length === 0) return null;
  return (
    <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs">
      {entries.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-slate-500">{k}</dt>
          <dd className="font-mono">{String(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

function JobView({ job, zone }: { job: Job; zone: DisplayZone }) {
  const color =
    job.status === "SUCCEEDED" ? "text-green-700 dark:text-green-300" : job.status === "RUNNING" ? "text-sky-700 dark:text-sky-300" : "text-red-700 dark:text-red-300";
  const positions = Array.isArray(job.result.positions) ? (job.result.positions as Record<string, unknown>[]) : [];
  const stillOpen = Array.isArray(job.result.still_open_tickets) ? (job.result.still_open_tickets as string[]) : [];
  return (
    <div className="rounded-md border border-slate-300/60 p-2 text-sm dark:border-slate-700" aria-label={`Job ${job.kind}`}>
      <div className="flex flex-wrap justify-between gap-2">
        <strong>{job.kind}</strong>
        <span className={color}>
          {JOB_TEXT[job.status]}
          {job.error_code ? ` (${job.error_code})` : ""}
        </span>
      </div>
      {job.message && job.status !== "SUCCEEDED" && <p className="text-xs">{job.message}</p>}
      <ol className="mt-1 space-y-0.5 text-xs text-slate-500">
        {job.steps.map((s, i) => (
          <li key={`${s.at}-${i}`}>
            <span className="tabular-nums">{formatInZone(s.at, zone).slice(11, 19)}</span> {s.message}
          </li>
        ))}
      </ol>
      <ResultRows result={job.result} />
      {positions.length > 0 && (
        <table className="mt-2 w-full text-left text-xs">
          <thead className="text-slate-500">
            <tr>
              <th>Ticket</th>
              <th>Kết quả</th>
              <th>Retcode</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <tr key={String(p.ticket)}>
                <td className="font-mono">{String(p.ticket)}</td>
                <td>{String(p.status)}</td>
                <td>{String(p.retcode ?? "—")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {stillOpen.length > 0 && (
        <p role="alert" className="mt-2 rounded border border-red-600 p-2 text-xs text-red-700 dark:text-red-300">
          Còn mở: {stillOpen.join(", ")}. {String(job.result.manual_hint ?? "Đóng tay trong MT5.")}
        </p>
      )}
    </div>
  );
}

function lastJob(status: ControlStatus | null, prefix: string): Job | undefined {
  return status?.recent_jobs.find((j) => j.kind.startsWith(prefix));
}

export function ControlPanel() {
  const [status, setStatus] = useState<ControlStatus | null>(null);
  const [report, setReport] = useState<PreflightReport | null>(null);
  const [journal, setJournal] = useState<JournalEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [preflightBusy, setPreflightBusy] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [pending, setPending] = useState<Pending>(null);
  const [disabled, setDisabled] = useState(false);
  const [zone, changeZone] = useDisplayZone("VN");
  const [recheck, setRecheck] = useState(0);

  const loadStatus = useCallback(async (signal?: AbortSignal) => {
    try {
      setStatus(await getControl<ControlStatus>("status", signal));
      setError(null);
    } catch (e) {
      if (signal?.aborted) return;
      if (isDisabled(e)) {
        setDisabled(true);
        return;
      }
      setError(e instanceof ControlRequestError ? `${e.info.code}: ${e.info.message}` : "không kết nối được dashboard server");
    }
  }, []);

  const runPreflight = useCallback(async () => {
    setPreflightBusy(true);
    try {
      setReport(await getControl<PreflightReport>("preflight?probe=true"));
    } catch (e) {
      setError(e instanceof ControlRequestError ? `${e.info.code}: ${e.info.message}` : "preflight thất bại");
    } finally {
      setPreflightBusy(false);
    }
  }, []);

  useEffect(() => {
    if (disabled) return; // CONTROL DISABLED: no polling at all until the trader asks to re-check
    const controller = new AbortController();
    const tick = () => void loadStatus(controller.signal);
    tick();
    const id = setInterval(tick, STATUS_POLL_MS);
    return () => {
      controller.abort();
      clearInterval(id);
    };
  }, [loadStatus, disabled, recheck]);

  useEffect(() => {
    if (disabled) return;
    const controller = new AbortController();
    getControl<PreflightReport>("preflight?probe=true", controller.signal)
      .then(setReport)
      .catch((e: unknown) => {
        if (controller.signal.aborted) return;
        if (isDisabled(e)) setDisabled(true);
        else if (e instanceof ControlRequestError) setError(`${e.info.code}: ${e.info.message}`);
      });
    return () => controller.abort();
  }, [disabled, recheck]);

  useEffect(() => {
    if (disabled) return;
    const load = () =>
      getControl<{ events: JournalEvent[] }>("journal")
        .then((r) => setJournal(r.events))
        .catch((e: unknown) => {
          if (isDisabled(e)) setDisabled(true);
        });
    load();
    const id = setInterval(load, JOURNAL_POLL_MS);
    return () => clearInterval(id);
  }, [disabled, recheck]);

  const submit = useCallback(
    async (path: string, body: Record<string, string>) => {
      setSubmitting(true);
      setNotice(null);
      try {
        const { job } = await postControl(path, body, newIdempotencyKey());
        setNotice(`Đã nhận thao tác ${job.kind}; theo dõi tiến trình bên dưới.`);
      } catch (e) {
        setNotice(e instanceof ControlRequestError ? `Không thực hiện: ${e.info.message}` : "Không gửi được yêu cầu");
      } finally {
        setSubmitting(false);
        void loadStatus();
      }
    },
    [loadStatus],
  );

  const actions = status?.actions;
  const act = (name: ActionName): ActionState | undefined => actions?.[name];
  const busy = submitting || Boolean(status?.active_job);
  const ks = status?.kill_switch;

  if (disabled) {
    return (
      <main className="mx-auto w-full max-w-[1200px] space-y-4 p-4 lg:p-6">
        <header className="flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">Điều khiển bot</h1>
          <Link href="/" className="text-sm underline">
            ← Về dashboard
          </Link>
        </header>
        <section data-testid="control-disabled" role="status" className="rounded-lg border-2 border-slate-500 p-4">
          <p className="text-lg font-bold">CONTROL DISABLED · điều khiển web đang tắt</p>
          <p className="mt-1 text-sm">
            API đang chạy không có điều khiển web (<code>XAU_EDGE_WEB_CONTROL</code> chưa bật), nên trang này không có gì để điều khiển và đã dừng
            hỏi máy chủ. Đây không phải lỗi: bàn PAPER và /trade vẫn hoạt động bình thường.
          </p>
          <button type="button" data-testid="control-recheck" onClick={() => { setDisabled(false); setRecheck((n) => n + 1); }} className="mt-3 rounded-md border border-slate-500 px-3 py-1 text-sm font-semibold">
            Kiểm tra lại
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-[1200px] space-y-4 p-4 lg:p-6">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Điều khiển bot</h1>
          <p className="text-sm text-slate-500">Chỉ chạy cục bộ (127.0.0.1). Chỉ DRY-RUN và DEMO; không có FUNDED/LIVE ở đây.</p>
        </div>
        <ZoneSelect zone={zone} onChange={changeZone} testId="control-zone" />
        <Link href="/" className="text-sm underline">
          ← Về dashboard
        </Link>
      </header>

      <section aria-label="Trạng thái chung" className="flex flex-wrap gap-2 text-sm">
        <span className="rounded-full border border-sky-600 px-3 py-1">Tài khoản: {status?.account_label ?? report?.account_label ?? "chưa xác minh"}</span>
        <span className={`rounded-full border px-3 py-1 ${status?.configured_mode === "DEMO" ? "border-sky-600 font-semibold" : "border-slate-400"}`}>
          Chế độ: {status ? status.configured_mode : "…"}
          {status?.bot.running_mode ? ` (bot đang chạy: ${status.bot.running_mode})` : ""}
        </span>
        <span
          className={`rounded-full border px-3 py-1 ${ks?.tripped ? "border-red-600 font-semibold text-red-700 dark:text-red-300" : "border-slate-400"}`}
        >
          Kill switch: {ks == null ? "…" : ks.tripped ? `TRIPPED (${ks.reason})` : ks.tripped === false ? "bình thường" : "chưa rõ"}
        </span>
        <span className="rounded-full border border-green-600 px-3 py-1 text-green-700 dark:text-green-300">Live: luôn tắt</span>
        {status?.wait_banner && (
          <span role="status" className="rounded-full border border-amber-500 bg-amber-500/15 px-3 py-1 font-semibold text-amber-800 dark:text-amber-300">
            {status.wait_banner}
          </span>
        )}
      </section>

      {error && (
        <p role="alert" className="rounded-md border border-red-500 p-2 text-sm text-red-700 dark:text-red-300">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="rounded-md border border-sky-500 p-2 text-sm">
          {notice}
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <section className={card} aria-label="Preflight">
          <div className="flex items-center justify-between">
            <h2 className={heading}>Preflight</h2>
            <button
              type="button"
              onClick={() => void runPreflight()}
              disabled={preflightBusy}
              className="rounded-md border border-slate-400 px-3 py-1 text-sm disabled:opacity-50"
            >
              {preflightBusy ? "Đang kiểm tra…" : "Chạy lại preflight"}
            </button>
          </div>
          {report ? (
            <>
              <p className="mb-2 text-xs text-slate-500">
                {report.counts.ok} OK · {report.counts.warn} cảnh báo · {report.counts.fail} lỗi · {report.counts.unknown} chưa rõ — terminal:{" "}
                {report.terminal_source === "terminal" ? "đã hỏi trực tiếp (chỉ đọc)" : report.terminal_source === "status.json" ? "theo status.json" : "chưa kiểm tra"}
              </p>
              <ul className="space-y-1">
                {report.checks.map((c) => (
                  <li key={c.id} className={`rounded-md border px-2 py-1 text-sm ${CHECK_STYLE[c.status]}`} data-check={c.id} data-status={c.status}>
                    <div className="flex justify-between gap-2">
                      <span className="font-medium">{c.label}</span>
                      <span className="text-xs font-semibold">{CHECK_TEXT[c.status]}</span>
                    </div>
                    <div className="text-xs">{c.detail}</div>
                    {c.fix_hint && <div className="text-xs italic">Cách sửa: {c.fix_hint}</div>}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="text-sm text-slate-500">Đang chạy preflight…</p>
          )}
        </section>

        <div className="space-y-4">
          <section className={card} aria-label="Bot">
            <h2 className={heading}>Bot</h2>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              <dt className="text-slate-500">Trạng thái</dt>
              <dd className="font-semibold">{status?.bot.state ?? "…"}</dd>
              <dt className="text-slate-500">Cách chạy</dt>
              <dd>{status ? (status.bot.backend === "nssm" ? "dịch vụ NSSM" : "tiến trình con của API") : "…"}</dd>
              <dt className="text-slate-500">Chi tiết</dt>
              <dd>{status?.bot.detail ?? "…"}</dd>
              <dt className="text-slate-500">Chu kỳ cuối</dt>
              <dd>
                {status?.bot.last_cycle
                  ? `${status.bot.last_cycle.direction} ${formatInZone(status.bot.last_cycle.decision_time, zone).slice(5, 16)}`
                  : "chưa có"}
              </dd>
            </dl>
            <div className="mt-3 flex flex-wrap gap-2">
              <ActionButton label="Khởi động" action={act("start")} busy={busy} onClick={() => void submit("bot/start", {})} />
              <ActionButton label="Dừng (mềm)" action={act("stop")} busy={busy} onClick={() => void submit("bot/stop", {})} />
              <ActionButton label="Khởi động lại" action={act("restart")} busy={busy} onClick={() => void submit("bot/restart", {})} />
            </div>
            <Reasons action={act("start")} />
          </section>

          <section className={card} aria-label="Chế độ">
            <h2 className={heading}>Chế độ</h2>
            <p className="text-sm">
              Hiện tại: <strong>{status?.configured_mode ?? "…"}</strong> · trần theo .env: {status?.mode_ceiling ?? "…"}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <ActionButton label="Chuyển sang DEMO…" action={act("mode_demo")} busy={busy} tone="warning" onClick={() => setPending({ kind: "mode_demo" })} />
              <ActionButton label="Về DRY-RUN" action={act("mode_dry_run")} busy={busy} onClick={() => void submit("mode", { mode: "DRY_RUN" })} />
            </div>
            <Reasons action={act("mode_demo")} />
          </section>

          <section className={card} aria-label="Smoke">
            <h2 className={heading}>Smoke test (DEMO)</h2>
            <p className="text-sm">
              1 lệnh BUY 0.01 lot, comment SMOKE, giữ vài giây rồi đóng và đối soát. {status?.smoke_limits}. Chỉ kiểm tra đường ống lệnh —{" "}
              <strong>không phải bằng chứng edge</strong>.
            </p>
            <div className="mt-3">
              <ActionButton label="Chạy smoke…" action={act("smoke")} busy={busy} tone="warning" onClick={() => setPending({ kind: "smoke" })} />
            </div>
            <Reasons action={act("smoke")} />
            {lastJob(status, "smoke") && (
              <div className="mt-2">
                <JobView job={lastJob(status, "smoke") as Job} zone={zone} />
              </div>
            )}
          </section>
        </div>
      </div>

      <section className="rounded-xl border-2 border-red-600 bg-red-500/5 p-4" aria-label="Flatten">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-red-700 dark:text-red-300">Khẩn cấp: Flatten</h2>
        <p className="text-sm">
          Bật kill switch (WEB_FLATTEN) trước, dừng bot, đóng mọi vị thế của bot (đúng magic; không đụng lệnh tay), đối soát. Không tự khởi động lại.
          Reset kill switch chỉ bằng CLI: <code className="break-all">{status?.reset_command}</code>
        </p>
        <div className="mt-3">
          <ActionButton label="FLATTEN…" action={act("flatten")} busy={busy} tone="danger" onClick={() => setPending({ kind: "flatten" })} />
        </div>
        <Reasons action={act("flatten")} />
        {lastJob(status, "flatten") && (
          <div className="mt-2">
            <JobView job={lastJob(status, "flatten") as Job} zone={zone} />
          </div>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className={card} aria-label="Thao tác gần đây">
          <h2 className={heading}>Thao tác gần đây</h2>
          {status?.active_job && <JobView job={status.active_job} zone={zone} />}
          <div className="mt-2 space-y-2">
            {(status?.recent_jobs ?? [])
              .filter((j) => j.id !== status?.active_job?.id)
              .map((j) => (
                <JobView key={j.id} job={j} zone={zone} />
              ))}
            {status && status.recent_jobs.length === 0 && <p className="text-sm text-slate-500">Chưa có thao tác nào.</p>}
          </div>
        </section>
        <section className={card} aria-label="Nhật ký">
          <h2 className={heading}>Nhật ký thực thi</h2>
          <ul className="space-y-0.5 text-xs">
            {journal.length === 0 && <li className="text-slate-500">Chưa có sự kiện.</li>}
            {journal.map((e, i) => (
              <li key={`${e.at}-${i}`} className="flex flex-wrap gap-x-2">
                <span className="tabular-nums text-slate-500">{formatInZone(e.at, zone).slice(5, 19)}</span>
                <span>{e.event}</span>
                {e.source && <span className="text-slate-500">[{e.source}]</span>}
                {e.result && <span>{e.result}</span>}
                {e.error_code && <span className="text-red-700 dark:text-red-300">{e.error_code}</span>}
              </li>
            ))}
          </ul>
        </section>
      </div>

      {pending?.kind === "mode_demo" && (
        <ConfirmDialog
          title="Chuyển bot sang DEMO"
          word="DEMO"
          tone="warning"
          points={[
            "Bot sẽ dừng mềm, chạy preflight mới với terminal, ghi runtime_mode.json = DEMO rồi khởi động lại.",
            "Ở DEMO bot có thể gửi lệnh thật lên tài khoản DEMO khi có tín hiệu hợp lệ (hiện thường là WAIT).",
            "Bị từ chối nếu thiếu whitelist, trade password, Algo Trading hoặc kill switch đang bật.",
          ]}
          onCancel={() => setPending(null)}
          onConfirm={() => {
            setPending(null);
            void submit("mode", { mode: "DEMO", confirm: "DEMO" });
          }}
        />
      )}
      {pending?.kind === "smoke" && (
        <ConfirmDialog
          title="Gửi 1 lệnh smoke lên tài khoản DEMO"
          word="SMOKE"
          tone="warning"
          points={[
            "Dừng bot, giữ lock, gửi 1 lệnh BUY 0.01 lot (comment SMOKE), giữ vài giây rồi đóng.",
            "Đối soát sau khi đóng; khởi động lại bot nếu trước đó đang chạy.",
            "Đây chỉ là kiểm tra đường ống lệnh, không phải bằng chứng edge.",
          ]}
          onCancel={() => setPending(null)}
          onConfirm={() => {
            setPending(null);
            void submit("smoke", { confirm: "SMOKE" });
          }}
        />
      )}
      {pending?.kind === "flatten" && (
        <ConfirmDialog
          title="FLATTEN: đóng mọi vị thế của bot"
          word="FLATTEN"
          tone="danger"
          points={[
            "Kill switch bật NGAY (WEB_FLATTEN), trước mọi việc khác.",
            "Dừng bot; đóng từng vị thế có magic của bot; lệnh tay không bị đụng tới.",
            "Không tự khởi động lại. Reset kill switch chỉ bằng CLI.",
          ]}
          onCancel={() => setPending(null)}
          onConfirm={() => {
            setPending(null);
            void submit("flatten", { confirm: "FLATTEN" });
          }}
        />
      )}
    </main>
  );
}
