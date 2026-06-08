# METHODOLOGY — Wie das WM-2026-Prognosesystem funktioniert

*Diese Seite erklärt das gesamte System von vorne bis hinten — auch für Leser:innen ohne
Statistik- oder Programmierhintergrund. Für die formale Mathematik siehe [ML_MODEL.md](ML_MODEL.md),
für die Datenbank-Felder [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md).*

---

## 1. Was das System tut

Es beantwortet drei Fragen für die Fußball-WM 2026:
1. **Wie geht ein einzelnes Spiel aus?** (Sieg/Unentschieden/Niederlage, erwartete Tore, wahrscheinlichste Ergebnisse)
2. **Wie weit kommt jedes Team?** (Gruppensieg, Achtelfinale … Titel — als Wahrscheinlichkeiten)
3. **Was ist ein guter Tipp / eine lohnende Wette?** (punktoptimaler Ergebnis-Tipp, Value-Bets gegen echte Quoten)

Alles basiert auf **Daten und nachvollziehbaren Formeln** — keine Bauchgefühle, keine Black-Box-KI.

---

## 2. Die Datengrundlage

| Daten | Woher | Echt oder Schätzung? |
|---|---|---|
| **Stärke jedes Teams (Elo)** | eloratings.net (etablierte Welt-Rangliste) | **echt**, extern |
| **Spielplan, Anstoßzeiten, Ergebnisse** | offizielle WM-API (live) | **echt**, live |
| **Stadien + Höhenlage/Koordinaten** | offizieller FIFA-Spielplan + Geodaten | **echt** |
| **Marktwert (Kader-Gesamtwert)** | einmalig eingepflegt | **Schätzung**, eingefroren |
| **Form** | aus echten Ergebnissen berechnet | **echt** (ab 1. Spieltag) |
| FIFA-Ranking, Alter, Caps | Seed | **Schätzung**, *fließen NICHT ins Modell* |

Kurz: Das, was die Prognose **trägt** (Elo, Spielplan, Ergebnisse, Stadien), ist echt. Der
einzige aktiv genutzte Schätzwert ist der **Marktwert** — und der wirkt bewusst nur schwach.

---

## 3. Die Pipeline auf einen Blick

```
   TEAMSTÄRKE          KONTEXT                TOR-MODELL            ERGEBNIS
   ─────────           ───────                ──────────            ────────
   Elo-Rating  ──┐
                 ├──► + Form, Marktwert,  ──► erwartete Tore   ──► P(Sieg/Remis/
   (live aktua-  │     Höhe, Reise,           pro Team             Niederlage),
    lisiert)     │     Erholung, Gastgeber    (Poisson +           xG, wahrschein-
                 │                            Dixon-Coles)         lichste Ergebnisse
                 │
                 └──► dasselbe, aber mit Zufall pro Spiel
                      ► 100.000× das ganze Turnier durchspielen (Monte-Carlo)
                      ► Anteil der Durchläufe = Titel-/Rundenwahrscheinlichkeit

   Daraus abgeleitet:  punktoptimaler Tipp   +   Value-Bets (Vergleich mit Marktquoten)
```

**Kernidee:** Die **Elo-Stärke trägt die Vorhersage**. Alle Zusatzfaktoren *verfeinern* sie nur
leicht. Das ist Absicht und durch eine [Modell-Evaluation](MODEL_EVALUATION.md) belegt.

---

## 4. Schritt für Schritt

### Schritt 1 — Teamstärke (Elo-Rating)
Jedes Team hat eine **Stärkezahl**. Höher = stärker (Spanien ~2155, Deutschland ~1925, Saudi-Arabien ~1569).
- **Herkunft:** Startwerte von eloratings.net (gleiche Formel wie im Projekt, kein Handtuning).
- **Lernen:** Nach **jedem echten Ergebnis** passt sich Elo an — Sieger steigen, Verlierer fallen;
  ein hoher Sieg zählt mehr, ein Sieg gegen einen Favoriten mehr als gegen einen Außenseiter.
- Elo ist die **einzige dynamische Stärkemetrik**. Verliert ein geschwächtes Team, fällt sein Elo
  automatisch — so „repariert" sich das Modell selbst, ohne dass wir Verletzungen kennen müssen.

