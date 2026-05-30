import Link from "next/link";

export default function HomePage() {
  return (
    <main className="container">
      <section className="hero">
        <h1>MailFlow</h1>
        <p className="muted">
          Open source AI email assistant. Use any LLM. Your inbox, your rules,
          your privacy.
        </p>
        <div
          style={{
            display: "flex",
            gap: "0.75rem",
            justifyContent: "center",
            marginTop: "1.5rem",
          }}
        >
          <Link className="btn" href="/onboarding">
            Get started
          </Link>
          <Link className="btn secondary" href="/app/dashboard">
            Open dashboard
          </Link>
        </div>
      </section>

      <div className="card">
        <h3>How it works</h3>
        <ol className="muted">
          <li>Connect an LLM provider (local Ollama, OpenAI, Anthropic…).</li>
          <li>Connect an IMAP mailbox.</li>
          <li>
            MailFlow classifies incoming email into folders and drafts replies —
            never sending, only saving drafts.
          </li>
        </ol>
      </div>
    </main>
  );
}
