# V2 — Aufstellungs-Engine: Architektur- & Umsetzungs-Design

**Status:** Design / Proposal (nicht implementiert) · **Branch:** `feature/v2-lineup-engine`
**Ziel:** Spielerzusammensetzung (Startelf, Ausfälle) als Modellfaktor — als **Version 2**, ohne V1 zu berühren.

> Querverweise: [METHODOLOGY.md](METHODOLOGY.md) · [ML_MODEL.md](ML_MODEL.md) ·
> [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) · [MODEL_EVALUATION.md](MODEL_EVALUATION.md) · [DECISIONS.md](DECISIONS.md)

---

## 0. Leitprinzip & kritische Vorab-Erkenntnis

**V1 bleibt unangetastet.** Die Trennung gelingt über drei bereits vorhandene Hebel:
das `model_version`-Feld (UNIQUE `(match_id, model_version)` auf `match_predictions` +
`tournament_simulations`), das **additive** Alembic-Schema und das `Settings`-Flag-Muster
(Präzedenz: `host_advantage_elo`).

> ⚠️ **Der Engpass ist nicht der Algorithmus, sondern die Daten.** Die Optimierung ist trivial
> (`scipy` kann es bereits). Es fehlen **Spielerdaten**: Die WM-API liefert (geprüft) **keine**
> Kader/Marktwerte; eine freie, zuverlässige Quelle für Nationalmannschafts-Marktwerte existiert
> nicht (Transfermarkt = Scraping/manuell). **Sperren** sind aus dem `commentary`-Endpoint
> ableitbar, **Verletzungen** nur manuell. Das Datenmodell muss mit **partiellen/kuratierten
> Daten** funktionieren und **sauber auf V1 zurückfallen**. → Risiko #1 und Voraussetzung.

---

# Phase 1 — Architektur

## A) Architektonischer Einbindungspunkt

| Option | Bewertung |
|---|---|
| In **Elo** integrieren | ❌ Elo ist der gelernte, selbstkorrigierende Backbone (updated aus Ergebnissen). Aufstellungs-Offset → **Double-Counting** + zerstört Lern-/Vergleichbarkeit. |
| Marktwert-Faktor **ersetzen** | ✅ teilweise — Startelf-Qualität ist die strikt bessere Version des „Gesamtkaderwert"-Signals. Aber nur **unter V2-Flag**. |
| Marktwert-Faktor **ergänzen** | ❌ Beide messen Kaderwert → **Kollinearität/Doppelzählung**. |
| **Neuer Faktor** im Feature Adjustment Layer | ✅ für den **Verfügbarkeits-/Ausfall**-Effekt (orthogonal, temporär). |

**Empfehlung:** Im Feature Adjustment Layer, **nicht** in Elo. In V2 entstehen **zwei** Faktoren,
die zusammen den alten Marktwert-Faktor ablösen:
1. **Kaderqualität (Startelf-basiert)** — *ersetzt* den V1-Marktwert-Input (optimale XI statt Kadersumme).
2. **Verfügbarkeit/Ausfälle (NEU)** — Degradation der real verfügbaren XI ggü. der eigenen Optimal-XI.

V1s Marktwert-Faktor (Gesamtkadersumme) bleibt für `model_version="v1.x"` unverändert.

## B) Datenmodell (rein additiv — keine bestehende Tabelle wird geändert)

```
positions           code PK · group(GK/DEF/MID/FWD)

players              id PK · full_name · nation_team_id FK→teams · primary_position FK→positions
                     · market_value_millions · age · club · foot · status · data_source · updated_at

player_positions     player_id FK · position_code FK · proficiency NUMERIC(0..1)   PK(player_id,position_code)

squad_memberships    id PK · team_id FK · player_id FK · tournament · shirt_number · called_up
                     UNIQUE(team_id, player_id, tournament)

player_availability  id PK · player_id FK · status(available/injured/suspended/doubtful)
                     · out_from · out_until  (ODER match_id FK für 1-Spiel-Sperre)
                     · reason · source · recorded_at

match_lineups        id PK · match_id FK · team_id FK · player_id FK
                     · role(starter/sub/bench) · position_played · formation · is_captain

formation_templates  id PK · name('4-3-3') · slots JSONB([{pos, weight}×11]) · active

lineup_strength      id PK · match_id FK · team_id FK · model_version · formation
                     · optimal_strength · actual_strength · availability_degradation · computed_at
                     UNIQUE(match_id, team_id, model_version)
```

Kern-Entscheidungen: **Polyvalenz** über `player_positions(.., proficiency)` (kein JSON-Geraschel);
**Verfügbarkeit zeit-/spielscoped** (Audit/Backtests); **`lineup_strength`** als Cache/Audit pro
`model_version` (reproduzierbare Erklärungen).

## C) Algorithmus „optimale Startelf"

Formation = 11 Slots mit Soll-Position; Spieler haben eligible Positionen mit `proficiency`.
Gesucht: Zuordnung 11 Spieler → 11 Slots, gewichtete Stärke maximal → **lineares Zuordnungsproblem**.

