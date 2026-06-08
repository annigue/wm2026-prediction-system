"""
WM 2026 Monte Carlo Turniersimulation — mit Context Injection Layer.

  Gruppenphase: vektorisiert (numpy), 12 × 6 × n_runs Poisson-Samples
  KO-Runden:   Python-Loop, 31 Spiele × n_runs
  Context:     optionaler stochastischer Feature-Modifier pro Spiel

  TournamentSimulator(groups, elos)              → reine Elo-Simulation (Fallback)
  TournamentSimulator(groups, elos, features)    → Elo + Context Injection
"""

import random
import numpy as np

from app.config import settings, HOST_NATIONS
from app.services.context_modifier import (
    compute_group_context_vectorized, compute_ko_context_scalar,
)

BASE_GOALS = 1.30
ELO_SCALE  = 800.0
GROUP_ORDER = list("ABCDEFGHIJKL")
KO_STAGES = ["round_of_32", "round_of_16", "quarterfinal", "semifinal", "final"]


def _lambda(elo_h: float, elo_a: float) -> tuple[float, float]:
    d = elo_h - elo_a
    lh = float(np.clip(BASE_GOALS * np.exp(d / ELO_SCALE), 0.25, 5.0))
    la = float(np.clip(BASE_GOALS * np.exp(-d / ELO_SCALE), 0.25, 5.0))
    return lh, la


def _lambda_vec(diff: np.ndarray):
    lh = np.clip(BASE_GOALS * np.exp(diff / ELO_SCALE), 0.25, 5.0)
    la = np.clip(BASE_GOALS * np.exp(-diff / ELO_SCALE), 0.25, 5.0)
    return lh, la


