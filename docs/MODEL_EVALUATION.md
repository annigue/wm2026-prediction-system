# MODEL_EVALUATION — Ist die Komplexität gerechtfertigt?

Rigorose, deterministische Bewertung (fester RNG-Seed). Code: `scripts/eval/`
(`metrics.py`, `run_evaluation.py`). Ziel: trägt das Modell, oder reicht etwas Einfacheres?

## Methodik
- **Varianten:** V1 Elo-only · V2 Elo+Poisson · V3 +Form · V4 +Form+Markt · V5 Full (DB-Prognose).
- **Bounded Backtest:** wenige reale Ergebnisse vor WM-Start → zwei klar benannte
  Ground-Truth-Szenarien (Full bzw. Elo+Poisson als „Wahrheit"), 2000 Outcome-Samples/Spiel.
- **Metriken:** LogLoss (primär), Brier, Accuracy, ECE (Kalibrierung).
- **Feature-Importance:** label-frei via Prognose-Sensitivität (mittlerer |ΔP(home)| beim
  Permutieren eines Features).

## Kernbefunde (72 Gruppenspiele, Seed 42)

| Variante | LogLoss | ECE |
|---|---|---|
| Elo only | ~1.05 | ~0.07–0.09 |
| **Elo + Poisson** | **~0.99** | **~0.002** |
| + Form / + Markt / Full | ~0.98–0.99 | ~0.002 |

1. **Elo + Poisson + Dixon-Coles ≈ 99 % der Performance.** Der größte Sprung kommt vom
   Poisson-/Dixon-Coles-Layer (Kalibrierung: ECE ~0.07 → ~0.002).
2. **Feature-Stack bewegt P(home) im Schnitt nur ~2 pp** und ändert nie die W/U/N-Reihenfolge.
3. **Feature-Importance:** Elo dominiert — ca. **6× stärker als Marktwert**, **~14× stärker
   als Form**. Alter/Caps lagen darunter → **entfernt** (reines Rauschen aus Seed-Schätzwerten).
4. **Tipping:** EV-Maximierung schlägt argmax-Tipp deutlich (~+24–28 % erwartete Punkte).
5. **Konsistenz:** Monte-Carlo-Champion == deterministische Projektion (keine strukturelle Verzerrung).

## Strategische Konsequenz
Das System ist **nicht mehr in der Modell-Entwicklungs-, sondern in der Datenqualitäts- und
Entscheidungs-Phase**. Daraus folgten (alle umgesetzt):
- Feature-Reduktion 7 → (4–)5 (Alter/Caps/FIFA-Live entfernt; Rest-Days als reproduzierbarer Faktor ergänzt).
- Form vollständig datengetrieben (form_engine v2: Punkte + Tore + Recency).
- Initial-Elo reproduzierbar aus eloratings.net statt Handwerten.
- Fokus weiterer Arbeit auf den **Decision Layer** (EV + Edge gegen echte Quoten).

## Verifikation nach Wiederherstellung (2026-06-07)
Nach dem Code-Rebuild reproduziert die Monte-Carlo-Simulation die bekannte Champion-Verteilung
(Spanien ~18 %, Argentinien ~11 %, Frankreich ~7.6 %), ECE des Full-Modells gehalten (~0.0016),
0 Prognose-Inversionen über 72 Spiele.

## Bekannte Grenzen der Evaluation
Wenige reale Ergebnisse vor WM-Start → label-freie Maße + bounded Backtest statt großem
historischem Out-of-Sample-Test. Während des Turniers liefern reale Ergebnisse echte Labels;
`run_evaluation.py` ist dafür wiederholbar.
