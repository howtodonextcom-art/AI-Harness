"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AnalogueChart } from "@/components/AnalogueChart";
import { BotPanel } from "@/components/BotPanel";
import { PriceChart } from "@/components/PriceChart";
import {
  api,
  type Bar,
  type BotCycle,
  type BotJournalEvent,
  type BotStatus,
  type PatternsResponse,
  type RegimeResponse,
  type PaperAccount,
  type RiskStatus,
  type RunSummary,
  type Signal,
} from "@/lib/api";

interface Snapshot {
  signal: Signal;
  regime: RegimeResponse;
  patterns: PatternsResponse;
  bars: Bar[];
  risk: RiskStatus;
  runs: RunSummary[];
  paper: PaperAccount | null;
  bot: BotStatus | null;
  botCycles: BotCycle[];
  botJournal: BotJournalEvent[];
  fetchedAt: number;
}

const pct = (value: number | null) => (value === null ? "n/a" : `${(value * 100).toFixed(0)}%`);
const num = (value: number | null, digits = 2) => (value === null ? "n/a" : value.toFixed(digits));
const bias = (trend: number) => (trend > 0 ? "Bullish" : trend < 0 ? "Bearish" : "Neutral");

const DECISION_STYLE: Record<string, string> = {
  WAIT: "border-amber-500 bg-amber-500/10 text-amber-600 dark:text-amber-300",
  BUY: "border-green-600 bg-green-600/10 text-green-700 dark:text-green-300",
  SELL: "border-red-600 bg-red-600/10 text-red-700 dark:text-red-300",
};

