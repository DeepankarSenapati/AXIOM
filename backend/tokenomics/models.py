from datetime import datetime

from pydantic import BaseModel


class TokenAllocation(BaseModel):
    bot_id: str
    public_tokens: float
    tech_tokens: float
    gov_tokens: float
    total: float


class HolderPayout(BaseModel):
    holder_address: str
    holder_type: str
    amount: float
    rst_balance: float


class RevenueDistribution(BaseModel):
    bot_id: str
    total_revenue: float
    public_share: float
    tech_share: float
    gov_share: float
    distributions: list[HolderPayout]


class LedgerEntry(BaseModel):
    bot_id: str
    holder_address: str
    amount: float
    timestamp: datetime
    reason: str
