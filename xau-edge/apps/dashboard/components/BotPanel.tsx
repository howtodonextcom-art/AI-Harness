"use client";

import type { BotCycle, BotJournalEvent, BotStatus } from "@/lib/api";

const SEVERITY_STYLE: Record<string, string> = {
  critical: "border-red-500 bg-red-500/10 text-red-700 dark:text-red-300",
  warning: "border-amber-500 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  info: "border-slate-400 bg-slate-500/10 text-slate-600 dark:text-slate-300",
};

const MODE_LABEL: Record<string, string> = {
  disabled: "Disabled",
  "dry-run": "Dry-run (decides, never sends)",
  demo: "Demo execution",
};

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <>
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right tabular-nums">{value}</dd>
    </>
  );
}

function ageLabel(iso: string): string {
  const minutes = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 60_000));
  return minutes < 90 ? `${minutes} min ago` : `${(minutes / 60).toFixed(1)} h ago`;
}

export function BotPanel({
  bot,
  cycles,
  journal,
}: {
  bot: BotStatus | null;
  cycles: BotCycle[];
  journal: BotJournalEvent[];
}) {
  const box =
    "rounded-xl border border-slate-300/60 bg-white/60 p-4 dark:border-slate-700 dark:bg-slate-900/60";
  if (bot === null) {
    return (
      <section className={box} aria-label="Demo bot">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Demo bot</h2>
        <p className="text-sm text-slate-500">
          The bot status is not available. Start the API with the bot files configured, then run{" "}
          <code>scripts/demo_trader.py</code>.
        </p>
      </section>
    );
  }
  const s = bot.status;
  const lastCycle = s?.last_cycle ?? null;
  return (
    <section className={`${box} space-y-4`} aria-label="Demo bot">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Demo bot</h2>
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="rounded-full border border-slate-400 px-2 py-0.5">
            Mode: {s ? MODE_LABEL[s.mode] : "no status yet"}
          </span>
          <span className="rounded-full border border-green-600 px-2 py-0.5 text-green-700 dark:text-green-300">
            Live trading: always off
          </span>
          <span
            className={`rounded-full border px-2 py-0.5 ${
              bot.kill_switch.tripped
                ? "border-red-500 font-semibold text-red-700 dark:text-red-300"
                : "border-slate-400"
            }`}
          >
            Kill switch: {bot.kill_switch.tripped ? `TRIPPED (${bot.kill_switch.reason})` : bot.kill_switch.known ? "clear" : "unknown"}
          </span>
        </div>
      </div>

      {bot.alerts.length > 0 && (
        <ul className="space-y-1" aria-label="Alerts">
          {bot.alerts.map((a) => (
            <li
              key={a.code}
              role={a.severity === "critical" ? "alert" : undefined}
              className={`rounded-md border px-3 py-1 text-sm ${SEVERITY_STYLE[a.severity]}`}
            >
              <strong>{a.code.replaceAll("_", " ")}</strong>: {a.message}
            </li>
          ))}
        </ul>
      )}

      {s && (
        <div className="grid gap-4 lg:grid-cols-3">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
            <Row label="Terminal" value={s.connected ? "connected" : "UNREACHABLE"} />
            <Row label="Account" value={s.account_demo === null ? "n/a" : s.account_demo ? "DEMO" : "NOT DEMO"} />
            <Row label="Balance" value={s.balance === null ? "n/a" : s.balance.toFixed(2)} />
            <Row label="Equity" value={s.equity === null ? "n/a" : s.equity.toFixed(2)} />
            <Row label="Status updated" value={ageLabel(s.updated_at)} />
            <Row label="News status" value={s.news_status === "unknown" ? "Unknown (no calendar)" : s.news_status} />
          </dl>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
            <Row label="Last decision bar" value={lastCycle?.decision_time ? new Date(lastCycle.decision_time).toUTCString().slice(5, 22) : "n/a"} />
            <Row label="Last signal" value={lastCycle ? lastCycle.direction : "n/a"} />
            <Row label="Order intent" value={lastCycle ? (lastCycle.accepted ? "yes (dry-run)" : "none") : "n/a"} />
            <Row label="Data age" value={lastCycle?.data_age_minutes == null ? "n/a" : `${lastCycle.data_age_minutes.toFixed(0)} min`} />
            <Row
              label="Reconciliation"
              value={s.reconcile_clean === null ? "n/a" : s.reconcile_clean ? "clean" : `DIRTY: ${s.reconcile_codes.join(", ")}`}
            />
          </dl>
          <div className="text-sm">
            <div className="mb-1 text-slate-500">Why no trade (last cycle)</div>
            <p>
              {lastCycle && lastCycle.reasons.length > 0
                ? lastCycle.reasons.map((r) => r.replaceAll("_", " ").toLowerCase()).join("; ")
                : "no refusal reason"}
            </p>
          </div>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Open demo positions</h3>
          {s && s.positions.length > 0 ? (
            <table className="w-full text-left text-xs">
              <thead className="text-slate-500">
                <tr>
                  <th>Ticket</th><th>Side</th><th>Lots</th><th>Entry</th><th>SL</th><th>TP</th><th>Owner</th>
                </tr>
              </thead>
              <tbody>
                {s.positions.map((p) => (
                  <tr key={p.ticket}>
                    <td>{p.ticket}</td>
                    <td>{p.direction > 0 ? "BUY" : "SELL"}</td>
                    <td>{p.lots}</td>
                    <td>{p.entry_price.toFixed(2)}</td>
                    <td>{p.stop_loss.toFixed(2)}</td>
                    <td>{p.take_profit.toFixed(2)}</td>
                    <td>{p.bot_owned ? "bot" : "manual"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-slate-500">No open positions.</p>
          )}
          <h3 className="mb-1 mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Recent decisions</h3>
          <ul className="space-y-1 text-xs">
            {cycles.length === 0 && <li className="text-slate-500">No cycles recorded yet.</li>}
            {[...cycles].reverse().map((c) => (
              <li key={`${c.recorded_at}-${c.reasons.join()}`} className="flex flex-wrap gap-x-2">
                <span className="tabular-nums text-slate-500">{c.decision_time ? c.decision_time.slice(5, 16).replace("T", " ") : "n/a"}</span>
                <strong>{c.direction}</strong>
                <span>{c.accepted ? "intent (dry-run)" : c.reasons.map((r) => r.replaceAll("_", " ").toLowerCase()).join("; ")}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Execution journal</h3>
          <ul className="space-y-1 text-xs">
            {journal.length === 0 && <li className="text-slate-500">No journal events yet.</li>}
            {[...journal].reverse().map((e, i) => (
              <li key={`${e.at}-${i}`} className="flex flex-wrap gap-x-2">
                <span className="tabular-nums text-slate-500">{e.at.slice(5, 19).replace("T", " ")}</span>
                <span>{e.event}</span>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-xs text-slate-500">
            This panel only reads. There is no control here that can place, change or close an order;
            the kill switch is a local command (<code>scripts/kill_switch.py</code>).
          </p>
        </div>
      </div>
    </section>
  );
}
