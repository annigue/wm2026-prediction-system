from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks, Depends
from sqlalchemy import select, desc, text, create_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import get_db, AsyncSessionLocal

router = APIRouter()


def _check_token(authorization: str):
    if (authorization or "").replace("Bearer ", "").strip() != settings.admin_token:
        raise HTTPException(status_code=401, detail="Ungültiges Admin-Token")


@router.get("/status")
async def sync_status():
    """Sync-/Rate-Limit-Status (KEIN API-Call)."""
    from app.services.sync_service import get_status
    return get_status()


@router.post("/sync")
async def sync_data(authorization: str = Header(...)):
    _check_token(authorization)
    from app.services.sync_service import sync_all
    engine = create_engine(settings.database_url_sync)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        result = sync_all(session)
    engine.dispose()
    return result


@router.post("/simulate")
async def run_simulation(background_tasks: BackgroundTasks, authorization: str = Header(...)):
    _check_token(authorization)
    background_tasks.add_task(_simulation_task)
    return {"status": "started",
            "message": f"Simulation mit {settings.monte_carlo_runs:,} Runs läuft im Hintergrund."}


@router.post("/refresh-features")
async def refresh_features(authorization: str = Header(...)):
    _check_token(authorization)
    from app.services.feature_engineering import refresh_all_teams_with_results
    engine = create_engine(settings.database_url_sync)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        results = refresh_all_teams_with_results(session)
        session.commit()
    engine.dispose()
    updated = [r for r in results if r.get("updated")]
    return {"teams_refreshed": len(results), "teams_with_updates": len(updated), "details": results}


@router.post("/refresh-form")
async def refresh_form(authorization: str = Header(...)):
    _check_token(authorization)
    from app.services.form_engine import update_all_forms
    engine = create_engine(settings.database_url_sync)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        results = update_all_forms(session)
        session.commit()
    engine.dispose()
    updated = [r for r in results if r.n_matches > 0]
    return {"teams_processed": len(results), "teams_with_form": len(updated),
            "forms": [{"team_id": r.team_id, "form_score": r.form_score,
                       "form_index": r.form_index, "n_matches": r.n_matches} for r in updated]}


@router.get("/odds-status")
async def odds_status():
    from app.services.odds_aggregator import status
    from app.services.odds_provider import last_good_age_seconds
    s = status()
    s["last_good_odds_age_seconds"] = last_good_age_seconds("h2h")
    s["cache_ttl_seconds"] = settings.odds_cache_ttl
    return s


@router.post("/resolve-bracket")
async def resolve_bracket_endpoint(authorization: str = Header(...)):
    _check_token(authorization)
    from app.services.knockout_resolver import resolve_bracket
    engine = create_engine(settings.database_url_sync)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        result = resolve_bracket(session)
        session.commit()
    engine.dispose()
    if result.get("filled"):
        async with AsyncSessionLocal() as db:
            from app.services.prediction_engine import predict_all_scheduled
            result["predictions_recomputed"] = await predict_all_scheduled(db)
            await db.commit()
        from app.services.cache import invalidate
        invalidate("wm2026:")
    return result


@router.get("/market-calibration")
async def market_calibration():
    from app.services.market_calibration_service import build_calibration_report
    engine = create_engine(settings.database_url_sync)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        report = build_calibration_report(session)
    engine.dispose()
    return report


@router.get("/feature-audit")
async def feature_audit():
    from app.services.feature_engineering import get_feature_audit
    engine = create_engine(settings.database_url_sync)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        audit = get_feature_audit(session)
    engine.dispose()
    return audit


@router.get("/simulation-status")
async def simulation_status(db: AsyncSession = Depends(get_db)):
    from app.models.simulation import TournamentSimulation
    sim = (await db.execute(
        select(TournamentSimulation).order_by(desc(TournamentSimulation.simulated_at)).limit(1)
    )).scalar_one_or_none()
    if not sim:
        return {"available": False}
    return {"available": True, "model_version": sim.model_version, "n_runs": sim.n_runs,
            "simulated_at": sim.simulated_at.isoformat(),
            "top_champions": sorted(sim.champion_probs.items(), key=lambda kv: kv[1],
                                    reverse=True)[:10]}


def _simulation_task():
    """Synchroner Task: Simulation berechnen und in DB speichern."""
    from app.models.simulation import TournamentSimulation
    from app.services.tournament_simulator import TournamentSimulator
    from app.services.context_modifier import venue_environment_stress

    engine = create_engine(settings.database_url_sync)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        feat_rows = session.execute(text("""
            SELECT DISTINCT ON (t.id) t.id, tf.elo_rating, tf.form_score, tf.market_value_millions
            FROM teams t JOIN team_features tf ON tf.team_id = t.id
            ORDER BY t.id, tf.snapshot_date DESC
        """)).fetchall()
        elos = {r[0]: float(r[1] or 1500) for r in feat_rows}
        features = {r[0]: {"form_score": float(r[2] or 0.0),
                           "market_value_millions": float(r[3] or 200.0)} for r in feat_rows}

        venue_rows = session.execute(text("""
            SELECT tid, v.altitude_m, v.lat FROM (
                SELECT home_team_id AS tid, venue_id FROM matches
                WHERE stage='GROUP_STAGE' AND home_team_id IS NOT NULL
                UNION ALL
                SELECT away_team_id AS tid, venue_id FROM matches
                WHERE stage='GROUP_STAGE' AND away_team_id IS NOT NULL
            ) m JOIN venues v ON v.id = m.venue_id
        """)).fetchall()
        es_acc: dict[str, list[float]] = {}
        for tid, alt, lat in venue_rows:
            es_acc.setdefault(tid, []).append(venue_environment_stress(alt, lat))
        for tid, vals in es_acc.items():
            if tid in features and vals:
                features[tid]["env_stress"] = sum(vals) / len(vals)

        group_rows = session.execute(text(
            "SELECT group_id, team_id FROM group_memberships ORDER BY group_id")).fetchall()
        groups: dict[str, list[str]] = {}
        for gid, tid in group_rows:
            groups.setdefault(gid, []).append(tid)
        if not groups:
            engine.dispose()
            return

        sim = TournamentSimulator(groups=groups, elos=elos, features=features)
        result = sim.run(n_runs=settings.monte_carlo_runs)

        version = datetime.now(timezone.utc).strftime("v1.%m%d-%H%M")
        session.add(TournamentSimulation(
            model_version=version, n_runs=result["n_runs"],
            champion_probs=result["champion_probs"], stage_probs=result["stage_probs"],
            triggered_by="admin_api",
        ))
        session.commit()
    engine.dispose()
