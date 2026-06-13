"use client";

import { authClient } from "@/lib/auth-client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

function slugify(value: string): string {
  const base = value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
  const suffix = Math.random().toString(36).slice(2, 8);
  return `${base || "org"}-${suffix}`;
}

export default function SignupPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);

    const signUp = await authClient.signUp.email({ email, password, name });
    if (signUp.error) {
      setError(signUp.error.message ?? "No se pudo crear la cuenta");
      setBusy(false);
      return;
    }

    // Crea la organización → dispara el aprovisionamiento en el API (API key).
    const org = await authClient.organization.create({
      name: orgName || name,
      slug: slugify(orgName || name),
    });
    if (org.error) {
      setError(org.error.message ?? "No se pudo crear la organización");
      setBusy(false);
      return;
    }

    router.push("/onboarding");
  }

  return (
    <main className="container">
      <h1>Crear cuenta</h1>
      {error && <div className="alert error">{error}</div>}
      <form onSubmit={onSubmit} className="card">
        <div className="field">
          <label htmlFor="name">Tu nombre</label>
          <input
            id="name"
            type="text"
            autoComplete="name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="org">Nombre de la organización</label>
          <input
            id="org"
            type="text"
            required
            value={orgName}
            onChange={(e) => setOrgName(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="password">Contraseña</label>
          <input
            id="password"
            type="password"
            autoComplete="new-password"
            minLength={8}
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <button type="submit" className="btn" disabled={busy}>
          {busy ? "Creando…" : "Crear cuenta"}
        </button>
      </form>
      <p className="muted">
        ¿Ya tienes cuenta? <Link href="/login">Iniciar sesión</Link>
      </p>
    </main>
  );
}
