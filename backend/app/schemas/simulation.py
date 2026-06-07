from typing import Optional
from pydantic import BaseModel


class StageProbsOut(BaseModel):
    group_stage: float = 1.0
    round_of_32: Optional[float] = None
    round_of_16: Optional[float] = None
    quarterfinal: Optional[float] = None
    semifinal: Optional[float] = None
    final: Optional[float] = None
    champion: Optional[float] = None


class SimulationResult(BaseModel):
    stage_probabilities: dict[str, StageProbsOut]
    model_config = {"from_attributes": True}


class GroupStandingEntry(BaseModel):
    team_id: str
    team_name: str
    flag_emoji: Optional[str] = None
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0
    qualification_probability: Optional[float] = None
    win_group_probability: Optional[float] = None


class GroupOut(BaseModel):
    id: str
    name: str
    teams: list[GroupStandingEntry] = []
