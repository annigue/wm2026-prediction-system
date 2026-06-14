import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routers import teams, matches, groups, tournament, dashboard, admin, predictions
from app.models import appstate  # noqa: F401 — vor create_all registrieren (app_state-Tabelle)
from app.models import results_history  # noqa: F401 — international_results-Tabelle


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="WM 2026 Prognose API",
    description="Fußball WM 2026 Simulation & Prognose-Tool",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS-Origins: explizite Liste (env CORS_ORIGINS) + Default inkl. Prod-Frontend.
# allow_origin_regex erlaubt zusätzlich JEDE *.vercel.app-Domain (Production + Previews),
# damit Browser-Aufrufe (Admin, StatusBar) nicht an einer falsch gesetzten Env-Var scheitern.
_cors_origins = [
    o.strip() for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,https://wm2026-prediction-system.vercel.app",
    ).split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(teams.router,       prefix="/api/v1/teams",      tags=["teams"])
app.include_router(matches.router,     prefix="/api/v1/matches",    tags=["matches"])
app.include_router(groups.router,      prefix="/api/v1/groups",     tags=["groups"])
app.include_router(tournament.router,  prefix="/api/v1/tournament", tags=["tournament"])
app.include_router(dashboard.router,   prefix="/api/v1/dashboard",  tags=["dashboard"])
app.include_router(admin.router,       prefix="/api/v1/admin",      tags=["admin"])
app.include_router(predictions.router, prefix="/api/v1",            tags=["predictions"])


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}
