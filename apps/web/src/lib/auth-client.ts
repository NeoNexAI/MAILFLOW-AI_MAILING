/**
 * Cliente de Better Auth para las páginas de login/signup (lado navegador).
 *
 * Solo habla con el servidor Next (`/api/auth/*`); nunca con el FastAPI ni con
 * la API key. El plugin de organización habilita crear/listar orgs y miembros.
 */
"use client";

import { organizationClient } from "better-auth/client/plugins";
import { createAuthClient } from "better-auth/react";

export const authClient = createAuthClient({
  plugins: [organizationClient()],
});

export const { signIn, signUp, signOut, useSession } = authClient;
