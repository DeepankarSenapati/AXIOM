from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.session import Base


class DBBot(Base):
    __tablename__ = "bots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    strategy_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

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