| Ansatz | Optimal? | Aufwand/Dep | Urteil |
|---|---|---|---|
| Greedy | ❌ lokal | trivial | nur Baseline/Fallback |
| LP-Relaxation | ✅ (integral) | LP-Solver | Overkill |
| Integer Programming | ✅ +Constraints | OR-Tools/PuLP (neu), langsamer | nur bei komplexen Constraints |
| **Hungarian / `linear_sum_assignment`** | ✅ optimal | **`scipy` schon da** | ✅ **Empfehlung** |
| Graph / Min-Cost-Flow | ✅ +Gruppen-Kap. | networkx/OR-Tools | elegant nur bei Positions-*Gruppen* |

**Empfehlung: Hungarian (`scipy.optimize.linear_sum_assignment`) pro Formation, dann beste wählen.**
Keine neue Abhängigkeit (scipy 1.13 vorhanden), 11×26 mikroskopisch.
Kostenmatrix `C[i][j] = w_slot(j) · s_i · proficiency(i,pos(j))` (`−∞` wenn nicht eligibel).
Polyvalenz fällt heraus; **Formationswahl** = `argmax_Formation(Optimal-XI-Stärke)` über kleines
Template-Set (4-3-3, 4-2-3-1, 3-5-2, 5-3-2, 4-4-2). ILP nur als spätere Option (gleiches Interface).

## D) Stärke einer Startelf

| Baustein | Entscheidung |
|---|---|
| Summe Marktwerte | ❌ zu grob (Stars dominieren) |
| **Diminishing Returns je Spieler** | ✅ `s_i = mv_i^α`, α≈0.6 |
| **Positionsgewichtung** | ✅ `w_pos`, normiert (Σ Standard-XI ≈ 11) |
| Star-Bonus | ❌ vorerst nicht (Overfitting) |
| **Bank/Tiefe** | ✅ klein: `β·Σ(beste 7 Bank)`, β≈0.15 |

`S_XI = Σ_{i∈XI} w_pos(i)·mv_i^α` ;  `S_team = S_XI + β·Σ_bench7 w·mv^α`.
Elo-Abbildung über **log-Differenz** zweier Team-Stärken (konsistent zum heutigen
`log10(mvh/mva)`-Marktwertfaktor). α, β, `w_pos` als `Settings`-Parameter tunebar.

## E) Ausfall-Mechanismus

**Relativ, nicht absolut:** `degradation = (S_optimal − S_actual)/S_optimal ∈ [0,1]` (skaleninvariant;
Beispiel 1000→850 M = 15 %). `S_actual` = **Re-Optimierung der XI ohne ausgefallene Spieler** →
**Positions-Spezifik fällt automatisch heraus** (fehlender Welttorwart ⇒ schwächerer Ersatz im
GK-Slot ⇒ entsprechend großer Abfall; gut gedeckter Flügel ⇒ kleiner Abfall). Kein separates
Per-Positions-Regelwerk nötig.

**Überreaktion verhindern:** konkave/`tanh`-Sättigung + Elo-Cap; nur **bestätigte** Ausfälle
(`doubtful` nur teilgewichtet); Replacement-Floor; fehlende Daten → Degradation = 0 (neutral, kein Raten).

## F) Modellintegration & Caps

| Variante | Konsequenz |
|---|---|
| Elo modulieren | ❌ Double-Counting, zerstört Selbstkorrektur |
| Marktwert **ersetzen** | ✅ für **Kaderqualität** |
| Marktwert **ergänzen** | ❌ Kollinearität |
| **Eigener Elo-Delta-Faktor** | ✅ für **Verfügbarkeit** |

**V2-Faktorliste:** `Form · Kaderqualität(Startelf) · Höhe · Reise · Rest · Verfügbarkeit(NEU) · +Host`.
- **Kaderqualität:** `Δ = cap(log10(S_home/S_away)·45, ±50)` — **erbt den ±50-Cap** des alten
  Marktwertfaktors (nicht aufblähen; Marktwert ist laut Evaluation ~6× schwächer als Elo → *verfeinern, nicht dominieren*).
- **Verfügbarkeit:** `Δ = cap(K·(degr_away − degr_home), ±40)` mit `tanh`-Sättigung, **Cap ±40**.
- Symmetrische Verteilung wie alle Faktoren; globaler Gesamt-Cap ±150 bleibt.

**Statistik:** Kollinearität mit Elo → moderater Cap. Aufstellungen kommender Spiele sind erst ~1 h
vor Anpfiff bekannt → **erwartete** Best-Available-XI; Unsicherheit eher als **Varianz** im Context
Injection Layer der Simulation abbilden, nicht den Punktwert verschärfen. **Reichweite:** Der
Verfügbarkeits-Faktor wirkt v. a. auf **unmittelbar anstehende** Spiele; die Tiefensimulation nutzt
`S_optimal` (Vollkader-Annahme).

---

# Phase 2 — Technischer Umsetzungsplan

