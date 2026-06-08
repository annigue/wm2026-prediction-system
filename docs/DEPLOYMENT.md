# DEPLOYMENT — Free-Stack (Vercel + Render + Neon)

**Live:** Frontend https://wm2026-prediction-system.vercel.app · Backend
https://wm2026-backend.onrender.com · DB Neon · Code github.com/annigue/wm2026-prediction-system.
**Kosten:** 0 €/Monat.

## Architektur
| Komponente | Dienst | Plan |
|---|---|---|
| Frontend (Next.js) | **Vercel** | Free |
| Backend (FastAPI, Docker) | **Render** | Free (1 Instanz, schläft nach ~15 min) |
| Datenbank (Postgres) | **Neon** | Free (Direct-Endpoint, SSL) |
| Redis | — | weggelassen (graceful) |

`render.yaml` ist **Backend-only**; Frontend → Vercel, DB → Neon (extern).

## 1. Datenbank (Neon)
1. neon.tech → Projekt anlegen (Region nahe EU). **Direct connection** (Host **ohne** `-pooler`).
2. Migration der bestehenden DB:
   ```bash
   pg_dump --no-owner --no-privileges --clean --if-exists <lokale-url> > wm2026.sql
   psql "<neon-direct-url>" -f wm2026.sql
   ```
3. Treiber-URLs ableiten:
   - `DATABASE_URL = postgresql+asyncpg://USER:PASS@HOST/DB?ssl=require`
   - `DATABASE_URL_SYNC = postgresql+psycopg2://USER:PASS@HOST/DB?sslmode=require`
   ⚠️ asyncpg nutzt `ssl=require` (nicht `sslmode`); Pooler-Endpoint vermeiden.

## 2. Backend (Render, Blueprint)
1. Render → New → **Blueprint** → Repo, Branch `main`, Path `render.yaml` → Apply (erstellt `wm2026-backend`).
2. Env-Vars (sync:false): `DATABASE_URL`, `DATABASE_URL_SYNC` (Neon, s. o.), `ODDS_API_KEY`,
   `RAPIDAPI_KEY`, `CORS_ORIGINS` (Vercel-URL), `REDIS_URL` (leer). `ADMIN_TOKEN` generiert Render;
   `MONTE_CARLO_RUNS=30000` steht in render.yaml.
3. Health-Check `/api/v1/health` muss grün sein. Docker-Build (numpy/scipy) dauert 2–4 min.

## 3. Frontend (Vercel)
1. vercel.com → Add New Project → Repo importieren. **Root Directory = `frontend`**.
2. Env-Var **`NEXT_PUBLIC_API_URL` = `https://wm2026-backend.onrender.com`** (Build-Zeit!).
3. Deploy → URL z. B. `…vercel.app`.

## 4. Initiale Boot-Sequenz (idempotent)
Bei migrierter DB ist alles vorhanden; nur auffrischen:
```bash
curl -X POST https://wm2026-backend.onrender.com/api/v1/predict-all
curl -X POST https://wm2026-backend.onrender.com/api/v1/admin/resolve-bracket -H "Authorization: <ADMIN_TOKEN>"
curl -X POST https://wm2026-backend.onrender.com/api/v1/admin/simulate -H "Authorization: <ADMIN_TOKEN>"
```
Reihenfolge: Daten/Sync → predict-all → resolve-bracket → simulate (= Auto-Flow nach jedem Ergebnis).

## 5. Migrations-/Safe-Deploy-Strategie
- Schema: `create_all` (idempotent) beim Boot; Indizes via `alembic stamp 001 && alembic upgrade head`.
- Sim ist idempotent/re-runbar; Backend = 1 Instanz/1 Worker (nie skalieren).
- Rollback: Render Deploy-Rollback + Neon-Branch/Backup. Modellcode unverändert → kein Modell-Rollback.

## 6. Validierungs-Checkliste
- [ ] `/api/v1/health` 200, `/docs` lädt
- [ ] `/api/v1/teams/` → 60, `/tournament/simulate` → champion_probabilities
- [ ] `/admin/odds-status` → `api_key_configured:true`
- [ ] Vercel-Startseite rendert Titelchancen; alle Seiten 200
- [ ] CORS-Preflight gibt die Vercel-Origin zurück
- [ ] Backend = 1 Instanz

## 7. Betrieb
- **Cold Start** ~30–60 s nach Inaktivität → optional UptimeRobot auf `/api/v1/health` alle 14 min.
- Ergebnisse/Sync brauchen `ADMIN_TOKEN`.
- Optional: `CORS_ORIGINS` exakt setzen, Neon-Passwort rotieren.
