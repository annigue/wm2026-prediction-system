# DATA_SOURCES — Datenquellen & Ingestion

## Übersicht

| Datum | Quelle | Verwendung | Status |
|---|---|---|---|
| Spielplan, Tabellen, Ergebnisse | **world-cup-2026-live-api** (RapidAPI) | Sync (`/wc/draw`, `/wc/standings`) | aktiv (`RAPIDAPI_KEY`) |
| Initial-Elo | **eloratings.net** (Datei-Import) | einmaliger Bootstrap | importiert |
| Wettquoten | **The Odds API** | Betting Decision Engine | aktiv (`ODDS_API_KEY`) |
| Form | berechnet aus `match_results` | form_engine v2 | datengetrieben |
| Marktwert/Alter/Caps | manueller Seed (Transfermarkt o. ä.) | PRIOR | statisch/eingefroren |
| Venue-Geodaten | Seed (Höhe, lat/lon) | Höhe/Reise/Umwelt-Stress | statisch |

## Spieldaten — world-cup-2026-live-api (`sync_service.py`)
- Host `world-cup-2026-live-api.p.rapidapi.com`, Header `X-RapidAPI-Key`/`-Host`.
- `/wc/draw` liefert die **72 Gruppenspiele** (Round 1–3) mit echten Kickoff-Zeiten; **keine**
  KO-Spiele (die KO-Termine sind Platzhalter / kommen aus dem offiziellen FIFA-Plan).
- `sync_all(session)` ist **idempotent**: aktualisiert Status/Kickoff, trägt Ergebnisse nach,
  legt nichts doppelt an. Namens-Mapping API→team_id wird aus der DB (`home_country`) gebaut
  + Aliase (z. B. „Bosnia & Herzegovina"→bosnia, „United States"→usa).
- `/admin/status` macht **keinen** API-Call (nur letzter bekannter Rate-Limit-Stand).

## Initial-Elo — eloratings.net
- Quelle committed: `backend/data/eloratings_2026-06-06.txt`. Import:
  `python scripts/import_initial_elo.py --file data/eloratings_2026-06-06.txt --eloratings --write-db`
  → `data/initial_elo.json` + DB (`data_source='eloratings_init'`).
- Gleiche Elo-Formulierung wie das Projekt (SCALE=400) → keine Umrechnung, **kein manuelles Tuning**.
- Danach läuft Elo live über Bayesian Updates weiter.

## Wettquoten — The Odds API (`odds_provider.py`)
- Sportkey `soccer_fifa_world_cup`, Märkte `h2h,totals`, Region EU, Decimal.
- TTL-Cache 15 min + **Fallback auf last-known odds** bei Rate-Limit/Fehler.
- Team-Matching: englische Namen (`home_country`) + Akzent-/Alias-Normalisierung.
- Ohne Key → graceful Fallback auf synthetische fair-odds (klar geflaggt, kein echter Edge).

## Form — datengetrieben (`form_engine.py`, v2)
Ausschließlich aus realen Ergebnissen: Punkte (3/1/0) + Tordifferenz + Recency-Decay über die
letzten N=6 Spiele → `form_score ∈ [−1,1]`. Ohne Ergebnisse exakt 0.0. **Single Source of
Truth** (nur diese Funktion + `scripts/refresh_form.py` schreiben `form_score`).

## Statische PRIOR
- **Marktwert** — bewusst **nicht** automatisiert (Scraping fragil; Modellnutzen 6× < Elo):
  statisch, eingefroren, klar gelabelt.
- **Alter/Caps** — als Modell-Faktoren entfernt; Spalten bleiben nur zur Anzeige.
- **Venue-Geodaten** — Höhe + Koordinaten; treiben Höhe/Reise (Adjuster) + Umwelt-Stress (Sim).

## Fallback-Strategie
System funktioniert ohne externe APIs: DB-Stand bleibt erhalten, Ergebnisse manuell via
`POST /matches/{id}/result` eintragbar, Elo/Form/Sim laufen lokal.
