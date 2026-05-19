from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db.models import DBGovernanceVote, DBSatisfactionPoll
from backend.governance.models import PollResult, VoteSubmission


class DuplicateVoteError(Exception):
    pass


class PollAlreadyClosedError(Exception):
    pass


class VotingManager:
    def __init__(self, db: Session) -> None:
        self.db = db

    def submit_vote(self, submission: VoteSubmission) -> None:
        existing = (
            self.db.query(DBGovernanceVote)
            .filter(
                DBGovernanceVote.bot_id == submission.bot_id,
                DBGovernanceVote.quarter == submission.quarter,
                DBGovernanceVote.voter_address == submission.voter_address,
            )
            .first()
        )
        if existing is not None:
            raise DuplicateVoteError(
                f"Voter '{submission.voter_address}' already voted for bot "
                f"'{submission.bot_id}' in quarter '{submission.quarter}'"
            )

        self.db.add(
            DBGovernanceVote(
                bot_id=submission.bot_id,
                quarter=submission.quarter,
                voter_address=submission.voter_address,
                vote=submission.vote,
                timestamp=datetime.now(tz=timezone.utc),
                token_weight=submission.token_weight,
            )
        )
        self.db.commit()

    def close_poll(self, bot_id: str, quarter: str, current_stage: int) -> PollResult:
        already_closed = (
            self.db.query(DBSatisfactionPoll)
            .filter(
                DBSatisfactionPoll.bot_id == bot_id,
                DBSatisfactionPoll.quarter == quarter,
            )
            .first()
        )
        if already_closed is not None:
            raise PollAlreadyClosedError(
                f"Poll for bot '{bot_id}' quarter '{quarter}' is already closed"
            )

        votes = (
            self.db.query(DBGovernanceVote)
            .filter(
                DBGovernanceVote.bot_id == bot_id,
                DBGovernanceVote.quarter == quarter,
            )
            .all()
        )

        total_weight = sum(v.token_weight for v in votes)
        satisfied_weight = sum(v.token_weight for v in votes if v.vote == "satisfied")
        satisfaction_rate = (satisfied_weight / total_weight) if total_weight > 0 else 0.0
        closed_at = datetime.now(tz=timezone.utc)

        self.db.add(
            DBSatisfactionPoll(
                bot_id=bot_id,
                quarter=quarter,
                satisfied_weight=satisfied_weight,
                total_weight=total_weight,
                satisfaction_rate=satisfaction_rate,
                stage_at_close=current_stage,
                closed_at=closed_at,
            )
        )
        self.db.commit()

        return PollResult(
            bot_id=bot_id,
            quarter=quarter,
            satisfaction_rate=satisfaction_rate,
            satisfied_weight=satisfied_weight,
            total_weight=total_weight,
            stage_at_close=current_stage,
            closed_at=closed_at,
            vote_count=len(votes),
        )

    def get_poll_history(self, bot_id: str) -> list[PollResult]:
        rows = (
            self.db.query(DBSatisfactionPoll)
            .filter(DBSatisfactionPoll.bot_id == bot_id)
            .order_by(DBSatisfactionPoll.quarter.asc())
            .all()
        )
        vote_counts: dict[str, int] = dict(
            self.db.query(DBGovernanceVote.quarter, func.count(DBGovernanceVote.id))
            .filter(DBGovernanceVote.bot_id == bot_id)
            .group_by(DBGovernanceVote.quarter)
            .all()
        )
        return [
            PollResult(
                bot_id=row.bot_id,
                quarter=row.quarter,
                satisfaction_rate=row.satisfaction_rate,
                satisfied_weight=row.satisfied_weight,
                total_weight=row.total_weight,
                stage_at_close=row.stage_at_close,
                closed_at=row.closed_at,
                vote_count=vote_counts.get(row.quarter, 0),
            )
            for row in rows
        ]
