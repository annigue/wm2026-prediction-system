# API_SPEC — REST-Endpunkte

Basis: `/api/v1`. Swagger UI: `/docs`. Live: `https://wm2026-backend-phwx.onrender.com`.
Antworten als JSON. Admin-Endpunkte erfordern Header `Authorization: <ADMIN_TOKEN>`
(auch `Bearer <token>` wird akzeptiert).

## Health
- `GET /api/v1/health` → `{"status":"ok"}`

## Teams
- `GET /teams/` → `{ "teams": TeamSummary[] }` (sortiert nach Titelchance/Elo)
- `GET /teams/{id}` → `TeamDetail` (features, elo_history, tournament_probs, group_id)

## Matches
- `GET /matches/?stage=&group_id=&team_id=&status=` → `{ "matches": MatchSummary[] }`
- `GET /matches/{id}` → `MatchDetail` (inkl. venue + PredictionDetail)
- `GET /matches/{id}/bets?home_odds=&draw_odds=&away_odds=&over25_odds=&under25_odds=&btts_yes_odds=`
  → BettingReport (best/safe/value/no_bets, EV, Edge). Ohne Query-Quoten: echte Odds-API o. fair-odds.
- `GET /matches/{id}/tip` → punktoptimaler Tipp (TipRecommendation)
- `POST /matches/{id}/result` *(admin)* — Body `ResultCreate` (home_goals, away_goals, …) →
  speichert Ergebnis, Elo-Update, startet Hintergrund-Kette (Form→KO→Predict→Sim).

## Groups
- `GET /groups/` → `{ "groups": Group[] }` (Tabellen aus realen Ergebnissen + Qualifikations-%)

## Tournament
- `GET /tournament/simulate` (= `/`) → `SimulationResult`
  (`simulation_id, n_runs, model_version, simulated_at, champion_probabilities, stage_probabilities`)
- `GET /tournament/champion-probabilities` → `{ "champion_probabilities": {team_id: p} }`
- `GET /tournament/projection` → deterministische Einzelprojektion (Tabellen, KO-Baum, Champion); Redis-gecacht
- `GET /tournament/bets?stage=&min_ev=&limit=` → aggregierte Best/Value Bets

## Dashboard
- `GET /dashboard/` → `{ top_favorites[], tournament_status{matches_played,matches_total,stage},
  next_matches[], recent_results[], last_simulation }`

## Predictions
- `POST /matches/{id}/predict` → Prognose für ein Spiel (neu berechnen)
- `POST /predict-all` *(admin optional)* → alle SCHEDULED/LIVE-Spiele mit Teams

## Admin (`Authorization`-Header)
- `GET /admin/status` → Sync-/Rate-Limit-Status (kein API-Call)
- `POST /admin/sync` → idempotenter Sync (world-cup-2026-live-api)
- **`POST /admin/auto-update`** → Sync (inkl. offizieller KO-Paarungen + Termine aus der API) +
  Elo idempotent für neu beendete Spiele + Recompute (Form/Ratings/Prognosen/Simulation). Von der
  CI (`sync-results.yml`) alle 30 min aufgerufen.
  Antwort: `{ synced, elo_newly_applied, ko_updated, recompute: "triggered"|"skip …" }`
- `POST /admin/simulate` → Monte-Carlo im Hintergrund
- `GET /admin/simulation-status` → letzter Lauf
- `POST /admin/predict-all` … (siehe Predictions)
- `POST /admin/refresh-form` · `POST /admin/refresh-features`
- `POST /admin/resolve-bracket` → offizielle KO-Paarungen + Termine aus der API ziehen + neu prognostizieren
- `GET /admin/feature-audit` → COMPUTED/PRIOR-Klassifikation je Team
- `GET /admin/odds-status` → Key-/Fallback-Status, Alter der letzten Quoten, TTL
- `GET /admin/market-calibration` → Modell vs. Markt (KL, mittl. Edge, Brier)

## Wichtige Response-Typen (Auszug)
- **TeamSummary**: id, name, short_name, flag_emoji, confederation, elo_rating, fifa_ranking,
  market_value_millions, avg_squad_age, form_score, champion_probability.
- **PredictionSummary/Detail**: prob_home_win/draw/away_win, xg_home/away, top_scoreline,
  (+ top_scorelines, score_distribution, explanation). `explanation` enthält u. a. `official`
  (markt-kalibrierte Prognose: outcome, score, probs, confidence, market) und `attack_defense`
  (γ + attack/defense je Team), sofern `ad_gamma>0`.
- **MatchSummary**: id, stage, group_id, home_team, away_team, kickoff_utc, status, prediction, result.
