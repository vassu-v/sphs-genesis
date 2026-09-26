import type { Metadata } from 'next';
import Script from 'next/script';
import './globals.css';

export const metadata: Metadata = {
  title: {
    default: 'S.H.O.A.V. — Shield for Hostile Operations & Agent Vulnerability',
    template: '%s — S.H.O.A.V.',
  },
  description:
    'An MCP server that gives any agent a real browser with a bodyguard in the path. Deterministic ingress and egress filters stop clickjacking, hidden prompt injection, and dark patterns before an agent acts on them.',
  icons: {
    icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23c81e3a'><rect x='3' y='3' width='18' height='18'/></svg>",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <Script src="/js/main.js" strategy="afterInteractive" />
      </body>
    </html>
  );
}
