import type { StatusStrip as Strip } from "@/lib/trade";
import { BAD, GOOD, INFO, NEUTRAL, Pill, WARN } from "@/components/trade/ui";

function tone(group: string, state: string): string {
  if (group === "data") return state === "GOOD" ? GOOD : state === "CLOSED" ? NEUTRAL : BAD;
  if (group === "core") return state === "RUNNING" ? GOOD : BAD;
  if (group === "desk") return state === "READY" ? GOOD : BAD;
  if (group === "forward") return state === "F3" || state === "F4" ? GOOD : WARN;
  if (group === "demo") return state === "LOCKED" ? INFO : WARN;
  return WARN; // strategy, edge
}

/** One compact line that removes any doubt about what is "ready": data, core, strategy, desk, evidence. */
export function StatusStrip({ strip, mode }: { strip: Strip | undefined; mode: string | undefined }) {
  if (!strip) return null;
  const chips: { id: string; group: string; label: string; value: string; detail: string }[] = [
    { id: "data", group: "data", label: "DATA", value: strip.data.state, detail: strip.data.detail },
    { id: "core", group: "core", label: "TRADING CORE", value: strip.trading_core.state, detail: strip.trading_core.detail },
    { id: "strategy", group: "strategy", label: "ACTIVE STRATEGY", value: strip.strategy.label, detail: "the baseline that is running now" },
    { id: "desk", group: "desk", label: "PAPER DESK", value: strip.paper_desk.state, detail: strip.paper_desk.detail },
    { id: "forward", group: "forward", label: "FORWARD ACCEPTANCE", value: strip.forward.state, detail: strip.forward.detail },
    { id: "demo", group: "demo", label: "DEMO", value: strip.demo.state, detail: strip.demo.detail },
    { id: "edge", group: "edge", label: "EDGE", value: strip.edge.state, detail: strip.edge.detail },
  ];
  return (
    <div data-testid="status-strip" role="group" aria-label="Trạng thái hệ thống" className="flex flex-wrap items-center gap-1.5">
      {mode && mode !== "LIVE" && <Pill value={`${mode.replace("_", " ")} — NOT LIVE`} tone={BAD} testId="source-mode-pill" />}
      {chips.map((c) => (
        <span key={c.id} title={c.detail}>
          <Pill testId={`status-${c.id}`} label={c.label} value={c.value} tone={tone(c.group, c.value)} />
        </span>
      ))}
    </div>
  );
}
