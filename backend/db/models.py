from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.session import Base


class DBUser(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # admin | tech_company | governance_company | token_holder
    company_name: Mapped[str | None] = mapped_column(String, nullable=True)
    wallet_balance: Mapped[float] = mapped_column(Float, default=10000.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class DBBot(Base):
    __tablename__ = "bots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    strategy_name: Mapped[str] = mapped_column(String, nullable=False)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Approval workflow — values: pending_approval | approved | live | rejected
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending_approval")
    # ID of the tech_company user who submitted this bot
    tech_company_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # Optional human-readable description supplied at submission time
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    trades: Mapped[list["DBTrade"]] = relationship("DBTrade", back_populates="bot")
    tokens: Mapped[list["DBToken"]] = relationship("DBToken", back_populates="bot")
    votes: Mapped[list["DBGovernanceVote"]] = relationship("DBGovernanceVote", back_populates="bot")
    polls: Mapped[list["DBSatisfactionPoll"]] = relationship("DBSatisfactionPoll", back_populates="bot")


class DBTrade(Base):
    """
    APPEND-ONLY. Never UPDATE or DELETE rows in this table.
    Corrections must be inserted as compensating records.
    """

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[str] = mapped_column(String, ForeignKey("bots.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    action_type: Mapped[str] = mapped_column(String, nullable=False)  # "BUY", "SELL", "HOLD"
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    cash_after: Mapped[float] = mapped_column(Float, nullable=False)
    pnl: Mapped[float] = mapped_column(Float, nullable=False)

    bot: Mapped["DBBot"] = relationship("DBBot", back_populates="trades")


class DBToken(Base):
    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[str] = mapped_column(String, ForeignKey("bots.id"), nullable=False)
    holder_address: Mapped[str] = mapped_column(String, nullable=False)
    balance: Mapped[float] = mapped_column(Float, nullable=False)
    holder_type: Mapped[str] = mapped_column(String, nullable=False)  # "public", "tech", "governance"

    bot: Mapped["DBBot"] = relationship("DBBot", back_populates="tokens")


class DBGovernanceVote(Base):
    __tablename__ = "governance_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quarter: Mapped[str] = mapped_column(String, nullable=False)  # e.g. "2026-Q1"
    bot_id: Mapped[str] = mapped_column(String, ForeignKey("bots.id"), nullable=False)
    voter_address: Mapped[str] = mapped_column(String, nullable=False)
    vote: Mapped[str] = mapped_column(String, nullable=False)  # "satisfied" or "unsatisfied"
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    token_weight: Mapped[float] = mapped_column(Float, nullable=False)

    bot: Mapped["DBBot"] = relationship("DBBot", back_populates="votes")


class DBSatisfactionPoll(Base):
    __tablename__ = "satisfaction_polls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[str] = mapped_column(String, ForeignKey("bots.id"), nullable=False)
    quarter: Mapped[str] = mapped_column(String, nullable=False)
    satisfied_weight: Mapped[float] = mapped_column(Float, nullable=False)
    total_weight: Mapped[float] = mapped_column(Float, nullable=False)
    satisfaction_rate: Mapped[float] = mapped_column(Float, nullable=False)  # satisfied_weight / total_weight
    stage_at_close: Mapped[int] = mapped_column(Integer, nullable=False)
    closed_at: Mapped[datetime] = mapped_column(nullable=False)

    bot: Mapped["DBBot"] = relationship("DBBot", back_populates="polls")


class DBBacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    bot_id: Mapped[str] = mapped_column(String, nullable=False)
    bot_name: Mapped[str] = mapped_column(String, nullable=False)
    strategy_key: Mapped[str] = mapped_column(String, nullable=False)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    timeframe: Mapped[str] = mapped_column(String, nullable=False)
    data_source: Mapped[str] = mapped_column(String, nullable=False)
    num_candles: Mapped[int] = mapped_column(Integer, nullable=False)
    starting_cash: Mapped[float] = mapped_column(Float, nullable=False)
    final_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    end_cash: Mapped[float] = mapped_column(Float, nullable=False)
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    win_rate: Mapped[float] = mapped_column(Float, nullable=False)
    sharpe_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=False)
    benchmark_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class DBGovernanceAudit(Base):
    __tablename__ = "governance_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[str] = mapped_column(String, ForeignKey("bots.id"), nullable=False)
    quarter: Mapped[str] = mapped_column(String, nullable=False)
    submitted_by: Mapped[str] = mapped_column(String, nullable=False)
    finding: Mapped[str] = mapped_column(String, nullable=False)
    recommendation: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False, default="medium")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class DBDistributionEvent(Base):
    __tablename__ = "distribution_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[str] = mapped_column(String, ForeignKey("bots.id"), nullable=False)
    total_revenue: Mapped[float] = mapped_column(Float, nullable=False)
    platform_fee: Mapped[float] = mapped_column(Float, nullable=False)
    distributable: Mapped[float] = mapped_column(Float, nullable=False)
    public_share: Mapped[float] = mapped_column(Float, nullable=False)
    tech_share: Mapped[float] = mapped_column(Float, nullable=False)
    gov_share: Mapped[float] = mapped_column(Float, nullable=False)
    quarter: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    payouts: Mapped[list["DBDistributionPayout"]] = relationship("DBDistributionPayout", back_populates="event")


class DBDistributionPayout(Base):
    __tablename__ = "distribution_payouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(Integer, ForeignKey("distribution_events.id"), nullable=False)
    bot_id: Mapped[str] = mapped_column(String, nullable=False)
    holder_address: Mapped[str] = mapped_column(String, nullable=False)
    holder_type: Mapped[str] = mapped_column(String, nullable=False)
    rst_balance: Mapped[float] = mapped_column(Float, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    event: Mapped["DBDistributionEvent"] = relationship("DBDistributionEvent", back_populates="payouts")
