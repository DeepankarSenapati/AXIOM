"""Request/response Pydantic models for the API layer."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.bots.registry import STRATEGY_MAP
from backend.bots.validation import normalize_strategy_params


# ── Bots ──────────────────────────────────────────────────────────────────────

class BotCreate(BaseModel):
    name: str
    strategy_key: str
    params: dict[str, object] = Field(default_factory=dict)
    starting_cash: float = 10_000.0
    description: str | None = None

    @field_validator("strategy_key")
    @classmethod
    def strategy_must_exist(cls, v: str) -> str:
        if v not in STRATEGY_MAP:
            raise ValueError(f"Unknown strategy '{v}'. Available: {list(STRATEGY_MAP.keys())}")
        return v

    @model_validator(mode="after")
    def validate_parameters(self) -> "BotCreate":
        self.params = normalize_strategy_params(self.strategy_key, self.params)
        return self


class BotResponse(BaseModel):
    id: str
    name: str
    strategy_name: str
    created_at: datetime
    is_active: bool
    status: str = "pending_approval"
    description: str | None = None


class AdminBotResponse(BaseModel):
    id: str
    name: str
    strategy_name: str
    status: str
    tech_company_id: str | None
    description: str | None
    created_at: datetime
    is_active: bool


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    company_name: str | None
    wallet_balance: float
    is_active: bool
    created_at: datetime


class PlatformStatsResponse(BaseModel):
    total_bots: int
    pending_approval: int
    total_users: int
    users_by_role: dict[str, int]
    total_backtest_runs: int


# ── Arena / Backtest ──────────────────────────────────────────────────────────

class RunArenaRequest(BaseModel):
    bot_ids: list[str]
    symbol: str
    num_candles: int = Field(default=100, ge=2, le=1000)
    start_price: float = Field(default=100.0, gt=0, le=1_000_000_000, allow_inf_nan=False)
    starting_cash: float = Field(default=10_000.0, gt=0, le=1_000_000_000_000, allow_inf_nan=False)
    data_source: Literal["mock", "live"] = "mock"
    timeframe: Literal["1h", "4h", "1d"] = "1d"
    bot_symbols: dict[str, str] = {}
    seed: int | None = None


class BacktestRequest(BaseModel):
    symbol: str = "BTC/USDT"
    num_candles: int = Field(default=100, ge=2, le=1000)
    start_price: float = Field(default=50_000.0, gt=0, le=1_000_000_000, allow_inf_nan=False)
    starting_cash: float = Field(default=10_000.0, gt=0, le=1_000_000_000_000, allow_inf_nan=False)
    data_source: Literal["mock", "live"] = "mock"
    timeframe: Literal["1h", "4h", "1d"] = "1d"
    seed: int | None = None


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
    win_rate: float = 0.0
    sharpe_ratio: float
    max_drawdown: float
    benchmark_pnl: float = 0.0
    alpha: float = 0.0
    trade_records: list[TradeRecordResponse]
    # Complete per-candle records for equity charts; trade_records stays BUY/SELL-only.
    equity_records: list[TradeRecordResponse] = Field(default_factory=list)


class ArenaResultResponse(BaseModel):
    results: dict[str, BacktestResultResponse]


class BacktestRunResponse(BaseModel):
    id: str
    bot_id: str
    bot_name: str
    strategy_key: str
    symbol: str
    timeframe: str
    data_source: str
    num_candles: int
    starting_cash: float
    final_pnl: float
    end_cash: float
    total_trades: int
    win_rate: float
    sharpe_ratio: float
    max_drawdown: float
    benchmark_pnl: float = 0.0
    alpha: float = 0.0
    created_at: datetime


# ── Tokenomics ────────────────────────────────────────────────────────────────

class InitTokensRequest(BaseModel):
    bot_id: str


class DistributeRevenueRequest(BaseModel):
    bot_id: str
    total_revenue: float = Field(gt=0, le=1_000_000_000_000, allow_inf_nan=False)
    quarter: str = Field(default="", pattern=r"^(?:[0-9]{4}-Q[1-4])?$")

    @field_validator("total_revenue", mode="before")
    @classmethod
    def reject_boolean_revenue(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("total_revenue must be a simulated cash amount")
        return value


class HolderPayoutResponse(BaseModel):
    holder_address: str
    holder_type: str
    amount: float
    rst_balance: float


class RevenueDistributionResponse(BaseModel):
    bot_id: str
    total_revenue: float
    platform_fee: float
    distributable: float
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
    quarter: str = Field(pattern=r"^[0-9]{4}-Q[1-4]$")
    # Optional legacy fields may only agree with the authenticated account and
    # its actual holdings; the server never uses them as the source of truth.
    voter_address: str | None = None
    vote: Literal["satisfied", "unsatisfied"]
    token_weight: float | None = Field(default=None, gt=0, allow_inf_nan=False)


class ClosePollRequest(BaseModel):
    bot_id: str
    quarter: str = Field(pattern=r"^[0-9]{4}-Q[1-4]$")


class PollResultResponse(BaseModel):
    bot_id: str
    quarter: str
    satisfaction_rate: float
    satisfied_weight: float
    total_weight: float
    stage_at_close: int
    closed_at: datetime
    vote_count: int = 0


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


class SubmitAuditRequest(BaseModel):
    quarter: str
    finding: str
    recommendation: str
    severity: Literal["low", "medium", "high"] = "medium"


class AuditResponse(BaseModel):
    id: int
    bot_id: str
    quarter: str
    submitted_by: str
    finding: str
    recommendation: str
    severity: str
    created_at: datetime


# ── Leaderboard ───────────────────────────────────────────────────────────────

class LeaderboardEntryResponse(BaseModel):
    rank: int
    strategy_key: str
    total_runs: int
    avg_sharpe: float
    avg_pnl: float
    best_pnl: float
    avg_win_rate: float
    avg_alpha: float = 0.0


# ── Portfolio (token purchases) ───────────────────────────────────────────────

class PurchaseTokensRequest(BaseModel):
    bot_id: str
    amount: int = Field(gt=0, le=1_000_000)  # whole simulated RST tokens

    @field_validator("amount", mode="before")
    @classmethod
    def reject_boolean_amount(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("amount must be a token quantity")
        return value


class HoldingResponse(BaseModel):
    bot_id: str
    bot_name: str
    amount: float  # RST tokens held
    cost_basis: float  # amount * RST_PRICE at purchase time


class MyHoldingsResponse(BaseModel):
    holdings: list[HoldingResponse]
    total_tokens: float
    total_value: float


class SellTokensRequest(BaseModel):
    bot_id: str
    # Existing local ledgers may contain fractional tokens from older versions.
    amount: float = Field(gt=0, le=1_000_000, allow_inf_nan=False)

    @field_validator("amount", mode="before")
    @classmethod
    def reject_boolean_amount(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("amount must be a token quantity")
        return value


class EarningPayoutResponse(BaseModel):
    bot_id: str
    bot_name: str
    amount: float
    rst_balance: float
    quarter: str
    distributed_at: datetime


class MyEarningsResponse(BaseModel):
    earnings: list[EarningPayoutResponse]
    total_earned: float


class PlatformRevenueResponse(BaseModel):
    total_fees_collected: float
    event_count: int


# ── Tech Company Dashboard ────────────────────────────────────────────────────

class TechBotSummary(BaseModel):
    id: str
    name: str
    strategy_key: str
    status: str
    description: str | None
    created_at: datetime
    total_revenue_distributed: float
    your_earnings: float
    distribution_count: int
    token_holder_count: int
    tokens_in_circulation: float


class TechDashboardSummary(BaseModel):
    total_bots: int
    approved_bots: int
    total_your_earnings: float
    total_distributions: int
    total_token_holders: int


class TechDashboardResponse(BaseModel):
    bots: list[TechBotSummary]
    summary: TechDashboardSummary


# ── Bot Profile (due diligence) ───────────────────────────────────────────────

class BotTokenDistribution(BaseModel):
    public_pool_remaining: float     # tokens still available to buy
    investor_holdings: float         # tokens held by real investors
    tech_holdings: float             # tech company allocation
    gov_holdings: float              # governance allocation
    total: float
    investor_count: int              # unique real investors


class BotBacktestSummary(BaseModel):
    id: str
    symbol: str
    timeframe: str
    data_source: str
    final_pnl: float
    sharpe_ratio: float
    win_rate: float
    max_drawdown: float
    num_candles: int
    created_at: datetime


class BotProfileResponse(BaseModel):
    id: str
    name: str
    strategy_key: str
    status: str
    description: str | None
    created_at: datetime
    tech_company_name: str | None    # company_name of the submitting user
    risk_rating: str                 # "Low" | "Medium" | "High" | "Unrated"
    avg_sharpe: float | None
    avg_pnl: float | None
    best_pnl: float | None
    run_count: int
    token_distribution: BotTokenDistribution | None
    recent_runs: list[BotBacktestSummary]
