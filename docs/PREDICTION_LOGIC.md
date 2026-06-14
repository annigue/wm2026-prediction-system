# PREDICTION_LOGIC — Schritt für Schritt

Die Pipeline für eine Einzelspiel-Prognose (`prediction_engine.predict_match`).

```
Input: match_id
 1. Match + Teams + Venue + bisherige Prognosen laden
 2. Elo beider Teams laden (neuester team_features-Eintrag; Fallback 1500)
 3. Rest-Days berechnen (nur GESPIELTE Vorspiele, aus kickoff_utc)
 4. Feature-Adjustment (5 Faktoren → Elo-Deltas → angepasste Elo-Werte)
 5. Poisson + Dixon-Coles → λ, Score-Verteilung, P(W/U/N), Top-Scorelines
 6. Erklärung bauen (Faktoren mit Elo-Delta, Richtung, Summary)
 7. Upsert in match_predictions (pro model_version)
Output: PredictionResult (Wahrscheinlichkeiten, xG, Scores, Erklärung)
```

## Schritt 2 — Elo
`elo = latest team_features.elo_rating` (sonst 1500). Typische Werte (eloratings, 06.06.2026):
Spanien 2155 · Argentinien 2113 · Frankreich 2062 · England 2020 · Brasilien 1988 ·
Deutschland 1925 · USA 1733 · Saudi-Arabien 1569.

## Schritt 3 — Rest-Days
`_rest_days(team, kickoff)`: jüngstes Spiel **mit Ergebnis** (`JOIN match_results`) vor `kickoff`.
Tage = (kickoff − prev)/86400. None = kein gespieltes Vorspiel → Faktor neutral.

## Schritt 4 — Feature Adjustment (`feature_adjuster.adjust`)
```
factors = {
  form:     cap((fh−fa)·50, 60),
  market:   cap(log10(mvh/mva)·45, 50),
  altitude: Höhenstrafe(Venue, Heimathöhen), cap 80,
  travel:   Reisestrafe(great_circle), cap 30,
  rest:     cap(20·tanh(Δd/2.5), 20),       # nur wenn beide rest_days bekannt
}
total = clip(Σ factors, ±150)
adj_home = elo_home + total·0.5 ;  adj_away = elo_away − total·0.5
```
Faktoren < Schwellwert (Höhe/Reise/Rest) werden weggelassen, damit nur relevante erscheinen.

## Schritt 5 — Poisson + Dixon-Coles
```
λ_home = 1.30·exp(adjΔ/800)·(Atk_h·Def_a)^γ ; λ_away = 1.30·exp(−adjΔ/800)·(Atk_a·Def_h)^γ  (clip 0.25–5.0)
# γ = ad_gamma (Default 0.5); Attack/Defense aus historischen Ergebnissen, Elo dominant, γ=0 ⇒ reines Elo
P(i:j) = Poisson(i;λh)·Poisson(j;λa)·τ(i,j)   i,j∈0..8 → normiert
P(Heim)=Σ_{i>j} · P(X)=Σ_{i=j} · P(Ausw)=Rest
xG = λ_home/λ_away ; top_scorelines = Top-5 nach Wahrscheinlichkeit
```

## Turnier-Logik
- **Gruppe:** 3 Pkt Sieg / 1 Remis / 0; Tie-Break Punkte→Tordifferenz→Tore→Elo.
- **Qualifikation:** Top 2 je Gruppe + 8 beste Drittplatzierte → 32 Teams (R32).
- **R32-Paarung** (kanonisch, `tournament_projection.rank_and_pair`): A1–B2, A2–B1, C1–D2, …
  + 8 beste Dritte paarweise.
- **KO:** Score aus Poisson; bei Gleichstand Elfmeter (≈50/50 + leichter Elo-Tilt).
- **KO-Befüllung in der DB:** `knockout_resolver.resolve_bracket` schreibt nach Abschluss der
  Gruppenphase die R32-Teams, danach inkrementell R16…Finale aus realen KO-Ergebnissen →
  KO-Spiele bekommen Teams → `predict_all` erzeugt Prognosen → erscheinen in /tipps.

## Auto-Update nach Ergebnis (`matches._after_result_tasks`)
`Ergebnis → Elo → Form (form_engine) → KO-Bracket (resolver) → predict_all →
Cache invalidieren → Simulation neu`. Der Recompute-Teil ist idempotent.

## Automatischer Ergebnis-Sync (`admin.auto_update`, CI alle 30 min)
`sync_all` (echte API-Ergebnisse) → für beendete Spiele **ohne** `elo_ratings`-Eintrag (chronologisch)
`apply_result` → derselbe Recompute. Die „ohne Elo-Eintrag"-Bedingung macht das Ganze **idempotent**
(wiederholter Lauf wendet Elo nie doppelt an; manuell eingetragene Spiele haben den Eintrag schon).
