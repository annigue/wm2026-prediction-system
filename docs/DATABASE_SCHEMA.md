# DATABASE_SCHEMA — Daten-Dictionary (PostgreSQL)

Definiert in `backend/app/models/`. Schema entsteht via `create_all` (Boot) bzw. alembic
(`001` Baseline aus Models, `002` Indizes). Treiber: asyncpg (App) + psycopg2 (Tasks).

**Legende Herkunft:** 🟢 echt/extern · 🔵 berechnet · 🟡 Schätzung/Prior · ⚪ abgeleitet/intern.
Eine Methodik-Gesamtschau gibt [METHODOLOGY.md](METHODOLOGY.md).

---

## teams — Nationalmannschaften
Stammdaten je Team (Identität + Heimat-Geodaten für Höhe/Reise).

| Spalte | Bedeutung / Einheit | Herkunft |
|---|---|---|
| `id` | Kanonische ID, z. B. `mexico`, `usa` (PK) | ⚪ |
| `name`, `short_name`, `flag_emoji` | Anzeigename (deutsch), Kürzel, Flagge | 🟢 |
| `confederation` | Konföderation (UEFA, CONMEBOL …) | 🟢 |
| `home_country` | Land in Englisch (für Odds-/Sync-Matching) | 🟢 |
| `home_lat`, `home_lon` | Repräsentativer Heimat-Punkt (1 Punkt/Nation) → Reisedistanz | 🟡 vereinfacht |
| `home_altitude_m` | Repräsentative Heimathöhe in Metern → Höhen-Akklimatisierung | 🟡 vereinfacht |
| `home_timezone` | IANA-Zeitzone (Zeitzonen-Faktor nicht implementiert) | 🟢 |

> Hinweis: 48 Teams sind WM-Teilnehmer (in `group_memberships`); weitere Teams können als
> Stammdaten existieren, spielen aber nicht mit.

## team_features — Zeitreihe der Team-Kennzahlen  (UNIQUE: team_id, snapshot_date)
Pro Team mehrere Snapshots; die App nutzt jeweils den **neuesten**.

| Spalte | Bedeutung / Einheit | Herkunft |
|---|---|---|
| `elo_rating` | **Teamstärke** (typ. 1500–2200). Modell-Hauptgröße. | 🟢 Init eloratings.net, dann 🔵 live |
| `form_score` | Form ∈ [−1, +1] (Punkte + Tore, Recency-gewichtet). 0 vor 1. Spiel. | 🔵 aus Ergebnissen |
| `form_goals_scored_avg`, `form_goals_conceded_avg` | Ø Tore/Gegentore der Formphase | 🔵 |
| `market_value_millions` | Kader-**Gesamtmarktwert** in Mio. € | 🟡 statischer Prior |
| `fifa_ranking`, `fifa_points` | FIFA-Rang/Punkte | 🟡 **nicht im Modell** |
| `avg_squad_age`, `avg_caps_per_player` | Ø Alter / Ø Länderspiele | 🟡 **nicht im Modell** |
| `data_source` | Herkunft des Snapshots: `eloratings_init` (Import), `form_engine_v2` (Form), `bayesian_update` (nach Ergebnis) | ⚪ beschreibt v. a. die **Elo**-Herkunft |
| `snapshot_date` | Stichtag des Snapshots | ⚪ |

## elo_ratings — Audit-Trail der Elo-Änderungen
Jede Elo-Anpassung wird protokolliert (Nachvollziehbarkeit).

| Spalte | Bedeutung | Herkunft |
|---|---|---|
| `rating` | neuer Elo-Wert nach dem Ereignis | 🔵 |
| `match_id` | auslösendes Spiel (NULL beim Initial-Import) | ⚪ |
| `reason` | Klartext, z. B. „WM2026 2:1" | ⚪ |
| `created_at` | Zeitpunkt | ⚪ |

## groups · group_memberships — Gruppen
`groups`: `id` („A"…„L"), `name`. `group_memberships`: M:N-Zuordnung Team↔Gruppe (48 Einträge). 🟢

