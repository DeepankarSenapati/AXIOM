"""Closed polls and chronological quarter transitions must remain coherent."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from backend.db.models import DBSatisfactionPoll
from backend.governance.models import GovernanceStage, PollResult, VoteSubmission
from backend.governance.stages import StageManager
from backend.governance.voting import PollAlreadyClosedError, VotingManager


def test_closed_poll_cannot_accept_a_late_vote(db_session, seeded_bot: str) -> None:
    manager = VotingManager(db_session)
    manager.submit_vote(VoteSubmission(
        bot_id=seeded_bot, quarter="2026-Q1", voter_address="first@example.test",
        vote="unsatisfied", token_weight=100,
    ))
    closed = manager.close_poll(seeded_bot, "2026-Q1", current_stage=1)

    with pytest.raises(PollAlreadyClosedError):
        manager.submit_vote(VoteSubmission(
            bot_id=seeded_bot, quarter="2026-Q1", voter_address="late@example.test",
            vote="satisfied", token_weight=1_000,
        ))

    history = manager.get_poll_history(seeded_bot)
    assert len(history) == 1
    assert history[0].vote_count == closed.vote_count == 1
    assert history[0].satisfaction_rate == closed.satisfaction_rate == 0.0
    assert history[0].total_weight == closed.total_weight == 100


def failed_poll(quarter: str) -> PollResult:
    return PollResult(
        bot_id="bot", quarter=quarter, satisfaction_rate=0.25,
        satisfied_weight=25, total_weight=100, stage_at_close=1,
        closed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def stage_for(*quarters: str) -> GovernanceStage:
    voting = MagicMock()
    voting.get_poll_history.return_value = [failed_poll(quarter) for quarter in quarters]
    return StageManager(db=MagicMock(), voting_manager=voting).get_current_stage("bot")


def test_a_missing_quarter_breaks_the_failed_streak() -> None:
    assert stage_for("2026-Q1", "2026-Q3") == GovernanceStage.NORMAL
    assert stage_for("2025-Q3", "2025-Q4", "2026-Q2", "2026-Q3") == GovernanceStage.REVIEW


def test_end_of_year_quarters_are_consecutive() -> None:
    assert stage_for("2025-Q4", "2026-Q1") == GovernanceStage.REVIEW
    assert stage_for("2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2") == GovernanceStage.COMMUNITY


def test_legacy_empty_poll_breaks_streak_without_rewriting_history(db_session, seeded_bot: str) -> None:
    for quarter, weight, rate in [("2026-Q1", 100, 0.25), ("2026-Q2", 0, 0.0), ("2026-Q3", 100, 0.25)]:
        db_session.add(DBSatisfactionPoll(
            bot_id=seeded_bot, quarter=quarter, satisfied_weight=weight * rate,
            total_weight=weight, satisfaction_rate=rate, stage_at_close=1,
            closed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ))
    db_session.commit()

    manager = StageManager(db_session, VotingManager(db_session))
    assert manager.get_current_stage(seeded_bot) == GovernanceStage.NORMAL
    db_session.expire_all()
    preserved = db_session.query(DBSatisfactionPoll).filter_by(bot_id=seeded_bot, quarter="2026-Q2").one()
    assert preserved.total_weight == 0 and preserved.satisfaction_rate == 0.0
