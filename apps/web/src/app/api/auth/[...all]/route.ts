/**
 * Route handler de Better Auth (signup / login / sesiones / orgs).
 *
 * En self-host (`WEB_AUTH=off`) la auth web está desactivada: devuelve 404 para
 * no exponer endpoints de auth que no aplican.
 */
import { auth, authEnabled } from "@/lib/auth";
import { toNextJsHandler } from "better-auth/next-js";

function disabled(): Response {
  return new Response(JSON.stringify({ error: "auth_disabled" }), {
    status: 404,
    headers: { "Content-Type": "application/json" },
  });
}

const handlers =
  authEnabled && auth
    ? toNextJsHandler(auth)
    : { GET: disabled, POST: disabled };

export const GET = handlers.GET;
export const POST = handlers.POST;
