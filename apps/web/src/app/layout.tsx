import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "MailFlow",
  description: "Open source AI email assistant",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <nav className="nav">
          <strong>
            <Link href="/">MailFlow</Link>
          </strong>
          <div className="spacer" />
          <Link href="/app/dashboard">Dashboard</Link>
          <Link href="/app/billing">Billing</Link>
          <Link href="/onboarding">Get started</Link>
        </nav>
        {children}
      </body>
    </html>
  );
}
