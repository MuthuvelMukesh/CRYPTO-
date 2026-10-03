import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Quant Lab v3.0 | Crypto Intelligence Platform",
  description: "Dense, fast, trustworthy crypto quantitative research and paper-trading workstation.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark h-full antialiased" data-theme="dark">
      <body className="min-h-full flex flex-col bg-[var(--bg-base)] text-[var(--text-primary)]">
        {children}
      </body>
    </html>
  );
}
