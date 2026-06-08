# PROJECT_STATUS — Aktueller Projektstand

**Zuletzt aktualisiert:** 2026-06-08
**Phase:** Live in Produktion (kostenloser Stack), performance-optimiert, Auto-Sync aktiv
**WM-Start:** 2026-06-11

> Hinweis: Die `docs/` wurden am 2026-06-07 nach einem Quellcode-Verlust vollständig neu
> erstellt und spiegeln den **tatsächlichen Stand des Codes**. Siehe [RECOVERY.md](RECOVERY.md).

---

## Live-Deployment (0 €/Monat)

| Komponente | Dienst | URL |
|---|---|---|
| Frontend | Vercel | https://wm2026-prediction-system.vercel.app |
| Backend-API | Render (Free, Docker, **Frankfurt**) | https://wm2026-backend-phwx.onrender.com |
| Datenbank | Neon (Postgres, eu-central) | (intern) |
| Code | GitHub | github.com/annigue/wm2026-prediction-system |

Details + Performance-Architektur: [DEPLOYMENT.md](DEPLOYMENT.md).

---

## System (was läuft)

- **Elo-Rating** (Init aus eloratings.net, live via Bayesian Update nach jedem Ergebnis)
- **Poisson + Dixon-Coles** Tormodell → W/U/N + xG + Scoreline-Verteilung
- **Feature Adjustment Layer** (5 deterministische Faktoren als Elo-Delta)
- **Context Injection Layer** (stochastische Varianz in der Simulation)
- **Monte-Carlo-Turniersimulation** (Prod: 100.000 Runs, Hintergrund-Task)
- **KO-Bracket-Resolver** (füllt KO-Spiele aus realen Ergebnissen)
- **Betting Decision Engine** (EV + Edge + NO_BET) mit echter Odds-Integration
- **Tipping Engine** (punktoptimaler Exakt-Tipp) + **Tipp-vs-Ergebnis-Auswertung** (Kicktipp-Punkte)
- **Automatischer Ergebnis-Sync** (CI-Cron → `/admin/auto-update`, idempotent)
- **Form Engine v2** (Punkte + Tore + Recency, Single Source of Truth)
- FastAPI-Backend + Next.js-14-Frontend + PostgreSQL

---

## Automatischer Datenfluss (kein manuelles Eintragen nötig)

```
GitHub Actions (sync-results.yml, alle 30 min)
  → POST /admin/auto-update (ADMIN_TOKEN)
     → sync_all: echte Ergebnisse von der WM-API in die DB
     → Elo idempotent für NEU beendete Spiele (nur Spiele ohne Elo-Eintrag)
     → Hintergrund: Form → KO-Bracket → Prognosen → Cache → Simulation
GitHub Actions (keepalive.yml, alle 10 min) → /health (gegen Render-Cold-Start)
```
Manuelles Eintragen via `POST /matches/{id}/result` bleibt als Fallback möglich.

---

## Performance-Architektur (Interface reagiert schnell)

- **Frontend ISR** (`revalidate = 60`): Listenseiten aus Vercel-Cache (~0.1 s).
- **`generateStaticParams`**: alle Spiel-/Team-Detailseiten beim Build vorgerendert → erster Aufruf sofort.
- **Backend in Frankfurt** (co-located mit Neon) → keine US↔EU-Latenz pro Query (Detail 4.5 s → 0.12 s).
- **Verschlankte Queries** (keine volle Prognose-JSONB/elo_history in Listen) + **In-Process-Cache** für die Projektion.
- **Keep-Alive-Ping** gegen Cold-Start. Die 100k-Simulation läuft im Hintergrund und blockiert das Interface nicht.

---

## Dateistruktur (Backend `backend/app/`)

| Datei | Rolle |
|---|---|
| `services/elo_model.py` | Elo: expected_score, update, goal_diff_multiplier |
| `services/poisson_model.py` | Poisson + Dixon-Coles (ρ=−0.13), PredictionResult |
| `services/feature_adjuster.py` | 5-Faktor-Adjustment (Form, Markt, Höhe, Reise, Rest-Days) |
| `services/context_modifier.py` | Simulations-Varianz (Form, Markt, KO-Druck, Umwelt-Stress) |
| `services/prediction_engine.py` | Orchestriert Elo+Features+Poisson → DB |
| `services/tournament_simulator.py` | Monte Carlo (vektorisierte Gruppen + KO-Loop) |
| `services/tournament_projection.py` | Deterministische Einzelprojektion + `rank_and_pair` |
| `services/knockout_resolver.py` | KO-Teilnehmer aus realen Ergebnissen in DB schreiben |
| `services/bayesian_updater.py` | Elo-Update beider Teams nach Ergebnis (K=20, inkrementell) |
| `services/form_engine.py` | Form v2 (Punkte+Tore+Recency) — Single Source of Truth |
| `services/betting_engine.py` / `decision_engine.py` | EV, Edge, NO_BET, Best/Safe/Value |
| `services/odds_*` | Odds-Normalizer, Provider (Cache/Fallback), Aggregator, Calibration |
| `services/tipping_engine.py` | Punktoptimaler Tipp + `_points` (Kicktipp-Scoring) |
| `services/sync_service.py` | Idempotenter Sync von world-cup-2026-live-api |
| `routers/admin.py` | u. a. **`/auto-update`** (Sync + Elo + Recompute) |
| `routers/matches.py` | Liste (verschlankt) + Detail + `_after_result_tasks` |
| `models/` `schemas/` `routers/` | SQLAlchemy-Models, Pydantic-Schemas, 7 Router |
| `scripts/` `alembic/` | seed/import/eval, Migrationen |

## Frontend (`frontend/src/`)
- Seiten: `/` (Dashboard), `/groups`, `/matches`, `/match/[id]`, `/bracket`, `/team/[id]`, `/tipps`
- `/tipps`: kommende Spiele + **„Bereits gespielt" (Tipp vs. Ergebnis + Punkte-Bilanz)**
- `lib/tips.ts`: `computeTips` + **`evaluateTip`** (Kicktipp-Punkte); Match-Detail mit Tipp-vs-Ergebnis-Karte

## CI (`.github/workflows/`)
- `keepalive.yml` — Health-Ping alle 10 min (Cold-Start)
- `sync-results.yml` — `/admin/auto-update` alle 30 min (Secret `ADMIN_TOKEN`)

---

## Datenbankstand (Neon, Stand vor WM-Start)
60 teams · 60 team_features · 48 group_memberships · 104 matches · 0 results · 72 predictions · 8 simulations.

## Offene Punkte
| Thema | Status |
|---|---|
| `ADMIN_TOKEN` als GitHub-Secret setzen (für Auto-Sync) | offen (User-Aktion) |
| Alten Render-Service `wm2026-backend` (US) löschen | optional (Aufräumen) |
| Venue-Zuordnung pro Spiel aus API | optional |
