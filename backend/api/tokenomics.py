from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.models import (
    DistributeRevenueRequest,
    EarningPayoutResponse,
    HoldingResponse,
    HolderPayoutResponse,
    InitTokensRequest,
    MyEarningsResponse,
    MyHoldingsResponse,
    PurchaseTokensRequest,
    RevenueDistributionResponse,
    SellTokensRequest,
    TokenBalancesResponse,
)
from backend.auth.dependencies import get_current_user
from backend.config import EXIT_FEE, RST_PRICE
from backend.db.models import DBBot, DBDistributionPayout, DBToken, DBUser
from backend.db.session import get_db
from backend.tokenomics.distributor import Distributor, InvalidRevenueError
from backend.tokenomics.ledger import InsufficientTokensError, TokenLedger

router = APIRouter(prefix="/tokenomics", tags=["tokenomics"])


def _get_active_bot(bot_id: str, db: Session) -> DBBot:
    bot = db.query(DBBot).filter(DBBot.id == bot_id).first()
    if bot is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")
    return bot


@router.post("/init", response_model=TokenBalancesResponse, status_code=201)
def init_tokens(
    payload: InitTokensRequest,
    db: Session = Depends(get_db),
    _: DBUser = Depends(get_current_user),
) -> TokenBalancesResponse:
    _get_active_bot(payload.bot_id, db)
    ledger = TokenLedger(db)

    existing = ledger.get_balances(payload.bot_id)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Tokens already initialised for bot '{payload.bot_id}'",
        )

    ledger.initialize_bot_tokens(payload.bot_id)
    balances = ledger.get_balances(payload.bot_id)
    return TokenBalancesResponse(bot_id=payload.bot_id, balances=balances)


@router.get("/{bot_id}/balances", response_model=TokenBalancesResponse)
def get_balances(bot_id: str, db: Session = Depends(get_db)) -> TokenBalancesResponse:
    _get_active_bot(bot_id, db)
    ledger = TokenLedger(db)
    balances = ledger.get_balances(bot_id)
    return TokenBalancesResponse(bot_id=bot_id, balances=balances)


@router.post("/distribute", response_model=RevenueDistributionResponse)
def distribute_revenue(
    payload: DistributeRevenueRequest,
    db: Session = Depends(get_db),
    _: DBUser = Depends(get_current_user),
) -> RevenueDistributionResponse:
    _get_active_bot(payload.bot_id, db)
    ledger = TokenLedger(db)
    distributor = Distributor(db, ledger)

    try:
        result = distributor.distribute(payload.bot_id, payload.total_revenue, payload.quarter)
    except InvalidRevenueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except InsufficientTokensError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return RevenueDistributionResponse(
        bot_id=result.bot_id,
        total_revenue=result.total_revenue,
        platform_fee=result.platform_fee,
        distributable=result.distributable,
        public_share=result.public_share,
        tech_share=result.tech_share,
        gov_share=result.gov_share,
        distributions=[
            HolderPayoutResponse(
                holder_address=p.holder_address,
                holder_type=p.holder_type,
                amount=p.amount,
                rst_balance=p.rst_balance,
            )
            for p in result.distributions
        ],
    )


@router.post("/purchase", status_code=201)
def purchase_tokens(
    payload: PurchaseTokensRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
) -> dict:
    """Simulated RST token purchase — deducts from wallet, transfers from public pool."""
    if payload.amount <= 0:
        raise HTTPException(status_code=422, detail="amount must be positive")

    bot = _get_active_bot(payload.bot_id, db)
    cost = round(payload.amount * RST_PRICE, 2)

    if current_user.wallet_balance < cost:
        raise HTTPException(
            status_code=422,
            detail=f"Insufficient wallet balance: have ${current_user.wallet_balance:.2f}, need ${cost:.2f}",
        )

    ledger = TokenLedger(db)
    try:
        ledger.transfer(payload.bot_id, "public_pool", current_user.email, payload.amount)
    except InsufficientTokensError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    current_user.wallet_balance = round(current_user.wallet_balance - cost, 2)
    db.commit()

    return {
        "bot_id": payload.bot_id,
        "bot_name": bot.name,
        "amount": payload.amount,
        "cost": cost,
        "wallet_balance": current_user.wallet_balance,
    }


@router.post("/sell", status_code=200)
def sell_tokens(
    payload: SellTokensRequest,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
) -> dict:
    """Sell RST tokens back to the public pool with a 2% exit fee."""
    if payload.amount <= 0:
        raise HTTPException(status_code=422, detail="amount must be positive")

    _get_active_bot(payload.bot_id, db)

    user_row = (
        db.query(DBToken)
        .filter(DBToken.bot_id == payload.bot_id, DBToken.holder_address == current_user.email)
        .first()
    )
    if user_row is None or user_row.balance < payload.amount:
        held = user_row.balance if user_row else 0.0
        raise HTTPException(
            status_code=422,
            detail=f"Insufficient tokens: hold {held} RST, cannot sell {payload.amount}",
        )

    gross = round(payload.amount * RST_PRICE, 4)
    fee = round(gross * EXIT_FEE, 4)
    proceeds = round(gross - fee, 4)

    ledger = TokenLedger(db)
    try:
        ledger.transfer(payload.bot_id, current_user.email, "public_pool", payload.amount)
    except InsufficientTokensError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    current_user.wallet_balance = round(current_user.wallet_balance + proceeds, 4)
    db.commit()

    return {
        "bot_id": payload.bot_id,
        "tokens_sold": payload.amount,
        "gross": gross,
        "fee": fee,
        "proceeds": proceeds,
        "wallet_balance": current_user.wallet_balance,
    }


@router.get("/my-holdings", response_model=MyHoldingsResponse)
def my_holdings(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
) -> MyHoldingsResponse:
    """Return all RST token holdings for the current user."""
    rows = (
        db.query(DBToken)
        .filter(DBToken.holder_address == current_user.email)
        .all()
    )

    holdings: list[HoldingResponse] = []
    for row in rows:
        bot = db.query(DBBot).filter(DBBot.id == row.bot_id).first()
        holdings.append(HoldingResponse(
            bot_id=row.bot_id,
            bot_name=bot.name if bot else row.bot_id,
            amount=row.balance,
            cost_basis=round(row.balance * RST_PRICE, 2),
        ))

    total_tokens = sum(h.amount for h in holdings)
    total_value = round(total_tokens * RST_PRICE, 2)

    return MyHoldingsResponse(
        holdings=holdings,
        total_tokens=total_tokens,
        total_value=total_value,
    )


@router.get("/my-earnings", response_model=MyEarningsResponse)
def my_earnings(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
) -> MyEarningsResponse:
    """Return all revenue distribution payouts received by the current user."""
    rows = (
        db.query(DBDistributionPayout)
        .filter(DBDistributionPayout.holder_address == current_user.email)
        .order_by(DBDistributionPayout.created_at.desc())
        .all()
    )

    earnings: list[EarningPayoutResponse] = []
    for row in rows:
        bot = db.query(DBBot).filter(DBBot.id == row.bot_id).first()
        # pull quarter from the parent event
        quarter = row.event.quarter if row.event else ""
        earnings.append(EarningPayoutResponse(
            bot_id=row.bot_id,
            bot_name=bot.name if bot else row.bot_id,
            amount=row.amount,
            rst_balance=row.rst_balance,
            quarter=quarter,
            distributed_at=row.created_at,
        ))

    total_earned = round(sum(e.amount for e in earnings), 4)
    return MyEarningsResponse(earnings=earnings, total_earned=total_earned)
