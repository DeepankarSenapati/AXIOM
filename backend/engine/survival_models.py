"""Typed input and output for the local-only Survival Lab simulation."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.engine.models import Candle


StrategyKey = Literal["simple_ma", "rsi", "bollinger_bands", "macd", "momentum"]
ActionName = Literal["BUY", "SELL", "HOLD"]
EventType = Literal["signal", "fill", "guard", "expired", "rejected", "blocked"]

# Tiny percentage points can underflow when converted to a fraction or be
# too small to affect floating-point account values. Keep risk limits practical.
MIN_RISK_PERCENTAGE_POINTS = 0.0001


class SurvivalRequest(BaseModel):
    """Percent values use percentage points; costs use basis points."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    strategy_key: StrategyKey = "simple_ma"
    seed: int = Field(default=42, ge=0, le=4_294_967_295)
    num_candles: int = Field(default=160, ge=2, le=600)
    start_price: float = Field(default=100.0, ge=0.0001, le=1_000_000_000)
    starting_cash: float = Field(default=10_000.0, ge=0.01, le=1_000_000_000_000)
    fee_bps: float = Field(default=10.0, ge=0.0, le=500.0)
    slippage_bps: float = Field(default=5.0, ge=0.0, le=500.0)
    shock_pct: float = Field(default=12.0, ge=0.0, le=80.0)
    shock_index: int | None = Field(default=None, ge=1)
    guard_enabled: bool = True
    guard_drawdown_pct: float = Field(
        default=8.0, ge=MIN_RISK_PERCENTAGE_POINTS, le=90.0,
        description="Drawdown threshold in percentage points, at least 0.0001 for practical floating-point precision.",
    )
    max_position_pct: float = Field(
        default=30.0, ge=MIN_RISK_PERCENTAGE_POINTS, le=100.0,
        description="Maximum exposure in percentage points, at least 0.0001 to avoid fraction underflow and precision loss.",
    )

    @model_validator(mode="after")
    def validate_shock_index(self) -> "SurvivalRequest":
        if self.shock_index is not None and self.shock_index >= self.num_candles:
            raise ValueError("shock_index must be smaller than num_candles")
        return self


class SurvivalEvent(BaseModel):
    candle_index: int
    timestamp: datetime
    event_type: EventType
    action: ActionName
    quantity: float
    price: float | None
    fee: float
    reason: str
    signal_index: int | None = None


class SurvivalEquityPoint(BaseModel):
    index: int
    timestamp: datetime
    equity: float
    cash: float
    position: float
    drawdown_pct: float


class SurvivalRun(BaseModel):
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    ending_cash: float
    ending_position: float
    total_fees: float
    total_slippage_cost: float
    trade_count: int
    guard_trigger_index: int | None
    equity_curve: list[SurvivalEquityPoint]
    events: list[SurvivalEvent]


class SurvivalScenario(BaseModel):
    source: Literal["synthetic"] = "synthetic"
    symbol: str
    timeframe: Literal["1d"] = "1d"
    seed: int
    candle_count: int
    shock_index: int | None
    shock_pct: float


class SurvivalResponse(BaseModel):
    fingerprint: str
    engine_version: str
    strategy_parameters: dict[str, int | float]
    # Fraction of available cash requested by built-in BUY signals, not the fill cap.
    signal_cash_fraction: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    scenario: SurvivalScenario
    assumptions: list[str]
    candles: list[Candle]
    unguarded: SurvivalRun
    guarded: SurvivalRun | None
    benchmark: SurvivalRun