### Schritt 2 — Kontext-Anpassung (kleine, gerichtete Korrekturen)
Zur Elo-Differenz kommen begrenzte Zu-/Abschläge (in „Elo-Punkten", gedeckelt):

| Faktor | Was er misst | Datenbasis | max. Einfluss |
|---|---|---|---|
| **Form** | letzte Spiele (Punkte + Tore) | echte Ergebnisse | ±60 |
| **Marktwert** | grobe Kaderqualität | Schätzung (statisch) | ±50 |
| **Höhe** | Spielort-Höhe vs. Heimathöhe der Teams | Geodaten | ±80 |
| **Reise** | Anreisedistanz zum Stadion | Geodaten | ±30 |
| **Erholung** | Tage Pause seit letztem Spiel | Spielplan | ±20 |
| **Gastgeber** | USA/Kanada/Mexiko im eigenen Land (nur Gruppenphase) | Team-Identität | +55 |

Wichtig: Diese Faktoren **verschieben** die Prognose nur leicht (im Schnitt ~2 Prozentpunkte) —
die Elo-Stärke dominiert. Bei einem WM-Spiel auf neutralem Boden sind „Heim/Auswärts" nur
Bezeichnungen; das Modell rechnet **symmetrisch**. Echten Heimvorteil gibt es nur für die drei
**Gastgeber** im eigenen Land.

### Schritt 3 — Vom Stärkewert zu Toren (Poisson + Dixon-Coles)
Aus der angepassten Elo-Differenz werden die **erwarteten Tore** jedes Teams (xG). Ein bewährtes
statistisches Tormodell (**Poisson**) verteilt daraus die Wahrscheinlichkeit **jedes Spielstands**
(0:0, 1:0, 2:1 …). Eine **Dixon-Coles-Korrektur** justiert die häufigen knappen Ergebnisse
(0:0, 1:0, 1:1) realistischer. Aufsummiert ergibt das die Balken **Sieg / Unentschieden / Niederlage**
und die Ergebnis-Heatmap.

### Schritt 4 — Das ganze Turnier (Monte-Carlo-Simulation)
Für Titelchancen wird das Turnier **100.000-mal** komplett durchgespielt — mit etwas **Zufall pro
Spiel** (Tagesform, Nervenstärke, Bedingungen). In jedem Durchlauf werden Gruppen ausgespielt,
Tabellen gebildet, der K.-o.-Baum gefüllt, Sieger ermittelt. Der **Anteil der Durchläufe**, in dem
ein Team Weltmeister wird, ist seine **Titelwahrscheinlichkeit** (analog für Achtelfinale, Halbfinale …).
Die Simulation läuft im Hintergrund und blockiert die App nicht.

### Schritt 5 — Tipps & Wetten
- **Punktoptimaler Tipp:** nicht das *wahrscheinlichste* Ergebnis, sondern der Tipp mit den **meisten
  erwarteten Tipp-Punkten** (Kicktipp-Schema: exakt 4 / Tordifferenz 3 / Tendenz 2 / 0). Für gespielte
  Spiele zeigt die Tipps-Seite **Tipp vs. echtes Ergebnis + erzielte Punkte**.
- **Value-Bets:** Wenn echte Buchmacher-Quoten vorliegen, vergleicht das System die **Modell-Wahr­schein­lich­keit**
  mit der **fairen Marktwahrscheinlichkeit** (Buchmacher-Marge herausgerechnet). **Edge** = wie viel
  optimistischer das Modell ist; **EV** = ob die Wette sich rechnerisch lohnt. Reines Analyse-Tool,
  kein Glücksspiel-Aufruf.

---

## 5. Wie alles zusammenhängt

Ein **echtes Ergebnis** kommt rein (automatisch via Sync alle 30 min) und löst eine Kette aus:

```
Ergebnis → Elo neu (beide Teams) → Form neu → K.-o.-Baum füllen →
   alle Prognosen neu → Titel-Simulation neu
```

So sind nach jedem Spieltag **Stärken, Spielprognosen, Tabellen, Titelchancen und Tipps**
automatisch aktuell — ohne manuelles Zutun. Genau eine Größe (Elo) ist der „Speicher" der
Teamstärke; alles andere wird daraus jedes Mal frisch berechnet.

---

## 6. Was das Modell kann — und bewusst nicht

**Kann:** Stärkeverhältnisse, Tor-/Ergebnisverteilungen, Turnierverläufe, Höhen-/Reise-/Gastgeber-Effekte,
Selbstkorrektur über echte Ergebnisse, kalibrierte Wahrscheinlichkeiten.

**Bewusst nicht:** einzelne Spieler, Verletzungen/Sperren, konkretes Wetter (nur grober Klima-/Höhen-Stress
als Unsicherheit), Taktik/Aufstellung, Schiedsrichter. Diese Grenzen sind dokumentiert
([LIMITATIONS.md](LIMITATIONS.md)) — der Grundsatz lautet: **lieber eine offen benannte Grenze als ein
versteckter Schätzwert.**

---

## 7. Mini-Glossar
- **Elo:** dynamische Stärkezahl eines Teams; steigt/fällt mit Ergebnissen.
- **xG (expected Goals):** statistisch erwartete Tore eines Teams in einem Spiel.
- **Poisson:** Standardmodell für die Verteilung von Tor-Anzahlen.
- **Dixon-Coles:** Korrektur, die knappe Ergebnisse realistischer macht.
- **Monte-Carlo:** „viele Zufallsdurchläufe" — hier 100.000 simulierte Turniere.
- **Edge / EV:** Vorsprung der Modell-Wahrscheinlichkeit gegenüber dem Markt / erwarteter Wettwert.
- **PRIOR:** ein vorab gesetzter, statischer Schätzwert (hier: Marktwert).
