# ML_MODEL — Modellarchitektur & Mathematik

## Überblick: dreischichtiges Ensemble

```
EINZEL-SPIEL-PROGNOSE
  Elo (global, stabil)
    + Feature Adjustment Layer (deterministisch, 5 Faktoren)
    → angepasste Elo-Differenz → Poisson + Dixon-Coles → P(W/U/N) + xG + Scores

TURNIERSIMULATION (Monte Carlo)
  Elo (global)
    + Context Injection Layer (stochastisch, pro Run)
    → per-Run Elo-Variation → Poisson → Champion-/Runden-Wahrscheinlichkeiten
```

Kernprinzip: **Elo trägt die Vorhersage**, die Zusatzschichten verfeinern (deterministisch
für Einzelspiele, stochastisch für Simulations-Varianz). Die Modell-Evaluation
([MODEL_EVALUATION.md](MODEL_EVALUATION.md)) belegt: Elo + Poisson + Dixon-Coles ≈ 99 % der
Performance; die Features bewegen P(home) im Mittel nur ~2 pp.

---

## Layer 1 — Elo Rating (`elo_model.py`)

```
Erwartung:  E(A) = 1 / (1 + 10^((R_B − R_A)/400))
Update:     R_neu = R_alt + K · Tordiff-Gewicht · (Ergebnis − Erwartung)
  Tordiff-Gewicht: Δ≤1→1.00, Δ=2→1.50, Δ=3→1.75, Δ≥4→min(1.75+(Δ−3)/8, 2.50)
  K = 32 (reguläre Länderspiele), K = 20 (während WM, konservativer)
```

- **Initialwerte:** reproduzierbar aus **eloratings.net** (gleiche Formulierung, SCALE=400);
  Import via `scripts/import_initial_elo.py` → `data/initial_elo.json` (`data_source='eloratings_init'`).
  Beispiele: Spanien 2155, Argentinien 2113, Frankreich 2062, England 2020, Deutschland 1925.
- **Live:** Bayesian Update beider Teams nach jedem Ergebnis (`bayesian_updater.py`, K=20),
  Audit-Trail in `elo_ratings`. Elo ist die **alleinige dynamische Stärkemetrik**.

## Layer 2a — Feature Adjustment (`feature_adjuster.py`, Einzelspiel)

Jeder Faktor trägt einen Elo-Delta bei; der Gesamt-Delta (gedeckelt ±150) wird hälftig
auf beide Teams verteilt: `adj_home = elo_home + total·0.5`, `adj_away = elo_away − total·0.5`.

| # | Faktor | Cap (Elo) | Quelle |
|---|---|---|---|
| 1 | Aktuelle Form | ±60 | form_engine (echte Ergebnisse) |
| 2 | Marktwert | ±50 | statischer PRIOR (Transfermarkt), eingefroren |
| 3 | Höhenunterschied | ±80 | Geodaten (Venue + Heimat) |
| 4 | Reisedistanz | ±30 | Geopy great_circle |
| 5 | Erholung (Rest Days) | ±20 | Spielplan (`kickoff_utc`), nur **gespielte** Spiele |

**Erholung:** `ΔElo = 20·tanh(Δd/2.5)` (Steigung ≈8 Elo/Tag, sanfte Sättigung). Aus
`prediction_engine._rest_days` — zählt nur Spiele mit echtem Ergebnis → keine Phantom-Fatigue
vor Turnierstart. **Entfernt** (Datenqualität): Alter, Caps (Seed-Schätzwerte, Einfluss ≈0),
FIFA-Ranking (nur noch Elo-Init). Zeitzone nie implementiert.

## Layer 2b — Context Injection (`context_modifier.py`, Simulation)

Stochastische Match-zu-Match-Varianz pro Run (deterministisch + Rauschen), gedeckelt ±40 Elo:

| Signal | deterministisch | σ stochastisch |
|---|---|---|
| Form-Momentum | ±20 Elo (Form-Diff) | 8 |
| Kader-Tiefe (Marktwert) | — | 5 (log-skaliert) |
| KO-Druck | — | 4–6 (steigt mit Runde) |
| **Umwelt-/Venue-Stress** | — | bis 5 × Stress |

**Umwelt-Stress** (`venue_environment_stress`): deterministischer Klima-/Venue-Proxy aus
Höhe (ab ~1000 m) + Breitengrad (Juni/Juli-Hitze) ∈ [0,1]. **Nur Varianz, kein Bias** —
der gerichtete Höheneffekt lebt in Layer 2a; kein Double-Counting (verschiedene Momente & Pfade).

## Layer 3 — Poisson Goal Model (`poisson_model.py`)

```
λ_home = 1.30 · exp(elo_diff/800)        λ_away = 1.30 · exp(−elo_diff/800)   (clip 0.25–5.0)
P(i:j) = Poisson(i;λ_h) · Poisson(j;λ_a) · τ(i,j)    Grid 0..8, dann normiert
Dixon-Coles τ (ρ=−0.13):  0:0→1−λhλaρ · 1:0→1+λaρ · 0:1→1+λhρ · 1:1→1−ρ · sonst 1
P(Heim)=Σ_{i>j}  P(X)=Σ_{i=j}  P(Ausw)=1−P(Heim)−P(X)
```

## Monte-Carlo-Simulation (`tournament_simulator.py`)

- **Gruppenphase vektorisiert** (numpy): pro Gruppe alle Paarungen × n_runs Poisson-Samples,
  Tabellen-Ranking (Punkte→TD→Tore→Elo), Sieger/Zweite/beste 8 Dritte pro Run.
- **KO-Runden** als Python-Loop pro Run (R32→Finale), Paarung identisch zu
  `tournament_projection.rank_and_pair`; Elfmeter = 0.5 + (Δelo)/10000.
- Output: `champion_probs` + `stage_probs` je Team. Prod: 30.000 Runs (~15 s; verifiziert
  gleichwertig zu 100.000 — Spanien ~18 %).

## Kalibrierung
Backtest-Kriterium Brier/LogLoss/ECE (siehe MODEL_EVALUATION). ECE des Full-Modells ≈ 0.0016
(Poisson+Dixon-Coles liefern den größten Kalibrierungsgewinn).
