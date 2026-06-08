# DECISIONS — Architecture Decision Records (ADR)

Kompakte Begründungen der wichtigsten Entscheidungen.

## ADR-001 — Elo als zentrale Stärkemetrik
Bewährt, interpretierbar, online-lernfähig. Live via Bayesian Update; alleinige dynamische
Stärkequelle. *Alternative:* reine FIFA-Punkte (weniger prädiktiv) — verworfen.

## ADR-002 — Poisson + Dixon-Coles statt direktem WDL-Klassifikator
Liefert volle Score-Verteilung (für xG, Heatmap, O/U, BTTS, Correct Score, Tipping) und den
größten Kalibrierungsgewinn (ECE ~0.07→~0.002). Belegt in MODEL_EVALUATION.

## ADR-003 — Feature-Layer additiv (Elo-Deltas), gedeckelt
Kontextfaktoren verschieben Elo um begrenzte Deltas (Gesamt ±150), statt Wahrscheinlichkeiten
direkt zu manipulieren → stabil & erklärbar. Einzelspiel deterministisch; Simulation stochastisch.

## ADR-004 — Feature-Reduktion (7 → 4–5), datengetrieben
Evaluation: Elo dominiert (6× Markt, 14× Form). Alter/Caps (ungeprüfte Seed-Schätzwerte,
Einfluss ≈0) **entfernt**; FIFA nur Elo-Init; Rest-Days als reproduzierbarer Faktor ergänzt.

## ADR-005 — Initial-Elo aus eloratings.net
Reproduzierbar, gleiche Formulierung (SCALE=400), kein manuelles Tuning. Quelle committed;
danach live via Bayesian.

## ADR-006 — Form v2: Punkte + Tore + Recency, Single Source of Truth
Datengetrieben aus echten Ergebnissen, keine Seed-Schätzung, deterministisch. Genau eine
schreibende Stelle (form_engine) → keine konkurrierenden Werte.

## ADR-007 — Marktwert nicht automatisieren
Scraping fragil/ToS-kritisch; Modellnutzen 6× < Elo. Statischer, eingefrorener PRIOR.

## ADR-008 — Umwelt-/Venue-Stress nur als Varianz (kein Wetter-Forecast)
Reproduzierbarer Proxy (Höhe+Klima) erhöht nur die Simulations-Streuung, kein Bias; gerichteter
Höheneffekt bleibt im Feature-Layer → kein Double-Counting. Forecast-APIs verworfen (nicht reproduzierbar).

## ADR-009 — Rest-Days nur aus GESPIELTEN Spielen
Fatigue entsteht durch gespielte Spiele; Zählen terminierter Spiele erzeugte Phantom-Fatigue
vor Turnierstart → Bug behoben (JOIN match_results) + sanfte tanh-Sättigung.

## ADR-010 — KO-Bracket-Resolver (Persistenz statt nur In-Memory)
Projektion berechnete KO-Teilnehmer nur im Speicher → KO-Spiele blieben team-/prognoselos.
Resolver schreibt qualifizierte Teams in die DB (R32 aus Tabellen, Folgerunden aus realen
KO-Ergebnissen); Ranking-/Paarungslogik geteilt (`rank_and_pair`) — keine Duplikation.

## ADR-011 — Decision Layer: EV **und** Edge
EV misst Auszahlung (quotenabhängig), Edge die overround-bereinigte Überzeugung. NO_BET bei
negativem EV/Edge. Markt = informativer Prior, **nie** Override der Modell-WS.

## ADR-012 — Single-Instance-Backend + sync BackgroundTasks
In-Memory-Odds-Cache + BG-Tasks ⇒ 1 Instanz/Worker. Sim als sync Task → Threadpool, blockiert
den Event-Loop nicht. Bewusst kein Autoscaling.

## ADR-013 — Free-Hosting-Stack (Vercel + Render-Free + Neon)
Kosten 0 € für ein privates Tool. Trade-off Cold Start akzeptiert; `MONTE_CARLO_RUNS=30000`
(verifiziert gleichwertig) spart Ressourcen. *Alternativen:* alles-Render-paid / Oracle-VPS — situativ.

## ADR-014 — Recovery-Strategie & .gitignore
Nach Quellcode-Verlust: Wiederherstellung aus .pyc-Decompile, **.next-Sourcemaps** (Frontend
verbatim) und intakter DB; danach `.gitignore` (venv/.next/__pycache__/.env) + eigenes Repo,
damit der Auslöser (Committen von Artefakten statt Source) nicht erneut passiert.
