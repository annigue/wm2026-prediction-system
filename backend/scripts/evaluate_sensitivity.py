"""Sensitivitäts-Backtest: Sind die Modell-Beschränkungen zu stark?

Walk-forward, point-in-time (kein Look-ahead) wie evaluate_attack_defense.py, aber:
  - lockert jede Beschränkung EINZELN um eine Baseline herum (one-at-a-time):
        γ (ad_gamma) · Clamp [lo,hi] · Shrinkage k · Elo-K
  - misst zusätzlich zur TENDENZ (1X2) auch die ERGEBNIS-Ebene:
        Score-LogLoss (−log P(exaktes Ergebnis) über die Poisson-DC-Matrix)
        Goal-MAE      (mittlerer |λ − tatsächliche Tore|)
    → der Clamp/γ wirken vor allem auf den Score; 1X2 allein fängt das nur teilweise.

Lesart:  Lockern verbessert die Metrik → Beschränkung war zu stark.
         Lockern verschlechtert sie     → Beschränkung schützt (berechtigt).

Datenbasis: martj42/international_results (CSV). Aufruf:
    PYTHONPATH=. python scripts/evaluate_sensitivity.py
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
CUTOFF = date(2015, 1, 1)
MIN_GAMES = 10
WINDOW, DECAY = 20, 0.90
BASE_GOALS, RHO, MAXG = 1.30, -0.13, 8
_AR = np.arange(MAXG + 1)

# ── Baseline = aktuelle Produktionswerte ─────────────────────────────────────
B_GAMMA, B_CLAMP, B_KSHRINK, B_KELO = 0.5, (0.65, 1.55), 8.0, 32.0

# ── Sweeps (one-at-a-time um die Baseline) ───────────────────────────────────
SW_GAMMA = [0.0, 0.3, 0.5, 0.7, 0.85, 1.0]
SW_CLAMP = [(0.75, 1.40), (0.65, 1.55), (0.55, 1.70), (0.50, 1.85), (0.45, 2.00)]
SW_KSHRINK = [2.0, 4.0, 8.0, 12.0, 20.0]
SW_KELO = [20.0, 32.0, 40.0, 50.0, 60.0]
KELO_VALUES = sorted({B_KELO, *SW_KELO})


def raw_weighted(games):
    """Recency-gewichtete Summen (decay) — unabhängig von Shrinkage/Clamp, daher 1× pro Spiel."""
    wsum = gf_w = ga_w = 0.0
    for i, (gf, ga) in enumerate(reversed(games)):  # i=0 = jüngstes
        w = DECAY ** i
        wsum += w; gf_w += w * gf; ga_w += w * ga
    return wsum, gf_w, ga_w


def rating(raw, mu, k_shrink, lo, hi):
    """attack, defense aus gewichteten Summen: Shrinkage zu 1.0 + Clamp."""
    wsum, gf_w, ga_w = raw
    if wsum == 0.0:
        return 1.0, 1.0
    atk = (gf_w + k_shrink * mu) / (wsum + k_shrink) / mu
    dfn = (ga_w + k_shrink * mu) / (wsum + k_shrink) / mu
    return max(lo, min(hi, atk)), max(lo, min(hi, dfn))


def grid(lh, la):
    """Normierte 9×9 Score-Matrix mit Dixon-Coles-Korrektur."""
    pi, pj = poisson.pmf(_AR, lh), poisson.pmf(_AR, la)
    M = np.outer(pi, pj)
    M[0, 0] *= 1 - lh * la * RHO
    M[1, 0] *= 1 + la * RHO
    M[0, 1] *= 1 + lh * RHO
    M[1, 1] *= 1 - RHO
    return M / M.sum()


def lambdas(eh, ea, ah, dh, aa, da, g):
    lh = BASE_GOALS * np.exp((eh - ea) / 800.0)
    la = BASE_GOALS * np.exp((ea - eh) / 800.0)
    if g > 0:
        lh *= (ah * da) ** g
        la *= (aa * dh) ** g
    return float(np.clip(lh, 0.25, 5.0)), float(np.clip(la, 0.25, 5.0))


class Acc:
    """Sammelt alle Metriken für EINE Konfiguration."""
    __slots__ = ("ll", "br", "sll", "gmae", "n", "bins")

    def __init__(self):
        self.ll = self.br = self.sll = self.gmae = 0.0
        self.n = 0
        self.bins = [[0.0, 0.0, 0] for _ in range(10)]  # conf_sum, hit_sum, n

    def add(self, lh, la, hg, ag, outcome):
        M = grid(lh, la)
        ph = float(np.tril(M, -1).sum()); pd = float(np.trace(M))
        pa = max(1.0 - ph - pd, 1e-12)
        p = (ph, pd, pa)
        self.ll += -np.log(max(p[outcome], 1e-12))
        self.br += sum((p[k] - (1.0 if k == outcome else 0.0)) ** 2 for k in range(3))
        self.sll += -np.log(max(M[min(hg, MAXG), min(ag, MAXG)], 1e-12))
        self.gmae += abs(lh - hg) + abs(la - ag)
        conf = max(p); pred = int(np.argmax(p))
        b = min(int(conf * 10), 9)
        self.bins[b][0] += conf; self.bins[b][1] += 1.0 if pred == outcome else 0.0
        self.bins[b][2] += 1
        self.n += 1

    def result(self):
        ece = sum(abs(x[1] / x[2] - x[0] / x[2]) * x[2] for x in self.bins if x[2]) / self.n
        return dict(LogLoss=self.ll / self.n, Brier=self.br / self.n, ECE=ece,
                    ScoreLL=self.sll / self.n, GoalMAE=self.gmae / (2 * self.n))


def build_configs():
    """(gruppe, label, params) — Baseline taucht in jeder Gruppe auf."""
    cfgs = []
    for g in SW_GAMMA:
        cfgs.append(("γ (ad_gamma)", f"γ={g}",
                     dict(gamma=g, clamp=B_CLAMP, kshrink=B_KSHRINK, kelo=B_KELO)))
    for c in SW_CLAMP:
        cfgs.append(("Clamp [lo,hi]", f"[{c[0]:.2f},{c[1]:.2f}]",
                     dict(gamma=B_GAMMA, clamp=c, kshrink=B_KSHRINK, kelo=B_KELO)))
    for k in SW_KSHRINK:
        cfgs.append(("Shrinkage k", f"k={k:g}",
                     dict(gamma=B_GAMMA, clamp=B_CLAMP, kshrink=k, kelo=B_KELO)))
    for ke in SW_KELO:
        cfgs.append(("Elo-K", f"K={ke:g}",
                     dict(gamma=B_GAMMA, clamp=B_CLAMP, kshrink=B_KSHRINK, kelo=ke)))
    return cfgs


def is_baseline(p):
    return (p["gamma"] == B_GAMMA and p["clamp"] == B_CLAMP
            and p["kshrink"] == B_KSHRINK and p["kelo"] == B_KELO)


def main():
    try:
        txt = __import__("httpx").get(CSV_URL, timeout=120).text
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
    mu = float(np.mean([g for _, _, _, hg, ag in rows for g in (hg, ag)]))

    # Elo pro K-Wert separat (K verändert die Elo-Entwicklung selbst)
    elo = {ke: defaultdict(lambda: 1500.0) for ke in KELO_VALUES}
    hist = defaultdict(lambda: deque(maxlen=WINDOW))
    played = defaultdict(int)

    configs = build_configs()
    acc = {id(p): Acc() for _, _, p in configs}

    for d, h, a, hg, ag in rows:
        if played[h] >= MIN_GAMES and played[a] >= MIN_GAMES:
            outcome = 0 if hg > ag else (1 if hg == ag else 2)
            raw_h, raw_a = raw_weighted(list(hist[h])), raw_weighted(list(hist[a]))
            for _, _, p in configs:
                ah, dh = rating(raw_h, mu, p["kshrink"], *p["clamp"])
                aa, da = rating(raw_a, mu, p["kshrink"], *p["clamp"])
                eh, ea = elo[p["kelo"]][h], elo[p["kelo"]][a]
                lh, la = lambdas(eh, ea, ah, dh, aa, da, p["gamma"])
                acc[id(p)].add(lh, la, hg, ag, outcome)
        # danach ins Modell aufnehmen (alle Elo-K-Varianten + gemeinsame Historie)
        for ke in KELO_VALUES:
            elo[ke][h], elo[ke][a] = EloModel.update_both(elo[ke][h], elo[ke][a], hg, ag, k=ke)
        hist[h].append((hg, ag)); hist[a].append((ag, hg))
        played[h] += 1; played[a] += 1

    base = next(acc[id(p)].result() for _, _, p in configs if is_baseline(p))
    n = next(acc[id(p)].n for _, _, p in configs if is_baseline(p))

    print(f"\nSensitivitäts-Backtest: {n} bewertete Spiele (ab {CUTOFF}, μ={mu:.3f})")
    print("Baseline = Produktion: γ=0.5 · Clamp[0.65,1.55] · k=8 · Elo-K=32")
    print("Alle Metriken: niedriger = besser. Δ = gegen Baseline. (B)=Baseline\n")

    cols = ["LogLoss", "Brier", "ECE", "ScoreLL", "GoalMAE"]
    last_group = None
    for group, label, p in configs:
        if group != last_group:
            print(f"\n── {group} ──")
            print(f"{'Konfig':>16} " + " ".join(f"{c:>9}" for c in cols) + "   ΔLogLoss ΔScoreLL")
            last_group = group
        r = acc[id(p)].result()
        bl = is_baseline(p)
        dll = r["LogLoss"] - base["LogLoss"]
        dsl = r["ScoreLL"] - base["ScoreLL"]
        tag = " (B)" if bl else ""
        print(f"{label:>16} " + " ".join(f"{r[c]:>9.4f}" for c in cols)
              + f"   {dll:>+8.4f} {dsl:>+8.4f}{tag}")

    # Pro Gruppe: bestes γ/Clamp/k/K nach LogLoss UND nach ScoreLL
    print("\n── Auswertung (bestes je Gruppe) ──")
    groups = {}
    for group, label, p in configs:
        groups.setdefault(group, []).append((label, p))
    for group, items in groups.items():
        best_ll = min(items, key=lambda it: acc[id(it[1])].result()["LogLoss"])
        best_sl = min(items, key=lambda it: acc[id(it[1])].result()["ScoreLL"])
        bl_label = next(l for l, p in items if is_baseline(p))
        verdict = []
        if best_ll[0] != bl_label:
            verdict.append(f"Tendenz besser bei {best_ll[0]}")
        if best_sl[0] != bl_label:
            verdict.append(f"Score besser bei {best_sl[0]}")
        msg = "; ".join(verdict) if verdict else "Baseline ist optimal → Beschränkung berechtigt"
        print(f"  {group:>16}: {msg}")


if __name__ == "__main__":
    main()
