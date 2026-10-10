"use client";

import type { Step } from "@/lib/lifecycle";
import { Term } from "@/components/terminal/Term";
import type { ReactNode } from "react";
import type { ActionText, ActionTone } from "@/lib/action";

/**
 * The decision card. TRADE-08 blind A/B (4 reviewers, 20 screenshots): the market's lean is a BIAS shown small and labelled
 * BELOW the action, with the prohibition ("KHÔNG VÀO LỆNH") next to the action word. Not beside it (a big "↑ MUA" next to CHỜ
 * read as "mua, chờ"), not above it (read first), not amber (read as a warning). Only BUY/SELL carry a coloured card.
 */

export const TONE_STYLE: Record<ActionTone, string> = {
  buy: "border-emerald-800 bg-emerald-700 text-white",
  sell: "border-red-800 bg-red-700 text-white",
  hold: "border-sky-700 bg-sky-500/15 text-sky-900 dark:text-sky-100",
  exit: "border-slate-600 bg-slate-500/15 text-slate-900 dark:text-slate-100",
  wait: "border-slate-500 bg-slate-500/10 text-slate-800 dark:text-slate-200",
  error: "border-red-700 bg-red-500/15 text-red-900 dark:text-red-100",
};
export const TONE_ICON: Record<ActionTone, string> = { buy: "▲", sell: "▼", hold: "●", exit: "✓", wait: "⏸", error: "⚠" };

interface Common {
  t: ActionText;
  word: string;
  sub: string;
  whenLabel: string;
  whenBody: string;
  whenShort: string;
  veil: string;
  extra: ReactNode;
  steps: Step[] | null;
}

const arrow = (side: "BUY" | "SELL" | null) => (side === "BUY" ? "↑" : side === "SELL" ? "↓" : "→");

function When({ label, body, short, veil, testId = "action-when" }: { label: string; body: string; short: string; veil: string; testId?: string }) {
  return (
    <p data-testid={testId} className={`mt-2 rounded-md px-2 py-1.5 text-sm ${veil}`}>
      <b>{label}</b>{" "}
      {short !== body ? (
        <>
          <span className="sm:hidden">{short}</span>
          <span className="hidden sm:inline">{body}</span>
        </>
      ) : (
        body
      )}
    </p>
  );
}

export function HeroCard(c: Common) {
  const { t } = c;
  const waiting = t.code === "WAIT";
  return (
    <>
      <div className="hidden text-xs font-semibold uppercase sm:block">Bạn nên làm gì bây giờ?</div>
      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
        <div className="flex items-center gap-2">
          <span aria-hidden="true" className="text-2xl">{TONE_ICON[t.tone]}</span>
          <span data-testid="action-word" className="text-3xl font-black leading-none sm:text-4xl">{c.word}</span>
        </div>
        {waiting && (
          <span data-testid="no-entry" className="rounded border border-dashed border-slate-600 px-1.5 py-0.5 text-[11px] font-bold uppercase tracking-wide dark:border-slate-400">Không vào lệnh</span>
        )}
      </div>
      {/* a phone drops the sub line only where it repeats the "KHÔNG VÀO LỆNH" badge (a lean with no setup yet); every other state keeps it */}
      <p data-testid="action-sub" className={`mt-1 text-sm font-semibold ${waiting && t.bias.side && t.setup === "Chưa có" ? "hidden sm:block" : ""}`}>{c.sub}</p>
      {waiting && (
        <dl data-testid="bias" data-bias={t.bias.side ?? "NONE"} className="mt-1 grid grid-cols-[6rem_1fr] gap-x-2 gap-y-0.5 text-[13px]">
          <dt className="font-bold uppercase tracking-wide opacity-75"><Term id="bias">Thiên hướng</Term></dt>
          <dd data-testid="bias-value">{arrow(t.bias.side)} {t.bias.word}<span className="text-slate-800 dark:text-slate-200"> — {t.bias.side ? "chỉ là hướng thị trường nghiêng về, không phải lệnh" : "chưa có hướng ưu tiên rõ"}</span></dd>
          <dt className="hidden font-bold uppercase tracking-wide opacity-75 sm:block"><Term id="setup">Setup</Term></dt>
          <dd data-testid="setup-stage" className="hidden sm:block">{t.setup}</dd>
        </dl>
      )}
      <When label={c.whenLabel} body={c.whenBody} short={c.whenShort} veil={c.veil} />
      {c.steps && (
        <ol data-testid="lifecycle" aria-label="Vòng đời tín hiệu" className="mt-2 hidden flex-wrap items-center gap-x-1 gap-y-0.5 text-[11px] sm:flex">
          {c.steps.map((st, i) => (
            <li key={st.key} data-step={st.key} data-status={st.status} title={st.at ? `${st.label}: ${st.at}` : st.label} className={st.status === "current" ? "font-black underline" : st.status === "done" ? "font-semibold" : "font-normal"}>
              {i > 0 && <span aria-hidden="true" className="mr-1">→</span>}
              {st.status === "done" ? "✓ " : st.status === "current" ? "● " : "○ "}{st.label}
            </li>
          ))}
        </ol>
      )}
      {c.extra}
    </>
  );
}

