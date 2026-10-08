/**
 * Client for the local web control plane (ADR-0023), always through this dashboard's own server
 * route `/api/control/*`. The browser never sees the control token: the Next.js server reads it from
 * the token file and adds it. No function here takes an order parameter.
 */

export type CheckStatus = "ok" | "warn" | "fail" | "unknown";

export interface PreflightCheck {
  id: string;
  label: string;
  status: CheckStatus;
  detail: string;
  fix_hint: string;
}

export interface Blocker {
  code: string;
  message: string;
}

export interface PreflightReport {
  generated_at: string;
  checks: PreflightCheck[];
  has_fail: boolean;
  counts: Record<CheckStatus, number>;
  terminal_source: "terminal" | "status.json" | "none";
  account_label: string | null;
  strategy_validated: boolean | null;
  configured_mode: "DRY_RUN" | "DEMO";
  mode_ceiling: "DRY_RUN" | "DEMO";
  demo_blockers: Blocker[];
  demo_unverified: string[];
  smoke_enabled: boolean;
}

export type ActionName = "start" | "stop" | "restart" | "mode_demo" | "mode_dry_run" | "smoke" | "flatten";

export interface ActionState {
  allowed: boolean;
  blockers: Blocker[];
}

export interface JobStep {
  at: string;
  message: string;
}

export interface Job {
  id: string;
  kind: string;
  status: "RUNNING" | "SUCCEEDED" | "FAILED" | "REFUSED";
  created_at: string;
  finished_at: string | null;
  steps: JobStep[];
  result: Record<string, unknown>;
  error_code: string | null;
  message: string;
}

export interface ControlStatus {
  now: string;
  bot: {
    state: "STOPPED" | "STARTING" | "RUNNING" | "STOPPING" | "ERROR";
    backend: "nssm" | "subprocess";
    pid: number | null;
    detail: string;
    running_mode: string | null;
    status_updated_at: string | null;
    last_cycle: { decision_time: string | null; direction: string; reasons: string[] } | null;
  };
  configured_mode: "DRY_RUN" | "DEMO";
  mode_ceiling: "DRY_RUN" | "DEMO";
  kill_switch: { tripped: boolean | null; reason: string };
  account_label: string | null;
  strategy_validated: boolean | null;
  wait_banner: string | null;
  preflight: { generated_at: string; has_fail: boolean; counts: Record<CheckStatus, number>; last_probe_at: string | null };
  actions: Record<ActionName, ActionState>;
  active_job: Job | null;
  recent_jobs: Job[];
  reset_command: string;
  smoke_limits: string;
}

export interface JournalEvent {
  at?: string;
  event?: string;
  source?: string;
  result?: string;
  error_code?: string;
  mode?: string;
  ticket?: string;
  retcode?: number;
}

export interface ControlError {
  status: number;
  code: string;
  message: string;
  blockers: Blocker[];
}

export class ControlRequestError extends Error {
  constructor(public readonly info: ControlError) {
    super(info.message);
  }
}

const BASE = "/api/control";

async function parse<T>(res: Response): Promise<T> {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (body as { detail?: Partial<ControlError> }).detail ?? {};
    throw new ControlRequestError({
      status: res.status,
      code: detail.code ?? `HTTP_${res.status}`,
      message: detail.message ?? "yêu cầu thất bại",
      blockers: detail.blockers ?? [],
    });
  }
  return body as T;
}

export async function getControl<T>(path: string, signal?: AbortSignal): Promise<T> {
  return parse<T>(await fetch(`${BASE}/${path}`, { cache: "no-store", signal }));
}

/** POST with a fresh idempotency key per click; the body only ever holds a mode or a confirmation word. */
export async function postControl(path: string, body: Record<string, string>, key: string): Promise<{ job: Job; replayed: boolean }> {
  const res = await fetch(`${BASE}/${path}`, {
    method: "POST",
    cache: "no-store",
    headers: { "Content-Type": "application/json", "Idempotency-Key": key },
    body: JSON.stringify(body),
  });
  return parse<{ job: Job; replayed: boolean }>(res);
}

export function newIdempotencyKey(): string {
  return crypto.randomUUID().replaceAll("-", "");
}
