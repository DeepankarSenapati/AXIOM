"""Regression tests for per-bot market selection in the legacy arena."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from backend.api import arena
from backend.api.models import RunArenaRequest
from backend.bots.strategies.base import BaseStrategy
from backend.db.models import DBBacktestRun, DBBot
from backend.engine.bot_runner import BotRunner
from backend.engine.models import Action, Candle, Portfolio


class BuyOnce(BaseStrategy):
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def on_candle(self, candles: list[Candle], portfolio: Portfolio) -> Action:
        return Action(
            action_type="BUY" if len(candles) == 1 else "HOLD",
            symbol=self.symbol,
            quantity=1.0 if len(candles) == 1 else 0.0,
            reason="buy once in test market",
        )


def market_candles(symbol: str, prices: list[float]) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            symbol=symbol,
            timestamp=start + timedelta(days=i),
            open=price,
            high=price + 1.0,
            low=price - 1.0,
            close=price,
            volume=1_000.0,
        )
        for i, price in enumerate(prices)
    ]


def test_arena_fetches_each_bot_market_and_persists_its_own_benchmark(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    for bot_id in ("a", "b", "c"):
        db_session.add(DBBot(
            id=bot_id,
            name=f"Bot {bot_id}",
            strategy_name="simple_ma",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            is_active=True,
            status="approved",
        ))
    db_session.commit()

    fetched: list[str] = []
    markets = {
        "AAA": market_candles("AAA", [100.0, 110.0]),
        "BBB": market_candles("BBB", [200.0, 180.0]),
    }

    def fake_fetch(payload: RunArenaRequest) -> list[Candle]:
        fetched.append(payload.symbol)
        return markets[payload.symbol]

    def fake_runner(bot: DBBot, symbol: str, starting_cash: float) -> BotRunner:
        return BotRunner(bot_id=bot.id, strategy=BuyOnce(symbol), starting_cash=starting_cash)

    monkeypatch.setattr(arena, "_fetch_candles", fake_fetch)
    monkeypatch.setattr(arena, "_build_runner", fake_runner)
    request = RunArenaRequest(
        bot_ids=["a", "b", "c"],
        symbol="AAA",
        bot_symbols={"b": "BBB"},
        num_candles=2,
        starting_cash=1_000.0,
        data_source="mock",
    )

    result = arena.run_arena(request, db_session)

    assert sorted(fetched) == ["AAA", "BBB"]  # AAA is shared by two bots.
    assert result.results["a"].benchmark_pnl == pytest.approx(100.0)
    assert result.results["b"].benchmark_pnl == pytest.approx(-100.0)
    assert result.results["c"].benchmark_pnl == pytest.approx(100.0)
    assert result.results["a"].trade_records[0].symbol == "AAA"
    assert result.results["a"].trade_records[0].price == pytest.approx(100.0)
    assert result.results["b"].trade_records[0].symbol == "BBB"
    assert result.results["b"].trade_records[0].price == pytest.approx(200.0)
    rows = {row.bot_id: row for row in db_session.query(DBBacktestRun).all()}
    assert rows["a"].symbol == rows["c"].symbol == "AAA"
    assert rows["b"].symbol == "BBB"
    assert rows["a"].benchmark_pnl == rows["c"].benchmark_pnl == pytest.approx(100.0)
    assert rows["b"].benchmark_pnl == pytest.approx(-100.0)
