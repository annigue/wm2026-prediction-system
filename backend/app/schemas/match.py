from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel
from app.schemas.team import TeamSummary


class VenueOut(BaseModel):
    name: str
    city: Optional[str] = None
    country: Optional[str] = None
    altitude_m: int = 0
    model_config = {"from_attributes": True}


class PredictionSummary(BaseModel):
    prob_home_win: float
    prob_draw: float
    prob_away_win: float
    xg_home: float
    xg_away: float
    model_version: Optional[str] = None
    top_scoreline: Optional[str] = None
    # Offizielle (markt-kalibrierte) Prognose, damit Listen/Tipps dieselbe EINE Prognose
    # zeigen wie die Detailseite (sonst weicht der xG-gerundete Tipp ab).
    official: Optional[dict[str, Any]] = None


class PredictionDetail(PredictionSummary):
    predicted_at: Optional[datetime] = None
    top_scorelines: Optional[list[dict]] = None
    score_distribution: Optional[dict[str, float]] = None
    explanation: Optional[dict[str, Any]] = None
    home_elo_at_prediction: Optional[float] = None
    away_elo_at_prediction: Optional[float] = None
    model_config = {"from_attributes": True}


class ResultOut(BaseModel):
    home_goals: int
    away_goals: int
    home_goals_ht: Optional[int] = None
    away_goals_ht: Optional[int] = None
    went_to_extra_time: bool = False
    went_to_penalties: bool = False
    model_config = {"from_attributes": True}


class MatchSummary(BaseModel):
    id: str
    stage: str
    group_id: Optional[str] = None
    home_team: Optional[TeamSummary] = None
    away_team: Optional[TeamSummary] = None
    kickoff_utc: Optional[datetime] = None
    status: Optional[str] = None
    prediction: Optional[PredictionSummary] = None
    result: Optional[ResultOut] = None
    model_config = {"from_attributes": True}


class MatchDetail(MatchSummary):
    venue: Optional[VenueOut] = None
    prediction: Optional[PredictionDetail] = None
    model_config = {"from_attributes": True}


class ResultCreate(BaseModel):
    home_goals: int
    away_goals: int
    home_goals_ht: Optional[int] = None
    away_goals_ht: Optional[int] = None
    went_to_extra_time: bool = False
    went_to_penalties: bool = False
