# DATABASE_SCHEMA — PostgreSQL

Definiert in `backend/app/models/`. Schema entsteht via `create_all` (Boot) bzw. alembic
(`001` Baseline aus Models, `002` Indizes). Treiber: asyncpg (App) + psycopg2 (Tasks).

## Tabellen

### teams
`id` (PK, str) · name · short_name · flag_emoji · confederation · home_country (englisch,
fürs Odds-/Sync-Matching) · home_lat · home_lon · home_altitude_m · home_timezone · created/updated_at.

### team_features  (UNIQUE: team_id, snapshot_date)
`id` (PK) · team_id (FK) · snapshot_date · fifa_ranking · fifa_points · **elo_rating** ·
market_value_millions · avg_squad_age · avg_caps_per_player · **form_score** ·
form_goals_scored_avg · form_goals_conceded_avg · **data_source** (`eloratings_init` /
`form_engine_v2` / `seed_*` / `bayesian_update`) · created_at.

### elo_ratings  (Audit-Trail)
`id` (PK) · team_id (FK) · rating · match_id · reason · created_at. Index: (team_id, created_at).

### groups · group_memberships
groups: `id` (PK, „A"…„L") · name. group_memberships: (group_id, team_id) M:N.

### venues
`id` (PK) · name · city · country · altitude_m · lat · lon · timezone · capacity.

### matches
`id` (PK, z. B. `WC2026_<hash>` oder `WC2026_ROUND_OF_32_01`) · tournament · **stage**
(`GROUP_STAGE`/`ROUND_OF_32`/…/`FINAL`/`THIRD_PLACE`) · group_id (FK) · match_number ·
home_team_id (FK, **nullable** — KO-Platzhalter) · away_team_id (FK, nullable) · venue_id (FK) ·
kickoff_utc · **status** (`SCHEDULED`/`LIVE`/`FINISHED`/`POSTPONED`) · created/updated_at.
Indizes: stage, status, kickoff_utc, (stage,status).

### match_results
`match_id` (PK, FK) · home_goals · away_goals · home_goals_ht · away_goals_ht ·
went_to_extra_time · went_to_penalties · penalty_winner_id (FK) · home_xg · away_xg ·
recorded_at · source.

### match_predictions  (UNIQUE: match_id, model_version)
`id` (PK) · match_id (FK) · model_version · predicted_at · prob_home_win/draw/away_win ·
xg_home · xg_away · top_scorelines (JSONB) · score_distribution (JSONB) · explanation (JSONB) ·
home/away_elo_at_prediction · home/away_features_snapshot (JSONB). Index: match_id.

### tournament_simulations
`id` (PK) · model_version · n_runs · simulated_at · **champion_probs** (JSONB: team_id→p) ·
**stage_probs** (JSONB: team_id→{group_stage,round_of_32,…,champion}) · group_probs ·
tournament_state_hash · triggered_by. Index: simulated_at.

## Beziehungen (Kurz)
team 1—n team_features · team 1—n elo_ratings · team n—m groups · group 1—n matches ·
match 1—1 match_result · match 1—n match_predictions · match n—1 venue.

## Aktueller Stand (Neon)
60 teams · 60 team_features · 48 memberships · 104 matches · 0 results · 72 predictions ·
8 simulations.
