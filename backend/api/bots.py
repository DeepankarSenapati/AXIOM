import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.models import BotCreate, BotResponse
from backend.auth.dependencies import get_current_user
from backend.db.models import DBBot, DBUser
from backend.db.session import get_db

router = APIRouter(prefix="/bots", tags=["bots"])


class BotNotFoundError(Exception):
    pass


@router.post("/", response_model=BotResponse, status_code=201)
def create_bot(
    payload: BotCreate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
) -> BotResponse:
    bot = DBBot(
        id=str(uuid.uuid4()),
        name=payload.name,
        strategy_name=payload.strategy_key,
        params=dict(payload.params) if payload.params else None,
        created_at=datetime.now(tz=timezone.utc),
        is_active=False,
        status="pending_approval",
        tech_company_id=current_user.id,
        description=payload.description,
    )
    db.add(bot)
    db.commit()
    db.refresh(bot)
    return BotResponse(
        id=bot.id,
        name=bot.name,
        strategy_name=bot.strategy_name,
        created_at=bot.created_at,
        is_active=bot.is_active,
        status=bot.status,
        description=bot.description,
    )


@router.get("/", response_model=list[BotResponse])
def list_bots(db: Session = Depends(get_db)) -> list[BotResponse]:
    bots = db.query(DBBot).order_by(DBBot.created_at.desc()).all()
    return [
        BotResponse(
            id=b.id,
            name=b.name,
            strategy_name=b.strategy_name,
            created_at=b.created_at,
            is_active=b.is_active,
            status=b.status,
            description=b.description,
        )
        for b in bots
    ]


@router.get("/{bot_id}", response_model=BotResponse)
def get_bot(bot_id: str, db: Session = Depends(get_db)) -> BotResponse:
    bot = db.query(DBBot).filter(DBBot.id == bot_id).first()
    if bot is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")
    return BotResponse(
        id=bot.id,
        name=bot.name,
        strategy_name=bot.strategy_name,
        created_at=bot.created_at,
        is_active=bot.is_active,
        status=bot.status,
        description=bot.description,
    )


@router.delete("/{bot_id}", status_code=204)
def deactivate_bot(bot_id: str, db: Session = Depends(get_db)) -> None:
    bot = db.query(DBBot).filter(DBBot.id == bot_id).first()
    if bot is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")
    bot.is_active = False
    db.commit()
