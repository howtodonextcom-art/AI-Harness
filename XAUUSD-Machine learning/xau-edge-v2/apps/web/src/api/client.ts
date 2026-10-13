import type { components } from "./schema";

export type State = components["schemas"]["StateSnapshot"];
export type Health = components["schemas"]["HealthResponse"];
export type WsEvent = components["schemas"]["WsEvent"];
export type Bars = components["schemas"]["BarsResponse"];
export type Forming = components["schemas"]["FormingResponse"];
export type Quote = components["schemas"]["QuoteResponse"];
export type FormingBar = components["schemas"]["FormingBar"];
export type PaperSummary = components["schemas"]["PaperSummary"];
export type PaperPosition = components["schemas"]["PaperPositionView"];
export type PaperPositions = components["schemas"]["PaperPositionsResponse"];
export type JournalEvent = components["schemas"]["JournalEventView"];
export type PaperAction = components["schemas"]["PaperActionResult"];
export type ModelDetail = components["schemas"]["ModelDetail"];
export type ForwardSummary = components["schemas"]["ForwardSummary"];
export type SystemAdvice = components["schemas"]["SystemAdvice"];
export type M1Execution = components["schemas"]["M1Execution"];
export type HumanRecord = components["schemas"]["HumanRecord"];
export type HumanChoice = components["schemas"]["HumanChoice"];
export type Intelligence = components["schemas"]["MarketIntelligence"];
export type IntelScenario = components["schemas"]["ScenarioView"];
export type IntelStep = components["schemas"]["FunnelStep"];
export type IntelGate = components["schemas"]["GateView"];
export type Readiness = State["readiness"];
export type Action = State["action"];

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { cache: "no-store", signal });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return (await response.json()) as T;
}

export const fetchState = (signal?: AbortSignal) => getJson<State>("/api/v2/state", signal);
export const fetchIntelligence = (signal?: AbortSignal) =>
  getJson<Intelligence>("/api/v2/intelligence", signal);
export const fetchHealth = (signal?: AbortSignal) => getJson<Health>("/api/v2/health", signal);
export const fetchForming = (signal?: AbortSignal) => getJson<Forming>("/api/v2/market/forming", signal);

export function fetchBars(
  timeframe: string,
  limit: number,
  before: string | null,
  signal?: AbortSignal,
): Promise<Bars> {
  const query = new URLSearchParams({ timeframe, limit: String(limit) });
  if (before) query.set("before", before);
  return getJson<Bars>(`/api/v2/market/bars?${query.toString()}`, signal);
}

export const fetchPaperSummary = (signal?: AbortSignal) => getJson<PaperSummary>("/api/v2/paper/summary", signal);
export const fetchPaperPositions = (signal?: AbortSignal) =>
  getJson<PaperPositions>("/api/v2/paper/positions?limit=300", signal);
export const fetchJournal = (signal?: AbortSignal) =>
  getJson<{ events: JournalEvent[] }>("/api/v2/paper/journal?limit=100", signal);

/** A write: the server recomputes everything, the client sends no price, size or level. */
export async function postPaper(path: string): Promise<PaperAction> {
  const response = await fetch(path, { method: "POST", cache: "no-store" });
  const body = (await response.json()) as PaperAction | { error_code: string; message: string };
  if (!response.ok) {
    const e = body as { error_code: string; message: string };
    throw new Error(`${e.error_code}: ${e.message}`);
  }
  return body as PaperAction;
}
export const openCurrentPlan = () => postPaper("/api/v2/paper/open-current");
export const closePosition = (id: string) => postPaper(`/api/v2/paper/positions/${encodeURIComponent(id)}/close`);

export const fetchModel = (signal?: AbortSignal) => getJson<ModelDetail>("/api/v2/model", signal);
export const fetchForward = (signal?: AbortSignal) => getJson<ForwardSummary>("/api/v2/forward/summary", signal);

export const fetchHumanDecisions = (signal?: AbortSignal) =>
  getJson<{ decisions: HumanRecord[] }>("/api/v2/human/decisions?limit=100", signal);

/**
 * The human's answer. Only the choice, the candidate it is about (setup_id) and a reason travel:
 * every number in the stored record is taken by the server from its own analysis.
 */
export async function postHuman(
  choice: HumanChoice,
  setupId: string,
  reason: string,
): Promise<{ message: string; record: HumanRecord }> {
  const response = await fetch("/api/v2/human/decision", {
    method: "POST",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ choice, setup_id: setupId, reason }),
  });
  const body = (await response.json()) as
    | { message: string; record: HumanRecord }
    | { error_code: string; message: string };
  if (!response.ok) {
    const e = body as { error_code: string; message: string };
    throw new Error(`${e.error_code}: ${e.message}`);
  }
  return body as { message: string; record: HumanRecord };
}
