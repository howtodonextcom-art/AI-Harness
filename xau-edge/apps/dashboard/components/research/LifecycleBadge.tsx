import { StatusBadge, type Tone } from "@/components/research/StatusBadge";
import { type EvidenceLabel, type LifecycleState, LIFECYCLE_STATES } from "@/lib/research";

const TONES: Record<LifecycleState, Tone> = {
  RESEARCH: "neutral",
  REJECTED: "fail",
  PAPER: "info",
  DEMO: "info",
  VALIDATED: "ok",
  FUNDED: "ok",
  WATCH: "warn",
  DEGRADED: "warn",
  DISABLED: "fail",
  RETIRED: "neutral",
};

/** The ONE component that shows a strategy lifecycle state (roadmap section 23.5). */
export function LifecycleBadge({ state }: { state: string }) {
  const known = (LIFECYCLE_STATES as string[]).includes(state);
  return (
    <StatusBadge tone={known ? TONES[state as LifecycleState] : "unknown"} title={known ? `Vòng đời: ${state}` : "Trạng thái không rõ"}>
      {known ? state : `KHÔNG RÕ (${state})`}
    </StatusBadge>
  );
}

const EVIDENCE_TONE: Record<EvidenceLabel, Tone> = { VALIDATED: "ok", UNVALIDATED: "warn", REJECTED: "fail" };

export function ValidationBadge({ label }: { label: EvidenceLabel }) {
  return <StatusBadge tone={EVIDENCE_TONE[label]}>{label}</StatusBadge>;
}
