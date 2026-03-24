from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.models import (
    DistributeRevenueRequest,
    HolderPayoutResponse,
    InitTokensRequest,
    RevenueDistributionResponse,
    TokenBalancesResponse,
)
from backend.db.models import DBBot
from backend.db.session import get_db
from backend.tokenomics.distributor import Distributor
from backend.tokenomics.ledger import InsufficientTokensError, TokenLedger

router = APIRouter(prefix="/tokenomics", tags=["tokenomics"])


def _get_active_bot(bot_id: str, db: Session) -> DBBot:
    bot = db.query(DBBot).filter(DBBot.id == bot_id).first()
    if bot is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")
    return bot


@router.post("/init", response_model=TokenBalancesResponse, status_code=201)
def init_tokens(payload: InitTokensRequest, db: Session = Depends(get_db)) -> TokenBalancesResponse:
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
    payload: DistributeRevenueRequest, db: Session = Depends(get_db)
) -> RevenueDistributionResponse:
    _get_active_bot(payload.bot_id, db)
    ledger = TokenLedger(db)
    distributor = Distributor(db, ledger)

    try:
        result = distributor.distribute(payload.bot_id, payload.total_revenue)
    except InsufficientTokensError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return RevenueDistributionResponse(
        bot_id=result.bot_id,
        total_revenue=result.total_revenue,
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
