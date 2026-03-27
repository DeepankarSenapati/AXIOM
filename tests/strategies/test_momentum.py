"""Tests for backend/bots/strategies/momentum.py"""
from datetime import datetime, timezone

import pytest

import backend.config as settings
from backend.bots.strategies.momentum import MomentumStrategy
from backend.bots.registry import STRATEGY_MAP
from backend.engine.models import Candle, Portfolio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SYMBOL = "BTC/USD"


def _portfolio(cash: float = 10_000.0, held: float = 0.0) -> Portfolio:
    positions = {SYMBOL: held} if held > 0 else {}
    return Portfolio(cash=cash, positions=positions, pnl=0.0)


def _candle(close: float, i: int = 0) -> Candle:
    return Candle(
        symbol=SYMBOL,
        timestamp=datetime(2026, 1, 1 + i, tzinfo=timezone.utc),
        open=close, high=close + 1.0, low=close - 1.0,
        close=close, volume=1_000.0,
    )


def _candles(closes: list[float]) -> list[Candle]:
    return [_candle(c, i) for i, c in enumerate(closes)]


def _strategy(
    window: int = 5,
    threshold: float = 0.02,
    stop_loss: float = 0.03,
) -> MomentumStrategy:
    return MomentumStrategy(symbol=SYMBOL, window=window, threshold=threshold, stop_loss=stop_loss)


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------

def test_invalid_window_raises() -> None:
    with pytest.raises(ValueError, match="window"):
        MomentumStrategy(symbol=SYMBOL, window=1)


def test_invalid_threshold_raises() -> None:
    with pytest.raises(ValueError, match="threshold"):
        MomentumStrategy(symbol=SYMBOL, threshold=0.0)


def test_invalid_stop_loss_raises() -> None:
    with pytest.raises(ValueError, match="stop_loss"):
        MomentumStrategy(symbol=SYMBOL, stop_loss=-0.01)


# ---------------------------------------------------------------------------
# HOLD — insufficient history
# ---------------------------------------------------------------------------

def test_hold_when_fewer_candles_than_window() -> None:
    s = _strategy(window=5)
    result = s.on_candle(_candles([100.0, 101.0, 102.0, 103.0]), _portfolio())
    assert result.action_type == "HOLD"


def test_hold_reason_mentions_required_count() -> None:
    s = _strategy(window=5)
    result = s.on_candle(_candles([100.0] * 3), _portfolio())
    assert "5" in result.reason
    assert "3" in result.reason


def test_hold_when_exactly_window_minus_one_candles() -> None:
    s = _strategy(window=5)
    result = s.on_candle(_candles([100.0] * 4), _portfolio())
    assert result.action_type == "HOLD"


# ---------------------------------------------------------------------------
# HOLD — price change below threshold
# ---------------------------------------------------------------------------

def test_hold_when_gain_below_threshold() -> None:
    s = _strategy(window=5, threshold=0.05)
    # +1% gain over 5 candles — below 5% threshold
    closes = [100.0, 100.2, 100.5, 100.8, 101.0]
    result = s.on_candle(_candles(closes), _portfolio())
    assert result.action_type == "HOLD"


def test_hold_when_price_flat() -> None:
    s = _strategy(window=5, threshold=0.02)
    result = s.on_candle(_candles([100.0] * 5), _portfolio())
    assert result.action_type == "HOLD"


def test_hold_when_price_falling() -> None:
    s = _strategy(window=5, threshold=0.02)
    closes = [100.0, 99.0, 98.0, 97.0, 96.0]
    result = s.on_candle(_candles(closes), _portfolio())
    assert result.action_type == "HOLD"


# ---------------------------------------------------------------------------
# BUY — momentum signal
# ---------------------------------------------------------------------------

def test_buy_when_price_rises_above_threshold() -> None:
    s = _strategy(window=5, threshold=0.02)
    # +4% gain over 5 candles — above 2% threshold
    closes = [100.0, 101.0, 102.0, 103.0, 104.0]
    result = s.on_candle(_candles(closes), _portfolio())
    assert result.action_type == "BUY"


def test_buy_at_exact_threshold() -> None:
    s = _strategy(window=5, threshold=0.02)
    closes = [100.0, 100.5, 101.0, 101.5, 102.0]  # exactly +2%
    result = s.on_candle(_candles(closes), _portfolio())
    assert result.action_type == "BUY"


def test_buy_quantity_uses_max_position_size() -> None:
    s = _strategy(window=5, threshold=0.02)
    closes = [100.0, 101.0, 102.0, 103.0, 104.0]
    cash = 10_000.0
    price = closes[-1]
    result = s.on_candle(_candles(closes), _portfolio(cash=cash))
    assert result.action_type == "BUY"
    assert result.quantity == pytest.approx((cash * settings.MAX_POSITION_SIZE) / price)


