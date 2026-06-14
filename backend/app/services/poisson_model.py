"""Poisson Goal Model mit Dixon-Coles-Korrektur."""

import numpy as np
from scipy.stats import poisson as sp_poisson
from dataclasses import dataclass


@dataclass
class PredictionResult:
    prob_home_win: float
    prob_draw: float
    prob_away_win: float
    lambda_home: float
    lambda_away: float
    score_distribution: dict[str, float]
    top_scorelines: list[dict]


class PoissonModel:
    BASE_GOALS = 1.30   # WM-historischer Tor-Durchschnitt pro Team
    MAX_GOALS  = 8
    RHO        = -0.13  # Dixon-Coles-Korrelationsparameter

    def compute_lambdas(self, elo_home: float, elo_away: float,
                        atk_home: float = 1.0, def_home: float = 1.0,
                        atk_away: float = 1.0, def_away: float = 1.0,
                        gamma: float = 0.0) -> tuple[float, float]:
        """Erwartete Tore: Elo-Baseline × gedämpfter Attack/Defense-Faktor.

        Elo (Exponentialfunktion) bleibt der dominante Hebel. Attack/Defense (≈1.0 neutral)
        modulieren nur gedämpft mit Exponent gamma:
            λ_home = BASE · exp(+Δ/800) · (Attack_home · Defense_away)^gamma
            λ_away = BASE · exp(−Δ/800) · (Attack_away · Defense_home)^gamma
        gamma=0 ⇒ exakt das reine Elo-Modell (keine Verhaltensänderung).
        """
        diff = elo_home - elo_away
        lh = self.BASE_GOALS * np.exp(diff / 800.0)
        la = self.BASE_GOALS * np.exp(-diff / 800.0)
        if gamma > 0:
            lh *= (max(atk_home, 0.1) * max(def_away, 0.1)) ** gamma
            la *= (max(atk_away, 0.1) * max(def_home, 0.1)) ** gamma
        return float(np.clip(lh, 0.25, 5.0)), float(np.clip(la, 0.25, 5.0))

    @staticmethod
    def _dc_tau(i: int, j: int, lh: float, la: float, rho: float) -> float:
        """Dixon-Coles-Korrektur τ für niedrige Scorelines."""
        if i == 0 and j == 0:
            return 1.0 - lh * la * rho
        if i == 1 and j == 0:
            return 1.0 + la * rho
        if i == 0 and j == 1:
            return 1.0 + lh * rho
        if i == 1 and j == 1:
            return 1.0 - rho
        return 1.0

    def compute_distribution(self, lh: float, la: float) -> dict[str, float]:
        """Score-Wahrscheinlichkeitsverteilung über 9×9 Grid (normiert)."""
        dist: dict[str, float] = {}
        total = 0.0
        for i in range(self.MAX_GOALS + 1):
            pi = sp_poisson.pmf(i, lh)
            for j in range(self.MAX_GOALS + 1):
                pj = sp_poisson.pmf(j, la)
                p = float(pi * pj * self._dc_tau(i, j, lh, la, self.RHO))
                dist[f"{i}:{j}"] = p
                total += p
        if total > 0:
            dist = {k: v / total for k, v in dist.items()}
        return dist

    def predict(self, elo_home: float, elo_away: float,
                atk_home: float = 1.0, def_home: float = 1.0,
                atk_away: float = 1.0, def_away: float = 1.0,
                gamma: float = 0.0) -> PredictionResult:
        lh, la = self.compute_lambdas(elo_home, elo_away,
                                      atk_home, def_home, atk_away, def_away, gamma)
        dist = self.compute_distribution(lh, la)

        p_home = sum(p for k, p in dist.items()
                     if int(k.split(":")[0]) > int(k.split(":")[1]))
        p_draw = sum(p for k, p in dist.items()
                     if int(k.split(":")[0]) == int(k.split(":")[1]))
        p_away = max(0.0, 1.0 - p_home - p_draw)

        top5 = sorted(dist.items(), key=lambda x: x[1], reverse=True)[:5]
        top_scorelines = [{"score": k, "prob": round(p, 4)} for k, p in top5]

        return PredictionResult(
            prob_home_win=round(p_home, 4),
            prob_draw=round(p_draw, 4),
            prob_away_win=round(p_away, 4),
            lambda_home=round(lh, 3),
            lambda_away=round(la, 3),
            score_distribution={k: round(v, 6) for k, v in dist.items()},
            top_scorelines=top_scorelines,
        )
