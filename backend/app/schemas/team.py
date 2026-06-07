from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class TeamFeatureOut(BaseModel):
    elo_rating: float
    fifa_ranking: Optional[int] = None
    market_value_millions: Optional[float] = None
    avg_squad_age: Optional[float] = None
    avg_caps_per_player: Optional[float] = None
    form_score: Optional[float] = None
    form_goals_scored_avg: Optional[float] = None
    form_goals_conceded_avg: Optional[float] = None
    snapshot_date: Optional[date] = None
    model_config = {"from_attributes": True}


class EloRatingOut(BaseModel):
    rating: float
    reason: Optional[str] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class TournamentProbsOut(BaseModel):
    group_stage: float = 1.0
    round_of_32: Optional[float] = None
    round_of_16: Optional[float] = None
    quarterfinal: Optional[float] = None
    semifinal: Optional[float] = None
    final: Optional[float] = None
    champion: Optional[float] = None


class TeamSummary(BaseModel):
    id: str
    name: str
    short_name: str
    flag_emoji: Optional[str] = None
    confederation: Optional[str] = None
    elo_rating: Optional[float] = None
    fifa_ranking: Optional[int] = None
    market_value_millions: Optional[float] = None
    avg_squad_age: Optional[float] = None
    form_score: Optional[float] = None
    champion_probability: Optional[float] = None
    model_config = {"from_attributes": True}


class TeamDetail(BaseModel):
    id: str
    name: str
    short_name: str
    flag_emoji: Optional[str] = None
    confederation: Optional[str] = None
    home_country: Optional[str] = None
    features: Optional[TeamFeatureOut] = None
    elo_history: list[EloRatingOut] = []
    tournament_probs: Optional[TournamentProbsOut] = None
    group_id: Optional[str] = None
    model_config = {"from_attributes": True}
