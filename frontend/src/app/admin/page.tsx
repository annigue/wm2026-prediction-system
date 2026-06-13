"use client";

// Leichtgewichtiges Admin-Panel: manuelles Auslösen von Daten-Sync & Simulation.
// Der Admin-Token wird vom Nutzer eingegeben und NUR lokal (localStorage) gehalten —
// er landet NICHT im öffentlichen Build. Ohne gültigen Token lehnt das Backend ab (401).
import { useEffect, useState } from "react";
import { API_BASE as API } from "@/lib/apiBase";

export default function AdminPage() {
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [show, setShow] = useState(false);

  useEffect(() => {
    setToken(localStorage.getItem("wm2026_admin_token") ?? "");
  }, []);

  function saveToken(v: string) {
    setToken(v);
    localStorage.setItem("wm2026_admin_token", v);
  }

  async function call(label: string, path: string) {
    if (!token) {
      setMsg({ ok: false, text: "Bitte zuerst den Admin-Token eingeben." });
      return;
    }
    setBusy(label);
    setMsg(null);
    try {
      const r = await fetch(`${API}/api/v1/${path}`, {
        method: "POST",
        headers: { Authorization: token.trim() },
      });
      let data: any = null;
      try { data = await r.json(); } catch { /* kein JSON */ }

      if (r.status === 401) {
        setMsg({ ok: false, text: "Falscher Admin-Token." });
      } else if (!r.ok || data?.ok === false) {
        setMsg({ ok: false, text: `Fehler (HTTP ${r.status}). Bitte später erneut versuchen.` });
      } else if (label === "sync") {
        const af = data?.synced?.apifootball ?? {};
        const abgeglichen = (af.results_added ?? 0) + (af.results_updated ?? 0);
        const parts = [`${abgeglichen} Ergebnis(se) abgeglichen`];
        if (af.results_added) parts.push(`${af.results_added} neu`);
        if (data.elo_newly_applied) parts.push(`${data.elo_newly_applied} Spiel(e) verrechnet`);
        parts.push(
          typeof data.recompute === "string" && data.recompute.startsWith("triggered")
            ? "Neuberechnung gestartet"
            : "keine neuen Ergebnisse"
        );
        setMsg({ ok: true, text: "Synchronisiert · " + parts.join(" · ") });
      } else {
        setMsg({ ok: true, text: "Simulation gestartet — Ergebnis in ~1–2 min sichtbar." });
      }
    } catch {
      setMsg({ ok: false, text: "Verbindungsfehler — Backend nicht erreichbar." });
    } finally {
      setBusy(null);
    }
  }

  const btn =
    "px-4 py-2 rounded-lg text-sm font-medium border transition-colors disabled:opacity-50 disabled:cursor-not-allowed";

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Admin</h1>
        <p className="text-wm-muted text-sm mt-1">
          Manuelles Auslösen von Daten-Sync &amp; Simulation. Läuft sonst automatisch alle 30 min.
        </p>
      </div>

      <div className="card space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-sm text-wm-muted">Admin-Token</label>
          <button
            type="button"
            onClick={() => setShow(!show)}
            className="text-xs text-wm-muted hover:text-white underline"
          >
            {show ? "verbergen" : "anzeigen"}
          </button>
        </div>
        <input
          type={show ? "text" : "password"}
          value={token}
          onChange={(e) => saveToken(e.target.value)}
          placeholder="ADMIN_TOKEN (aus Render)"
          autoComplete="off"
          spellCheck={false}
          className="w-full bg-wm-dark border border-wm-border rounded-lg px-3 py-2 text-sm text-white focus:border-gray-500 outline-none font-mono"
        />
        <p className="text-[11px] text-wm-muted">
          {token.length} Zeichen · nur lokal im Browser gespeichert. Muss exakt dem ADMIN_TOKEN aus Render entsprechen.
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          onClick={() => call("sync", "admin/auto-update")}
          disabled={!!busy}
          className={`${btn} border-wm-border text-white hover:border-gray-500`}
          title="Ergebnisse synchronisieren (API-Football) + Elo/Form/Bracket/Prognosen/Simulation neu berechnen"
        >
          {busy === "sync" ? "Synchronisiere…" : "🔄 Daten synchronisieren + neu berechnen"}
        </button>
        <button
          onClick={() => call("sim", "admin/simulate")}
          disabled={!!busy}
          className={`${btn} border-wm-gold/40 text-wm-gold hover:border-wm-gold hover:bg-wm-gold/10`}
          title="100.000 Monte-Carlo-Simulationen im Hintergrund starten"
        >
          {busy === "sim" ? "Starte…" : "🎲 Nur Simulation starten"}
        </button>
      </div>

      {msg && (
        <div
          className={`card text-sm border ${
            msg.ok ? "border-green-600/40 text-green-300" : "border-red-600/40 text-red-300"
          }`}
        >
          {msg.ok ? "✅ " : "❌ "}
          {msg.text}
        </div>
      )}

      <p className="text-[11px] text-wm-muted">
        „Daten synchronisieren" macht alles (Ergebnisse holen → Elo → Form → Bracket → Prognosen →
        Simulation). „Nur Simulation" rechnet ausschließlich die Turniersimulation neu.
      </p>
    </div>
  );
}
