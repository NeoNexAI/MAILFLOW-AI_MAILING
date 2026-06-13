/**
 * Resolución server-side de la API key con la que el proxy BFF habla con el
 * FastAPI. La key nunca llega al navegador.
 *
 *  - self-host (`WEB_AUTH=off`): usa `SINGLE_TENANT_API_KEY` (puede ir vacía si
 *    el API local está abierto).
 *  - SaaS (`WEB_AUTH=on`): exige sesión de Better Auth, lee la org activa y
 *    descifra su API key del metadata (cifrada en Part B).
 */
import { auth, authEnabled } from "@/lib/auth";
import { decryptSecret } from "@/lib/crypto";

export const API_INTERNAL_URL =
  process.env.API_INTERNAL_URL ?? "http://localhost:8000";

export type KeyResolution =
  | { ok: true; apiKey: string | null }
  | { ok: false; status: number; error: string };

interface OrgMeta {
  mf_api_key_enc?: string;
  mf_org_id?: string;
}

function parseMeta(raw: unknown): OrgMeta {
  if (typeof raw === "string") {
    try {
      return JSON.parse(raw) as OrgMeta;
    } catch {
      return {};
    }
  }
  if (raw && typeof raw === "object") {
    return raw as OrgMeta;
  }
  return {};
}

export async function resolveApiKey(
  reqHeaders: Headers,
): Promise<KeyResolution> {
  if (!authEnabled || !auth) {
    return { ok: true, apiKey: process.env.SINGLE_TENANT_API_KEY || null };
  }

  const session = await auth.api.getSession({ headers: reqHeaders });
  if (!session) {
    return { ok: false, status: 401, error: "not_authenticated" };
  }

  const orgId = session.session.activeOrganizationId;
  const org = await auth.api.getFullOrganization({
    headers: reqHeaders,
    query: orgId ? { organizationId: orgId } : {},
  });
  if (!org) {
    return { ok: false, status: 400, error: "no_active_organization" };
  }

  const meta = parseMeta((org as { metadata?: unknown }).metadata);
  if (!meta.mf_api_key_enc) {
    return { ok: false, status: 500, error: "organization_not_provisioned" };
  }
  return { ok: true, apiKey: decryptSecret(meta.mf_api_key_enc) };
}
