"""Tests for backend/engine/bot_runner.py"""
from datetime import datetime, timezone

import pytest

from backend.engine.bot_runner import BotRunner, InsufficientFundsError
from backend.engine.models import Action, Candle, Portfolio, TradeRecord
from tests.conftest import (
    AlwaysBuyStrategy,
    AlwaysHoldStrategy,
    AlwaysSellStrategy,
    BuyThenSellStrategy,
    make_candle,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def single_candle() -> list[Candle]:
    return [make_candle(close=100.0)]


@pytest.fixture()
def three_candles() -> list[Candle]:
    return [
        make_candle(close=100.0, timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        make_candle(close=110.0, timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc)),
        make_candle(close=120.0, timestamp=datetime(2026, 1, 3, tzinfo=timezone.utc)),
    ]


# ---------------------------------------------------------------------------
# run() — basic record counts
# ---------------------------------------------------------------------------

def test_run_returns_one_record_per_candle(single_candle: list[Candle]) -> None:
    runner = BotRunner("bot1", AlwaysHoldStrategy(), starting_cash=1000.0)
    records = runner.run(single_candle)
    assert len(records) == 1


def test_run_returns_record_per_candle_multi(three_candles: list[Candle]) -> None:
    runner = BotRunner("bot1", AlwaysHoldStrategy(), starting_cash=1000.0)
    records = runner.run(three_candles)
    assert len(records) == 3


def test_run_returns_list_of_trade_records(single_candle: list[Candle]) -> None:
    runner = BotRunner("bot1", AlwaysHoldStrategy(), starting_cash=500.0)
    records = runner.run(single_candle)
    assert all(isinstance(r, TradeRecord) for r in records)


def test_run_empty_candles_returns_empty_list() -> None:
    runner = BotRunner("bot1", AlwaysHoldStrategy(), starting_cash=1000.0)
    assert runner.run([]) == []


# ---------------------------------------------------------------------------
# Blindness guarantee — strategy never sees future candles
# ---------------------------------------------------------------------------

class _WindowRecordingStrategy(AlwaysHoldStrategy):
    def __init__(self) -> None:
        self.window_sizes: list[int] = []

    def on_candle(self, candles: list[Candle], portfolio: Portfolio) -> Action:
        self.window_sizes.append(len(candles))
        return super().on_candle(candles, portfolio)


def test_strategy_receives_increasing_window_sizes(three_candles: list[Candle]) -> None:
    strategy = _WindowRecordingStrategy()
    BotRunner("bot1", strategy, starting_cash=1000.0).run(three_candles)
    assert strategy.window_sizes == [1, 2, 3]


def test_strategy_never_receives_future_candles(three_candles: list[Candle]) -> None:
    class _FutureCheckStrategy(AlwaysHoldStrategy):
        def __init__(self, full_series: list[Candle]) -> None:
            self.full = full_series
            self.violation = False

        def on_candle(self, candles: list[Candle], portfolio: Portfolio) -> Action:
            current_idx = len(candles) - 1
            if candles[-1].timestamp != self.full[current_idx].timestamp:
                self.violation = True
            if len(candles) > current_idx + 1:
                self.violation = True
            return super().on_candle(candles, portfolio)

    strategy = _FutureCheckStrategy(three_candles)
    BotRunner("bot1", strategy, starting_cash=1000.0).run(three_candles)
    assert not strategy.violation


# ---------------------------------------------------------------------------
# BUY execution
# ---------------------------------------------------------------------------

def test_buy_reduces_cash_by_cost() -> None:
    # cost = 100.0 * 2 = 200 → cash_after = 800
    records = BotRunner("bot1", AlwaysBuyStrategy(qty=2.0), starting_cash=1000.0).run(
        [make_candle(close=100.0)]
    )
    assert records[0].cash_after == pytest.approx(800.0)


def test_buy_action_type_recorded() -> None:
    records = BotRunner("bot1", AlwaysBuyStrategy(qty=1.0), starting_cash=500.0).run(
        [make_candle(close=50.0)]
    )
    assert records[0].action_type == "BUY"


def test_buy_quantity_recorded() -> None:
    records = BotRunner("bot1", AlwaysBuyStrategy(qty=3.0), starting_cash=500.0).run(
        [make_candle(close=50.0)]
    )
    assert records[0].quantity == 3.0


def test_buy_records_correct_price() -> None:
    records = BotRunner("bot1", AlwaysBuyStrategy(qty=1.0), starting_cash=500.0).run(
        [make_candle(close=200.0)]
    )
    assert records[0].price == pytest.approx(200.0)


def test_buy_raises_insufficient_funds_when_cost_exceeds_cash() -> None:
    with pytest.raises(InsufficientFundsError):
        BotRunner("bot1", AlwaysBuyStrategy(qty=200.0), starting_cash=100.0).run(
            [make_candle(close=100.0)]
        )


def test_buy_insufficient_funds_error_message_contains_bot_id() -> None:
    with pytest.raises(InsufficientFundsError, match="my-bot"):
        BotRunner("my-bot", AlwaysBuyStrategy(qty=200.0), starting_cash=50.0).run(
            [make_candle(close=100.0)]
        )


# ---------------------------------------------------------------------------
# SELL execution
# ---------------------------------------------------------------------------

def test_sell_with_no_position_does_not_raise() -> None:
    # held=0, sell_qty=min(5,0)=0, cash unchanged
    records = BotRunner("bot1", AlwaysSellStrategy(qty=5.0), starting_cash=500.0).run(
        [make_candle(close=100.0)]
    )
    assert records[0].cash_after == pytest.approx(500.0)


def test_sell_increases_cash() -> None:
    candles = [
        make_candle(close=100.0, timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        make_candle(close=110.0, timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc)),
    ]
    # BUY at 100 → cash=900; SELL at 110 → cash=1010
    records = BotRunner("bot1", BuyThenSellStrategy(), starting_cash=1000.0).run(candles)
    assert records[1].cash_after == pytest.approx(1010.0)


def test_sell_quantity_capped_at_held() -> None:
    """Requesting to sell 10 when only 1 held — only 1 is sold."""
    class _BuyOneThenSellTen(AlwaysHoldStrategy):
        def on_candle(self, candles: list[Candle], portfolio: Portfolio) -> Action:
            if len(candles) == 1:
                return Action(action_type="BUY", symbol="BTC/USD", quantity=1.0, reason="buy")
            return Action(action_type="SELL", symbol="BTC/USD", quantity=10.0, reason="sell")

    candles = [
        make_candle(close=100.0, timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        make_candle(close=100.0, timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc)),
    ]
    records = BotRunner("bot1", _BuyOneThenSellTen(), starting_cash=1000.0).run(candles)
    # Sold only 1 at 100: cash = 900 + 100 = 1000
    assert records[1].cash_after == pytest.approx(1000.0)


# ---------------------------------------------------------------------------
# HOLD execution
# ---------------------------------------------------------------------------

def test_hold_does_not_change_cash() -> None:
    records = BotRunner("bot1", AlwaysHoldStrategy(), starting_cash=750.0).run(
        [make_candle(close=100.0)]
    )
    assert records[0].cash_after == pytest.approx(750.0)


def test_hold_action_type_recorded() -> None:
    records = BotRunner("bot1", AlwaysHoldStrategy(), starting_cash=1000.0).run(
        [make_candle(close=100.0)]
    )
    assert records[0].action_type == "HOLD"


# ---------------------------------------------------------------------------
# PnL — portfolio-level: (cash + position_value) - starting_cash
# ---------------------------------------------------------------------------

def test_pnl_zero_after_hold_with_no_position() -> None:
    records = BotRunner("bot1", AlwaysHoldStrategy(), starting_cash=1000.0).run(
        [make_candle(close=100.0)]
    )
    assert records[0].pnl == pytest.approx(0.0)


def test_pnl_zero_immediately_after_buy() -> None:
    # After BUY at 100: cash=900, positions={1 unit @ 100} → pnl=(900+100)-1000=0
    records = BotRunner("bot1", AlwaysBuyStrategy(qty=1.0), starting_cash=1000.0).run(
        [make_candle(close=100.0)]
    )
    assert records[0].pnl == pytest.approx(0.0)


def test_pnl_positive_after_price_rise() -> None:
    candles = [
        make_candle(close=100.0, timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        make_candle(close=150.0, timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc)),
    ]
    # BUY@100 → pnl=0; SELL@150 → cash=1050, pnl=50
    records = BotRunner("bot1", BuyThenSellStrategy(), starting_cash=1000.0).run(candles)
    assert records[1].pnl == pytest.approx(50.0)


def test_pnl_negative_after_price_drop() -> None:
    candles = [
        make_candle(close=100.0, timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        make_candle(close=80.0, timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc)),
    ]
    # BUY@100 → pnl=0; SELL@80 → cash=980, pnl=-20
    records = BotRunner("bot1", BuyThenSellStrategy(), starting_cash=1000.0).run(candles)
    assert records[1].pnl == pytest.approx(-20.0)


# ---------------------------------------------------------------------------
# TradeRecord field integrity
# ---------------------------------------------------------------------------

def test_trade_record_bot_id_matches() -> None:
    records = BotRunner("my-special-bot", AlwaysHoldStrategy(), starting_cash=1000.0).run(
        [make_candle()]
    )
    assert records[0].bot_id == "my-special-bot"


def test_trade_record_symbol_matches_candle() -> None:
    records = BotRunner("bot1", AlwaysHoldStrategy(), starting_cash=1000.0).run(
        [make_candle(symbol="ETH/USD")]
    )
    assert records[0].symbol == "ETH/USD"


def test_trade_record_timestamp_matches_candle() -> None:
    ts = datetime(2026, 6, 15, tzinfo=timezone.utc)
    records = BotRunner("bot1", AlwaysHoldStrategy(), starting_cash=1000.0).run(
        [make_candle(timestamp=ts)]
    )
    assert records[0].timestamp == ts


def test_trade_record_reason_matches_action() -> None:
    records = BotRunner("bot1", AlwaysHoldStrategy(), starting_cash=1000.0).run(
        [make_candle()]
    )
    assert records[0].reason == "always hold"
