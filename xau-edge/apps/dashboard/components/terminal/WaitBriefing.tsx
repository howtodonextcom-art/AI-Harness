"use client";

import type { Diagnostic, DiagnosticRow, TradeView } from "@/lib/trade";
import { STAGE_VI, waitingText } from "@/lib/vi";

/**
 * BIAS != ACTION. While the action is CHỜ this card answers, in order: which way the market leans (a description),
 * what I am allowed to do (nothing), what blocks it, what else is missing and what has to happen next. Everything is read
 * from `why_wait.diagnostic` (the server owns the semantics); the browser only words and colours it. Colour is never the
 * only channel: every state carries an icon and a word.
 */

type Side = "BUY" | "SELL" | "NEUTRAL";

const BIAS_STYLE: Record<Side, string> = {
  BUY: "border-emerald-600 bg-emerald-500/10 text-emerald-900 dark:border-emerald-500 dark:text-emerald-100",
  SELL: "border-red-600 bg-red-500/10 text-red-900 dark:border-red-500 dark:text-red-100",
  NEUTRAL: "border-slate-500 bg-slate-500/10 text-slate-800 dark:text-slate-200",
};
const BIAS_ICON: Record<Side, string> = { BUY: "▲", SELL: "▼", NEUTRAL: "—" };
const BIAS_WORD: Record<Side, string> = { BUY: "MUA", SELL: "BÁN", NEUTRAL: "TRUNG TÍNH" };
const BIAS_TEXT: Record<Side, string> = {
  BUY: "H1 đang tăng",
  SELL: "H1 đang giảm",
  NEUTRAL: "H1 chưa rõ hướng",
};

/** Short blocker wording, one line per server refusal code. */
export const BLOCKER_SHORT: Record<string, string> = {
  SPREAD_TOO_WIDE: "Spread M1 quá rộng",
  VOLATILITY_TOO_LOW: "Biến động thấp",
  VOLATILITY_TOO_HIGH: "Biến động bất thường",
  NO_DIRECTION: "H1 chưa có hướng",
  TIMEFRAME_CONFLICT: "H4 hoặc M15 đi ngược H1",
  NO_SETUP: "M15 chưa có pullback",
  NO_TRIGGER: "M5 chưa kích hoạt",
  VOLUME_TOO_LOW: "Tick volume M1 thấp",
  RR_TOO_LOW: "R/R chưa đạt",
  TOO_CLOSE_TO_RESISTANCE: "Sát kháng cự",
  TOO_CLOSE_TO_SUPPORT: "Sát hỗ trợ",
  INVALID_STOP_DISTANCE: "Khoảng cách SL không hợp lệ",
  RISK_LIMIT: "Vượt giới hạn rủi ro",
  MARKET_CLOSED: "Thị trường đóng cửa",
  STALE_DATA: "Dữ liệu cũ",
  UNKNOWN_STATE: "Thiếu dữ liệu",
  COOLDOWN: "Đang nghỉ sau lệnh trước",
  DAILY_LIMIT: "Đã chạm giới hạn ngày",
  NEWS_WINDOW: "Trong cửa sổ tin tức",
  NEWS_UNKNOWN: "Tin tức chưa xác minh",
  BROKER_DISCONNECTED: "Mất kết nối broker",
};

const MISSING_TEXT: Record<string, string> = {
  "H1 direction": "H1 chưa có hướng",
  "H4 / M15 alignment": "H4 hoặc M15 đi ngược hướng H1",
  "M15 setup": "M15 chưa có pullback",
  "M5 trigger": "M5 chưa kích hoạt",
  "M1 execution": "M1 chưa sẵn sàng thực thi",
  "Trade plan": "Kế hoạch lệnh chưa đạt",
};