class TournamentSimulator:
    def __init__(self, groups: dict, elos: dict, features: dict | None = None):
        self.groups = {k: v for k, v in sorted(groups.items())}
        self.elos = elos
        self.features = features or {}
        self._use_context = bool(features)
        self.groups_order = list(self.groups.keys())
        self.all_teams = [t for g in self.groups.values() for t in g]

    # ── Gruppenphase (vektorisiert) ───────────────────────────────────────────
    def _simulate_groups(self, n_runs: int) -> dict:
        """Gibt pro Gruppe (n_runs,)-Arrays für Sieger/Zweiter/Dritter + Dritter-Score."""
        out = {}
        for gid, team_ids in self.groups.items():
            k = len(team_ids)
            team_arr = np.array(team_ids, dtype=object)
            # Gastgeber-Heimvorteil: Gruppenspiele werden im eigenen Land ausgetragen
            # → Host-Team bekommt den Bonus in allen Gruppenspielen (konsistent zur Einzelprognose).
            _hb = settings.host_advantage_elo
            elos = np.array(
                [self.elos.get(t, 1500.0) + (_hb if t in HOST_NATIONS else 0.0) for t in team_ids],
                dtype=np.float64,
            )
            pts = np.zeros((n_runs, k), dtype=np.int32)
            gf  = np.zeros((n_runs, k), dtype=np.int32)
            ga  = np.zeros((n_runs, k), dtype=np.int32)

            for i in range(k):
                for j in range(i + 1, k):
                    base_diff = float(elos[i] - elos[j])
                    if self._use_context:
                        fi = self.features.get(team_ids[i], {})
                        fj = self.features.get(team_ids[j], {})
                        ctx = compute_group_context_vectorized(
                            n_runs,
                            form_home=fi.get("form_score", 0.0),
                            form_away=fj.get("form_score", 0.0),
                            mv_home=fi.get("market_value_millions", 200.0),
                            mv_away=fj.get("market_value_millions", 200.0),
                            env_stress=max(fi.get("env_stress", 0.0), fj.get("env_stress", 0.0)),
                        )
                        diff = base_diff + ctx
                    else:
                        diff = np.full(n_runs, base_diff)
                    lh, la = _lambda_vec(diff)
                    hg = np.random.poisson(lh).astype(np.int32)
                    ag = np.random.poisson(la).astype(np.int32)

                    hw = hg > ag
                    aw = ag > hg
                    dr = ~hw & ~aw
                    pts[:, i] += np.where(hw, 3, np.where(dr, 1, 0))
                    pts[:, j] += np.where(aw, 3, np.where(dr, 1, 0))
                    gf[:, i] += hg; ga[:, i] += ag
                    gf[:, j] += ag; ga[:, j] += hg

            gd = gf - ga
            score = pts.astype(np.int64) * 1_000_000 + gd * 1_000 + gf
            order = np.argsort(-score, axis=1)  # absteigend
            win_idx, run_idx, third_idx = order[:, 0], order[:, 1], order[:, 2]
            third_score = np.take_along_axis(score, third_idx[:, None], axis=1)[:, 0]
            out[gid] = {
                "winner": team_arr[win_idx],
                "runner": team_arr[run_idx],
                "third":  team_arr[third_idx],
                "third_score": third_score,
            }
        return out

    # ── KO-Sieger ─────────────────────────────────────────────────────────────
    def _ko_winner(self, h_id, a_id, stage):
        h_elo = self.elos.get(h_id, 1500.0)
        a_elo = self.elos.get(a_id, 1500.0)
        if self._use_context:
            fh = self.features.get(h_id, {})
            fa = self.features.get(a_id, {})
            ctx = compute_ko_context_scalar(
                form_home=fh.get("form_score", 0.0), form_away=fa.get("form_score", 0.0),
                mv_home=fh.get("market_value_millions", 200.0),
                mv_away=fa.get("market_value_millions", 200.0),
                stage=stage.upper(),
                env_stress=max(fh.get("env_stress", 0.0), fa.get("env_stress", 0.0)),
            )
            h_elo += ctx * 0.5
            a_elo -= ctx * 0.5
        lh, la = _lambda(h_elo, a_elo)
        hg = np.random.poisson(lh)
        ag = np.random.poisson(la)
        if hg > ag:
            return h_id
        if ag > hg:
            return a_id
        # Elfmeter: leichter Elo-Tilt
        p = 0.5 + (h_elo - a_elo) / 10_000.0
        return h_id if random.random() < p else a_id

    # ── Orchestrierung ────────────────────────────────────────────────────────
    def run(self, n_runs: int = 100_000) -> dict:
        groups = self._simulate_groups(n_runs)

        stage_counts = {t: {s: 0 for s in ["round_of_32", "round_of_16",
                                           "quarterfinal", "semifinal", "final", "champion"]}
                        for t in self.all_teams}
        champion_counts = {t: 0 for t in self.all_teams}

        go = self.groups_order
        for r in range(n_runs):
            winners = {g: groups[g]["winner"][r] for g in go}
            runners = {g: groups[g]["runner"][r] for g in go}
            thirds = [(groups[g]["third"][r], groups[g]["third_score"][r]) for g in go]
            best_thirds = [t for t, _ in sorted(thirds, key=lambda x: x[1], reverse=True)[:8]]

            # R32-Paarungen (identisch zu projection/resolver)
            pairs = []
            for i in range(0, 12, 2):
                gA, gB = go[i], go[i + 1]
                pairs.append((winners[gA], runners[gB]))
                pairs.append((runners[gA], winners[gB]))
            for i in range(0, len(best_thirds) - 1, 2):
                pairs.append((best_thirds[i], best_thirds[i + 1]))

            # R32-Teilnehmer
            for h, a in pairs:
                stage_counts[h]["round_of_32"] += 1
                stage_counts[a]["round_of_32"] += 1

            # Runden durchspielen
            current = pairs
            for stage in KO_STAGES[1:] + ["champion"]:
                winners_round = []
                for h, a in current:
                    w = self._ko_winner(h, a, stage if stage != "champion" else "final")
                    winners_round.append(w)
                    if stage == "champion":
                        champion_counts[w] += 1
                        stage_counts[w]["champion"] += 1
                    else:
                        stage_counts[w][stage] += 1
                if stage == "champion":
                    break
                current = [(winners_round[i], winners_round[i + 1])
                           for i in range(0, len(winners_round) - 1, 2)]

        champion_probs = {t: round(c / n_runs, 5) for t, c in champion_counts.items() if c}
        stage_probs = {
            t: {s: round(cnt / n_runs, 5) for s, cnt in sc.items() if cnt}
            for t, sc in stage_counts.items()
            if any(sc.values())
        }
        for t in stage_probs:
            stage_probs[t]["group_stage"] = 1.0

        return {"n_runs": n_runs, "champion_probs": champion_probs, "stage_probs": stage_probs}
