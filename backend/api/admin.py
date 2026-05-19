"""Admin-only endpoints for platform management."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.api.models import AdminBotResponse, PlatformRevenueResponse, PlatformStatsResponse, UserResponse
from backend.auth.dependencies import require_role
from backend.db.models import DBBacktestRun, DBBot, DBDistributionEvent, DBUser
from backend.db.session import get_db

router = APIRouter(prefix="/admin", tags=["admin"])
_admin = require_role("admin")


@router.get("/stats", response_model=PlatformStatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    _: DBUser = Depends(_admin),
) -> PlatformStatsResponse:
    bots = db.query(DBBot).all()
    users = db.query(DBUser).all()
    runs = db.query(DBBacktestRun).count()
    users_by_role: dict[str, int] = {}
    for u in users:
        users_by_role[u.role] = users_by_role.get(u.role, 0) + 1
    return PlatformStatsResponse(
        total_bots=len(bots),
        pending_approval=sum(1 for b in bots if b.status == "pending_approval"),
        total_users=len(users),
        users_by_role=users_by_role,
        total_backtest_runs=runs,
    )


@router.get("/bots", response_model=list[AdminBotResponse])
def list_all_bots(
    db: Session = Depends(get_db),
    _: DBUser = Depends(_admin),
) -> list[AdminBotResponse]:
    bots = db.query(DBBot).order_by(DBBot.created_at.desc()).all()
    return [
        AdminBotResponse(
            id=b.id,
            name=b.name,
            strategy_name=b.strategy_name,
            status=b.status,
            tech_company_id=b.tech_company_id,
            description=b.description,
            created_at=b.created_at,
            is_active=b.is_active,
        )
        for b in bots
    ]


@router.post("/bots/{bot_id}/approve", response_model=AdminBotResponse)
def approve_bot(
    bot_id: str,
    db: Session = Depends(get_db),
    _: DBUser = Depends(_admin),
) -> AdminBotResponse:
    bot = db.query(DBBot).filter(DBBot.id == bot_id).first()
    if bot is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")
    bot.status = "approved"
    bot.is_active = True
    db.commit()
    db.refresh(bot)
    return AdminBotResponse(
        id=bot.id,
        name=bot.name,
        strategy_name=bot.strategy_name,
        status=bot.status,
        tech_company_id=bot.tech_company_id,
        description=bot.description,
        created_at=bot.created_at,
        is_active=bot.is_active,
    )


@router.post("/bots/{bot_id}/reject", response_model=AdminBotResponse)
def reject_bot(
    bot_id: str,
    db: Session = Depends(get_db),
    _: DBUser = Depends(_admin),
) -> AdminBotResponse:
    bot = db.query(DBBot).filter(DBBot.id == bot_id).first()
    if bot is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")
    bot.status = "rejected"
    bot.is_active = False
    db.commit()
    db.refresh(bot)
    return AdminBotResponse(
        id=bot.id,
        name=bot.name,
        strategy_name=bot.strategy_name,
        status=bot.status,
        tech_company_id=bot.tech_company_id,
        description=bot.description,
        created_at=bot.created_at,
        is_active=bot.is_active,
    )


@router.get("/platform-revenue", response_model=PlatformRevenueResponse)
def get_platform_revenue(
    db: Session = Depends(get_db),
    _: DBUser = Depends(_admin),
) -> PlatformRevenueResponse:
    result = db.query(
        func.coalesce(func.sum(DBDistributionEvent.platform_fee), 0.0).label("total_fees"),
        func.count(DBDistributionEvent.id).label("event_count"),
    ).one()
    return PlatformRevenueResponse(
        total_fees_collected=round(float(result.total_fees), 4),
        event_count=int(result.event_count),
    )


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _: DBUser = Depends(_admin),
) -> list[UserResponse]:
    users = db.query(DBUser).order_by(DBUser.created_at.desc()).all()
    return [
        UserResponse(
            id=u.id,
            email=u.email,
            role=u.role,
            company_name=u.company_name,
            wallet_balance=u.wallet_balance,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in users
    ]
