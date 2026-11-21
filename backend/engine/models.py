from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Candle(BaseModel):
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class Portfolio(BaseModel):
    cash: float
    positions: dict[str, float]  # symbol → quantity held
    pnl: float


class Action(BaseModel):
    action_type: Literal["BUY", "SELL", "HOLD"]
    symbol: str
    quantity: float
    reason: str


class TradeRecord(BaseModel):
    bot_id: str
    symbol: str
    action_type: str
    quantity: float
    price: float
    timestamp: datetime
    reason: str
    cash_after: float
    pnl: float


class BacktestResult(BaseModel):
    bot_id: str
    total_trades: int
    final_pnl: float
    trade_records: list[TradeRecord]
    # One point per candle, including HOLDs, for time-aligned equity charts.
    equity_records: list[TradeRecord] = Field(default_factory=list)
    start_cash: float
    end_cash: float
    sharpe_ratio: float
    max_drawdown: float


class ArenaResult(BaseModel):
    results: dict[str, BacktestResult]
