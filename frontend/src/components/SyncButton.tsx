"use client";

import { useState, useEffect } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const ADMIN_TOKEN = process.env.NEXT_PUBLIC_ADMIN_TOKEN ?? "wm2026-admin-token";

interface SyncStatus {
  requests_remaining: number | null;
  requests_limit: number | null;
  last_sync: string | null;
  last_check: string | null;
  error?: string;
}

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("de-DE", {
    day: "2-digit", month: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

function RateBar({ remaining, limit }: { remaining: number | null; limit: number | null }) {
  if (remaining == null || limit == null) return null;
  const pct = Math.round((remaining / limit) * 100);
  const color = pct > 50 ? "bg-green-500" : pct > 20 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2 text-xs text-wm-muted">
      <div className="w-20 h-1.5 rounded-full bg-gray-700 overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span>{remaining} / {limit} req/Tag</span>
    </div>
  );
}

export function SyncButton() {
  const [status, setStatus]   = useState<SyncStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  // Status beim Mounten laden
  useEffect(() => {
    fetchStatus();
  }, []);

  async function fetchStatus() {
    try {
      const r = await fetch(`${API}/api/v1/admin/status`);
      if (r.ok) setStatus(await r.json());
    } catch {
      // Backend nicht erreichbar
    }
  }

  async function handleSimulate() {
    setLoading(true);
    setMessage(null);
    try {
      await fetch(`${API}/api/v1/admin/simulate`, {
        method: "POST",
        headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
      });
      setMessage("⏳ Simulation läuft (100.000 Runs, ~25s)…");
      setTimeout(() => { setMessage("✓ Simulation abgeschlossen"); fetchStatus(); }, 30000);
    } catch {
      setMessage("Verbindungsfehler.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSync() {
    setLoading(true);
    setMessage(null);
    try {
      const r = await fetch(`${API}/api/v1/admin/sync`, {
        method: "POST",
        headers: { Authorization: `Bearer ${ADMIN_TOKEN}` },
      });
      const data = await r.json();
      if (!r.ok) {
        setMessage(`Fehler: ${data.detail ?? r.statusText}`);
      } else {
        setMessage(
          `✓ ${data.groups_updated} Gruppen, ${data.matches_updated} Spiele aktualisiert`
        );
        setStatus({
          requests_remaining: data.requests_remaining,
          requests_limit:     data.requests_limit,
          last_sync:          data.last_sync,
          last_check:         data.last_check,
        });
        // Seite neu laden damit Gruppen/Matches aktuell sind
        setTimeout(() => window.location.reload(), 1200);
      }
    } catch (e) {
      setMessage("Verbindungsfehler zum Backend.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center gap-3 flex-wrap">
      {/* Rate-Limit-Anzeige */}
      <div className="flex flex-col gap-0.5">
        <RateBar
          remaining={status?.requests_remaining ?? null}
          limit={status?.requests_limit ?? null}
        />
        {status?.last_sync && (
          <span className="text-xs text-wm-muted">
            Sync: {formatTime(status.last_sync)}
          </span>
        )}
      </div>

      {/* Sync-Button */}
      <button
        onClick={handleSync}
        disabled={loading}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors
          ${loading ? "border-gray-700 text-gray-600 cursor-not-allowed"
                    : "border-wm-border text-wm-muted hover:border-gray-500 hover:text-white cursor-pointer"}`}
        title="Daten von RapidAPI aktualisieren"
      >
        <span className={loading ? "animate-spin" : ""}>↻</span>
        {loading ? "Sync…" : "Sync"}
      </button>

      {/* Simulate-Button */}
      <button
        onClick={handleSimulate}
        disabled={loading}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors
          ${loading ? "border-gray-700 text-gray-600 cursor-not-allowed"
                    : "border-wm-gold/40 text-wm-gold hover:border-wm-gold hover:bg-wm-gold/10 cursor-pointer"}`}
        title="100.000 Monte-Carlo-Simulationen starten"
      >
        🎲 {loading ? "…" : "Simulieren"}
      </button>

      {/* Feedback-Meldung */}
      {message && (
        <span className={`text-xs ${message.startsWith("✓") ? "text-green-400" : "text-red-400"}`}>
          {message}
        </span>
      )}
    </div>
  );
}