## Neue Dateien
```
backend/app/models/player.py            Player, PlayerPosition, SquadMembership,
                                        PlayerAvailability, MatchLineup, FormationTemplate
backend/app/schemas/lineup.py
backend/app/services/squad_strength.py    mv^α, Positionsgewichte, S_XI/S_team
backend/app/services/lineup_optimizer.py  Hungarian (scipy) + Formationswahl
backend/app/services/availability_service.py  verfügbare Spielermenge je Team/Spiel
backend/app/services/lineup_adjuster.py   erzeugt die 2 Elo-Delta-Faktoren (Factor-Interface)
backend/app/routers/lineups.py
backend/scripts/import_squads.py          einmaliger kuratierter Kader-/Wert-Import
backend/scripts/eval/lineup_eval.py
backend/alembic/versions/003_lineup_engine.py
```
**Berührungspunkt am Bestand (minimal, flag-gated):** `prediction_engine.predict_match(model_version=…)`
ruft für `v2.*` `lineup_adjuster` auf und nutzt Kaderqualität **statt** Marktwert. V1-Pfad bleibt unverändert.

## Datenbankmigrationen
**`003_lineup_engine`** — legt ausschließlich die **neuen Tabellen** an (rein additiv, kein `ALTER`
an Bestehendem). Down-Migration dropt nur die neuen Tabellen.

## API-Endpunkte (neu, V2-/Flag-namespaced)
```
GET  /api/v1/teams/{id}/squad
GET  /api/v1/players/{id}
GET  /api/v1/matches/{id}/optimal-lineup?team=
GET  /api/v1/matches/{id}/lineup-impact
POST /api/v1/matches/{id}/lineup          (admin)
POST /api/v1/admin/availability           (admin, manueller Ausfall-Override)
GET  /api/v1/matches/{id}?model_version=v2.0
```

## Backward Compatibility
- **`model_version`:** v1.x / v2.0 koexistieren (UNIQUE-Constraint existiert). Default bleibt v1.
- **Feature-Flag:** `Settings.lineup_engine_enabled=False`, `default_model_version="v1.0"` +
  Tuning (`lineup_alpha`, `lineup_bench_beta`, Caps).
- **Shadow-Betrieb:** v2 parallel zu v1 (eigene `model_version`-Zeilen) — Vergleich ohne Risiko.
- **Graceful Fallback:** fehlen Kader/Verfügbarkeit → v2 nutzt V1-Marktwert → **nie schlechter als V1**.
- **Rollback:** Flag/Default zurück auf v1.0; v2-Prognosen löschen (v1 immer vorhanden); Tabellen bleiben oder Down-Migration.

## Branch-/Versionsplan
```
main (= V1, produktiv, Modell-Logik eingefroren)
└─ feature/v2-lineup-engine
   ├─ additive Migration 003 + neue Services/Models (kein Eingriff in V1-Pfade)
   ├─ Shadow-Deploy: v2 rechnet parallel, Default bleibt v1
   ├─ Evaluations-Gate bestanden?
   └─ erst dann: Default-model_version → v2 (per Flag, reversibel)
```

## Evaluationsplan & Erfolgskriterien
- **Shadow-Vergleich** v1 vs v2 auf denselben Spielen (echte WM-Ergebnisse, fortlaufend).
- **Metriken:** LogLoss (primär), Brier, **ECE**, Accuracy; mittlere **|ΔP|** der Lineup-Faktoren
  (Feature Importance); Ablation v1 · v1+Kaderqualität · v1+Verfügbarkeit · v2-voll.
- **Zielgerichteter Subset-Test:** Spiele **mit signifikanten Ausfällen** — dort muss v2 v1 schlagen.
- **Promotion-Gate (alle erfüllen):**
  1. v2-LogLoss ≤ v1 gesamt (keine Regression);
  2. v2 strikt besser auf dem **Ausfall-Subset**;
  3. ECE nicht schlechter;
  4. keine fußball-logischen Inversionen;
  5. Importance des Verfügbarkeits-Faktors > 0 und auf Ausfall-Spiele konzentriert.
  Nur dann → v2 wird Default.

---

## Gesamtbewertung
- **Technisch** sauber & risikoarm: additive Tabellen, flag-/version-gated, Hungarian via vorhandenem
  `scipy`, graceful Fallback → V1 strukturell unkaputtbar.
- **Hebel real, aber schmal:** Prognose-Kern ist nahezu optimal; Mehrwert steckt fast ausschließlich
  in **Ausfall-Spielen** — und nur, wenn die **Verfügbarkeitsdaten stimmen**.
- **Kosten/Risiko #1 = Daten:** ~48 Kader × ~26 Spieler kuratiert pflegen + laufend Ausfälle
  (Sperren via `commentary` automatisierbar, Verletzungen manuell).

**Empfehlung:** Architektur **freigeben** (Schema + Services + Flags), Umsetzung an einen
**Daten-Tauglichkeitstest** koppeln (Pilot mit 4–6 Top-Teams kuratiert, Shadow-Evaluation auf deren
Ausfall-Spielen). Gate bestanden → ausrollen; sonst bleibt V1 Default und der Code ruht risikofrei
hinter dem Flag.
