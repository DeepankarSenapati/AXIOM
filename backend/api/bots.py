import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.api.models import (
    BotBacktestSummary,
    BotCreate,
    BotProfileResponse,
    BotResponse,
    BotTokenDistribution,
)
from backend.auth.dependencies import get_current_user, require_role
from backend.db.models import DBBacktestRun, DBBot, DBToken, DBUser
from backend.db.session import get_db

router = APIRouter(prefix="/bots", tags=["bots"])


class BotNotFoundError(Exception):
    pass


@router.post("/", response_model=BotResponse, status_code=201)
def create_bot(
    payload: BotCreate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(require_role("admin", "tech_company")),
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
def deactivate_bot(
    bot_id: str,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
) -> None:
    bot = db.query(DBBot).filter(DBBot.id == bot_id).first()
    if bot is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")
    if current_user.role != "admin" and not (
        current_user.role == "tech_company" and bot.tech_company_id == current_user.id
    ):
        raise HTTPException(status_code=403, detail="Only the owner or an admin can deactivate this bot.")
    bot.is_active = False
    db.commit()


_SYSTEM_WALLETS = ("public_pool", "tech_wallet", "gov_wallet")


def _compute_risk_rating(avg_sharpe: float | None, avg_drawdown: float | None, run_count: int) -> str:
    """Return a historical heuristic, using drawdown magnitude rather than its sign."""
    if run_count == 0 or avg_sharpe is None or avg_drawdown is None:
        return "Unrated"
    drawdown_magnitude = abs(avg_drawdown)
    if avg_sharpe >= 1.0 and drawdown_magnitude <= 0.15:
        return "Low"
    if avg_sharpe >= 0.3 and drawdown_magnitude <= 0.30:
        return "Medium"
    return "High"


@router.get("/{bot_id}/profile", response_model=BotProfileResponse)
def get_bot_profile(bot_id: str, db: Session = Depends(get_db)) -> BotProfileResponse:
    bot = db.query(DBBot).filter(DBBot.id == bot_id).first()
    if bot is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")

    # Tech company name
    tech_company_name: str | None = None
    if bot.tech_company_id:
        owner = db.query(DBUser).filter(DBUser.id == bot.tech_company_id).first()
        if owner:
            tech_company_name = owner.company_name or owner.email

    # Token distribution
    token_rows = db.query(DBToken).filter(DBToken.bot_id == bot_id).all()
    token_distribution: BotTokenDistribution | None = None
    if token_rows:
        public_pool = sum(r.balance for r in token_rows if r.holder_address == "public_pool")
        tech_holdings = sum(r.balance for r in token_rows if r.holder_address == "tech_wallet")
        gov_holdings = sum(r.balance for r in token_rows if r.holder_address == "gov_wallet")
        investor_rows = [r for r in token_rows if r.holder_address not in _SYSTEM_WALLETS]
        investor_holdings = sum(r.balance for r in investor_rows)
        total = public_pool + tech_holdings + gov_holdings + investor_holdings
        token_distribution = BotTokenDistribution(
            public_pool_remaining=public_pool,
            investor_holdings=investor_holdings,
            tech_holdings=tech_holdings,
            gov_holdings=gov_holdings,
            total=total,
            investor_count=len(investor_rows),
        )

    # Backtest aggregates
    agg = (
        db.query(
            func.count(DBBacktestRun.id).label("run_count"),
            func.avg(DBBacktestRun.sharpe_ratio).label("avg_sharpe"),
            func.avg(DBBacktestRun.final_pnl).label("avg_pnl"),
            func.max(DBBacktestRun.final_pnl).label("best_pnl"),
            func.avg(DBBacktestRun.max_drawdown).label("avg_drawdown"),
        )
        .filter(DBBacktestRun.bot_id == bot_id)
        .one()
    )
    run_count = int(agg.run_count or 0)
    avg_sharpe = round(float(agg.avg_sharpe), 3) if agg.avg_sharpe is not None else None
    avg_pnl = round(float(agg.avg_pnl), 2) if agg.avg_pnl is not None else None
    best_pnl = round(float(agg.best_pnl), 2) if agg.best_pnl is not None else None
    avg_drawdown = float(agg.avg_drawdown) if agg.avg_drawdown is not None else None

    # Recent runs (last 5)
    recent = (
        db.query(DBBacktestRun)
        .filter(DBBacktestRun.bot_id == bot_id)
        .order_by(DBBacktestRun.created_at.desc())
        .limit(5)
        .all()
    )
    recent_runs = [
        BotBacktestSummary(
            id=r.id,
            symbol=r.symbol,
            timeframe=r.timeframe,
            data_source=r.data_source,
            final_pnl=round(r.final_pnl, 2),
            sharpe_ratio=round(r.sharpe_ratio, 3),
            win_rate=round(r.win_rate, 3),
            max_drawdown=round(r.max_drawdown, 3),
            num_candles=r.num_candles,
            created_at=r.created_at,
        )
        for r in recent
    ]

    return BotProfileResponse(
        id=bot.id,
        name=bot.name,
        strategy_key=bot.strategy_name,
        status=bot.status,
        description=bot.description,
        created_at=bot.created_at,
        tech_company_name=tech_company_name,
        risk_rating=_compute_risk_rating(avg_sharpe, avg_drawdown, run_count),
        avg_sharpe=avg_sharpe,
        avg_pnl=avg_pnl,
        best_pnl=best_pnl,
        run_count=run_count,
        token_distribution=token_distribution,
        recent_runs=recent_runs,
    )
