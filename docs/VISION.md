# VISION — WM 2026 Prognose- & Tipp-System

## Ziel
Ein **datengetriebenes, transparentes** Prognose- und Tipp-Tool für die Fußball-WM 2026, das
von überall im Browser nutzbar ist — als persönliches Werkzeug für Tipprunden und zur
Turnier-Analyse.

## Leitprinzipien
1. **Reproduzierbar & datengetrieben** — keine Bauchwerte. Stärke aus eloratings.net + live
   gelernt; Form aus echten Ergebnissen; klare Trennung COMPUTED vs. PRIOR.
2. **Transparenz** — jede Prognose erklärt ihre Faktoren (Elo-Differenz + Kontextfaktoren mit
   Beitrag und Richtung); Limitationen werden offen kommuniziert.
3. **Statistisch fundiert, nicht überkomplex** — Elo + Poisson + Dixon-Coles tragen die
   Vorhersage; Zusatzfaktoren bleiben bewusst klein (durch Evaluation belegt).
4. **Robust & einfach im Betrieb** — graceful degradation (ohne Redis/Odds lauffähig),
   deterministische Kernlogik, kostengünstiges Hosting.

## Kernfunktionen
- Spiel-Prognosen (W/U/N, xG, Scoreline-Heatmap, Erklärung)
- Gruppen-Tabellen + Qualifikations-Wahrscheinlichkeiten
- Monte-Carlo-Titelchancen + Turnierbaum
- Tipprunden-Tipps (xG-Tipp, Modell-Tipp, punktoptimaler Tipp)
- Betting Decision Engine (EV + Edge gegen echte Marktquoten) — reines Analyse-Tool
- Live-Lernen: nach jedem Ergebnis aktualisieren sich Elo, Form, KO-Baum, Prognosen, Simulation

## Nicht-Ziele
Kein Wettanbieter, kein Glücksspiel-Aufruf. Keine ML-Black-Box. Keine nicht-reproduzierbaren
Datenquellen. Keine Skalierung über das hinaus, was ein privates Tool braucht.

## Zielgruppe
Der Betreiber + Freunde/Tipprunde. Geringe Last, klarer Fokus auf Erklärbarkeit und Spaß.
