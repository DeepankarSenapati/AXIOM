"""Tech-company-specific endpoints."""
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from backend.api.models import TechBotSummary, TechDashboardResponse, TechDashboardSummary
from backend.auth.dependencies import require_role
from backend.db.models import DBBot, DBDistributionEvent, DBToken, DBUser
from backend.db.session import get_db

router = APIRouter(prefix="/tech", tags=["tech"])
_tech = require_role("tech_company")

_SYSTEM_WALLETS = ("public_pool", "tech_wallet", "gov_wallet")


@router.get("/my-dashboard", response_model=TechDashboardResponse)
def my_dashboard(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(_tech),
) -> TechDashboardResponse:
    bots = (
        db.query(DBBot)
        .filter(DBBot.tech_company_id == current_user.id)
        .order_by(DBBot.created_at.desc())
        .all()
    )

    bot_summaries: list[TechBotSummary] = []
    total_your_earnings = 0.0
    total_distributions = 0
    all_holder_addresses: set[str] = set()

    for bot in bots:
        # Revenue distribution aggregates
        dist_row = (
            db.query(
                func.coalesce(func.sum(DBDistributionEvent.total_revenue), 0.0).label("total_rev"),
                func.coalesce(func.sum(DBDistributionEvent.tech_share), 0.0).label("tech_share"),
                func.count(DBDistributionEvent.id).label("dist_count"),
            )
            .filter(DBDistributionEvent.bot_id == bot.id)
            .one()
        )

        # Real investor token holders (exclude system wallets)
        holder_rows = (
            db.query(DBToken.holder_address, DBToken.balance)
            .filter(
                DBToken.bot_id == bot.id,
                DBToken.holder_address.notin_(_SYSTEM_WALLETS),
                DBToken.balance > 0,
            )
            .all()
        )
        holder_count = len(holder_rows)
        tokens_in_circulation = sum(r.balance for r in holder_rows)
        for r in holder_rows:
            all_holder_addresses.add(r.holder_address)

        your_earnings = round(float(dist_row.tech_share), 4)
        total_your_earnings += your_earnings
        total_distributions += int(dist_row.dist_count)

        bot_summaries.append(TechBotSummary(
            id=bot.id,
            name=bot.name,
            strategy_key=bot.strategy_name,
            status=bot.status,
            description=bot.description,
            created_at=bot.created_at,
            total_revenue_distributed=round(float(dist_row.total_rev), 4),
            your_earnings=your_earnings,
            distribution_count=int(dist_row.dist_count),
            token_holder_count=holder_count,
            tokens_in_circulation=round(tokens_in_circulation, 2),
        ))

    summary = TechDashboardSummary(
        total_bots=len(bots),
        approved_bots=sum(1 for b in bots if b.is_active and b.status in ("approved", "live")),
        total_your_earnings=round(total_your_earnings, 4),
        total_distributions=total_distributions,
        total_token_holders=len(all_holder_addresses),
    )

    return TechDashboardResponse(bots=bot_summaries, summary=summary)
