# ROADMAP — Verlauf & Stand

**Status:** Feature-complete, evaluiert, gehärtet, **live deployed** (Free-Stack). WM-Start 2026-06-11.

## Abgeschlossene Phasen
| Phase | Inhalt |
|---|---|
| Architektur & Setup | FastAPI + SQLAlchemy async, Next.js 14, Docker, Modelle/Migrationen |
| Datenpipeline | world-cup-2026-live-api (RapidAPI) Sync; Seed |
| Elo + Poisson Modell | EloModel, PoissonModel + Dixon-Coles, FeatureAdjuster, PredictionEngine |
| Turniersimulation | Monte Carlo (vektorisierte Gruppen + KO-Loop), Champion-/Runden-WS |
| UI/Dashboard | Dashboard, Gruppen, Spiele, Match-Detail (Heatmap/Erklärung), Team, Tipps, Bracket |
| Elo-Updates | Elo-Update nach Ergebnis (K=20) + Hintergrund-Recompute |
| Context Injection | stochastische Simulations-Varianz (Form, Markt, KO-Druck) |
| Betting Decision Engine | EV, Edge, Risiko, Best/Safe/Value Bets, Märkte |
| Final Hardening | Form-Engine v2, Tipping-Engine (EV), Odds-Integration, Cache, Indizes |
| Model Evaluation | Ablation/Kalibrierung → Elo+Poisson ≈ 99 %; Empfehlungen |
| Decision Layer Opt. | Edge + Facade (decision_engine), Overround-Bereinigung |
| Data Quality Hardening | Form-Konsolidierung, 7→4 Faktoren, eloratings-Initial-Elo, Marktwert eingefroren |
| Hardening Pass | Rest-Days-Faktor, Umwelt-/Venue-Stress-Varianz, LIMITATIONS |
| Hardening Fix-Pass | Rest-Days nur gespielte Spiele + tanh; „Wetter"→Umwelt-Stress; Double-Counting verifiziert |
| Odds-Markt-Upgrade | odds_normalizer (Single Source), NO_BET-Kategorie, last-known-Fallback, Calibration-Monitor |
| KO-Bracket-Resolver | KO-Teilnehmer aus realen Ergebnissen in DB → Prognosen/Tipps erscheinen automatisch |
| **Recovery (2026-06-07)** | Quellcode-Totalverlust → vollständig wiederhergestellt (siehe RECOVERY.md) |
| **Deployment (2026-06-07)** | Free-Stack live: Vercel + Render-Free + Neon |
| **Doku-Neuaufbau (2026-06-08)** | Gesamte `docs/` nach dem Verlust neu erstellt |
| **Performance (2026-06-08)** | Frankfurt-Co-Location + ISR + `generateStaticParams` + verschlankte Queries + In-Process-Cache → Detail 4.5 s→0.12 s; Keep-Alive-Workflow |
| **Auto-Sync (2026-06-08)** | `/admin/auto-update` (idempotent) + `sync-results.yml` (30 min) → Ergebnisse organisieren sich automatisch |
| **Tipp-Auswertung (2026-06-08)** | Tipp vs. Ergebnis + Kicktipp-Punkte + Bilanz (Tipps-Seite & Match-Detail) |
| **Modell: Gastgeber (2026-06-08)** | Gerichteter Heimvorteil USA/Kanada/Mexiko (Gruppenphase, tunebar) |
| **Venues aktiviert (2026-06-08)** | 72 Gruppenspiele via FIFA-Spielplan verknüpft → Höhe/Reise/Umwelt aktiv; 16 echte Stadien |
| **Daten-Audit (2026-06-08)** | Vollständigkeit geprüft; Schätzwerte im UI gekennzeichnet; Methodik-Doku für externe |

## Risiko-Log (Auszug, alle behandelt)
- football-data.org deckt WM 2026 nicht ab → world-cup-2026-live-api ✓
- FIFA-Ranking doppelte Stärke zu Elo → nur Elo-Init ✓
- Form nicht datengetrieben / zwei Form-Engines → form_engine v2 als Single Source ✓
- Initial-Elo manuell getunt → eloratings.net-Import ✓
- KO-Spiele ohne Teilnehmer → knockout_resolver ✓
- Phantom-Fatigue vor Turnierstart → Rest-Days nur gespielte Spiele ✓
- **Quellcode-Verlust** → Recovery aus .pyc/.next-Sourcemaps/DB ✓; `.gitignore` verhindert Wiederholung
- Hosting-Kosten → Free-Stack ✓

## Offen / Optional
- Uptime-Pinger gegen Cold Start · CORS exakt · Neon-Passwort rotieren · Venue-Zuordnung pro Spiel aus API.
