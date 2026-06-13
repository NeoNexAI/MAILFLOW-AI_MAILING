"use client";

import { authClient } from "@/lib/auth-client";
import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useState } from "react";

interface Member {
  id: string;
  role: string;
  user?: { email?: string; name?: string };
}

interface Invitation {
  id: string;
  email: string;
  role: string;
  status: string;
}

export default function MembersPage() {
  const [members, setMembers] = useState<Member[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"member" | "admin">("member");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    const membersRes = await authClient.organization.listMembers();
    if (membersRes.error) {
      setError(
        membersRes.error.message ?? "No se pudieron cargar los miembros",
      );
      return;
    }
    const data = membersRes.data as unknown as { members?: Member[] };
    setMembers(data?.members ?? []);

    const invitesRes = await authClient.organization.listInvitations();
    if (!invitesRes.error) {
      setInvitations((invitesRes.data as unknown as Invitation[]) ?? []);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function invite(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const res = await authClient.organization.inviteMember({ email, role });
    if (res.error) {
      setError(res.error.message ?? "No se pudo invitar");
    } else {
      setEmail("");
    }
    setBusy(false);
    await load();
  }

  return (
    <main className="container">
      <p>
        <Link href="/app/dashboard">← Dashboard</Link>
      </p>
      <h1>Miembros del equipo</h1>
      {error && <div className="alert error">{error}</div>}

      <div className="card">
        <h3>Miembros</h3>
        <ul>
          {members.map((m) => (
            <li key={m.id}>
              {m.user?.email ?? m.user?.name ?? m.id}{" "}
              <span className="muted">· {m.role}</span>
            </li>
          ))}
          {members.length === 0 && (
            <li className="muted">Sin miembros todavía.</li>
          )}
        </ul>
      </div>

      <div className="card">
        <h3>Invitar por email</h3>
        <form
          onSubmit={invite}
          style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}
        >
          <input
            type="email"
            required
            placeholder="persona@empresa.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as "member" | "admin")}
          >
            <option value="member">Miembro</option>
            <option value="admin">Administrador</option>
          </select>
          <button type="submit" className="btn" disabled={busy}>
            Invitar
          </button>
        </form>
      </div>

      {invitations.length > 0 && (
        <div className="card">
          <h3>Invitaciones pendientes</h3>
          <ul>
            {invitations.map((inv) => (
              <li key={inv.id}>
                {inv.email}{" "}
                <span className="muted">
                  · {inv.role} · {inv.status}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </main>
  );
}