## venues — Spielorte (16 echte WM-Stadien)
| Spalte | Bedeutung / Einheit | Herkunft |
|---|---|---|
| `name`, `city`, `country` | Stadion, Stadt, Land | 🟢 |
| `altitude_m` | Stadion-Höhe in m (Azteca 2240 … Meereshöhe) → **Höhen-Faktor** | 🟢 |
| `lat`, `lon` | Koordinaten → **Reise-Faktor** | 🟢 |
| `timezone`, `capacity` | Zeitzone, Kapazität | 🟢 |

## matches — Spiele (104: 72 Gruppe + 32 K.-o.)
| Spalte | Bedeutung | Herkunft |
|---|---|---|
| `id` | Spiel-ID (aus API-`matchId` bzw. K.-o.-Slot) | 🟢 |
| `stage` | `GROUP_STAGE`, `ROUND_OF_32` … `FINAL`, `THIRD_PLACE` | 🟢 |
| `group_id`, `match_number` | Gruppe / interne Nummer (≠ FIFA-Spielnummer!) | 🟢 |
| `home_team_id`, `away_team_id` | Teams. **Nominelle** Listung aus der API (neutraler Boden → nur Label). K.-o.: NULL bis Teilnehmer feststehen | 🟢 |
| `venue_id` | Stadion (Gruppe: 72/72 verknüpft via offiziellem Spielplan; K.-o.: fest) | 🟢 |
| `kickoff_utc` | Anstoß (UTC) → auch Erholungs-Faktor | 🟢 |
| `status` | `SCHEDULED`/`LIVE`/`FINISHED`/`POSTPONED` | 🟢 live |

## match_results — Ergebnisse
| Spalte | Bedeutung | Herkunft |
|---|---|---|
| `home_goals`, `away_goals` (+ `_ht` Halbzeit) | Endstand / Halbzeit | 🟢 live |
| `went_to_extra_time`, `went_to_penalties`, `penalty_winner_id` | Verlängerung / Elfmeter (K.-o.) | 🟢 |
| `home_xg`, `away_xg` | (optional) reale xG | 🟢 falls vorhanden |
| `source` | `manual` oder `api` | ⚪ |

## match_predictions — Prognosen  (UNIQUE: match_id, model_version)
| Spalte | Bedeutung | Herkunft |
|---|---|---|
| `prob_home_win`/`draw`/`away_win` | Wahrscheinlichkeiten W/U/N (Σ=1) | 🔵 Modell |
| `xg_home`, `xg_away` | erwartete Tore je Team | 🔵 |
| `top_scorelines` (JSONB) | Top-5 wahrscheinlichste Ergebnisse + p | 🔵 |
| `score_distribution` (JSONB) | volle Ergebnis-Matrix (für Heatmap, Tipp, O/U, BTTS) | 🔵 |
| `explanation` (JSONB) | Elo-Basis + Faktoren mit Beitrag/Richtung (Transparenz) | 🔵 |
| `home/away_elo_at_prediction`, `*_features_snapshot` | Stand zum Prognosezeitpunkt | ⚪ |

## tournament_simulations — Monte-Carlo-Läufe
| Spalte | Bedeutung | Herkunft |
|---|---|---|
| `n_runs` | Anzahl Durchläufe (Prod 100.000) | ⚪ |
| `champion_probs` (JSONB) | Titelwahrscheinlichkeit je Team | 🔵 |
| `stage_probs` (JSONB) | je Team: P(Gruppensieg, Achtelfinale, … Titel) | 🔵 |
| `model_version`, `simulated_at`, `triggered_by` | Versionsstempel / Auslöser | ⚪ |

---

## Beziehungen (Kurz)
team 1—n team_features · team 1—n elo_ratings · team n—m groups · group 1—n matches ·
match 1—1 match_result · match 1—n match_predictions · match n—1 venue.

## Was ist „echt" vs. „Schätzung"? (für externe Leser)
- **Trägt die Prognose & ist echt:** Elo (eloratings.net + live), Spielplan/Ergebnisse (API),
  Stadien/Höhen/Koordinaten, daraus berechnete Form/Prognosen/Simulationen.
- **Aktiv genutzte Schätzung:** nur `market_value_millions` (statischer Prior, schwacher Faktor).
- **Schätzung, aber NICHT im Modell (nur Anzeige):** `fifa_ranking`, `avg_squad_age`, `avg_caps_per_player`
  — im UI als „nicht im Modell" gekennzeichnet.
