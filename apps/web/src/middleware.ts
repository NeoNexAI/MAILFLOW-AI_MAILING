/**
 * Protección de rutas en SaaS (`WEB_AUTH=on`): exige sesión para `/app/*` y
 * `/onboarding`. Comprobación optimista por cookie (Better Auth recomienda
 * `getSessionCookie` en middleware; la validación real ocurre en el servidor).
 *
 * En self-host (`WEB_AUTH=off`, por defecto) el middleware es un no-op: la web
 * funciona sin login, como hasta ahora.
 */
import { getSessionCookie } from "better-auth/cookies";
import { type NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest) {
  if (process.env.WEB_AUTH !== "on") {
    return NextResponse.next();
  }
  const sessionCookie = getSessionCookie(request);
  if (!sessionCookie) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/app/:path*", "/onboarding"],
};
