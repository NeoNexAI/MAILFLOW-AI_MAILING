"use client";

import { ApiError, api } from "@/lib/api";
import type { EmailAccount } from "@/lib/types";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

export default function DashboardPage() {
  const [accounts, setAccounts] = useState<EmailAccount[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [runningId, setRunningId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setAccounts(await api.listAccounts());
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `Could not reach the API (${err.message})`
          : "Could not reach the API",
      );
      setAccounts([]);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function runNow(id: string) {
    setRunningId(id);
    setNotice(null);
    setError(null);
    try {
      const res = await api.runCycle(id);
      setNotice(
        res.enqueued
          ? "Cycle enqueued — refresh history in a moment."
          : "Could not enqueue (is the worker/Redis running?).",
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Run failed");
    } finally {
      setRunningId(null);
    }
  }

  return (
    <main className="container">
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <h1>Dashboard</h1>
        <Link className="btn" href="/onboarding">
          + Connect mailbox
        </Link>
      </div>

      {error && <div className="alert error">{error}</div>}
      {notice && <div className="alert ok">{notice}</div>}

      {accounts === null && <p className="muted">Loading…</p>}

      {accounts !== null && accounts.length === 0 && !error && (
        <div className="card empty">
          <p>No mailboxes connected yet.</p>
          <Link className="btn" href="/onboarding">
            Connect your first mailbox
          </Link>
        </div>
      )}

      {accounts !== null && accounts.length > 0 && (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Mailbox</th>
                <th>Status</th>
                <th>Every</th>
                <th>Last cycle</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.id}>
                  <td>
                    <Link href={`/app/accounts/${a.id}`}>{a.username}</Link>
                    <div className="muted" style={{ fontSize: "0.8rem" }}>
                      {a.imap_host}
                    </div>
                  </td>
                  <td>
                    <span className={`pill ${a.is_active ? "ok" : "off"}`}>
                      {a.is_active ? "active" : "paused"}
                    </span>
                  </td>
                  <td>{a.interval_minutes} min</td>
                  <td className="muted">
                    {a.last_cycle_at
                      ? new Date(a.last_cycle_at).toLocaleString()
                      : "never"}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn secondary"
                      disabled={runningId === a.id}
                      onClick={() => runNow(a.id)}
                    >
                      {runningId === a.id ? "Running…" : "Run now"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