def test_buy_hold_when_cash_is_zero() -> None:
    s = _strategy(window=5, threshold=0.02)
    closes = [100.0, 101.0, 102.0, 103.0, 104.0]
    result = s.on_candle(_candles(closes), _portfolio(cash=0.0))
    assert result.action_type == "HOLD"


def test_buy_reason_mentions_gain_and_threshold() -> None:
    s = _strategy(window=5, threshold=0.02)
    closes = [100.0, 101.0, 102.0, 103.0, 104.0]
    result = s.on_candle(_candles(closes), _portfolio())
    assert "Momentum" in result.reason or "momentum" in result.reason.lower()
    assert "2.0%" in result.reason or "threshold" in result.reason


def test_buy_symbol_matches() -> None:
    s = _strategy(window=5, threshold=0.02)
    closes = [100.0, 101.0, 102.0, 103.0, 104.0]
    result = s.on_candle(_candles(closes), _portfolio())
    assert result.symbol == SYMBOL


# ---------------------------------------------------------------------------
# SELL — stop loss
# ---------------------------------------------------------------------------

def test_sell_when_stop_loss_triggered() -> None:
    s = _strategy(window=5, threshold=0.02, stop_loss=0.03)
    # First: trigger a BUY to set entry price at 104.0
    closes = [100.0, 101.0, 102.0, 103.0, 104.0]
    buy = s.on_candle(_candles(closes), _portfolio())
    assert buy.action_type == "BUY"
    # Now: price drops 5% below entry — exceeds 3% stop loss
    entry = closes[-1]
    drop_price = round(entry * 0.94, 4)
    new_closes = closes + [drop_price]
    result = s.on_candle(_candles(new_closes), _portfolio(held=buy.quantity))
    assert result.action_type == "SELL"


def test_sell_quantity_equals_full_position() -> None:
    s = _strategy(window=5, threshold=0.02, stop_loss=0.03)
    closes = [100.0, 101.0, 102.0, 103.0, 104.0]
    buy = s.on_candle(_candles(closes), _portfolio())
    entry = closes[-1]
    drop_price = round(entry * 0.94, 4)
    new_closes = closes + [drop_price]
    held = buy.quantity
    result = s.on_candle(_candles(new_closes), _portfolio(held=held))
    assert result.quantity == pytest.approx(held)


def test_no_sell_when_drop_below_stop_loss_threshold() -> None:
    s = _strategy(window=5, threshold=0.02, stop_loss=0.05)
    closes = [100.0, 101.0, 102.0, 103.0, 104.0]
    buy = s.on_candle(_candles(closes), _portfolio())
    assert buy.action_type == "BUY"
    # Drop only 2% — below the 5% stop loss
    entry = closes[-1]
    small_drop = round(entry * 0.98, 4)
    new_closes = closes + [small_drop]
    result = s.on_candle(_candles(new_closes), _portfolio(held=buy.quantity))
    assert result.action_type != "SELL"


def test_no_sell_without_position() -> None:
    s = _strategy(window=5, threshold=0.02, stop_loss=0.03)
    # Inject entry price manually to simulate stale state, but held=0
    s._entry_price = 104.0
    closes = [100.0, 101.0, 102.0, 103.0, 98.0]
    result = s.on_candle(_candles(closes), _portfolio(held=0.0))
    assert result.action_type != "SELL"


def test_sell_reason_mentions_stop_loss() -> None:
    s = _strategy(window=5, threshold=0.02, stop_loss=0.03)
    closes = [100.0, 101.0, 102.0, 103.0, 104.0]
    buy = s.on_candle(_candles(closes), _portfolio())
    entry = closes[-1]
    drop_price = round(entry * 0.94, 4)
    new_closes = closes + [drop_price]
    result = s.on_candle(_candles(new_closes), _portfolio(held=buy.quantity))
    assert "stop" in result.reason.lower() or "Stop" in result.reason


# ---------------------------------------------------------------------------
# Strategy is blind — uses only past candles
# ---------------------------------------------------------------------------

def test_uses_only_window_candles_for_gain() -> None:
    """Gain is computed from candles[-window] to candles[-1], not from candle[0]."""
    s = _strategy(window=3, threshold=0.02)
    # First 5 candles: big rise then flat. Window of 3 = flat → HOLD
    closes = [100.0, 200.0, 201.0, 202.0, 203.0]
    # window=3: base=201.0, now=203.0 → +0.99% < 2% threshold
    result = s.on_candle(_candles(closes), _portfolio())
    assert result.action_type == "HOLD"


# ---------------------------------------------------------------------------
# Registry membership
# ---------------------------------------------------------------------------

def test_momentum_in_strategy_map() -> None:
    assert "momentum" in STRATEGY_MAP


def test_strategy_map_returns_momentum_class() -> None:
    assert STRATEGY_MAP["momentum"] is MomentumStrategy
