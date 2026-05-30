"use client";

import { ApiError, api } from "@/lib/api";
import type { PlanStatus } from "@/lib/types";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

function limitLabel(value: number | null): string {
  return value === null ? "Unlimited" : String(value);
}

export default function BillingPage() {
  const [status, setStatus] = useState<PlanStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setStatus(await api.planStatus());
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not load billing",
      );
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function upgrade(plan: "pro" | "team") {
    setBusy(true);
    setError(null);
    try {
      const { url } = await api.checkout(plan);
      window.location.href = url;
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 501
            ? "Billing is not configured on this server."
            : err.message
          : "Checkout failed",
      );
      setBusy(false);
    }
  }

  async function openPortal() {
    setBusy(true);
    setError(null);
    try {
      const { url } = await api.billingPortal();
      window.location.href = url;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not open portal");
      setBusy(false);
    }
  }

  return (
    <main className="container">
      <p>
        <Link href="/app/dashboard">← Dashboard</Link>
      </p>
      <h1>Billing</h1>

      {error && <div className="alert error">{error}</div>}

      {status && (
        <>
          <div className="card">
            <h3>
              Current plan: {status.label}{" "}
              {!status.billing_enabled && (
                <span className="pill off">self-host</span>
              )}
            </h3>
            <div className="stat-grid" style={{ marginTop: "1rem" }}>
              <div className="stat">
                <div className="n">
                  {status.accounts_used}/{limitLabel(status.max_accounts)}
                </div>
                <div className="l">mailboxes</div>
              </div>
              <div className="stat">
                <div className="n">
                  {status.emails_today}/{limitLabel(status.max_emails_per_day)}
                </div>
                <div className="l">emails today</div>
              </div>
            </div>
          </div>

          {status.billing_enabled ? (
            <div className="card">
              <h3>Manage subscription</h3>
              {status.plan === "free" ? (
                <div
                  style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}
                >
                  <button
                    type="button"
                    className="btn"
                    disabled={busy}
                    onClick={() => upgrade("pro")}
                  >
                    Upgrade to Pro
                  </button>
                  <button
                    type="button"
                    className="btn secondary"
                    disabled={busy}
                    onClick={() => upgrade("team")}
                  >
                    Upgrade to Team
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  className="btn"
                  disabled={busy}
                  onClick={openPortal}
                >
                  Manage / cancel subscription
                </button>
              )}
            </div>
          ) : (
            <div className="card">
              <p className="muted">
                This is a self-hosted instance — no plan limits apply. Billing
                (Stripe) is only used on the managed SaaS.
              </p>
            </div>
          )}
        </>
      )}
    </main>
  );
}
