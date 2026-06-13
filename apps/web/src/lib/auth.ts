/**
 * Instancia de Better Auth (servidor) — patrón BFF de M1.1.
 *
 * Solo está activa en SaaS (`WEB_AUTH=on`). En self-host single-tenant
 * (`WEB_AUTH=off`, por defecto) la auth web está desactivada y `auth` es null:
 * la web sigue usando el flujo actual sin tocar Better Auth ni la base de datos.
 *
 * Al crear una organización, el hook `beforeCreateOrganization` la aprovisiona
 * en el API (POST /internal/orgs), recibe su API key y la guarda cifrada en el
 * `metadata` de la org. Así la API key nunca llega al navegador.
 */
import { betterAuth } from "better-auth";
import { organization } from "better-auth/plugins";
import { Pool } from "pg";
import { encryptSecret } from "./crypto";
import { provisionOrg } from "./provision";

export const authEnabled = process.env.WEB_AUTH === "on";

function buildAuth() {
  return betterAuth({
    baseURL: process.env.BETTER_AUTH_URL ?? "http://localhost:3000",
    database: new Pool({ connectionString: process.env.DATABASE_URL }),
    emailAndPassword: { enabled: true },
    plugins: [
      organization({
        organizationHooks: {
          // Aprovisiona la org en el API y cifra su API key en el metadata.
          beforeCreateOrganization: async ({ organization: org }) => {
            const provisioned = await provisionOrg({
              name: org.name ?? "Organization",
              slug: org.slug,
            });
            return {
              data: {
                ...org,
                metadata: {
                  ...(org.metadata ?? {}),
                  mf_org_id: provisioned.org_id,
                  mf_api_key_enc: encryptSecret(provisioned.api_key),
                },
              },
            };
          },
        },
      }),
    ],
  });
}

export type Auth = ReturnType<typeof buildAuth>;

// Construida solo cuando la auth web está activa (evita exigir DB/secretos en
// self-host y en tiempo de build).
export const auth: Auth | null = authEnabled ? buildAuth() : null;
