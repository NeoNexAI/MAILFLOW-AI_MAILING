/**
 * Proxy BFF: el navegador llama a `/api/mf/*` (mismo origen) y este handler
 * reenvía al FastAPI por la red interna añadiendo la `X-API-Key` resuelta en el
 * servidor. Así la API key nunca viaja al navegador.
 *
 * Solo se permiten prefijos de datos conocidos; `/internal/*` jamás se expone.
 */
import { API_INTERNAL_URL, resolveApiKey } from "@/lib/server-api";
import { type NextRequest, NextResponse } from "next/server";

// Allowlist por primer segmento de la ruta. Nunca incluir "internal".
const ALLOWED_PREFIXES = new Set([
  "accounts",
  "llm-providers",
  "oauth",
  "billing",
  "health",
]);

function buildForwardHeaders(
  request: NextRequest,
  apiKey: string | null,
): Headers {
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers.set("content-type", contentType);
  }
  if (apiKey) {
    headers.set("X-API-Key", apiKey);
  }
  return headers;
}

async function proxy(
  request: NextRequest,
  ctx: { params: Promise<{ path?: string[] }> },
): Promise<Response> {
  const { path = [] } = await ctx.params;
  if (path.length === 0 || !ALLOWED_PREFIXES.has(path[0])) {
    return NextResponse.json({ detail: "not_found" }, { status: 404 });
  }

  const resolution = await resolveApiKey(request.headers);
  if (!resolution.ok) {
    return NextResponse.json(
      { detail: resolution.error },
      { status: resolution.status },
    );
  }

  const target = `${API_INTERNAL_URL}/${path.join("/")}${request.nextUrl.search}`;
  const init: RequestInit = {
    method: request.method,
    headers: buildForwardHeaders(request, resolution.apiKey),
    cache: "no-store",
  };
  if (request.method !== "GET" && request.method !== "HEAD") {
    const body = await request.arrayBuffer();
    if (body.byteLength > 0) {
      init.body = body;
    }
  }

  const res = await fetch(target, init);
  const payload = await res.arrayBuffer();
  return new Response(payload, {
    status: res.status,
    headers: {
      "Content-Type": res.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store",
    },
  });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
