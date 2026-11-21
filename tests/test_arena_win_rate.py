"""Legacy win-rate accounting for multiple entries and partial exits."""
from datetime import datetime, timezone

import pytest

from backend.api.arena import _compute_win_rate
from backend.engine.models import BacktestResult, TradeRecord


def record(action: str, qty: float, price: float, symbol: str = "AAA") -> TradeRecord:
    return TradeRecord(
        bot_id="bot",
        symbol=symbol,
        action_type=action,
        quantity=qty,
        price=price,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        reason="test",
        cash_after=0.0,
        pnl=0.0,
    )


def result(trades: list[TradeRecord]) -> BacktestResult:
    return BacktestResult(
        bot_id="bot",
        total_trades=len(trades),
        final_pnl=0.0,
        trade_records=trades,
        start_cash=1_000.0,
        end_cash=1_000.0,
        sharpe_ratio=0.0,
        max_drawdown=0.0,
    )


def test_multiple_buys_and_partial_sells_use_weighted_remaining_cost_basis() -> None:
    trades = [
        record("BUY", 1, 100),
        record("BUY", 3, 200),      # Average cost: 175.
        record("SELL", 1, 180),     # Win; 3 units remain at cost 175.
        record("SELL", 0, 999),     # No fill, must not enter denominator.
        record("SELL", 1, 160),     # Loss; 2 units remain at cost 175.
        record("BUY", 2, 50),       # New average of remaining 4 units: 112.5.
        record("SELL", 2, 110),     # Loss.
        record("SELL", 1, 120),     # Win.
    ]

    assert _compute_win_rate(result(trades[:3])) == pytest.approx(1.0)
    assert _compute_win_rate(result(trades[:5])) == pytest.approx(0.5)
    assert _compute_win_rate(result(trades[:7])) == pytest.approx(1 / 3)
    assert _compute_win_rate(result(trades)) == pytest.approx(0.5)


def test_symbols_have_independent_cost_bases() -> None:
    trades = [
        record("BUY", 1, 100, "AAA"),
        record("BUY", 1, 500, "BBB"),
        record("SELL", 1, 110, "AAA"),
        record("SELL", 1, 480, "BBB"),
    ]
    assert _compute_win_rate(result(trades)) == pytest.approx(0.5)


def test_sell_without_holdings_and_zero_fills_are_not_counted() -> None:
    trades = [record("SELL", 10, 100), record("BUY", 0, 100), record("SELL", 0, 100)]
    assert _compute_win_rate(result(trades)) == 0.0
