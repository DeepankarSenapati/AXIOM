from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.config import (
    STAGE2_CONSECUTIVE_QUARTERS,
    STAGE2_TRIGGER_THRESHOLD,
    STAGE3_CONSECUTIVE_QUARTERS,
)
from backend.governance.models import GovernanceStage, StageTransitionEvent
from backend.governance.voting import VotingManager


class StageManager:
    def __init__(self, db: Session, voting_manager: VotingManager) -> None:
        self.db = db
        self.voting_manager = voting_manager

    def get_current_stage(self, bot_id: str) -> GovernanceStage:
        polls = self.voting_manager.get_poll_history(bot_id)
        if not polls:
            return GovernanceStage.NORMAL

        rates = [p.satisfaction_rate for p in polls]
        consecutive_below = self._trailing_below(rates, STAGE2_TRIGGER_THRESHOLD)

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
        prior_rates = [p.satisfaction_rate for p in polls[:-1]]
        prior_consecutive = self._trailing_below(prior_rates, STAGE2_TRIGGER_THRESHOLD)
        prior_stage = self._stage_from_consecutive(prior_consecutive)

        all_rates = [p.satisfaction_rate for p in polls]
        current_consecutive = self._trailing_below(all_rates, STAGE2_TRIGGER_THRESHOLD)
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
    def _stage_from_consecutive(consecutive: int) -> GovernanceStage:
        if consecutive >= STAGE3_CONSECUTIVE_QUARTERS:
            return GovernanceStage.COMMUNITY
        if consecutive >= STAGE2_CONSECUTIVE_QUARTERS:
            return GovernanceStage.REVIEW
        return GovernanceStage.NORMAL
