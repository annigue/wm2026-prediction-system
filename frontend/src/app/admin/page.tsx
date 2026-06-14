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
  const [cal, setCal] = useState<any>(null);
  const [calBusy, setCalBusy] = useState(false);
  const [unmapped, setUnmapped] = useState<string[]>([]);

  useEffect(() => {
    setToken(localStorage.getItem("wm2026_admin_token") ?? "");
    loadCal();
    loadStatus();
  }, []);

  async function loadStatus() {
    try {
      const r = await fetch(`${API}/api/v1/admin/status`);
      const d = r.ok ? await r.json() : null;
      setUnmapped(Array.isArray(d?.unmapped) ? d.unmapped : []);
    } catch {
      setUnmapped([]);
    }
  }

  async function loadCal() {
    setCalBusy(true);
    try {
      const r = await fetch(`${API}/api/v1/admin/market-calibration`);
      setCal(r.ok ? await r.json() : null);
    } catch {
      setCal(null);
    } finally {
      setCalBusy(false);
    }
  }

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
        loadStatus(); // Unmapped-Warnung aktualisieren
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

      {unmapped.length > 0 && (
        <div className="card text-sm border border-amber-600/50 text-amber-300 space-y-1">
          <div className="font-semibold">
            ⚠️ {unmapped.length} beendete(s) Spiel(e) nicht zugeordnet
          </div>
          <p className="text-[12px] text-amber-200/80">
            Die Ergebnis-API liefert einen Teamnamen, den das System nicht zuordnen konnte — diese
            Spiele werden NICHT synchronisiert. Bitte Alias im Backend ergänzen:
          </p>
          <ul className="list-disc list-inside font-mono text-[12px]">
            {unmapped.map((u) => (
              <li key={u}>{u}</li>
            ))}
          </ul>
        </div>
      )}

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

      {/* Kalibrierungs-Monitor: reines Modell vs. Markt vs. offizielle (geblendete) Prognose */}
      <div className="card space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white">📊 Modell-Kalibrierung</h3>
          <button
            type="button"
            onClick={loadCal}
            disabled={calBusy}
            className="text-xs text-wm-muted hover:text-white underline disabled:opacity-50"
          >
            {calBusy ? "lädt…" : "aktualisieren"}
          </button>
        </div>

        {!cal || cal.available === false ? (
          <p className="text-xs text-wm-muted">
            {cal?.reason ?? "Noch keine Kalibrierungsdaten."}
          </p>
        ) : (
          <div className="space-y-2">
            <div className="text-xs text-wm-muted">
              {cal.n_matches} Spiele mit Markt-Snapshot · {cal.n_with_results} gespielt · Blend-Gewicht
              {" "}w={Math.round((cal.blend_weight ?? 0) * 100)}%
            </div>

            {cal.n_with_results > 0 ? (
              <>
                <div className="text-xs text-wm-muted">Brier-Score (niedriger = besser):</div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  {([
                    ["Modell", "mean_brier_model", "modell"],
                    ["Markt", "mean_brier_market", "markt"],
                    ["Geblendet", "mean_brier_blended", "geblendet"],
                  ] as const).map(([lbl, key, id]) => (
                    <div
                      key={id}
                      className={`rounded-lg py-2 ${
                        cal.best_brier === id
                          ? "bg-green-600/15 border border-green-600/40"
                          : "bg-white/5"
                      }`}
                    >
                      <div className="font-mono font-bold text-white">
                        {typeof cal[key] === "number" ? cal[key].toFixed(3) : "—"}
                      </div>
                      <div className="text-[11px] text-wm-muted">
                        {lbl}{id === "geblendet" ? " (offiziell)" : ""}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="text-[11px] text-wm-muted">
                  Bestes Verfahren bisher: <span className="text-gray-300">{cal.best_brier}</span>
                </div>
              </>
            ) : (
              <p className="text-xs text-wm-muted">
                Noch kein gespieltes Spiel mit Markt-Snapshot — der Brier-Vergleich erscheint, sobald
                die ersten jetzt prognostizierten Spiele ausgetragen sind.
              </p>
            )}

            {cal.note && <p className="text-[10px] text-wm-muted">{cal.note}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
