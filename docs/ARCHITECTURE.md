# ARCHITECTURE — Systemübersicht

```
                Browser (überall)
                      │ HTTPS
        ┌─────────────┴───────────────┐
        ▼                             ▼
  Frontend (Next.js 14, Vercel)   Backend (FastAPI, Render Free, Docker, 1 Instanz)
  - App Router, SSR-Seiten         - Prediction Core (Elo/Poisson/Dixon-Coles)
  - lib/api.ts → Backend           - Feature/Context Layer, Monte-Carlo-Sim
  - Komponenten (Sync/Result        - KO-Resolver, Betting/Decision, Tipping, Form, Sync
    = clientseitig, CORS)           - BackgroundTasks (Threadpool) für Sim/Resolve
        │ NEXT_PUBLIC_API_URL          │ asyncpg (read) + psycopg2 (sync tasks)
        └───────────── API ───────────┤
                                       ▼
                          PostgreSQL (Neon, managed)
                                       │
                  externe APIs: eloratings (Init) · The Odds API · world-cup-2026-live-api
                  optional: Redis (graceful, im Free-Stack weggelassen)
```

## Schichten (Backend)
1. **Data Layer** — SQLAlchemy-Models (`models/`), async Engine (`database.py`), Config (`config.py`).
2. **Domain/Services** (`services/`) — reine, gut testbare Logik (Elo, Poisson, Adjuster, Form,
   Simulator, Resolver, Betting, Odds, Tipping). Stateless wo möglich.
3. **Orchestrierung** — `prediction_engine` (async), Hintergrund-Tasks in `routers/matches`,
   `routers/admin._simulation_task`.
4. **API** (`routers/`) — 7 Router unter `/api/v1/*`; Pydantic-Schemas (`schemas/`) als Contract.

## Wichtige Design-Entscheidungen
- **Single-Instance-Backend:** In-Memory-Odds-Cache + BackgroundTasks ⇒ genau 1 Instanz/Worker.
- **Sim als sync BackgroundTask** → läuft im Starlette-Threadpool, blockiert den Event-Loop nicht;
  HTTP-Request kehrt sofort (202) zurück.
- **Zwei DB-Treiber:** asyncpg (`DATABASE_URL`) für die App, psycopg2 (`DATABASE_URL_SYNC`) für
  synchrone Hintergrund-Tasks/Scripts/alembic.
- **Schema:** `lifespan` ruft `create_all` (idempotent) beim Boot; alembic (001 Baseline aus
  Models, 002 Indizes) für reproduzierbare Migrationen.
- **Graceful Degradation:** Redis optional, Odds optional — System läuft immer.
- **Determinismus:** Prognose & Projektion deterministisch; Simulation reproduzierbar (Seed).

## Datenfluss „Ergebnis eintragen"
```
POST /matches/{id}/result (ADMIN_TOKEN)
  → MatchResult speichern + status=FINISHED
  → bayesian_updater.apply_result (Elo beider Teams, K=20)
  → BackgroundTask: form_engine → knockout_resolver → predict_all → cache.invalidate → _simulation_task
```

## Frontend
Next.js 14 App Router. Datenseiten sind **Server Components** (SSR, holen die API serverseitig
→ kein CORS). Interaktive Teile (SyncButton, ResultForm) sind **Client Components** (Browser-Fetch
→ CORS). `output: "standalone"`; auf Vercel nativer Next-Build.
