from datetime import datetime
from enum import IntEnum
from typing import Literal

from pydantic import BaseModel


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


class VoteSubmission(BaseModel):
    bot_id: str
    quarter: str
    voter_address: str
    vote: Literal["satisfied", "unsatisfied"]
    token_weight: float


class StageTransitionEvent(BaseModel):
    bot_id: str
    from_stage: int
    to_stage: int
    triggered_by: str
    timestamp: datetime