function Card({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-slate-300/60 bg-white/60 p-4 dark:border-slate-700 dark:bg-slate-900/60 ${className}`}>
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h2>
      {children}
    </section>
  );
}

function ProbabilityBar({ label, value, color }: { label: string; value: number | null; color: string }) {
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="w-16 text-slate-600 dark:text-slate-300">{label}</span>
      <div className="h-3 flex-1 overflow-hidden rounded bg-slate-200 dark:bg-slate-800" role="meter"
        aria-label={`${label} probability`} aria-valuemin={0} aria-valuemax={100}
        aria-valuenow={value === null ? undefined : Math.round(value * 100)}>
        <div className={`h-full ${color}`} style={{ width: `${(value ?? 0) * 100}%` }} />
      </div>
      <span className="w-10 text-right tabular-nums">{pct(value)}</span>
    </div>
  );
}

async function fetchSnapshot(signal: AbortSignal): Promise<Snapshot> {
  const [sig, regime, patterns, bars, risk, runs, paper, bot, botCycles, botJournal] = await Promise.all([
    api.signal(signal),
    api.regime(signal),
    api.patterns(signal),
    api.bars(signal),
    api.risk(signal),
    api.runs(signal),
    api.paper(signal),
    api.bot(signal),
    api.botCycles(signal),
    api.botJournal(signal),
  ]);
  return { signal: sig, regime, patterns, bars: bars.bars, risk, runs: runs.runs, paper, bot, botCycles, botJournal, fetchedAt: Date.now() };
}

export function Dashboard() {
  const [data, setData] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  const refresh = useCallback(() => {
    setLoading(true);
    setReloadKey((k) => k + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchSnapshot(controller.signal)
      .then((snapshot) => {
        setData(snapshot);
        setError(null);
      })
      .catch((e: unknown) => {
        if (!(e instanceof DOMException && e.name === "AbortError")) {
          setError(e instanceof Error ? e.message : "Could not reach the API");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [reloadKey]);

  if (error && !data) {
    return (
      <main className="mx-auto max-w-3xl p-6">
        <h1 className="text-2xl font-semibold">XAU EDGE</h1>
        <p role="alert" className="mt-4 rounded-lg border border-red-500 p-4 text-red-600 dark:text-red-300">
          Cannot reach the API ({error}). Start it with <code>uv run python scripts/serve_api.py</code>.
        </p>
      </main>
    );
  }
  if (!data) {
    return <main className="p-6 text-slate-500">Loading market state...</main>;
  }

  const { signal, regime, patterns, bars, risk, runs, paper, bot, botCycles, botJournal, fetchedAt } = data;
  const last = bars[bars.length - 1];
  const passedRuns = runs.filter((r) => r.passed === true).length;
  const staleHours = (fetchedAt - Date.parse(signal.data_as_of)) / 3_600_000;
  const staleLabel = staleHours < 1 ? "under an hour old" : `${staleHours.toFixed(0)} h old`;

  return (
    <main className={`mx-auto w-full max-w-[1440px] space-y-4 p-4 lg:p-6 ${error ? "opacity-70" : ""}`}>
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">XAU EDGE</h1>
          <p className="text-sm text-slate-500">
            XAUUSD probabilistic decision support. Research only: no orders can be placed.
          </p>
        </div>
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <Link href="/research" className="rounded-md border border-sky-600 px-3 py-1 text-sky-700 dark:text-sky-300">
            Research
          </Link>
          <Link href="/control" className="rounded-md border border-sky-600 px-3 py-1 text-sky-700 dark:text-sky-300">
            Điều khiển
          </Link>
          <span>Decision time {new Date(signal.timestamp).toUTCString()}</span>
          <button type="button" onClick={refresh} disabled={loading}
            className="rounded-md border border-slate-400 px-3 py-1 hover:bg-slate-200 disabled:opacity-50 dark:hover:bg-slate-800">
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </header>

      {error && (
        <p role="alert" className="rounded-md border border-red-500 p-2 text-sm text-red-600 dark:text-red-300">
          Last refresh failed ({error}). The figures below are OLD and may no longer describe the market.
        </p>
      )}
      <p className={`text-xs ${staleHours > 6 ? "font-semibold text-red-600 dark:text-red-300" : "text-slate-500"}`}>
        Data as of {new Date(signal.data_as_of).toUTCString()} ({staleLabel}).
        {staleHours > 6 ? " This dataset is not live." : ""}
      </p>

      <BotPanel bot={bot} cycles={botCycles} journal={botJournal} />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Decision" className="lg:col-span-1">
          <div className={`rounded-lg border-2 p-4 text-center ${DECISION_STYLE[signal.direction]}`}>
            <div className="text-4xl font-bold tracking-wide" data-testid="decision">{signal.direction}</div>
            {signal.candidate_direction && signal.direction === "WAIT" && (
              <div className="mt-1 text-sm">analysis leans {signal.candidate_direction}, but it is not actionable</div>
            )}
          </div>
          <p className="mt-3 text-sm">
            <strong>Why:</strong>{" "}
            {signal.reasons.length === 0
              ? "every check passed and the evidence gate is open"
              : signal.reasons.map((r) => r.replaceAll("_", " ").toLowerCase()).join("; ")}
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Evidence status: <strong>{signal.evidence_status}</strong>. WAIT is a valid answer: a
            high-quality WAIT is worth more than a low-quality BUY or SELL.
          </p>
        </Card>

        <Card title="Probabilities and value" className="lg:col-span-1">
          <div className="space-y-2">
            <ProbabilityBar label="Up" value={signal.prob_up} color="bg-green-600" />
            <ProbabilityBar label="Down" value={signal.prob_down} color="bg-red-600" />
            <ProbabilityBar label="Neutral" value={signal.prob_neutral} color="bg-slate-500" />
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Source: {signal.probability_source}. These are frequencies of what followed similar
            patterns, not calibrated confidence.
          </p>
          <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
            <dt className="text-slate-500">Expected return</dt>
            <dd className="text-right tabular-nums">{num(signal.expected_return === null ? null : signal.expected_return * 100)}%</dd>
            <dt className="text-slate-500">Expected R (after costs)</dt>
            <dd className="text-right tabular-nums">{num(signal.expected_R)}</dd>
            <dt className="text-slate-500">Historical matches</dt>
            <dd className="text-right tabular-nums">{signal.historical_matches_count}</dd>
            <dt className="text-slate-500">Similarity (lower is closer)</dt>
            <dd className="text-right tabular-nums">{num(signal.similarity_quality)}</dd>
          </dl>
        </Card>

        <Card title="Market context" className="lg:col-span-1">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
            <dt className="text-slate-500">Price (M15 close)</dt>
            <dd className="text-right tabular-nums">{last ? last.close.toFixed(2) : "n/a"}</dd>
            <dt className="text-slate-500">Regime</dt>
            <dd className="text-right">{regime.M15.regime ?? "unknown"}</dd>
            <dt className="text-slate-500">H4 bias</dt>
            <dd className="text-right">{bias(regime.H4.trend)}</dd>
            <dt className="text-slate-500">H1 bias</dt>
            <dd className="text-right">{bias(regime.H1.trend)}</dd>
            <dt className="text-slate-500">M15 setup</dt>
            <dd className="text-right">{bias(regime.M15.trend)}</dd>
            <dt className="text-slate-500">M5 trigger</dt>
            <dd className="text-right">{regime.M5.bos || regime.M5.choch ? (regime.M5.bos || regime.M5.choch) > 0 ? "Break up" : "Break down" : "No break"}</dd>
            <dt className="text-slate-500">Risk status</dt>
            <dd className={`text-right ${risk.kill_switch.tripped !== false ? "font-semibold text-red-700 dark:text-red-300" : ""}`}>
              {risk.kill_switch.tripped === true
                ? `BOT KILL SWITCH TRIPPED (${risk.kill_switch.reason})`
                : risk.kill_switch.tripped === false
                  ? "Bot kill switch not tripped"
                  : `Bot kill switch UNKNOWN${risk.kill_switch.error ? ` (${risk.kill_switch.error})` : ""}`}
            </dd>
            <dt className="text-slate-500">News risk</dt>
            <dd className="text-right">{signal.news_status === "unknown" ? "Unknown (no calendar)" : signal.news_status === "risk" ? "High-impact event window" : "Clear"}</dd>
          </dl>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Price, M15 (last 200 bars)">
          <PriceChart bars={bars} />
        </Card>
        <Card title="Current pattern vs top historical analogues">
          <AnalogueChart data={patterns} topN={10} />
          <p className="mt-2 text-xs text-slate-500">
            Amber: the last 30 bars. Grey: the 10 most similar earlier windows, with what followed
            them to the right of the pattern end. The part after the end is context only.
          </p>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Explanation">
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {signal.explanation.map((line, i) => (
              <li key={`${i}-${line}`}>{line}</li>
            ))}
          </ul>
          <p className="mt-3 break-all text-xs text-slate-500">
            Reproduce: inputs {signal.inputs_hash} at commit {signal.code_version.slice(0, 7)}
          </p>
        </Card>
        <Card title="Validation and limits">
          <p className="text-sm">
            {runs.length} recorded runs, {passedRuns} passed the pre-registered criteria.
          </p>
          <p className="mt-2 text-sm">
            Prop profile {risk.prop_profile.name}: daily loss {risk.prop_profile.daily_loss_limit_pct}%,
            maximum loss {risk.prop_profile.max_loss_limit_pct}% ({risk.prop_profile.max_loss_kind}),
            verified {risk.prop_profile.verified_on}. Automation rules: {risk.prop_profile.ea_restrictions}.
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Live trading is {risk.live_trading ? "ENABLED" : "disabled"} and cannot be enabled from
            this application.
          </p>
          <h3 className="mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Paper trading (simulated)
          </h3>
          {paper ? (
            <p className="mt-1 text-sm">
              Balance {paper.balance.toFixed(2)}, equity {paper.equity.toFixed(2)}, open positions{" "}
              {paper.open_positions}. Simulated money only.
            </p>
          ) : (
            <p className="mt-1 text-sm text-slate-500">Paper trading is not running.</p>
          )}
        </Card>
      </div>
    </main>
  );
}
