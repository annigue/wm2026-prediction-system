# MODEL_EXPLANATION — Das Modell in einfachen Worten

Für Tipprunden-Teilnehmer & Neugierige: *Wie kommt die Prognose zustande?* — ohne Formeln.

## Die Grundidee

Jedes Team hat eine **Stärkezahl (Elo)**. Je höher, desto stärker. Spielen zwei Teams,
vergleicht das Modell ihre Elo-Werte und leitet daraus ab, wie viele Tore jedes Team
voraussichtlich schießt (**xG, erwartete Tore**). Aus diesen erwarteten Toren berechnet es
die Wahrscheinlichkeit für **jedes mögliche Ergebnis** (0:0, 1:0, 2:1, …) und fasst sie zu
**Sieg / Unentschieden / Niederlage** zusammen.

## Die Stärkezahl (Elo)
- Startwerte kommen von **eloratings.net** (eine etablierte, öffentliche Welt-Rangliste) —
  keine Bauchentscheidungen.
- Nach **jedem echten Spiel** passt sich Elo an: Sieger steigen, Verlierer fallen; ein hoher
  Sieg zählt mehr als ein knapper, ein Sieg gegen einen Favoriten mehr als gegen einen Außenseiter.

## Was die Prognose noch beeinflusst (kleine Korrekturen)
Zusätzlich zur Elo-Stärke berücksichtigt das Modell ein paar **Kontextfaktoren** — bewusst klein:
- **Form** — wie ein Team zuletzt wirklich gespielt hat (Punkte + Tore der letzten Spiele).
- **Marktwert** — grober Indikator für Kaderqualität.
- **Höhe** — Spiele in großer Höhe (Mexiko-Stadt!) sind für Flachland-Teams zehrender.
- **Reise** — sehr weite Anreise kostet etwas.
- **Erholung** — wer mehr Pause seit dem letzten Spiel hatte, ist leicht im Vorteil.

Wichtig: Diese Faktoren **verschieben** die Prognose nur leicht (im Schnitt ~2 Prozentpunkte) —
die **Elo-Stärke dominiert**. Das ist Absicht und durch Tests belegt.

## Tore & Ergebnisse
Die erwarteten Tore kommen aus der Elo-Stärke, zusätzlich fein justiert durch **Attack-/Defense-
Ratings** (wie viele Tore ein Team zuletzt erzielt/kassiert hat — aus echten Ergebnissen,
gedämpft, Elo bleibt dominant). Daraus erzeugt ein bewährtes statistisches Tormodell (**Poisson**
mit **Dixon-Coles-Korrektur** für knappe Ergebnisse wie 1:0/1:1) die Wahrscheinlichkeit jedes
Spielstands. Daraus kommen die Balken „Heimsieg/Unentschieden/Auswärtssieg" und die Heatmap.

## Der Tipp
- **xG-Tipp:** die gerundeten erwarteten Tore (z. B. xG 1.7:0.9 → „2:1").
- **Modell-Tipp:** das wahrscheinlichste Einzelergebnis.
- **Punktoptimaler Tipp** (Tipps-Seite): nicht das wahrscheinlichste Ergebnis, sondern der Tipp,
  der über alle möglichen Ausgänge die **meisten erwarteten Tipp-Punkte** bringt.

## Das ganze Turnier
Für Titelchancen wird das Turnier **zehntausende Male durchgespielt** (Monte-Carlo) — mit
etwas Zufall pro Spiel (Tagesform, Nervenstärke, Bedingungen). Der Anteil der Durchläufe, in
denen ein Team Weltmeister wird, ist seine **Titelwahrscheinlichkeit**.

## Wetten (Decision Engine)
Wenn echte Buchmacher-Quoten vorliegen, vergleicht das System die **Modell-Wahrscheinlichkeit**
mit der **fairen Markt-Wahrscheinlichkeit** (Buchmacher-Marge herausgerechnet):
- **Edge** = wie viel optimistischer das Modell ist als der Markt.
- **EV (Expected Value)** = lohnt sich die Wette rechnerisch?
- Kategorien: **Value Bet** (Modell schlägt den Markt) bis **No Bet** (kein Vorteil).
> Reines Analyse-Tool, kein Aufruf zum Glücksspiel.

## Was das Modell NICHT weiß
- **Konkretes Wetter** (Regen/Wind/Tagestemperatur) — kein Forecast (nur ein grober
  Höhen-/Klima-Stress als Unsicherheit in der Simulation).
- **Verletzungen/Sperren** — kein Live-Datenstrom; Elo fängt es erst nach dem Spiel auf.
- **Taktik, Aufstellung, Schiedsrichter, Tagesform im Detail, Rivalitäten/Head-to-Head.**
Diese Grenzen sind bewusst und dokumentiert ([LIMITATIONS.md](LIMITATIONS.md)).
