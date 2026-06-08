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
Kosten 0 € für ein privates Tool. *Alternativen:* alles-Render-paid / Oracle-VPS — situativ.

## ADR-014 — Recovery-Strategie & .gitignore
Nach Quellcode-Verlust: Wiederherstellung aus .pyc-Decompile, **.next-Sourcemaps** (Frontend
verbatim) und intakter DB; danach `.gitignore` (venv/.next/__pycache__/.env) + eigenes Repo,
damit der Auslöser (Committen von Artefakten statt Source) nicht erneut passiert.

## ADR-015 — Performance: Frankfurt-Co-Location + ISR + Prerender
Ursache früherer Langsamkeit war **nicht** das Modell, sondern Cross-Region-Latenz
(Render-US ↔ Neon-EU) pro DB-Query × vieler `selectinload`-Round-Trips. Fixes: Backend nach
**Frankfurt** (zu Neon co-located), Listen-Queries verschlankt (keine volle Prognose-JSONB/
elo_history), **In-Process-Cache** für die Projektion; im Frontend **ISR** (`revalidate=60`) statt
`no-store` + **`generateStaticParams`** (Detailseiten beim Build vorgerendert). Ergebnis:
Detail 4.5 s → 0.12 s. `MONTE_CARLO_RUNS=100000` bleibt (Sim ist Hintergrund-Task, entkoppelt vom Interface).

## ADR-016 — Automatischer Sync via CI statt In-Process-Scheduler
Ein Render-Free-Service schläft → ein interner Scheduler stoppt mit ihm. Stattdessen triggert
**GitHub Actions** extern: `keepalive.yml` (Health, 10 min) + `sync-results.yml` (`/admin/auto-update`,
30 min). Der externe Cron **weckt** das Backend zuverlässig. 30-min-Takt schont das RapidAPI-Kontingent.

## ADR-017 — Auto-Update idempotent (Elo nur für Spiele ohne Elo-Eintrag)
Da der Sync wiederholt läuft, darf Elo nicht doppelt angewandt werden. `apply_result` ist
inkrementell/nicht-idempotent → `/admin/auto-update` wählt nur beendete Spiele **ohne**
`elo_ratings`-Eintrag (chronologisch). Manuelle Eingabe legt den Eintrag bereits an → wird übersprungen.

## ADR-018 — Tipp-vs-Ergebnis transparent (Kicktipp-Scoring im Frontend)
„Empfohlener Tipp" = xG-Tipp (konsistent zur Tipps-Seite). Punkte exakt zur Backend-Logik
(`tipping_engine._points`): Exakt 4 / Tordifferenz 3 (inkl. Remis) / Tendenz 2 / 0. Anzeige auf
Tipps-Seite (inkl. Punkte-Bilanz) + Match-Detail. Reine Auswertung, keine Modelländerung.

## ADR-019 — Gastgeber-Heimvorteil (einziger gerichteter „Heim"-Term)
Poisson ist bewusst symmetrisch (WM = neutraler Boden). Echten Heimvorteil hat nur der Gastgeber
im eigenen Land. Daher gerichteter Bonus (`host_advantage_elo=55`, tunebar) **nur** für USA/Kanada/
Mexiko in der **Gruppenphase**, gekoppelt an die **Team-Identität** (nicht an die nominelle Home/Away-
Listung). K.-o. neutral. Konservativ wegen Co-Gastgeber-Verdünnung. Konsistent in Prognose + Simulation.

## ADR-020 — Venue-Verknüpfung aus offiziellem Spielplan (API hat keine Stadien)
Geprüft: die WM-API liefert keine Venue-/Spieler-/Karten-Daten (nur Fixtures + Tabellen). Höhe/Reise/
Umwelt-Stress brauchen aber Stadien → die 72 Gruppenspiele wurden via **offiziellem FIFA-Spielplan**
verknüpft (`scripts/load_venue_schedule.py`, Match-Schlüssel = Team-Paarung). Fehlende echte Spielorte
(Atlanta, Seattle) ergänzt; Seed-Fremdkörper (Denver, Las Vegas) entfernt. Keine erfundenen Zuordnungen.

## ADR-021 — Transparenz statt versteckter Schätzwerte
Schätzwerte werden offen gekennzeichnet, nicht versteckt: im UI sind `fifa_ranking`, `avg_squad_age`,
`avg_caps` als „nicht im Modell", der Marktwert als „Schätzung" markiert. Spielerebene wurde geprüft
und **bewusst verworfen** (keine freie/zuverlässige Quelle; Nutzen ≪ Aufwand) — siehe auch die
geprüfte, aber nicht umgesetzte Sperren-Logik via `/wc/match/{id}/commentary`.
