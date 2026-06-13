"use client";

import { authClient } from "@/lib/auth-client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

function redirectTarget(): string {
  if (typeof window === "undefined") {
    return "/app/dashboard";
  }
  return (
    new URLSearchParams(window.location.search).get("redirect") ||
    "/app/dashboard"
  );
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const { error: err } = await authClient.signIn.email({ email, password });
    if (err) {
      setError(err.message ?? "No se pudo iniciar sesión");
      setBusy(false);
      return;
    }
    router.push(redirectTarget());
  }

  return (
    <main className="container">
      <h1>Iniciar sesión</h1>
      {error && <div className="alert error">{error}</div>}
      <form onSubmit={onSubmit} className="card">
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
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <button type="submit" className="btn" disabled={busy}>
          {busy ? "Entrando…" : "Entrar"}
        </button>
      </form>
      <p className="muted">
        ¿No tienes cuenta? <Link href="/signup">Crear cuenta</Link>
      </p>
    </main>
  );
}
