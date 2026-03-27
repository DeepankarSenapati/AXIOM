"""Request/response Pydantic models for the API layer."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from backend.bots.registry import STRATEGY_MAP


# ── Bots ──────────────────────────────────────────────────────────────────────

class BotCreate(BaseModel):
    name: str
    strategy_key: str
    params: dict[str, float | int | str] = {}
    starting_cash: float = 10_000.0

    @field_validator("strategy_key")
    @classmethod
    def strategy_must_exist(cls, v: str) -> str:
        if v not in STRATEGY_MAP:
            raise ValueError(f"Unknown strategy '{v}'. Available: {list(STRATEGY_MAP.keys())}")
        return v


class BotResponse(BaseModel):
    id: str
    name: str
    strategy_name: str
    created_at: datetime
    is_active: bool


# ── Arena / Backtest ──────────────────────────────────────────────────────────

class RunArenaRequest(BaseModel):
    bot_ids: list[str]
    symbol: str
    num_candles: int = 100
    start_price: float = 100.0
    starting_cash: float = 10_000.0
    data_source: Literal["mock", "live"] = "mock"
    timeframe: Literal["1h", "4h", "1d"] = "1d"


class BacktestRequest(BaseModel):
    symbol: str = "BTC/USDT"
    num_candles: int = 100
    start_price: float = 50_000.0
    starting_cash: float = 10_000.0
    data_source: Literal["mock", "live"] = "mock"
    timeframe: Literal["1h", "4h", "1d"] = "1d"


class TradeRecordResponse(BaseModel):
    bot_id: str
    symbol: str
    action_type: str
    quantity: float
    price: float
    timestamp: datetime
    reason: str
    cash_after: float
    pnl: float


class BacktestResultResponse(BaseModel):
    bot_id: str
    total_trades: int
    final_pnl: float
    start_cash: float
    end_cash: float
    sharpe_ratio: float
    max_drawdown: float
    trade_records: list[TradeRecordResponse]


class ArenaResultResponse(BaseModel):
    results: dict[str, BacktestResultResponse]


# ── Tokenomics ────────────────────────────────────────────────────────────────

class InitTokensRequest(BaseModel):
    bot_id: str


class DistributeRevenueRequest(BaseModel):
    bot_id: str
    total_revenue: float


class HolderPayoutResponse(BaseModel):
    holder_address: str
    holder_type: str
    amount: float
    rst_balance: float


class RevenueDistributionResponse(BaseModel):
    bot_id: str
    total_revenue: float
    public_share: float
    tech_share: float
    gov_share: float
    distributions: list[HolderPayoutResponse]


class TokenBalancesResponse(BaseModel):
    bot_id: str
    balances: dict[str, float]


# ── Governance ────────────────────────────────────────────────────────────────

class SubmitVoteRequest(BaseModel):
    bot_id: str
    quarter: str
    voter_address: str
    vote: Literal["satisfied", "unsatisfied"]
    token_weight: float


class ClosePollRequest(BaseModel):
    bot_id: str
    quarter: str


class PollResultResponse(BaseModel):
    bot_id: str
    quarter: str
    satisfaction_rate: float
    satisfied_weight: float
    total_weight: float
    stage_at_close: int
    closed_at: datetime


class StageResponse(BaseModel):
    bot_id: str
    current_stage: int
    stage_name: str


class StageTransitionResponse(BaseModel):
    bot_id: str
    from_stage: int
    to_stage: int
    triggered_by: str
    timestamp: datetime
