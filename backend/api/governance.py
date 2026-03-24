from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.models import (
    ClosePollRequest,
    PollResultResponse,
    StageResponse,
    StageTransitionResponse,
    SubmitVoteRequest,
)
from backend.db.models import DBBot
from backend.db.session import get_db
from backend.governance.models import GovernanceStage, VoteSubmission
from backend.governance.stages import StageManager
from backend.governance.voting import DuplicateVoteError, PollAlreadyClosedError, VotingManager

router = APIRouter(prefix="/governance", tags=["governance"])

_STAGE_NAMES: dict[int, str] = {
    GovernanceStage.NORMAL: "Normal",
    GovernanceStage.REVIEW: "Review",
    GovernanceStage.COMMUNITY: "Community",
}


def _get_bot(bot_id: str, db: Session) -> DBBot:
    bot = db.query(DBBot).filter(DBBot.id == bot_id).first()
    if bot is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")
    return bot


@router.post("/vote", status_code=204)
def submit_vote(payload: SubmitVoteRequest, db: Session = Depends(get_db)) -> None:
    _get_bot(payload.bot_id, db)
    manager = VotingManager(db)
    submission = VoteSubmission(
        bot_id=payload.bot_id,
        quarter=payload.quarter,
        voter_address=payload.voter_address,
        vote=payload.vote,
        token_weight=payload.token_weight,
    )
    try:
        manager.submit_vote(submission)
    except DuplicateVoteError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/poll/close", response_model=PollResultResponse)
def close_poll(payload: ClosePollRequest, db: Session = Depends(get_db)) -> PollResultResponse:
    _get_bot(payload.bot_id, db)
    voting = VotingManager(db)
    stage_mgr = StageManager(db, voting)
    current_stage = int(stage_mgr.get_current_stage(payload.bot_id))

    try:
        result = voting.close_poll(payload.bot_id, payload.quarter, current_stage)
    except PollAlreadyClosedError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    return PollResultResponse(
        bot_id=result.bot_id,
        quarter=result.quarter,
        satisfaction_rate=result.satisfaction_rate,
        satisfied_weight=result.satisfied_weight,
        total_weight=result.total_weight,
        stage_at_close=result.stage_at_close,
        closed_at=result.closed_at,
    )


@router.get("/{bot_id}/stage", response_model=StageResponse)
def get_stage(bot_id: str, db: Session = Depends(get_db)) -> StageResponse:
    _get_bot(bot_id, db)
    voting = VotingManager(db)
    stage_mgr = StageManager(db, voting)
    stage = stage_mgr.get_current_stage(bot_id)
    return StageResponse(
        bot_id=bot_id,
        current_stage=int(stage),
        stage_name=_STAGE_NAMES[stage],
    )


@router.get("/{bot_id}/stage/transition", response_model=StageTransitionResponse | None)
def evaluate_transition(
    bot_id: str, db: Session = Depends(get_db)
) -> StageTransitionResponse | None:
    _get_bot(bot_id, db)
    voting = VotingManager(db)
    stage_mgr = StageManager(db, voting)
    event = stage_mgr.evaluate_transition(bot_id)
    if event is None:
        return None
    return StageTransitionResponse(
        bot_id=event.bot_id,
        from_stage=event.from_stage,
        to_stage=event.to_stage,
        triggered_by=event.triggered_by,
        timestamp=event.timestamp,
    )


@router.get("/{bot_id}/polls", response_model=list[PollResultResponse])
def get_poll_history(bot_id: str, db: Session = Depends(get_db)) -> list[PollResultResponse]:
    _get_bot(bot_id, db)
    voting = VotingManager(db)
    polls = voting.get_poll_history(bot_id)
    return [
        PollResultResponse(
            bot_id=p.bot_id,
            quarter=p.quarter,
            satisfaction_rate=p.satisfaction_rate,
            satisfied_weight=p.satisfied_weight,
            total_weight=p.total_weight,
            stage_at_close=p.stage_at_close,
            closed_at=p.closed_at,
        )
        for p in polls
    ]
