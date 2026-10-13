import type { NextRequest } from "next/server";

/**
 * Server-side proxy for the two PAPER desk actions (`/trade/paper/open`, `/trade/paper/close`).
 * Only those two paths are forwarded; POSTs must come from this dashboard (same Origin, JSON body).
 * The API re-checks everything and can only reach the paper desk, never MT5.
 */

const API_URL = process.env.XAU_EDGE_API_URL ?? "http://127.0.0.1:8000";
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1"]);
const POST_PATHS = new Set(["paper/open", "paper/close"]);
const MAX_BODY = 1024;

function deny(status: number, code: string, message: string): Response {
  return Response.json({ detail: { code, message } }, { status });
}

export async function POST(request: NextRequest, ctx: RouteContext<"/api/trade/[...path]">): Promise<Response> {
  const host = request.headers.get("host") ?? "";
  if (!LOCAL_HOSTS.has(host.replace(/:\d+$/, ""))) return deny(403, "BAD_HOST", "chỉ dùng từ localhost");
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
  try {
    const res = await fetch(`${API_URL}/trade/${target}`, {
      method: "POST",
      body,
      cache: "no-store",
      headers: { "Content-Type": "application/json", "X-Paper-Desk": "1", Origin: "http://localhost:3000" },
    });
    return new Response(await res.text(), {
      status: res.status,
      headers: { "Content-Type": res.headers.get("content-type") ?? "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    return deny(502, "API_UNREACHABLE", "không kết nối được API (127.0.0.1)");
  }
}
