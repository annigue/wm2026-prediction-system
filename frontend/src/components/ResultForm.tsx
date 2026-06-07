"use client";

import { useState } from "react";

const API          = process.env.NEXT_PUBLIC_API_URL  ?? "http://localhost:8000";
const ADMIN_TOKEN  = process.env.NEXT_PUBLIC_ADMIN_TOKEN ?? "wm2026-admin-token";

interface Props {
  matchId:   string;
  homeName:  string;
  awayName:  string;
  homeFlag:  string;
  awayFlag:  string;
  onSuccess: (result: { home: number; away: number }) => void;
}

export function ResultForm({ matchId, homeName, awayName, homeFlag, awayFlag, onSuccess }: Props) {
  const [home,      setHome]      = useState("");
  const [away,      setAway]      = useState("");
  const [extra,     setExtra]     = useState(false);
  const [penalties, setPenalties] = useState(false);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState<string | null>(null);
  const [open,      setOpen]      = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const hg = parseInt(home);
    const ag = parseInt(away);
    if (isNaN(hg) || isNaN(ag) || hg < 0 || ag < 0) {
      setError("Bitte gültige Toranzahl eingeben (≥ 0).");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`${API}/api/v1/matches/${matchId}/result`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${ADMIN_TOKEN}`,
        },
        body: JSON.stringify({
          home_goals:         hg,
          away_goals:         ag,
          went_to_extra_time: extra,
          went_to_penalties:  penalties,
        }),
      });
      const data = await r.json();
      if (!r.ok) {
        setError(data.detail ?? `Fehler ${r.status}`);
      } else {
        onSuccess({ home: hg, away: ag });
        setOpen(false);
      }
    } catch {
      setError("Verbindungsfehler.");
    } finally {
      setLoading(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="text-xs px-3 py-1.5 rounded-lg border border-wm-border text-wm-muted hover:border-gray-500 hover:text-white transition-colors"
      >
        ✏️ Ergebnis eintragen
      </button>
    );
  }

  return (
    <form onSubmit={submit} className="card border-orange-800 bg-orange-950/20 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">✏️ Ergebnis eintragen</h3>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="text-wm-muted hover:text-white text-lg leading-none"
        >
          ×
        </button>
      </div>

      {/* Toranzahl */}
      <div className="flex items-center gap-4">
        {/* Heimteam */}
        <div className="flex-1 text-center space-y-1">
          <div className="text-2xl">{homeFlag}</div>
          <div className="text-xs text-wm-muted">{homeName}</div>
          <input
            type="number"
            min="0"
            max="20"
            value={home}
            onChange={(e) => setHome(e.target.value)}
            placeholder="0"
            className="w-16 text-center text-2xl font-bold bg-gray-800 border border-wm-border rounded-lg px-2 py-2 text-white focus:border-orange-500 focus:outline-none"
            required
            autoFocus
          />
        </div>

        <div className="text-wm-muted text-xl font-bold">:</div>

        {/* Auswärtsteam */}
        <div className="flex-1 text-center space-y-1">
          <div className="text-2xl">{awayFlag}</div>
          <div className="text-xs text-wm-muted">{awayName}</div>
          <input
            type="number"
            min="0"
            max="20"
            value={away}
            onChange={(e) => setAway(e.target.value)}
            placeholder="0"
            className="w-16 text-center text-2xl font-bold bg-gray-800 border border-wm-border rounded-lg px-2 py-2 text-white focus:border-orange-500 focus:outline-none"
            required
          />
        </div>
      </div>

      {/* Optionen */}
      <div className="flex gap-4 text-xs">
        <label className="flex items-center gap-1.5 cursor-pointer text-wm-muted hover:text-white">
          <input
            type="checkbox"
            checked={extra}
            onChange={(e) => setExtra(e.target.checked)}
            className="rounded"
          />
          Verlängerung
        </label>
        <label className="flex items-center gap-1.5 cursor-pointer text-wm-muted hover:text-white">
          <input
            type="checkbox"
            checked={penalties}
            onChange={(e) => setPenalties(e.target.checked)}
            className="rounded"
          />
          Elfmeter
        </label>
      </div>

      {error && <p className="text-red-400 text-xs">{error}</p>}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={loading || !home || !away}
          className="flex-1 py-2 rounded-lg bg-orange-700 hover:bg-orange-600 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium transition-colors"
        >
          {loading ? "Speichere…" : "Ergebnis speichern"}
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="px-4 py-2 rounded-lg border border-wm-border text-wm-muted hover:text-white text-sm transition-colors"
        >
          Abbrechen
        </button>
      </div>

      <p className="text-xs text-wm-muted">
        Nach dem Speichern: Elo beider Teams wird aktualisiert, alle Prognosen und die Simulation werden neu berechnet (~30s).
      </p>
    </form>
  );
}
