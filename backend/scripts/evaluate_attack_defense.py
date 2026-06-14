"""Walk-forward-Backtest: reines Elo (γ=0) vs. Elo+Attack/Defense (γ>0).

Point-in-time (kein Look-ahead): Elo UND Attack/Defense werden chronologisch aus der Historie
aufgebaut; jedes Spiel wird VOR seinem Ergebnis prognostiziert, dann erst fließt es ins Modell.
Metriken (1X2): LogLoss, Brier, ECE. Vergleich über mehrere γ → Grundlage für die Freigabe.

Datenbasis: martj42/international_results (CSV), Team-Namen als Schlüssel (DB nicht nötig).
Aufruf:  PYTHONPATH=. python scripts/evaluate_attack_defense.py
"""
import csv
import io
from collections import defaultdict, deque
from datetime import date, datetime

import numpy as np
from scipy.stats import poisson

from app.services.elo_model import EloModel

CSV_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
LOCAL = "/tmp/intl_results.csv"
CUTOFF = date(2015, 1, 1)     # langer Backtest-Zeitraum
MIN_GAMES = 10               # beide Teams brauchen so viele Vorspiele (Warmup)
WINDOW, DECAY, K_SHRINK = 20, 0.90, 8.0
CLAMP_LO, CLAMP_HI = 0.65, 1.55
BASE_GOALS, RHO, MAXG = 1.30, -0.13, 8
GAMMAS = [0.0, 0.5, 0.7, 0.85, 1.0, 1.2]
_AR = np.arange(MAXG + 1)


def probs_1x2(lh, la):
    pi, pj = poisson.pmf(_AR, lh), poisson.pmf(_AR, la)
    M = np.outer(pi, pj)
    M[0, 0] *= 1 - lh * la * RHO
    M[1, 0] *= 1 + la * RHO
    M[0, 1] *= 1 + lh * RHO
    M[1, 1] *= 1 - RHO
    M /= M.sum()
    ph = float(np.tril(M, -1).sum())   # i>j
    pd = float(np.trace(M))
    return ph, pd, max(1.0 - ph - pd, 1e-9)


def rating(games, mu):
    """attack, defense aus letzten Spielen (recency + Shrinkage zu 1.0)."""
    if not games:
        return 1.0, 1.0
    wsum = gf_w = ga_w = 0.0
    for i, (gf, ga) in enumerate(reversed(games)):   # i=0 = jüngstes
        w = DECAY ** i
        wsum += w; gf_w += w * gf; ga_w += w * ga
    atk = (gf_w + K_SHRINK * mu) / (wsum + K_SHRINK) / mu
    dfn = (ga_w + K_SHRINK * mu) / (wsum + K_SHRINK) / mu
    return max(CLAMP_LO, min(CLAMP_HI, atk)), max(CLAMP_LO, min(CLAMP_HI, dfn))


def lambdas(eh, ea, ah, dh, aa, da, g):
    lh = BASE_GOALS * np.exp((eh - ea) / 800.0)
    la = BASE_GOALS * np.exp((ea - eh) / 800.0)
    if g > 0:
        lh *= (ah * da) ** g
        la *= (aa * dh) ** g
    return float(np.clip(lh, 0.25, 5.0)), float(np.clip(la, 0.25, 5.0))


def main():
    try:
        txt = __import__("httpx").get(CSV_URL, timeout=90).text
    except Exception:
        txt = open(LOCAL).read()

    rows = []
    for r in csv.DictReader(io.StringIO(txt)):
        if r["home_score"] in ("", "NA") or r["away_score"] in ("", "NA"):
            continue
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
        except ValueError:
            continue
        if d < CUTOFF:
            continue
        rows.append((d, r["home_team"], r["away_team"], int(r["home_score"]), int(r["away_score"])))
    rows.sort(key=lambda x: x[0])
    mu = np.mean([g for _, _, _, hg, ag in rows for g in (hg, ag)])

    elo = defaultdict(lambda: 1500.0)
    hist = defaultdict(lambda: deque(maxlen=WINDOW))
    played = defaultdict(int)
    # Metriken je gamma
    ll = {g: 0.0 for g in GAMMAS}
    br = {g: 0.0 for g in GAMMAS}
    bins = {g: [[0.0, 0.0, 0] for _ in range(10)] for g in GAMMAS}  # conf_sum, acc_sum, n
    n = 0

    for d, h, a, hg, ag in rows:
        outcome = 0 if hg > ag else (1 if hg == ag else 2)
        if played[h] >= MIN_GAMES and played[a] >= MIN_GAMES:
            ah, dh = rating(list(hist[h]), mu)
            aa, da = rating(list(hist[a]), mu)
            for g in GAMMAS:
                lh, la = lambdas(elo[h], elo[a], ah, dh, aa, da, g)
                p = probs_1x2(lh, la)
                ll[g] += -np.log(p[outcome])
                br[g] += sum((p[k] - (1.0 if k == outcome else 0.0)) ** 2 for k in range(3))
                conf = max(p); pred = int(np.argmax(p))
                b = min(int(conf * 10), 9)
                bins[g][b][0] += conf
                bins[g][b][1] += 1.0 if pred == outcome else 0.0
                bins[g][b][2] += 1
            n += 1
        # danach ins Modell aufnehmen
        elo[h], elo[a] = EloModel.update_both(elo[h], elo[a], hg, ag, k=32.0)
        hist[h].append((hg, ag)); hist[a].append((ag, hg))
        played[h] += 1; played[a] += 1

    def ece(g):
        tot = sum(b[2] for b in bins[g])
        return sum(abs(b[1] / b[2] - b[0] / b[2]) * b[2] for b in bins[g] if b[2]) / tot

    print(f"Backtest: {n} bewertete Spiele (ab {CUTOFF}, μ={mu:.3f})\n")
    print(f"{'gamma':>6} {'LogLoss':>9} {'Brier':>8} {'ECE':>7}")
    base = None
    for g in GAMMAS:
        L, B, E = ll[g] / n, br[g] / n, ece(g)
        if g == 0.0:
            base = (L, B, E)
        tag = "  (Basis: reines Elo)" if g == 0.0 else \
              f"  ΔLogLoss {L-base[0]:+.4f} · ΔBrier {B-base[1]:+.4f}"
        print(f"{g:>6.2f} {L:>9.4f} {B:>8.4f} {E:>7.4f}{tag}")
    best = min(GAMMAS, key=lambda g: ll[g] / n)
    print(f"\nBestes γ nach LogLoss: {best}"
          + ("  → Attack/Defense verbessert die Kalibrierung" if best != 0.0
             else "  → reines Elo bleibt am besten (Attack/Defense NICHT aktivieren)"))


if __name__ == "__main__":
    main()
