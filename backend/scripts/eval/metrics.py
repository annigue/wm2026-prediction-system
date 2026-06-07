"""
Reine Evaluations-Metriken (deterministisch, keine Seiteneffekte).

3-Klassen-Outcomes (Heimsieg/Remis/Auswärtssieg) als Index 0/1/2.
Prognosen sind 3er-Wahrscheinlichkeitsvektoren.
"""

from __future__ import annotations
import math

EPS = 1e-12


def _clip(p: float) -> float:
    return min(max(p, EPS), 1 - EPS)


def log_loss(probs, outcomes) -> float:
    """Mittlerer negativer Log-Likelihood (niedriger = besser)."""
    if not outcomes:
        return float("nan")
    total = 0.0
    for p, y in zip(probs, outcomes):
        total += -math.log(_clip(p[y]))
    return total / len(outcomes)


def brier_score(probs, outcomes) -> float:
    """Multiklassen-Brier-Score (niedriger = besser)."""
    if not outcomes:
        return float("nan")
    total = 0.0
    for p, y in zip(probs, outcomes):
        for k in range(3):
            target = 1 if k == y else 0
            total += (p[k] - target) ** 2
    return total / len(outcomes)


def accuracy(probs, outcomes) -> float:
    """Anteil korrekt vorhergesagter Ausgänge (argmax)."""
    if not outcomes:
        return float("nan")
    correct = sum(1 for p, y in zip(probs, outcomes) if max(range(3), key=lambda k: p[k]) == y)
    return correct / len(outcomes)


def expected_calibration_error(probs, outcomes, n_bins: int = 10) -> float:
    """ECE über die Konfidenz (max-Wahrscheinlichkeit), gewichteter |acc − conf|."""
    if not outcomes:
        return float("nan")
    bins = [[] for _ in range(n_bins)]
    for p, y in zip(probs, outcomes):
        pred = max(range(3), key=lambda k: p[k])
        conf = p[pred]
        b = min(int(conf * n_bins), n_bins - 1)
        bins[b].append((conf, 1 if pred == y else 0))
    n = len(outcomes)
    ece = 0.0
    for b in bins:
        if not b:
            continue
        conf_mean = sum(c for c, _ in b) / len(b)
        acc_mean = sum(h for _, h in b) / len(b)
        ece += abs(acc_mean - conf_mean) * len(b) / n
    return ece


def spearman_corr(a, b) -> float:
    """Spearman-Rangkorrelation zwischen zwei Wertereihen."""
    if len(a) != len(b) or len(a) < 2:
        return float("nan")
    ra, rb = _ranks(a), _ranks(b)
    n = len(a)
    mean_a = sum(ra) / n
    mean_b = sum(rb) / n
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(ra, rb))
    va = math.sqrt(sum((x - mean_a) ** 2 for x in ra))
    vb = math.sqrt(sum((y - mean_b) ** 2 for y in rb))
    return cov / (va * vb) if va and vb else float("nan")


def _ranks(values) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    for rank, idx in enumerate(order):
        ranks[idx] = rank
    return ranks
