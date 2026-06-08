# RECOVERY — Quellcode-Wiederherstellung (2026-06-07)

## Was passiert war
Der gesamte Quellcode unter `2026-06 WM 2026/` war von der Platte verschwunden. Übrig blieben
nur kompilierte Artefakte: `backend/**/__pycache__/*.pyc`, `frontend/.next/`, `venv/`,
`backend/.env`. Ein „Initial commit" hatte fälschlich nur diese Artefakte (Bytecode/venv)
erfasst, **nicht** den Quellcode (`.py`, `.tsx`, `.md`, Configs). Ursache war ein Commit-/Clean-
Ablauf, der Source-Dateien verwarf und Build-Artefakte einbezog.

**Die PostgreSQL-DB war vollständig intakt** — der wertvollste Teil (alle Daten) war nie betroffen.

## Wiederherstellungsquellen
| Bereich | Quelle | Fidelität |
|---|---|---|
| Backend `.py` | Decompile der `.pyc` (Python 3.12, pycdc) + Session-Wissen | hoch (Logik exakt; Deklaratives 1:1, Methodenkörper rekonstruiert) |
| **Frontend `.tsx/.ts`** | **`.next` eval-source-map → eingebettete `sourcesContent`** | **verbatim** (Originalquelle!) |
| Config/Infra/Docs | Session-Wissen + DB + `pip freeze` | rekonstruiert |
| Initial-Elo-Daten | vom Nutzer eingefügter eloratings-Export | exakt |
| Daten (Teams/Spiele/…) | intakte DB | exakt |

## Vorgehen (Batches, jeweils verifiziert)
1. **Backup** aller Recovery-Assets (read-only): `/home/anne/wm2026_recovery_backup_20260607_130233`.
2. **Decompiler** (pycdc) gebaut; alle `.pyc` → Referenz.
3. Backend in Schichten: Data-Layer → Core-Services → Logik-Services → Simulator (gegen
   bekannte Champion-Verteilung verifiziert) → Router + `main` (voller App-Boot gegen DB, alle Endpoints 200).
4. Scripts + alembic + Infra (`requirements.txt` aus venv); `.gitignore`.
5. **Frontend** aus `.next`-Sourcemaps extrahiert (24 Dateien verbatim) + Configs/`types.ts` neu;
   `npm run build` erfolgreich. Die wiederhergestellte `api.ts` diente als maßgeblicher
   API-Contract → Backend exakt darauf ausgerichtet.
6. Sauberes, **eigenes** Git-Repo angelegt, vollständigen Source committet (diesmal echte
   Quellen, keine Artefakte), zu GitHub gepusht.
7. Deploy auf Free-Stack (Vercel + Render-Free + Neon), DB migriert, end-to-end verifiziert.

## Lessons learned / Prävention
- **`.gitignore`** schließt jetzt `venv/`, `node_modules/`, `.next/`, `__pycache__/`, `.env` aus —
  der Auslöser (Artefakte committen, Source ignorieren/löschen) kann nicht erneut greifen.
- **Eigenes Repo** für das Projekt (nicht im fremden „Albumgenerator"-Repo).
- Dev-Builds mit `eval-source-map` enthalten den Originalquellcode — ein realer Recovery-Anker
  für Frontends ohne Bytecode.
- Reproduzierbare externe Daten (eloratings-Datei committed) erleichtern Wiederaufbau.

## Verbleibende Artefakte
- Backup: `/home/anne/wm2026_recovery_backup_20260607_130233` (pyc, .next, .env, DB-Dump).
- Decompile-Referenz: `/home/anne/wm2026_recovery_work/decompiled`.
- DB-Migrationsdump: `/home/anne/wm2026_neon_migration.sql`.
