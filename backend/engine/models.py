from datetime import datetime
from typing import Literal

from pydantic import BaseModel


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
    start_cash: float
    end_cash: float


class ArenaResult(BaseModel):
    results: dict[str, BacktestResult]