export const TF_HELP: Record<string, { can: "QUYẾT ĐỊNH" | "CHẶN" | "BỐI CẢNH" | "SETUP" | "TRIGGER" | "THỰC THI"; text: string }> = {
  H4: { can: "CHẶN", text: "Chế độ thị trường. Không tạo MUA/BÁN, chỉ chặn khi đi ngược mạnh." },
  H1: { can: "QUYẾT ĐỊNH", text: "Nguồn duy nhất của hướng MUA/BÁN." },
  M30: { can: "BỐI CẢNH", text: "Bối cảnh để tham khảo, không quyết định và không chặn." },
  M15: { can: "SETUP", text: "Tìm setup: pullback trong xu hướng H1." },
  M5: { can: "TRIGGER", text: "Xác nhận trigger theo hướng H1." },
  M1: { can: "THỰC THI", text: "Kiểm tra chất lượng vào lệnh (spread, nhiễu). Chỉ được chặn." },
};

const num = (v: number | null | undefined, d = 2) => (v === null || v === undefined ? "—" : v.toFixed(d));
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${(v * 100).toFixed(1)}%`);

function Mark({ status, info = false }: { status: DiagnosticRow["status"] | "INFO"; info?: boolean }) {
  if (info || status === "INFO") return <span aria-hidden="true" className="w-4 text-center font-bold text-sky-700 dark:text-sky-300">i</span>;
  if (status === "PASS") return <span aria-hidden="true" className="w-4 text-center font-bold text-emerald-700 dark:text-emerald-400">✓</span>;
  if (status === "FAIL") return <span aria-hidden="true" className="w-4 text-center font-bold text-red-700 dark:text-red-400">✗</span>;
  return <span aria-hidden="true" className="w-4 text-center font-bold text-slate-600 dark:text-slate-400">○</span>;
}

const STATUS_VI = { PASS: "đạt", FAIL: "chặn / thiếu", NOT_EVALUATED: "chưa đánh giá", INFO: "chỉ để tham khảo" } as const;

export function BiasAction({ d }: { d: Diagnostic }) {
  const side = d.bias.side;
  const waiting = d.action === "WAIT";
  return (
    <div data-testid="bias-action" data-bias={side} className="grid grid-cols-2 gap-2">
      <div data-testid="bias-card" role="group" aria-label={`Thiên hướng: ${BIAS_WORD[side]}. ${BIAS_TEXT[side]}.`} className={`rounded-md border-l-4 border px-2 py-1.5 ${BIAS_STYLE[side]}`}>
        <div className="text-[10px] font-bold uppercase tracking-wide">Thiên hướng</div>
        <div className="text-base font-black leading-tight">
          <span data-testid="bias-side">{side === "NEUTRAL" ? "— TRUNG TÍNH" : `${BIAS_ICON[side]} ${BIAS_WORD[side]}`}</span>
        </div>
        <div className="text-xs">{BIAS_TEXT[side]}</div>
      </div>
      <div data-testid="action-card" className="rounded-md border-2 border-amber-700 bg-amber-500/10 px-2 py-1.5 text-amber-950 dark:border-amber-500 dark:text-amber-100">
        <div className="text-[10px] font-bold uppercase tracking-wide">Hành động</div>
        <div className="text-base font-black leading-tight"><span aria-hidden="true">⏸ </span>{waiting ? "CHỜ" : d.action}</div>
        <div className="text-xs font-semibold">Chưa được vào lệnh</div>
      </div>
      {waiting && (
        <p data-testid="bias-note" className="col-span-2 text-xs text-slate-800 dark:text-slate-200">
          {side === "NEUTRAL" ? "H1 chưa có hướng rõ." : "Đây là thiên hướng, không phải tín hiệu. Thiên hướng không phải quyền vào lệnh."}
        </p>
      )}
    </div>
  );
}

function Blockers({ d }: { d: Diagnostic }) {
  const primary = d.primary_blocker;
  const others = (d.blockers ?? []).filter((c) => c !== primary);
  const gate = d.primary_stage === "Spread & regime";
  const missing = d.rows
    .filter((r) => r.status === "FAIL" && r.stage !== d.primary_stage && r.stage !== "M1 execution" && r.stage !== "Spread & regime")
    .map((r) => r.stage);
  const waits = [primary, ...others].filter((c): c is string => Boolean(c)).map((c) => waitingText(c, null, { phase: null, age: null }) ?? BLOCKER_SHORT[c] ?? c);
  const next = [...waits.map((w, i) => (i === 0 ? `Chờ ${w}` : w)), ...missing.map((m) => `${(STAGE_VI[m] ?? m).replace(/^Hướng /, "")}`)];
  return (
    <div data-testid="blockers" className="space-y-1 text-sm">
      {primary && (
        <p data-testid="primary-blocker" className="rounded-md border border-amber-700 bg-amber-500/10 px-2 py-1 font-semibold text-amber-950 dark:border-amber-500 dark:text-amber-100">
          <span aria-hidden="true">⚠ </span>
          <span className="text-[10px] font-bold uppercase tracking-wide">Blocker chính </span>
          {BLOCKER_SHORT[primary] ?? primary}
        </p>
      )}
      {others.length > 0 && (
        <p data-testid="other-blockers" className="px-2 text-amber-950 dark:text-amber-100">
          <span aria-hidden="true">⚠ </span>
          <span className="text-[10px] font-bold uppercase tracking-wide">Blocker khác </span>
          {others.map((c) => BLOCKER_SHORT[c] ?? c).join(" · ")}
        </p>
      )}
      {missing.length > 0 && (
        <ul data-testid="missing" aria-label="Còn thiếu" className="px-2">
          {missing.map((m) => (
            <li key={m}>
              <span aria-hidden="true">○ </span>
              <span className="text-[10px] font-bold uppercase tracking-wide">{m === "M15 setup" ? "Setup " : m === "M5 trigger" ? "Trigger " : "Còn thiếu "}</span>
              {MISSING_TEXT[m] ?? m}
            </li>
          ))}
        </ul>
      )}
      {next.length > 0 && (
        <p data-testid="next-steps" className="px-2 text-slate-800 dark:text-slate-200">
          <span className="text-[10px] font-bold uppercase tracking-wide">Tiếp theo </span>
          {next.join(" → ")}
          {gate ? "" : ""}
        </p>
      )}
    </div>
  );
}

function Formation({ d, validBars }: { d: Diagnostic; validBars: number }) {
  const f = d.formation;
  if (!f || d.bias.side === "NEUTRAL") return null;
  const side = d.bias.side === "BUY" ? "MUA" : "BÁN";
  const text =
    f.state === "FORMING" ? `SETUP ${side} ĐANG HÌNH THÀNH${f.bars_since_armed !== null && f.bars_since_armed !== undefined ? ` · nến ${f.bars_since_armed}/${validBars} · còn ${Math.max(validBars - f.bars_since_armed, 0)} nến` : ""} · chờ M5 trigger` :
    f.state === "WAITING_TRIGGER" ? `Setup ${side} đã có, chờ M5 trigger` :
    f.state === "READY" ? `Sẵn sàng ${side}` :
    "Chưa có setup";
  return <p data-testid="formation" data-formation={f.state} className="px-2 text-sm"><span className="text-[10px] font-bold uppercase tracking-wide">Hình thành </span><span aria-hidden="true">{f.state === "NO_SETUP" ? "○ " : "◐ "}</span>{text}</p>;
}

export function Stepper({ d, m30, tf, onFocusTf }: { d: Diagnostic; m30: string | null; tf: string; onFocusTf: (tf: string) => void }) {
  const pass = d.rows.filter((r) => r.status === "PASS").length;
  const fail = d.rows.filter((r) => r.status === "FAIL").length;
  const notEval = d.rows.filter((r) => r.status === "NOT_EVALUATED").length;
  return (
    <div data-testid="why-wait">
      <p data-testid="stages-progress" className="mb-1 text-sm font-semibold">
        Điều kiện bắt buộc: <span className="text-emerald-800 dark:text-emerald-300">{pass} đạt</span> · <span className="text-red-800 dark:text-red-300">{fail} chặn/thiếu</span> · <span>{notEval} chưa đánh giá</span> (tổng {d.rows.length})
      </p>
      <ol data-testid="stages" className="space-y-0.5 text-sm" aria-label="Tiến trình hình thành lệnh">
        {d.rows.map((s) => (
          <li key={s.stage}>
            <button
              type="button"
              data-testid={`stage-${s.stage.replace(/[^A-Za-z0-9]+/g, "-")}`}
              data-timeframe={s.timeframe}
              data-status={s.status}
              aria-label={`${STAGE_VI[s.stage] ?? s.stage}: ${STATUS_VI[s.status]}. Xem biểu đồ ${s.timeframe}`}
              onClick={() => onFocusTf(s.timeframe)}
              className={`flex w-full items-center gap-2 rounded px-1.5 py-0.5 text-left hover:bg-slate-500/10 ${tf === s.timeframe ? "bg-sky-500/10" : ""}`}
            >
              <Mark status={s.status} />
              <span className="flex-1">{STAGE_VI[s.stage] ?? s.stage}{s.status !== "NOT_EVALUATED" && s.stage !== "Trade plan" ? <span className="ml-1 text-xs text-slate-600 dark:text-slate-400">({s.observed})</span> : null}</span>
              <span className="text-xs text-slate-600 dark:text-slate-400">{s.timeframe}</span>
            </button>
          </li>
        ))}
        {m30 && (
          <li>
            <span data-testid="stage-M30-context" data-status="INFO" aria-label="M30: chỉ để tham khảo, không phải điều kiện" className="flex w-full items-center gap-2 rounded px-1.5 py-0.5 text-slate-700 dark:text-slate-300">
              <Mark status="INFO" info />
              <span className="flex-1">M30 <span className="text-xs">({m30})</span> <b className="text-[10px] uppercase tracking-wide">chỉ tham khảo</b></span>
              <span className="text-xs">M30</span>
            </span>
          </li>
        )}
      </ol>
    </div>
  );
}

export function ExecutionCard({ d }: { d: Diagnostic }) {
  const e = d.execution;
  if (!e) return null;
  const spreadBlocked = (d.blockers ?? []).includes("SPREAD_TOO_WIDE");
  const volBlocked = (d.blockers ?? []).includes("VOLATILITY_TOO_LOW") || (d.blockers ?? []).includes("VOLATILITY_TOO_HIGH");
  const volWord = e.volatility_regime === "LOW" ? "THẤP" : e.volatility_regime === "HIGH" ? "CAO" : e.volatility_regime === "NORMAL" ? "BÌNH THƯỜNG" : e.volatility_regime;
  const m1 = e.m1_state === "QUIET" ? "YÊN" : e.m1_state === "ABNORMAL" ? "BẤT THƯỜNG" : e.m1_state.startsWith("ACTIVE") ? "SÔI ĐỘNG" : e.m1_state === "UNKNOWN" ? "CHƯA RÕ" : "BÌNH THƯỜNG";
  const tone = (blocked: boolean) => (blocked ? "text-amber-950 dark:text-amber-100 font-bold" : "text-emerald-900 dark:text-emerald-200");
  return (
    <div data-testid="execution-card" className={`rounded-md border px-2 py-1.5 text-sm ${spreadBlocked || volBlocked ? "border-amber-700 bg-amber-500/10 dark:border-amber-500" : "border-slate-400 dark:border-slate-600"}`}>
      <div className="text-[10px] font-bold uppercase tracking-wide">{spreadBlocked || volBlocked ? "⚠ Execution blocker" : "Execution"}</div>
      <ul className="mt-0.5 space-y-0.5">
        <li data-testid="exec-spread" className={tone(spreadBlocked)}>
          {spreadBlocked ? "⚠" : "✓"} Spread: {num(e.spread_points, 0)} điểm · {spreadBlocked ? "CHẶN" : "TỐT"}
          <span className="block text-xs font-normal text-slate-700 dark:text-slate-300">
            phân vị {pct(e.spread_percentile)} (giới hạn {pct(e.spread_percentile_limit)}) · spread/ATR M5 {num(e.spread_to_atr_m5, 3)} (giới hạn {num(e.spread_to_atr_limit, 2)})
          </span>
        </li>
        <li data-testid="exec-vol" className={tone(volBlocked)}>
          {volBlocked ? "⚠" : "✓"} Biến động: {volWord}{volBlocked ? " · CHẶN" : ""}
          <span className="block text-xs font-normal text-slate-700 dark:text-slate-300">
            ATR M15 {num(e.atr_m15, 2)} · phân vị {pct(e.atr_percentile)} (tối thiểu {pct(e.atr_percentile_min)})
          </span>
        </li>
        <li data-testid="exec-m1">M1: {m1}</li>
      </ul>
    </div>
  );
}

export function ColorLegend() {
  return (
    <details data-testid="color-legend" className="text-xs">
      <summary className="inline cursor-pointer text-slate-700 underline decoration-dotted dark:text-slate-300">Chú giải màu</summary>
      <ul className="mt-1 space-y-0.5">
        <li><b className="text-emerald-800 dark:text-emerald-300">▲ Xanh lá</b>: thiên hướng MUA (hoặc quyền MUA khi nhãn ghi MUA PAPER)</li>
        <li><b className="text-red-800 dark:text-red-300">▼ Đỏ</b>: thiên hướng BÁN (hoặc quyền BÁN khi nhãn ghi BÁN PAPER). ✕ SL và lỗi hệ thống dùng thêm biểu tượng, không chỉ màu</li>
        <li><b className="text-amber-900 dark:text-amber-200">⏸ Hổ phách</b>: CHỜ, thận trọng, blocker thực thi</li>
        <li><b className="text-sky-800 dark:text-sky-300">● Xanh dương</b>: đang GIỮ vị thế, thông tin</li>
        <li><b className="text-slate-700 dark:text-slate-300">○ Xám</b>: trung tính, chưa đánh giá, không khả dụng</li>
        <li className="font-semibold">Màu hướng không đồng nghĩa được phép vào lệnh.</li>
      </ul>
    </details>
  );
}

/** The whole WAIT explanation; the caller renders it only while the action is CHỜ and a diagnostic exists. */
export function WaitBriefing({ view, tf, onFocusTf }: { view: TradeView; tf: string; onFocusTf: (tf: string) => void }) {
  const d = view.why_wait?.diagnostic;
  if (!d) return null;
  const m30 = view.timeframes?.find((t) => t.timeframe === "M30")?.state ?? null;
  return (
    <div data-testid="wait-briefing" className="space-y-2">
      <BiasAction d={d} />
      <Blockers d={d} />
      <Formation d={d} validBars={view.setup?.valid_bars ?? 6} />
      <ExecutionCard d={d} />
      <Stepper d={d} m30={m30} tf={tf} onFocusTf={onFocusTf} />
      <ColorLegend />
    </div>
  );
}

/** A thin line above the chart while the action is CHỜ: the lean, never a plan (no Entry / SL / TP is drawn for it). */
export function ChartBiasStrip({ view }: { view: TradeView }) {
  const d = view.why_wait?.diagnostic;
  if (!d || d.action !== "WAIT" || d.bias.side === "NEUTRAL" || view.hero.action.code !== "WAIT") return null;
  const buy = d.bias.side === "BUY";
  return (
    <div
      data-testid="chart-bias-strip"
      data-bias={d.bias.side}
      role="status"
      className={`rounded-sm border-l-4 px-2 py-0.5 text-xs font-semibold ${buy ? "border-emerald-600 bg-emerald-500/5 text-emerald-900 dark:text-emerald-200" : "border-red-600 bg-red-500/5 text-red-900 dark:text-red-200"}`}
    >
      <span aria-hidden="true">{buy ? "▲" : "▼"} </span>
      {buy ? "H1 BIAS: MUA" : "H1 BIAS: BÁN"} · {d.formation?.state === "WAITING_TRIGGER" ? "CHỜ TRIGGER" : "CHỜ SETUP"} · chưa được vào lệnh
    </div>
  );
}
