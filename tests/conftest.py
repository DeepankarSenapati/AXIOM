from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.db.session import Base
from backend.db.models import DBBot
from backend.engine.models import Action, Candle, Portfolio
from backend.bots.strategies.base import BaseStrategy


# ---------------------------------------------------------------------------
# In-memory SQLite session — fresh for every test function
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# Shared bot fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def bot_id() -> str:
    return "bot-test-001"


@pytest.fixture()
def seeded_bot(db_session: Session, bot_id: str) -> str:
    """Insert a DBBot row so FK constraints are satisfied."""
    db_session.add(
        DBBot(
            id=bot_id,
            name="Test Bot",
            strategy_name="HoldStrategy",
            created_at=datetime.now(tz=timezone.utc),
            is_active=True,
        )
    )
    db_session.commit()
    return bot_id


# ---------------------------------------------------------------------------
# Candle factory
# ---------------------------------------------------------------------------

def make_candle(
    symbol: str = "BTC/USD",
    close: float = 100.0,
    timestamp: datetime | None = None,
) -> Candle:
    ts = timestamp or datetime(2026, 1, 1, tzinfo=timezone.utc)
    return Candle(
        symbol=symbol,
        timestamp=ts,
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=1000.0,
    )


# ---------------------------------------------------------------------------
# Deterministic stub strategies for engine tests
# ---------------------------------------------------------------------------

class AlwaysHoldStrategy(BaseStrategy):
    def on_candle(self, candles: list[Candle], portfolio: Portfolio) -> Action:
        return Action(
            action_type="HOLD",
            symbol=candles[-1].symbol,
            quantity=0.0,
            reason="always hold",
        )


class AlwaysBuyStrategy(BaseStrategy):
    def __init__(self, qty: float = 1.0) -> None:
        self.qty = qty

    def on_candle(self, candles: list[Candle], portfolio: Portfolio) -> Action:
        return Action(
            action_type="BUY",
            symbol=candles[-1].symbol,
            quantity=self.qty,
            reason="always buy",
        )


class AlwaysSellStrategy(BaseStrategy):
    def __init__(self, qty: float = 1.0) -> None:
        self.qty = qty

    def on_candle(self, candles: list[Candle], portfolio: Portfolio) -> Action:
        return Action(
            action_type="SELL",
            symbol=candles[-1].symbol,
            quantity=self.qty,
            reason="always sell",
        )


class BuyThenSellStrategy(BaseStrategy):
    """Buys on the first candle, sells on all subsequent candles."""
    def on_candle(self, candles: list[Candle], portfolio: Portfolio) -> Action:
        if len(candles) == 1:
            return Action(
                action_type="BUY",
                symbol=candles[-1].symbol,
                quantity=1.0,
                reason="initial buy",
            )
        return Action(
            action_type="SELL",
            symbol=candles[-1].symbol,
            quantity=1.0,
            reason="selling position",
        )
