"""Tests for backend/engine/backtester.py"""
from datetime import datetime, timezone

import pytest

from backend.engine.backtester import Backtester
from backend.engine.bot_runner import BotRunner
from backend.engine.models import Action, BacktestResult, Candle, Portfolio
from backend.api.arena import _to_response
from tests.conftest import (
    AlwaysHoldStrategy,
    BuyThenSellStrategy,
    make_candle,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def hold_runner() -> BotRunner:
    return BotRunner("backtester-bot", AlwaysHoldStrategy(), starting_cash=1000.0)


@pytest.fixture()
def three_candles() -> list[Candle]:
    return [
        make_candle(close=100.0, timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        make_candle(close=110.0, timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc)),
        make_candle(close=120.0, timestamp=datetime(2026, 1, 3, tzinfo=timezone.utc)),
    ]


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

def test_run_returns_backtest_result(
    hold_runner: BotRunner, three_candles: list[Candle]
) -> None:
    result = Backtester(hold_runner).run(three_candles)
    assert isinstance(result, BacktestResult)


# ---------------------------------------------------------------------------
# bot_id propagation
# ---------------------------------------------------------------------------

def test_result_bot_id_matches_runner(
    hold_runner: BotRunner, three_candles: list[Candle]
) -> None:
    result = Backtester(hold_runner).run(three_candles)
    assert result.bot_id == "backtester-bot"


# ---------------------------------------------------------------------------
# trade_records
# ---------------------------------------------------------------------------

def test_trade_records_exclude_hold_decisions(
    hold_runner: BotRunner, three_candles: list[Candle]
) -> None:
    result = Backtester(hold_runner).run(three_candles)
    assert result.trade_records == []
    assert result.total_trades == 0


def test_trade_records_empty_for_empty_candles() -> None:
    runner = BotRunner("bot1", AlwaysHoldStrategy(), starting_cash=500.0)
    result = Backtester(runner).run([])
    assert result.trade_records == []


def test_equity_series_includes_hold_candles_and_reaches_final_pnl(
    three_candles: list[Candle],
) -> None:
    class _BuyThenHold(AlwaysHoldStrategy):
        def on_candle(self, candles: list[Candle], portfolio: Portfolio) -> Action:
            if len(candles) == 1:
                return Action(action_type="BUY", symbol=candles[-1].symbol, quantity=1.0, reason="buy")
            return super().on_candle(candles, portfolio)

    result = Backtester(BotRunner("bot1", _BuyThenHold(), starting_cash=1_000.0)).run(three_candles)
    response = _to_response(result)

    assert [r.action_type for r in result.trade_records] == ["BUY"]
    assert [r.action_type for r in result.equity_records] == ["BUY", "HOLD", "HOLD"]
    assert [r.timestamp for r in result.equity_records] == [c.timestamp for c in three_candles]
    assert result.equity_records[-1].pnl == pytest.approx(result.final_pnl)
    assert result.final_pnl == pytest.approx(20.0)
    assert [r.pnl for r in response.equity_records] == pytest.approx([0.0, 10.0, 20.0])


# ---------------------------------------------------------------------------
# total_trades — only BUY and SELL count, HOLD does not
# ---------------------------------------------------------------------------

def test_total_trades_counts_buy_and_sell(three_candles: list[Candle]) -> None:
    # BuyThenSellStrategy: BUY tick0, SELL tick1, SELL tick2 (held=0, no-op but still SELL type)
    runner = BotRunner("bot1", BuyThenSellStrategy(), starting_cash=1000.0)
    result = Backtester(runner).run(three_candles)
    assert result.total_trades == 3


def test_total_trades_zero_when_all_hold(
    hold_runner: BotRunner, three_candles: list[Candle]
) -> None:
    result = Backtester(hold_runner).run(three_candles)
    assert result.total_trades == 0


def test_total_trades_zero_for_empty_candles() -> None:
    runner = BotRunner("bot1", AlwaysHoldStrategy(), starting_cash=1000.0)
    result = Backtester(runner).run([])
    assert result.total_trades == 0


# ---------------------------------------------------------------------------
# start_cash / end_cash
# ---------------------------------------------------------------------------

def test_start_cash_matches_runner_starting_cash(three_candles: list[Candle]) -> None:
    runner = BotRunner("bot1", AlwaysHoldStrategy(), starting_cash=5000.0)
    result = Backtester(runner).run(three_candles)
    assert result.start_cash == pytest.approx(5000.0)


def test_end_cash_equals_start_cash_for_all_hold(
    hold_runner: BotRunner, three_candles: list[Candle]
) -> None:
    result = Backtester(hold_runner).run(three_candles)
    assert result.end_cash == pytest.approx(1000.0)


def test_end_cash_reflects_last_trade_record(three_candles: list[Candle]) -> None:
    runner = BotRunner("bot1", BuyThenSellStrategy(), starting_cash=1000.0)
    result = Backtester(runner).run(three_candles)
    assert result.end_cash == pytest.approx(result.trade_records[-1].cash_after)


def test_end_cash_equals_start_cash_when_no_candles() -> None:
    runner = BotRunner("bot1", AlwaysHoldStrategy(), starting_cash=2000.0)
    result = Backtester(runner).run([])
    assert result.end_cash == pytest.approx(2000.0)


# ---------------------------------------------------------------------------
# final_pnl
# ---------------------------------------------------------------------------

def test_final_pnl_zero_for_hold_no_positions(
    hold_runner: BotRunner, three_candles: list[Candle]
) -> None:
    result = Backtester(hold_runner).run(three_candles)
    assert result.final_pnl == pytest.approx(0.0)


def test_final_pnl_zero_when_no_candles() -> None:
    runner = BotRunner("bot1", AlwaysHoldStrategy(), starting_cash=1000.0)
    result = Backtester(runner).run([])
    assert result.final_pnl == pytest.approx(0.0)


def test_final_pnl_positive_on_profitable_run() -> None:
    candles = [
        make_candle(close=100.0, timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        make_candle(close=200.0, timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc)),
    ]
    # BUY@100 then SELL@200 → pnl = +100
    runner = BotRunner("bot1", BuyThenSellStrategy(), starting_cash=1000.0)
    result = Backtester(runner).run(candles)
    assert result.final_pnl == pytest.approx(100.0)


def test_final_pnl_matches_last_trade_record_pnl(three_candles: list[Candle]) -> None:
    runner = BotRunner("bot1", BuyThenSellStrategy(), starting_cash=1000.0)
    result = Backtester(runner).run(three_candles)
    assert result.final_pnl == pytest.approx(result.trade_records[-1].pnl)


# ---------------------------------------------------------------------------
# Blindness guarantee — Backtester must not reveal it is a backtest
# ---------------------------------------------------------------------------

def test_backtester_does_not_inject_future_data(three_candles: list[Candle]) -> None:
    """Strategy window must grow 1→2→3, proving no future data is injected."""
    class _WindowSpy(AlwaysHoldStrategy):
        def __init__(self) -> None:
            self.sizes: list[int] = []

        def on_candle(self, candles: list[Candle], portfolio: Portfolio) -> Action:
            self.sizes.append(len(candles))
            return super().on_candle(candles, portfolio)

    spy = _WindowSpy()
    runner = BotRunner("bot1", spy, starting_cash=1000.0)
    Backtester(runner).run(three_candles)
    assert spy.sizes == [1, 2, 3]
