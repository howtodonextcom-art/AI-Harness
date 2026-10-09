import { readFile } from "node:fs/promises";
import path from "node:path";
import type { NextRequest } from "next/server";

/**
 * Server-side proxy to the API's `/control/*` (ADR-0023). The control token is read here from the
 * file the API writes at start (current user only) and is never sent to the browser. Only the
 * listed paths are forwarded; POSTs must come from this dashboard (same Origin, JSON body).
 */

const API_URL = process.env.XAU_EDGE_API_URL ?? "http://127.0.0.1:8000";
const TOKEN_FILE =
  process.env.XAU_EDGE_CONTROL_TOKEN_FILE ?? path.resolve(process.cwd(), "..", "..", "data", "execution", "control_token");
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1"]);
const GET_PATHS = [/^status$/, /^preflight$/, /^bot$/, /^jobs$/, /^jobs\/[a-f0-9]{32}$/, /^journal$/];
const POST_PATHS = new Set(["bot/start", "bot/stop", "bot/restart", "mode", "smoke", "flatten", "lifecycle/demote"]);
const MAX_BODY = 2048;

function deny(status: number, code: string, message: string): Response {
  return Response.json({ detail: { code, message } }, { status });
}

function localHost(request: NextRequest): string | null {
  const host = request.headers.get("host") ?? "";
  const name = host.replace(/:\d+$/, "");
  return LOCAL_HOSTS.has(name) ? host : null;
}

async function readToken(): Promise<string | null> {
  try {
    const token = (await readFile(/*turbopackIgnore: true*/ TOKEN_FILE, "utf8")).trim();
    return token.length >= 32 ? token : null;
  } catch {
    return null;
  }
}

async function forward(request: NextRequest, target: string, init: RequestInit): Promise<Response> {
  const token = await readToken();
  if (token === null) {
    return deny(503, "CONTROL_UNAVAILABLE", "API chưa chạy với XAU_EDGE_WEB_CONTROL=true (không có file token)");
  }
  const headers = new Headers(init.headers);
  headers.set("X-XAU-Control-Token", token);
  try {
    const res = await fetch(`${API_URL}/control/${target}`, { ...init, headers, cache: "no-store" });
    const body = await res.text();
    return new Response(body, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("content-type") ?? "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return deny(502, "API_UNREACHABLE", "không kết nối được API (127.0.0.1)");
  }
}

export async function GET(request: NextRequest, ctx: RouteContext<"/api/control/[...path]">): Promise<Response> {
  if (localHost(request) === null) return deny(403, "BAD_HOST", "chỉ dùng từ localhost");
  const target = (await ctx.params).path.join("/");
  if (!GET_PATHS.some((re) => re.test(target))) return deny(404, "NOT_FOUND", "không có đường dẫn này");
  const probe = request.nextUrl.searchParams.get("probe");
  const query = target === "preflight" && (probe === "true" || probe === "false") ? `?probe=${probe}` : "";
  return forward(request, target + query, { method: "GET" });
}

export async function POST(request: NextRequest, ctx: RouteContext<"/api/control/[...path]">): Promise<Response> {
  const host = localHost(request);
  if (host === null) return deny(403, "BAD_HOST", "chỉ dùng từ localhost");
  const origin = request.headers.get("origin");
  if (origin !== `http://${host}`) return deny(403, "BAD_ORIGIN", "Origin không khớp dashboard");
  const fetchSite = request.headers.get("sec-fetch-site");
  if (fetchSite !== null && fetchSite !== "same-origin") return deny(403, "BAD_ORIGIN", "yêu cầu không cùng nguồn");
  const ctype = (request.headers.get("content-type") ?? "").split(";")[0].trim().toLowerCase();
  if (ctype !== "application/json") return deny(403, "BAD_CONTENT_TYPE", "Content-Type phải là application/json");
  const target = (await ctx.params).path.join("/");
  if (!POST_PATHS.has(target)) return deny(404, "NOT_FOUND", "không có thao tác này");
  const body = await request.text();
  if (body.length > MAX_BODY) return deny(413, "BODY_TOO_LARGE", "nội dung quá lớn");
  const key = request.headers.get("idempotency-key") ?? "";
  return forward(request, target, {
    method: "POST",
    body,
    headers: { "Content-Type": "application/json", "Idempotency-Key": key, Origin: origin },
  });
}
