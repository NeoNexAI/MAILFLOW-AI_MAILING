"use client";

import { ApiError, api } from "@/lib/api";
import type { LLMProvider } from "@/lib/types";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

type Step = "llm" | "account" | "done";

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("llm");
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // LLM form
  const [llm, setLlm] = useState({
    label: "Local Ollama",
    type: "ollama",
    base_url: "http://localhost:11434",
    default_classification_model: "ollama/llama3.1:8b",
    default_generation_model: "ollama/llama3.1:8b",
    api_key: "",
  });

  // Account form
  const [acct, setAcct] = useState({
    imap_host: "",
    username: "",
    password: "",
    interval_minutes: 5,
    llm_provider_id: "",
  });

  useEffect(() => {
    api
      .listProviders()
      .then((p) => {
        setProviders(p);
        if (p.length > 0) {
          setAcct((a) => ({ ...a, llm_provider_id: p[0].id }));
          setStep("account");
        }
      })
      .catch(() => {
        /* API may be unreachable; stay on step 1 */
      });
  }, []);

  async function submitLlm(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const created = await api.createProvider({
        label: llm.label,
        type: llm.type,
        base_url: llm.base_url,
        default_classification_model: llm.default_classification_model,
        default_generation_model: llm.default_generation_model,
        api_key: llm.api_key || null,
      });
      setProviders((p) => [...p, created]);
      setAcct((a) => ({ ...a, llm_provider_id: created.id }));
      setStep("account");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not save provider",
      );
    } finally {
      setBusy(false);
    }
  }

  async function submitAccount(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.createAccount({
        imap_host: acct.imap_host,
        username: acct.username,
        password: acct.password,
        interval_minutes: Number(acct.interval_minutes),
        llm_provider_id: acct.llm_provider_id || null,
      });
      setStep("done");
      setTimeout(() => router.push("/app/dashboard"), 900);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not connect account",
      );
    } finally {
      setBusy(false);
    }
  }

  async function connectOAuth(provider: "gmail" | "microsoft") {
    setError(null);
    setBusy(true);
    try {
      const { authorize_url } = await api.oauthAuthorizeUrl(provider);
      // Redirige el navegador al consentimiento del proveedor.
      window.location.href = authorize_url;
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : `Could not start ${provider} sign-in`,
      );
      setBusy(false);
    }
  }

  return (
    <main className="container">
      <h1>Get started</h1>
      <p className="muted">
        Step {step === "llm" ? "1" : step === "account" ? "2" : "✓"} of 2
      </p>

      {error && <div className="alert error">{error}</div>}

      {step === "llm" && (
        <form className="card" onSubmit={submitLlm}>
          <h3>1. Connect an LLM provider</h3>
          <div className="field">
            <label htmlFor="llm-label">Label</label>
            <input
              id="llm-label"
              value={llm.label}
              onChange={(e) => setLlm({ ...llm, label: e.target.value })}
              required
            />
          </div>
          <div className="row">
            <div className="field">
              <label htmlFor="llm-type">Type</label>
              <select
                id="llm-type"
                value={llm.type}
                onChange={(e) => setLlm({ ...llm, type: e.target.value })}
              >
                <option value="ollama">Ollama (local)</option>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="custom">Custom (OpenAI-compatible)</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="llm-url">Base URL</label>
              <input
                id="llm-url"
                value={llm.base_url}
                onChange={(e) => setLlm({ ...llm, base_url: e.target.value })}
                required
              />
            </div>
          </div>
          <div className="row">
            <div className="field">
              <label htmlFor="llm-cls">Classification model</label>
              <input
                id="llm-cls"
                value={llm.default_classification_model}
                onChange={(e) =>
                  setLlm({
                    ...llm,
                    default_classification_model: e.target.value,
                  })
                }
                required
              />
            </div>
            <div className="field">
              <label htmlFor="llm-gen">Generation model</label>
              <input
                id="llm-gen"
                value={llm.default_generation_model}
                onChange={(e) =>
                  setLlm({ ...llm, default_generation_model: e.target.value })
                }
                required
              />
            </div>
          </div>
          <div className="field">
            <label htmlFor="llm-key">
              API key (leave empty for local Ollama)
            </label>
            <input
              id="llm-key"
              type="password"
              value={llm.api_key}
              onChange={(e) => setLlm({ ...llm, api_key: e.target.value })}
            />
          </div>
          <button className="btn" type="submit" disabled={busy}>
            {busy ? "Saving…" : "Continue"}
          </button>
        </form>
      )}

      {step === "account" && (
        <>
          <div className="card">
            <h3>2. Connect a mailbox</h3>
            <p className="muted">
              Use one-click sign-in (recommended) or enter IMAP details below.
            </p>
            <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
              <button
                type="button"
                className="btn secondary"
                disabled={busy}
                onClick={() => connectOAuth("gmail")}
              >
                Connect Gmail
              </button>
              <button
                type="button"
                className="btn secondary"
                disabled={busy}
                onClick={() => connectOAuth("microsoft")}
              >
                Connect Microsoft 365
              </button>
            </div>
            <p
              className="muted"
              style={{ fontSize: "0.8rem", marginBottom: 0 }}
            >
              OAuth must be configured on the server (GOOGLE_/MICROSOFT_ client
              credentials). Otherwise use IMAP below.
            </p>
          </div>

          <form className="card" onSubmit={submitAccount}>
            <h3>Or connect via IMAP</h3>
            <div className="row">
              <div className="field">
                <label htmlFor="imap-host">IMAP host</label>
                <input
                  id="imap-host"
                  placeholder="imap.example.com"
                  value={acct.imap_host}
                  onChange={(e) =>
                    setAcct({ ...acct, imap_host: e.target.value })
                  }
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="imap-user">Username</label>
                <input
                  id="imap-user"
                  placeholder="you@example.com"
                  value={acct.username}
                  onChange={(e) =>
                    setAcct({ ...acct, username: e.target.value })
                  }
                  required
                />
              </div>
            </div>
            <div className="row">
              <div className="field">
                <label htmlFor="imap-pass">Password / app password</label>
                <input
                  id="imap-pass"
                  type="password"
                  value={acct.password}
                  onChange={(e) =>
                    setAcct({ ...acct, password: e.target.value })
                  }
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="imap-interval">Check every (minutes)</label>
                <input
                  id="imap-interval"
                  type="number"
                  min={1}
                  max={1440}
                  value={acct.interval_minutes}
                  onChange={(e) =>
                    setAcct({
                      ...acct,
                      interval_minutes: Number(e.target.value),
                    })
                  }
                />
              </div>
            </div>
            {providers.length > 0 && (
              <div className="field">
                <label htmlFor="acct-llm">LLM provider</label>
                <select
                  id="acct-llm"
                  value={acct.llm_provider_id}
                  onChange={(e) =>
                    setAcct({ ...acct, llm_provider_id: e.target.value })
                  }
                >
                  {providers.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <button className="btn" type="submit" disabled={busy}>
              {busy ? "Connecting…" : "Finish"}
            </button>
          </form>
        </>
      )}

      {step === "done" && (
        <div className="alert ok">
          Mailbox connected. Redirecting to your dashboard…
        </div>
      )}
    </main>
  );
}
