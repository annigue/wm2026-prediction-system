"""Elo Rating System für Nationalmannschaften."""


class EloModel:
    SCALE = 400.0   # Standard-Skalierungsfaktor
    K     = 32.0    # Standard K-Faktor (Länderspiele)
    K_WC  = 20.0    # Konservativerer K während des Turniers

    @staticmethod
    def expected_score(rating_a: float, rating_b: float) -> float:
        """Erwarteter Ausgang für Team A gegen Team B (0–1)."""
        return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / EloModel.SCALE))

    @staticmethod
    def goal_diff_multiplier(n: int) -> float:
        """Gewichtung nach Tordifferenz (aus FIFA/ELO-Ratings Konvention)."""
        if n <= 1:    return 1.00
        elif n == 2:  return 1.50
        elif n == 3:  return 1.75
        else:         return min(1.75 + (n - 3) / 8.0, 2.50)

    @classmethod
    def update(cls, rating: float, actual: float, expected: float,
               k: float = 32.0, goal_diff: int = 1) -> float:
        """Neuer Elo-Wert nach einem Spiel.
        actual: 1.0=Sieg, 0.5=Unentschieden, 0.0=Niederlage
        """
        mult = cls.goal_diff_multiplier(goal_diff)
        return rating + k * mult * (actual - expected)

    @classmethod
    def update_both(
        cls,
        rating_a: float,
        rating_b: float,
        goals_a: int,
        goals_b: int,
        k: float = 32.0,
    ) -> tuple[float, float]:
        """Beide Elo-Werte nach einem Spiel aktualisieren."""
        if goals_a > goals_b:
            actual_a, actual_b = 1.0, 0.0
        elif goals_a < goals_b:
            actual_a, actual_b = 0.0, 1.0
        else:
            actual_a, actual_b = 0.5, 0.5

        expected_a = cls.expected_score(rating_a, rating_b)
        expected_b = 1.0 - expected_a
        goal_diff  = abs(goals_a - goals_b)

        new_a = cls.update(rating_a, actual_a, expected_a, k, goal_diff)
        new_b = cls.update(rating_b, actual_b, expected_b, k, goal_diff)
        return round(new_a, 2), round(new_b, 2)
