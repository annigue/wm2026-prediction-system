import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { Providers } from "./providers";
import { StatusBar } from "@/components/StatusBar";

export const metadata: Metadata = {
  title: "WM 2026 Prognose",
  description: "FIFA Weltmeisterschaft 2026 — Simulation & Prognose-Tool",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de" className="dark">
      <body className="min-h-screen bg-wm-dark text-gray-100">
        <Providers>
          <header className="border-b border-wm-border bg-wm-card/80 backdrop-blur sticky top-0 z-50">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
              <Link href="/" className="flex items-center gap-2 font-bold text-lg">
                <span>🏆</span>
                <span className="text-white">WM 2026</span>
                <span className="text-wm-muted font-normal text-sm hidden sm:block">Prognose</span>
              </Link>
              <div className="flex items-center gap-4">
                <nav className="flex items-center gap-1">
                  <NavLink href="/">Dashboard</NavLink>
                  <NavLink href="/groups">Gruppen</NavLink>
                  <NavLink href="/matches">Spiele</NavLink>
                  <NavLink href="/bracket">Baum</NavLink>
                  <NavLink href="/tipps">🎯 Tipps</NavLink>
                  <NavLink href="/admin">⚙</NavLink>
                </nav>
                <div className="hidden md:flex border-l border-wm-border pl-4">
                  <StatusBar />
                </div>
              </div>
            </div>
          </header>

          <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
            {children}
          </main>

          <footer className="border-t border-wm-border mt-12 py-6">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 text-center text-wm-muted text-sm">
              WM 2026 Prognose · Elo + Poisson + Monte Carlo (100.000 Runs) · Kein Wettanbieter
            </div>
          </footer>
        </Providers>
      </body>
    </html>
  );
}

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="px-3 py-1.5 rounded-lg text-sm text-wm-muted hover:text-white hover:bg-white/5 transition-colors"
    >
      {children}
    </Link>
  );
}
