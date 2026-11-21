from datetime import datetime
from enum import IntEnum
from typing import Literal

from pydantic import BaseModel, Field


class GovernanceStage(IntEnum):
    NORMAL = 1
    REVIEW = 2
    COMMUNITY = 3


class PollResult(BaseModel):
    bot_id: str
    quarter: str
    satisfaction_rate: float
    satisfied_weight: float
    total_weight: float
    stage_at_close: int
    closed_at: datetime
    vote_count: int = 0


class VoteSubmission(BaseModel):
    bot_id: str
    quarter: str = Field(pattern=r"^[0-9]{4}-Q[1-4]$")
    voter_address: str
    vote: Literal["satisfied", "unsatisfied"]
    token_weight: float = Field(gt=0, allow_inf_nan=False)


class StageTransitionEvent(BaseModel):
    bot_id: str
    from_stage: int
    to_stage: int
    triggered_by: str
    timestamp: datetime
