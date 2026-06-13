/**
 * Aprovisionamiento de la organización en el API (server-to-server).
 *
 * Llama al endpoint interno del FastAPI `POST /internal/orgs` con el secreto
 * compartido `INTERNAL_API_SECRET`. Devuelve el id y la API key (en claro, una
 * sola vez) que el hook de Better Auth cifra y guarda en el metadata de la org.
 *
 * Solo se ejecuta en el servidor. `API_INTERNAL_URL` apunta al FastAPI por la
 * red interna (nunca pasa por el navegador).
 */
const INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

export interface ProvisionedOrg {
  org_id: string;
  slug: string;
  api_key: string;
}

export async function provisionOrg(input: {
  name: string;
  slug?: string;
}): Promise<ProvisionedOrg> {
  const secret = process.env.INTERNAL_API_SECRET;
  if (!secret) {
    throw new Error("INTERNAL_API_SECRET no configurado");
  }
  const res = await fetch(`${INTERNAL_URL}/internal/orgs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Internal-Secret": secret,
    },
    body: JSON.stringify({ name: input.name, slug: input.slug }),
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`provision_failed: ${res.status} ${detail}`);
  }
  return (await res.json()) as ProvisionedOrg;
}
