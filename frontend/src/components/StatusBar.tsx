"use client";

// Reine Status-Anzeige (kein Admin-Eingriff): zeigt, wie aktuell Daten + Simulation sind.
// Sync läuft automatisch alle 30 min, die Simulation nach jedem neuen Spielergebnis.
import { useState, useEffect } from "react";
import { API_BASE as API } from "@/lib/apiBase";

interface SyncStatus {
  requests_remaining: number | null;
  requests_limit: number | null;
  last_sync: string | null;
}
interface SimStatus {
  available?: boolean;
  simulated_at?: string;
  n_runs?: number;
}

function fmt(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("de-DE", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

export function StatusBar() {
  const [sync, setSync] = useState<SyncStatus | null>(null);
  const [sim, setSim] = useState<SimStatus | null>(null);

  useEffect(() => {
    // Letzte bekannte Werte sofort aus dem Cache zeigen (kein Flackern/Verschwinden beim Reload)
    try {
      const cs = localStorage.getItem("wm2026_sync");
      if (cs) setSync(JSON.parse(cs));
      const cm = localStorage.getItem("wm2026_sim");
      if (cm) setSim(JSON.parse(cm));
    } catch { /* ignore */ }

    // Aktualisieren — nur überschreiben, wenn der Fetch erfolgreich ist (sonst Cache behalten)
    fetch(`${API}/api/v1/admin/status`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d) { setSync(d); localStorage.setItem("wm2026_sync", JSON.stringify(d)); } })
      .catch(() => {});
    fetch(`${API}/api/v1/admin/simulation-status`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d) { setSim(d); localStorage.setItem("wm2026_sim", JSON.stringify(d)); } })
      .catch(() => {});
  }, []);

  const rate =
    sync?.requests_remaining != null && sync?.requests_limit != null
      ? `${sync.requests_remaining}/${sync.requests_limit} req`
      : null;

  return (
    <div className="flex items-center gap-4 text-xs text-wm-muted flex-wrap">
      <span title="Letzter Datenabgleich mit der WM-API (automatisch alle 30 min)">
        ↻ Daten-Sync: <span className="text-gray-300">{fmt(sync?.last_sync)}</span>
        {rate && <span className="ml-1 opacity-70">· {rate}/Tag</span>}
      </span>
      <span title="Letzte Monte-Carlo-Simulation (automatisch nach jedem Spielergebnis)">
        🎲 Simulation: <span className="text-gray-300">{sim?.available ? fmt(sim.simulated_at) : "—"}</span>
      </span>
    </div>
  );
}
