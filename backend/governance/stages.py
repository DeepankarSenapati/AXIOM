import math
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.config import (
    STAGE2_CONSECUTIVE_QUARTERS,
    STAGE2_TRIGGER_THRESHOLD,
    STAGE3_CONSECUTIVE_QUARTERS,
)
from backend.governance.models import GovernanceStage, PollResult, StageTransitionEvent
from backend.governance.voting import VotingManager


class StageManager:
    def __init__(self, db: Session, voting_manager: VotingManager) -> None:
        self.db = db
        self.voting_manager = voting_manager

    def get_current_stage(self, bot_id: str) -> GovernanceStage:
        polls = self.voting_manager.get_poll_history(bot_id)
        if not polls:
            return GovernanceStage.NORMAL

        consecutive_below = self._trailing_below_polls(polls, STAGE2_TRIGGER_THRESHOLD)

        if consecutive_below >= STAGE3_CONSECUTIVE_QUARTERS:
            return GovernanceStage.COMMUNITY
        if consecutive_below >= STAGE2_CONSECUTIVE_QUARTERS:
            return GovernanceStage.REVIEW
        return GovernanceStage.NORMAL

    def evaluate_transition(self, bot_id: str) -> StageTransitionEvent | None:
        polls = self.voting_manager.get_poll_history(bot_id)
        if not polls:
            return None

        # Stage before the most recent poll
        prior_consecutive = self._trailing_below_polls(polls[:-1], STAGE2_TRIGGER_THRESHOLD)
        prior_stage = self._stage_from_consecutive(prior_consecutive)

        current_consecutive = self._trailing_below_polls(polls, STAGE2_TRIGGER_THRESHOLD)
        current_stage = self._stage_from_consecutive(current_consecutive)

        if current_stage == prior_stage:
            return None

        return StageTransitionEvent(
            bot_id=bot_id,
            from_stage=int(prior_stage),
            to_stage=int(current_stage),
            triggered_by=f"satisfaction_rate below {STAGE2_TRIGGER_THRESHOLD} "
            f"for {current_consecutive} consecutive quarters",
            timestamp=datetime.now(tz=timezone.utc),
        )

    @staticmethod
    def _trailing_below(rates: list[float], threshold: float) -> int:
        """Count how many trailing entries are below the threshold."""
        count = 0
        for rate in reversed(rates):
            if rate < threshold:
                count += 1
            else:
                break
        return count

    @staticmethod
    def _trailing_below_polls(polls: list[PollResult], threshold: float) -> int:
        """Count only adjacent, canonical quarters; a gap breaks the streak."""
        count = 0
        next_quarter: int | None = None
        for poll in reversed(polls):
            match = re.fullmatch(r"([0-9]{4})-Q([1-4])", poll.quarter)
            if (
                match is None
                or not math.isfinite(poll.total_weight)
                or poll.total_weight <= 0
                or not poll.satisfaction_rate < threshold
            ):
                break
            quarter = int(match.group(1)) * 4 + int(match.group(2))
            if next_quarter is not None and quarter + 1 != next_quarter:
                break
            count += 1
            next_quarter = quarter
        return count

    @staticmethod
    def _stage_from_consecutive(consecutive: int) -> GovernanceStage:
        if consecutive >= STAGE3_CONSECUTIVE_QUARTERS:
            return GovernanceStage.COMMUNITY
        if consecutive >= STAGE2_CONSECUTIVE_QUARTERS:
            return GovernanceStage.REVIEW
        return GovernanceStage.NORMAL
