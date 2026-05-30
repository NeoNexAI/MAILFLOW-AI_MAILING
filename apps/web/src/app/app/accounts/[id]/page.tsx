"use client";

import { ApiError, api } from "@/lib/api";
import type { Cycle, EmailAccount } from "@/lib/types";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

export default function AccountDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const [account, setAccount] = useState<EmailAccount | null>(null);
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [acc, cyc] = await Promise.all([
        api.getAccount(id),
        api.listCycles(id),
      ]);
      setAccount(acc);
      setCycles(cyc);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not load account",
      );
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function runNow() {
    setBusy(true);
    setError(null);
    try {
      await api.runCycle(id);
      setTimeout(load, 1200);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Run failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!confirm("Disconnect this mailbox? Processing history is removed.")) {
      return;
    }
    setBusy(true);
    try {
      await api.deleteAccount(id);
      router.push("/app/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
      setBusy(false);
    }
  }

  const totals = cycles.reduce(
    (acc, c) => {
      acc.emails += c.emails_processed;
      acc.drafts += c.drafts_saved;
      acc.errors += c.error_count;
      return acc;
    },
    { emails: 0, drafts: 0, errors: 0 },
  );

  return (
    <main className="container">
      <p>
        <Link href="/app/dashboard">← Dashboard</Link>
      </p>

      {error && <div className="alert error">{error}</div>}

      {account && (
        <>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: "0.75rem",
            }}
          >
            <h1 style={{ margin: 0 }}>{account.username}</h1>
            <div style={{ display: "flex", gap: "0.6rem" }}>
              <button
                type="button"
                className="btn"
                onClick={runNow}
                disabled={busy}
              >
                {busy ? "Working…" : "Run cycle now"}
              </button>
              <button
                type="button"
                className="btn danger"
                onClick={remove}
                disabled={busy}
              >
                Disconnect
              </button>
            </div>
          </div>
          <p className="muted">
            {account.imap_host}:{account.imap_port} · every{" "}
            {account.interval_minutes} min ·{" "}
            {account.is_active ? "active" : "paused"}
          </p>

          <div className="stat-grid" style={{ margin: "1.25rem 0" }}>
            <div className="stat">
              <div className="n">{cycles.length}</div>
              <div className="l">cycles</div>
            </div>
            <div className="stat">
              <div className="n">{totals.emails}</div>
              <div className="l">emails processed</div>
            </div>
            <div className="stat">
              <div className="n">{totals.drafts}</div>
              <div className="l">drafts saved</div>
            </div>
            <div className="stat">
              <div className="n">{totals.errors}</div>
              <div className="l">errors</div>
            </div>
          </div>

          <div className="card">
            <h3>Cycle history</h3>
            {cycles.length === 0 ? (
              <p className="muted">
                No cycles yet. Hit “Run cycle now” or wait for the scheduler.
              </p>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Emails</th>
                    <th>Drafts</th>
                    <th>Errors</th>
                    <th>Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {cycles.map((c) => (
                    <tr key={c.id}>
                      <td className="muted">
                        {new Date(c.created_at).toLocaleString()}
                      </td>
                      <td>{c.emails_processed}</td>
                      <td>{c.drafts_saved}</td>
                      <td>
                        {c.error_count > 0 ? (
                          <span className="pill" style={{ color: "#ff6b6b" }}>
                            {c.error_count}
                          </span>
                        ) : (
                          0
                        )}
                      </td>
                      <td className="muted">
                        {c.duration_ms != null ? `${c.duration_ms} ms` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </main>
  );
}
