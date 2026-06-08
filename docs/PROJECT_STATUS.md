# PROJECT_STATUS — Aktueller Projektstand

**Zuletzt aktualisiert:** 2026-06-07
**Phase:** Live in Produktion (kostenloser Stack)
**WM-Start:** 2026-06-11

> Hinweis: Die `docs/` wurden am 2026-06-07 nach einem Quellcode-Verlust vollständig neu
> erstellt und spiegeln den **tatsächlichen Stand des wiederhergestellten Codes**.
> Siehe [RECOVERY.md](RECOVERY.md).

---

## Live-Deployment (0 €/Monat)

| Komponente | Dienst | URL |
|---|---|---|
| Frontend | Vercel | https://wm2026-prediction-system.vercel.app |
| Backend-API | Render (Free, Docker) | https://wm2026-backend.onrender.com |
| Datenbank | Neon (Postgres) | (intern) |
| Code | GitHub | github.com/annigue/wm2026-prediction-system |

Details: [DEPLOYMENT.md](DEPLOYMENT.md).

---

## System (was läuft)

- **Elo-Rating** (Init aus eloratings.net, live via Bayesian Update nach jedem Ergebnis)
- **Poisson + Dixon-Coles** Tormodell → W/U/N + xG + Scoreline-Verteilung
- **Feature Adjustment Layer** (5 deterministische Faktoren als Elo-Delta)
- **Context Injection Layer** (stochastische Varianz in der Simulation)
- **Monte-Carlo-Turniersimulation** (konfigurierbar; Prod: 30.000 Runs)
- **KO-Bracket-Resolver** (füllt KO-Spiele aus realen Ergebnissen)
- **Betting Decision Engine** (EV + Edge + NO_BET) mit echter Odds-Integration
- **Tipping Engine** (punktoptimaler Exakt-Tipp)
- **Form Engine v2** (Punkte + Tore + Recency, Single Source of Truth)
- FastAPI-Backend + Next.js-14-Frontend + PostgreSQL

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
| `services/bayesian_updater.py` | Elo-Update beider Teams nach Ergebnis (K=20) |
| `services/form_engine.py` | Form v2 (Punkte+Tore+Recency) — Single Source of Truth |
| `services/feature_engineering.py` | COMPUTED/PRIOR-Klassifikation + goals_avg |
| `services/betting_engine.py` | EV, Edge, NO_BET, Best/Safe/Value, fair_odds |
| `services/decision_engine.py` | Kanonische Decision-Facade (delegiert an betting_engine) |
| `services/odds_normalizer.py` | Overround-Entfernung (Single Source of Truth) |
| `services/odds_provider.py` | The Odds API Client (Cache + last-known-Fallback) |
| `services/odds_aggregator.py` | Marktquoten → faire WS |
| `services/market_calibration_service.py` | Monitoring Modell vs. Markt (KL, Brier) |
| `services/tipping_engine.py` | Punktoptimaler Exakt-Tipp (EV-Maximierung) |
| `services/cache.py` | Redis-Cache mit Graceful Degradation |
| `services/sync_service.py` | Idempotenter Sync von world-cup-2026-live-api |
| `models/` `schemas/` `routers/` | SQLAlchemy-Models, Pydantic-Schemas, 7 Router |
| `scripts/` | seed_data, import_initial_elo, refresh_form, eval/ |
| `alembic/` | Migrationen (001 Baseline, 002 Indizes) |

## Frontend (`frontend/src/`)
- Seiten: `/` (Dashboard), `/groups`, `/matches`, `/match/[id]`, `/bracket`, `/team/[id]`, `/tipps`
- Komponenten: SyncButton, ResultForm(+Wrapper), BettingPanel, TipPanel, ui/{ProbabilityBar, ScoreHeatmap, FactorExplanation}
- `lib/api.ts` (API-Client), `lib/tips.ts` (xG-/Modell-Tipp), `types.ts`

---

## Datenbankstand (Neon, 2026-06-07)

| Tabelle | Einträge |
|---|---|
| teams | 60 |
| team_features | 60 (elo: eloratings_init; form: 0.0 bis erste Ergebnisse) |
| group_memberships | 48 |
| matches | 104 (72 Gruppe + 32 KO-Platzhalter) |
| match_predictions | 72 |
| match_results | 0 (WM noch nicht gestartet) |
| tournament_simulations | 8 |

---

## Offene Punkte
| Thema | Priorität |
|---|---|
| Uptime-Pinger gegen Render-Cold-Start (UptimeRobot → /api/v1/health) | Niedrig |
| `CORS_ORIGINS` exakt auf Vercel-URL (statt `*`) | Niedrig |
| Neon-Passwort rotieren | Niedrig |
| Venue-Zuordnung pro Spiel aus API (aktuell vereinfacht) | Niedrig |
