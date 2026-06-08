# BETTING_ENGINE — Decision Layer (EV + Edge)

Wandelt Modell-Prognosen in strukturierte Wett-/Tipp-Empfehlungen. **Stateless,
deterministisch, additiv** — kein Eingriff in Elo/Poisson. Reines Analyse-Tool.

## Module
| Modul | Rolle |
|---|---|
| `decision_engine.py` | Kanonische Facade (`compute_expected_value`, `compute_edge`, `rank_bets_by_ev`, `generate_recommendations`) — delegiert an betting_engine |
| `betting_engine.py` | Implementierung: `generate_report`, EV/Edge/Risiko, Best/Safe/Value/**No Bet** |
| `odds_normalizer.py` | **Single Source of Truth** Overround-Entfernung (implizite & faire WS) |
| `odds_provider.py` / `odds_aggregator.py` | Odds-API-Client (Cache, last-known) + faire Markt-WS |
| `market_calibration_service.py` | Monitoring Modell vs. Markt (KL-Divergenz, Edge, Brier) |

## Kernkonzepte
```
EV   = Modell-WS × Quote − 1          # erwartete Auszahlung (hängt an der Quote)
Edge = Modell-WS − faire Markt-WS     # Informationsvorsprung (overround-bereinigt)

faire Markt-WS:  p_raw = 1/odds ; overround = Σ p_raw ; p_fair = p_raw/overround (Σ=1)
```
- **EV** misst die Auszahlung, **Edge** die Überzeugung — sie ergänzen sich.
- Beispiel (echte Quoten): Heimsieg Modell 49.4 % vs. faire Markt-WS 45.4 % → Edge +4.0 pp, EV +3.7 %.

## Empfehlungs-Kategorien (je Selektion `recommendation`)
- **VALUE** — EV ≥ +2 % **und** positiver Edge.
- **SAFE** — hohe Wahrscheinlichkeit (≥60 %), geringes Risiko.
- **NO_BET** — negativer EV **oder** negativer Edge (Modell schlägt den Markt nicht).
- Report: `best_bet` (höchster EV), `safe_bet`, `value_bets` (Top-3), **`no_bets`**, `scoreline_tip`.

## Märkte
1X2 · Over/Under 2.5 · BTTS · Correct Score (Top-3 aus Poisson). O/U & BTTS aus der
`score_distribution` abgeleitet (nicht neu modelliert).

## Quoten: echt vs. synthetisch
- **Echt** (Odds-API verfügbar): EV/Edge gegen den realen Markt; `odds_estimated=false`,
  `ev_calculable=true`. Team-Matching über englische Namen (DB `home_country`).
- **Synthetisch** (kein Key/Treffer): `fair_odds = (1/WS)·(1−Marge)`; EV ≈ −Marge → alles
  landet in NO_BET (kein echter Edge ohne echten Markt). Klar geflaggt.

## Caching & Robustheit
TTL 15 min; bei API-Ausfall **last-known odds** statt Fehler; ohne Redis graceful (Odds-Cache
ist in-memory pro Prozess → Single-Instance-Backend hält ihn warm).

## Endpunkte
- `GET /api/v1/matches/{id}/bets` (optional echte Quoten als Query-Params)
- `GET /api/v1/matches/{id}/tip` (punktoptimaler Tipp, Tipping Engine)
- `GET /api/v1/tournament/bets?stage=…&min_ev=…` (aggregierte Value Bets)
- `GET /api/v1/admin/odds-status` · `GET /api/v1/admin/market-calibration`

## Tipping Engine (`tipping_engine.py`)
Punktoptimaler Exakt-Tipp via **Erwartungswert-Maximierung** über die Score-Verteilung
(nicht argmax). Kicktipp-Schema (`tipping_engine._points`): exakt 4 / Tordifferenz 3 (inkl.
beide Remis) / Tendenz 2 / sonst 0. Frontend: `BettingPanel.tsx`, `TipPanel.tsx`.

## Tipp-vs-Ergebnis-Auswertung (gespielte Spiele)
Für beendete Spiele wird der **empfohlene Tipp** (xG-Tipp, konsistent zur Tipps-Seite) gegen das
**tatsächliche Ergebnis** ausgewertet und die erzielten **Kicktipp-Punkte** angezeigt.
- Frontend-Logik `lib/tips.ts → evaluateTip(tipScore, result)` → `{points, kind, label}` —
  identische Punktelogik wie das Backend (Exakt 4 / Tordifferenz 3 / Tendenz 2 / 0).
- Anzeige: **Tipps-Seite** Sektion „Bereits gespielt" (pro Spiel Tipp → Ergebnis + Punkte) inkl.
  **Punkte-Bilanz** (Gesamtpunkte, exakt-Treffer, Trefferquote); **Match-Detail** als Vergleichskarte.
- Reine Auswertung — keine Änderung am Prognose-/Tipping-Modell.

## Haftungsausschluss
Statistisches Analyse-Tool, kein Wettangebot. Synthetische Quoten ≠ echte Buchmacher-Quoten.
Keine Gewähr. Kein Aufruf zum Glücksspiel.
