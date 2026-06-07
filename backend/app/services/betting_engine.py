"""
Betting Decision Engine (BDE) — Prognosen → strukturierte Wett-Empfehlungen.

  1. Liest ausschliesslich aus der Prediction Engine (keine eigene W-Berechnung)
  2. Vollständig zustandslos: gleiche Eingabe → gleiche Ausgabe
  3. Quoten optional: ohne Eingabe werden faire Buchmacher-Quoten geschätzt
Märkte: 1X2, Over/Under 2.5, BTTS, Correct Score.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict as _asdict
from typing import Optional

EV_RECOMMEND   = 0.02
EV_VALUE_BET   = 0.05
PROB_SAFE      = 0.60
BM_MARGIN_1X2  = 0.05
BM_MARGIN_CS   = 0.12
OU_LINE        = 2.5


@dataclass
class BetOption:
    market:         str
    selection:      str
    probability:    float
    odds:           float
    implied_prob:   float
    ev:             float
    ev_label:       str
    confidence:     str
    risk:           str
    rationale:      str
    is_value:       bool
    odds_estimated: bool
    market_prob:    float = 0.0
    edge:           float = 0.0
    recommendation: str = "NEUTRAL"   # "VALUE" | "SAFE" | "NO_BET" | "NEUTRAL"


@dataclass
class BettingReport:
    match_id:         str
    home_name:        str
    away_name:        str
    best_bet:         Optional[BetOption]  = None
    safe_bet:         Optional[BetOption]  = None
    value_bets:       list[BetOption]      = field(default_factory=list)
    no_bets:          list[BetOption]      = field(default_factory=list)
    scoreline_tip:    Optional[str]        = None
    all_options:      list[BetOption]      = field(default_factory=list)
    model_confidence: str                  = "MEDIUM"
    ev_calculable:    bool                 = True
    disclaimer: str = (
        "Empfehlungen basieren auf einem statistischen Modell. "
        "Quoten ohne explizite Eingabe sind Modell-Schätzungen (≠ echte Buchmacher-Quoten). "
        "Kein Anspruch auf Richtigkeit oder Vollständigkeit."
    )


def compute_ev(probability: float, odds: float) -> float:
    return round(probability * odds - 1.0, 4)


def implied_prob(odds: float) -> float:
    return round(1.0 / max(odds, 1.01), 4)


def compute_edge(model_prob: float, market_prob: float) -> float:
    """Edge = Modell-WS − overround-bereinigte Markt-WS."""
    return round(model_prob - market_prob, 4)


def rank_bets_by_ev(options: list["BetOption"]) -> list["BetOption"]:
    return sorted(options, key=lambda o: o.ev, reverse=True)


def fair_odds(probability: float, margin: float = BM_MARGIN_1X2) -> float:
    if probability <= 0.001:
        return 99.0
    if probability >= 0.999:
        return 1.01
    fair = 1.0 / probability
    bm   = fair * (1.0 - margin / 3.0)
    return round(max(bm, 1.01), 2)


def classify_confidence(prob: float) -> str:
    if prob >= 0.70:  return "HIGH"
    if prob >= 0.55:  return "MEDIUM"
    return "LOW"


def classify_risk(prob: float, ev: float, dispersion: float) -> str:
    if prob >= 0.65 and dispersion < 0.85:
        return "LOW"
    if prob >= 0.45:
        return "MEDIUM"
    return "HIGH"


def score_dispersion(dist: dict[str, float]) -> float:
    hhi = sum(p * p for p in dist.values())
    return round(1.0 - hhi, 4)


def _make_option(market, selection, prob, odds_in, rationale,
                 disp=0.5, margin=BM_MARGIN_1X2, market_prob=None) -> BetOption:
    estimated = odds_in is None
    odds      = odds_in if odds_in else fair_odds(prob, margin)
    ev        = compute_ev(prob, odds)
    imp       = implied_prob(odds)
    mkt_prob  = market_prob if market_prob is not None else imp
    edge      = compute_edge(prob, mkt_prob)
    if ev < 0 or edge < 0:
        rec = "NO_BET"
    elif ev >= EV_RECOMMEND and edge > 0:
        rec = "VALUE"
    elif prob >= PROB_SAFE:
        rec = "SAFE"
    else:
        rec = "NEUTRAL"
    return BetOption(
        market=market, selection=selection, probability=round(prob, 4),
        odds=odds, implied_prob=imp, ev=ev, ev_label=f"{ev * 100:+.1f}%",
        confidence=classify_confidence(prob), risk=classify_risk(prob, ev, disp),
        rationale=rationale, is_value=(ev >= EV_RECOMMEND), odds_estimated=estimated,
        market_prob=round(mkt_prob, 4), edge=edge, recommendation=rec,
    )


def generate_report(
    match_id: str, home_name: str, away_name: str,
    prob_home: float, prob_draw: float, prob_away: float,
    xg_home: float, xg_away: float,
    score_dist: dict[str, float], top_scores: list[dict],
    odds_home: float | None = None, odds_draw: float | None = None,
    odds_away: float | None = None, odds_over25: float | None = None,
    odds_under25: float | None = None, odds_btts_yes: float | None = None,
) -> BettingReport:
    disp     = score_dispersion(score_dist)
    total_xg = xg_home + xg_away
    options: list[BetOption] = []

    from app.services.odds_normalizer import normalize_list

    def _normalize(*odds_vals):
        if any(o is None for o in odds_vals):
            return None
        return normalize_list(list(odds_vals))

    mkt_1x2 = _normalize(odds_home, odds_draw, odds_away)
    mp_home, mp_draw, mp_away = (mkt_1x2 if mkt_1x2 else (None, None, None))
    mkt_ou = _normalize(odds_over25, odds_under25)
    mp_over, mp_under = (mkt_ou if mkt_ou else (None, None))

    options.append(_make_option(
        "1X2", f"Heimsieg ({home_name})", prob_home, odds_home,
        (f"Modell: {home_name} {prob_home:.0%} Sieg. xG {xg_home:.2f}:{xg_away:.2f} → "
         f"{'Klarer Favorit.' if prob_home > 0.55 else 'Ausgeglichenes Spiel.'}"),
        disp, market_prob=mp_home))
    options.append(_make_option(
        "1X2", "Unentschieden", prob_draw, odds_draw,
        (f"Unentschieden-WS {prob_draw:.0%}. xG-Differenz {abs(xg_home - xg_away):.2f} — "
         f"{'Sehr ausgeglichen.' if abs(xg_home - xg_away) < 0.3 else 'Leichter Favorit erwartet.'}"),
        disp, market_prob=mp_draw))
    options.append(_make_option(
        "1X2", f"Auswärtssieg ({away_name})", prob_away, odds_away,
        f"Modell: {away_name} {prob_away:.0%} Sieg. xG {xg_home:.2f}:{xg_away:.2f}.",
        disp, market_prob=mp_away))

    p_over25 = sum(p for k, p in score_dist.items()
                   if sum(int(x) for x in k.split(":")) > OU_LINE)
    p_under25 = 1.0 - p_over25
    scoring_note = ("Hohes Scoring-Spiel (xG > 2.8)." if total_xg > 2.8
                    else "Defensives Spiel (xG < 2.2)." if total_xg < 2.2
                    else "Moderates Scoring-Niveau.")
    options.append(_make_option("Over/Under", "Over 2.5 Tore", p_over25, odds_over25,
                                f"Gesamt-xG {total_xg:.2f}. {scoring_note}", disp, market_prob=mp_over))
    options.append(_make_option("Over/Under", "Under 2.5 Tore", p_under25, odds_under25,
                                f"Gesamt-xG {total_xg:.2f}. {scoring_note}", disp, market_prob=mp_under))

    p_btts = sum(p for k, p in score_dist.items()
                 if int(k.split(":")[0]) >= 1 and int(k.split(":")[1]) >= 1)
    options.append(_make_option("BTTS", "Beide Teams treffen — Ja", p_btts, odds_btts_yes,
                                (f"Beide Teams treffen in {p_btts:.0%} der Simulationen. "
                                 f"xG-Heimteam {xg_home:.2f}, Auswärts {xg_away:.2f}."), disp))
    options.append(_make_option("BTTS", "Beide Teams treffen — Nein", 1.0 - p_btts, None,
                                f"Clean-Sheet-Chance {1 - p_btts:.0%}.", disp))

    for entry in (top_scores or [])[:3]:
        score = entry.get("score", "")
        prob  = float(entry.get("prob", 0.0))
        cs_odds = round((1.0 / max(prob, 0.01)) * (1.0 - BM_MARGIN_CS), 2)
        options.append(_make_option("Correct Score", score, prob, cs_odds,
                                    f"Scoreline {score}: {prob:.1%} Modell-WS (Poisson). "
                                    f"Quote mit {BM_MARGIN_CS:.0%} Buchmacher-Marge geschätzt.",
                                    disp, margin=BM_MARGIN_CS))

    non_cs = [o for o in options if o.market != "Correct Score"]
    ev_sorted = sorted(non_cs, key=lambda o: o.ev, reverse=True)
    best_bet = ev_sorted[0] if ev_sorted else None

    safe_candidates = sorted(
        [o for o in non_cs if o.probability >= PROB_SAFE and o.risk in ("LOW", "MEDIUM")],
        key=lambda o: o.probability, reverse=True)
    safe_bet = safe_candidates[0] if safe_candidates else None

    value_bets = sorted([o for o in non_cs if o.is_value], key=lambda o: o.ev, reverse=True)[:3]
    no_bets = sorted([o for o in non_cs if o.recommendation == "NO_BET"], key=lambda o: o.ev)

    scoreline_tip = top_scores[0]["score"] if top_scores else None
    model_conf = "HIGH" if disp < 0.80 else "MEDIUM" if disp < 0.90 else "LOW"
    ev_calculable = any(x is not None for x in
                        [odds_home, odds_draw, odds_away, odds_over25, odds_btts_yes])

    return BettingReport(
        match_id=match_id, home_name=home_name, away_name=away_name,
        best_bet=best_bet, safe_bet=safe_bet, value_bets=value_bets, no_bets=no_bets,
        scoreline_tip=scoreline_tip, all_options=options,
        model_confidence=model_conf, ev_calculable=ev_calculable,
    )


def report_to_dict(report: BettingReport) -> dict:
    return _asdict(report)


async def generate_betting_recommendations(
    match_id: str, db, odds: Optional[dict[str, float]] = None,
) -> Optional[BettingReport]:
    """Async-Wrapper: lädt Match + neueste Prognose, ruft generate_report() auf."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.match import Match

    q = await db.execute(
        select(Match).options(
            selectinload(Match.home_team), selectinload(Match.away_team),
            selectinload(Match.predictions),
        ).where(Match.id == match_id)
    )
    match = q.scalar_one_or_none()
    if not match:
        return None

    home = match.home_team.name if match.home_team else "Heim"
    away = match.away_team.name if match.away_team else "Auswärts"
    # Odds-Matching über ENGLISCHE Namen (Odds-API englisch, DB-Anzeige deutsch).
    home_en = (getattr(match.home_team, "home_country", None) or home)
    away_en = (getattr(match.away_team, "home_country", None) or away)

    if not match.predictions:
        return BettingReport(match_id=match_id, home_name=home, away_name=away, ev_calculable=False)

    pred = sorted(match.predictions, key=lambda p: p.predicted_at, reverse=True)[0]
    odds = dict(odds or {})

    if not odds:
        try:
            from app.services.odds_provider import find_match_odds
            real = find_match_odds(home_en, away_en)
            if real:
                if real.get("home"):    odds["1X2:HOME"] = real["home"]
                if real.get("draw"):    odds["1X2:DRAW"] = real["draw"]
                if real.get("away"):    odds["1X2:AWAY"] = real["away"]
                if real.get("over25"):  odds["OVER_UNDER_2.5:OVER"] = real["over25"]
                if real.get("under25"): odds["OVER_UNDER_2.5:UNDER"] = real["under25"]
        except Exception:
            pass

    return generate_report(
        match_id=match_id, home_name=home, away_name=away,
        prob_home=pred.prob_home_win, prob_draw=pred.prob_draw, prob_away=pred.prob_away_win,
        xg_home=pred.xg_home, xg_away=pred.xg_away,
        score_dist=pred.score_distribution or {}, top_scores=pred.top_scorelines or [],
        odds_home=odds.get("1X2:HOME"), odds_draw=odds.get("1X2:DRAW"),
        odds_away=odds.get("1X2:AWAY"), odds_over25=odds.get("OVER_UNDER_2.5:OVER"),
        odds_under25=odds.get("OVER_UNDER_2.5:UNDER"), odds_btts_yes=odds.get("BTTS:YES"),
    )
