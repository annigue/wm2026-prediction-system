# LIMITATIONS — Bekannte Grenzen (bewusst & dokumentiert)

Prinzip: lieber eine **explizit dokumentierte, reproduzierbare** Grenze als ein versteckter
Schätzwert. Keine ML-Modelle, keine erfundenen Daten.

## Im Modell enthaltene, aber bewusst begrenzte Faktoren
| Thema | Umsetzung | Grenze |
|---|---|---|
| Form | form_engine v2 (Punkte+Tore+Recency, echte Ergebnisse) | vor 1. Spiel = 0.0 (neutral) |
| Rest-Days/Fatigue | nur **gespielte** Spiele, sanfte tanh-Sättigung (±20) | greift erst während des Turniers; Gruppenphase weitgehend symmetrisch |
| Umwelt-/Venue-Stress | nur **Varianz** in der Simulation (Höhe+Klima-Proxy) | grober Proxy (Breitengrad statt echter Klimadaten); kein Bias, kein Forecast |
| Marktwert | statischer PRIOR, eingefroren | Importance 6× < Elo; nicht automatisiert (bewusst) |

## Verbleibende, NICHT modellierte Faktoren
| Thema | Impact | Mitigation |
|---|---|---|
| Verletzungen/Sperren | Hoch | kein reproduzierbarer Live-Stream; Elo fängt es nach dem Spiel auf; ggf. manuelle Elo-Korrektur |
| Konkretes Wetter (Regen/Wind/Temp) | Niedrig | kein Forecast (Reproduzierbarkeit); nur Umwelt-Stress als Varianz |
| KO-Sieger bei Elfmeterschießen | Niedrig | aus Torergebnis nicht ableitbar → Fallback höheres Elo (wie Sim/Projektion) |
| KO-Bracket-Pfad | Niedrig | vereinfachte A1–B2-Paarung, nicht der offizielle Überkreuz-Pfad |
| Taktik / Aufstellung / Schiedsrichter / Head-to-Head | mittel–niedrig | nicht modelliert; im Frontend als „Was das Modell nicht weiß" kommuniziert |
| Venue-Zuordnung pro Spiel | Niedrig | vereinfacht (nicht je Spiel aus API); betrifft nur Höhe/Reise/Umwelt, alle klein gedeckelt |
| Dixon-Coles ρ=−0.13 | Niedrig | aus Literatur (WM 2010–2022), nicht neu kalibriert |

## Bewusste Nicht-Ziele
Keine neuen ML-Modelle/Feature-Explosion (Prediction Core ist nahe optimal, siehe
MODEL_EVALUATION). Keine nicht-reproduzierbaren Live-Quellen (z. B. Wetter-Forecast-APIs).
Keine Änderung an Elo/Poisson/Dixon-Coles/Simulationsarchitektur ohne Anlass.

## Betriebliche Grenzen (Free-Stack)
- Backend (Render Free) **schläft nach ~15 min** → Cold Start. **Gemindert** durch den
  Keep-Alive-Workflow (`keepalive.yml`, Health-Ping alle 10 min); Detailseiten sind zudem
  vorgerendert (kein Backend-Treffer beim Erstaufruf).
- Backend **eine Instanz / ein Worker** (In-Process-Cache + BackgroundTasks) — bewusst, nicht skalieren.
- Simulation läuft als Hintergrund-Task (100k Runs; entkoppelt vom Interface); ein laufender Lauf
  geht bei Neustart verloren, ist aber idempotent neu auslösbar.
- Auto-Sync alle 30 min (RapidAPI-Kontingent) → Ergebnisse erscheinen mit bis zu ~30 min Verzug
  (kein Live-Ticker; bewusst, um die API-Quota zu schonen).
