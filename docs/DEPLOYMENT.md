# DEPLOYMENT — Free-Stack (Vercel + Render + Neon)

**Live:** Frontend https://wm2026-prediction-system.vercel.app · Backend
https://wm2026-backend-phwx.onrender.com · DB Neon · Code github.com/annigue/wm2026-prediction-system.
**Kosten:** 0 €/Monat.

## Architektur
| Komponente | Dienst | Plan / Region |
|---|---|---|
| Frontend (Next.js) | **Vercel** | Free |
| Backend (FastAPI, Docker) | **Render** | Free, **Region Frankfurt** (1 Instanz) |
| Datenbank (Postgres) | **Neon** | Free (Direct-Endpoint, eu-central, SSL) |
| Redis | — | weggelassen (graceful, In-Process-Cache statt) |

`render.yaml` ist **Backend-only**; Frontend → Vercel, DB → Neon (extern).

> **Wichtig — Region:** Backend und Neon liegen beide in **Frankfurt/eu-central**. Das
> eliminiert die Cross-Region-Latenz pro DB-Query (war die Hauptursache früherer Langsamkeit:
> Detailseite 4.5 s → 0.12 s). Render-Region ist pro Service fix → ein Wechsel erfordert
> Service-Neuanlage (daher die aktuelle URL mit `-phwx`-Suffix).

## 1. Datenbank (Neon)
1. neon.tech → Projekt (Region nahe Backend, **Frankfurt/eu-central**). **Direct connection** (Host **ohne** `-pooler`).
2. Migration:
   ```bash
   pg_dump --no-owner --no-privileges --clean --if-exists <lokale-url> > wm2026.sql
   psql "<neon-direct-url>" -f wm2026.sql
   ```
3. Treiber-URLs: `DATABASE_URL = postgresql+asyncpg://…?ssl=require` ·
   `DATABASE_URL_SYNC = postgresql+psycopg2://…?sslmode=require` (asyncpg nutzt `ssl`, nicht `sslmode`).

## 2. Backend (Render, Blueprint)
1. Render → New → **Blueprint** → Repo, Branch `main`, `render.yaml` → Apply.
2. Env-Vars (sync:false): `DATABASE_URL`, `DATABASE_URL_SYNC`, `ODDS_API_KEY`, `RAPIDAPI_KEY`,
   `CORS_ORIGINS` (`*` oder Vercel-URL), `REDIS_URL` (leer). `ADMIN_TOKEN` generiert Render;
   `MONTE_CARLO_RUNS=100000` und `region: frankfurt` stehen in render.yaml.
3. Health `/api/v1/health` grün. Docker-Build (numpy/scipy) ~2–4 min.

## 3. Frontend (Vercel)
1. vercel.com → Add New Project → Repo. **Root Directory = `frontend`**.
2. Env-Var **`NEXT_PUBLIC_API_URL`** = Backend-URL (Build-Zeit → bei Änderung neu deployen!).
3. Deploy.

### Frontend-Performance (im Code)
- **ISR** (`export const revalidate = 60` + `fetch(..., {next:{revalidate:60}})`): Seiten aus Vercel-Cache.
- **`generateStaticParams`** für `/match/[id]` + `/team/[id]`: alle Detailseiten beim Build vorgerendert
  (Build ruft das Backend → Backend muss erreichbar sein; bei Ausfall Fallback auf On-Demand).

## 4. Automatisierung (GitHub Actions, `.github/workflows/`)
| Workflow | Takt | Zweck |
|---|---|---|
| `keepalive.yml` | alle 10 min | `GET /health` — hält das Free-Backend wach (kein Cold-Start) |
| `sync-results.yml` | alle 30 min | `POST /admin/auto-update` — Ergebnisse syncen + Recompute |

**Secret:** `sync-results.yml` braucht das Repo-Secret **`ADMIN_TOKEN`** (= Render-`ADMIN_TOKEN`).
GitHub → Settings → Secrets and variables → Actions → New repository secret.
Bei URL-Wechsel des Backends: `BASE` in beiden Workflows anpassen.

### `/admin/auto-update` (idempotent)
1. `sync_all` → echte Ergebnisse von der WM-API in die DB.
2. Elo **nur für neu beendete Spiele** (die noch keinen `elo_ratings`-Eintrag haben), chronologisch.
3. Bei neuen Ergebnissen: Hintergrund-Recompute (Form → KO-Bracket → Prognosen → Cache → Simulation).

## 5. Migrations-/Safe-Deploy
- Schema: `create_all` (idempotent) beim Boot; Indizes via `alembic stamp 001 && alembic upgrade head`.
- Backend = 1 Instanz / 1 Worker (In-Process-Cache + BackgroundTasks) — nie skalieren.
- Rollback: Render Deploy-Rollback + Neon-Branch/Backup. Modellcode unverändert → kein Modell-Rollback.

## 6. Validierungs-Checkliste
- [ ] `/api/v1/health` 200, `/docs` lädt
- [ ] `/teams/` → 60, `/tournament/simulate` → champion_probabilities
- [ ] `/admin/odds-status` → `api_key_configured:true`
- [ ] Vercel: Startseite + Detailseiten schnell (`x-vercel-cache: HIT/PRERENDER`)
- [ ] GitHub Actions: keepalive grün; sync-results grün (nach `ADMIN_TOKEN`)
- [ ] Backend = 1 Instanz, Region Frankfurt

## 7. Betrieb
- Cold-Start durch keepalive weitgehend vermieden. 100k-Simulation läuft im Hintergrund.
- Render-Free-Kontingent: 24/7 ≈ 720 von 750 h/Monat — passt für den einen Service.
- Optional: `CORS_ORIGINS` exakt setzen, Neon-Passwort rotieren, alten US-Service löschen.
