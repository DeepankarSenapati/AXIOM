"""Tests for backend/bots/strategies/bollinger_bands.py"""
import math
from datetime import datetime, timezone

import pytest

from backend.bots.strategies.bollinger_bands import BollingerBandsStrategy
from backend.engine.models import Action, Candle, Portfolio


# ---------------------------------------------------------------------------
# Fixtures / helpers
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
        close=close, volume=1000.0,
    )


def _flat_candles(price: float, n: int) -> list[Candle]:
    return [_candle(price, i) for i in range(n)]


def _strategy(window: int = 20, num_std: float = 2.0) -> BollingerBandsStrategy:
    return BollingerBandsStrategy(symbol=SYMBOL, window=window, num_std=num_std)


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------

def test_init_raises_on_window_less_than_two() -> None:
    with pytest.raises(ValueError, match="window"):
        BollingerBandsStrategy(symbol=SYMBOL, window=1)


def test_init_raises_on_nonpositive_num_std() -> None:
    with pytest.raises(ValueError, match="num_std"):
        BollingerBandsStrategy(symbol=SYMBOL, num_std=0.0)


# ---------------------------------------------------------------------------
# HOLD when insufficient history
# ---------------------------------------------------------------------------

def test_hold_when_fewer_candles_than_window() -> None:
    s = _strategy(window=20)
    candles = _flat_candles(100.0, 19)
    record = s.on_candle(candles, _portfolio())
    assert record.action_type == "HOLD"


def test_hold_reason_mentions_required_count() -> None:
    s = _strategy(window=20)
    candles = _flat_candles(100.0, 10)
    record = s.on_candle(candles, _portfolio())
    assert "20" in record.reason


def test_hold_on_exactly_window_minus_one_candles() -> None:
    s = _strategy(window=5)
    candles = _flat_candles(100.0, 4)
    assert s.on_candle(candles, _portfolio()).action_type == "HOLD"


# ---------------------------------------------------------------------------
# _bands helper
# ---------------------------------------------------------------------------

def test_bands_flat_price_has_zero_std() -> None:
    s = _strategy(window=5)
    lower, middle, upper = s._bands([100.0] * 10)
    assert middle == pytest.approx(100.0)
    assert lower == pytest.approx(100.0)
    assert upper == pytest.approx(100.0)


def test_bands_symmetry() -> None:
    s = _strategy(window=10, num_std=2.0)
    closes = [float(i) for i in range(10)]
    lower, middle, upper = s._bands(closes)
    assert middle - lower == pytest.approx(upper - middle, rel=1e-9)


def test_bands_width_scales_with_num_std() -> None:
    closes = [float(i) for i in range(20)]
    lower1, mid1, upper1 = BollingerBandsStrategy(symbol=SYMBOL, window=20, num_std=1.0)._bands(closes)
    lower2, mid2, upper2 = BollingerBandsStrategy(symbol=SYMBOL, window=20, num_std=2.0)._bands(closes)
    assert (upper2 - lower2) == pytest.approx(2 * (upper1 - lower1), rel=1e-9)


def test_bands_uses_only_last_window_candles() -> None:
    """Adding irrelevant old candles should not affect bands computed on the window."""
    s = _strategy(window=5)
    tail = [100.0, 101.0, 99.0, 100.5, 100.2]
    bands_short = s._bands(tail)
    bands_long = s._bands([999.0, 1.0, 500.0] + tail)
    assert bands_short == pytest.approx(bands_long)


# ---------------------------------------------------------------------------
# BUY signal
# ---------------------------------------------------------------------------

def _candles_with_spike_down(window: int, base: float, spike: float) -> list[Candle]:
    """window flat candles followed by one candle at spike price."""
    return _flat_candles(base, window) + [_candle(spike, window)]


def test_buy_when_price_touches_lower_band() -> None:
    """Bands are computed from the previous window candles; current candle triggers the signal."""
    s = _strategy(window=10, num_std=2.0)
    history = [100.0, 102.0, 98.0, 101.0, 99.0,
               100.0, 102.0, 98.0, 101.0, 99.0]
    lower, _, _ = s._bands(history)
    # 10 history candles + 1 boundary candle = 11 total (window+1)
    candles = [_candle(history[i], i) for i in range(len(history))]
    candles.append(_candle(lower, len(history)))
    result = s.on_candle(candles, _portfolio(cash=10_000.0))
    assert result.action_type == "BUY"


def test_buy_quantity_uses_95_percent_of_cash() -> None:
    s = _strategy(window=10, num_std=2.0)
    history = [100.0, 102.0, 98.0, 101.0, 99.0,
               100.0, 102.0, 98.0, 101.0, 99.0]
    lower, _, _ = s._bands(history)
    candles = [_candle(history[i], i) for i in range(len(history))]
    candles.append(_candle(lower, len(history)))
    cash = 10_000.0
    result = s.on_candle(candles, _portfolio(cash=cash))
    assert result.quantity == pytest.approx((cash * 0.95) / lower)


def test_buy_hold_when_cash_is_zero() -> None:
    s = _strategy(window=10, num_std=2.0)
    history = [100.0, 102.0, 98.0, 101.0, 99.0,
               100.0, 102.0, 98.0, 101.0, 99.0]
    lower, _, _ = s._bands(history)
    candles = [_candle(history[i], i) for i in range(len(history))]
    candles.append(_candle(lower, len(history)))
    result = s.on_candle(candles, _portfolio(cash=0.0))
    assert result.action_type == "HOLD"


# ---------------------------------------------------------------------------
# SELL signal
# ---------------------------------------------------------------------------

def test_sell_when_price_touches_upper_band() -> None:
    s = _strategy(window=10, num_std=2.0)
    history = [100.0, 102.0, 98.0, 101.0, 99.0,
               100.0, 102.0, 98.0, 101.0, 99.0]
    _, _, upper = s._bands(history)
    candles = [_candle(history[i], i) for i in range(len(history))]
    candles.append(_candle(upper, len(history)))
    result = s.on_candle(candles, _portfolio(cash=0.0, held=2.0))
    assert result.action_type == "SELL"


def test_sell_quantity_equals_full_position() -> None:
    s = _strategy(window=10, num_std=2.0)
    history = [100.0, 102.0, 98.0, 101.0, 99.0,
               100.0, 102.0, 98.0, 101.0, 99.0]
    _, _, upper = s._bands(history)
    candles = [_candle(history[i], i) for i in range(len(history))]
    candles.append(_candle(upper, len(history)))
    held = 3.5
    result = s.on_candle(candles, _portfolio(cash=0.0, held=held))
    assert result.quantity == pytest.approx(held)


def test_no_sell_when_upper_band_touched_but_no_position() -> None:
    s = _strategy(window=10, num_std=2.0)
    closes = [100.0, 102.0, 98.0, 101.0, 99.0,
              100.0, 102.0, 98.0, 101.0, 99.0]
    _, _, upper = s._bands(closes)
    candles = [_candle(closes[i], i) for i in range(len(closes))]
    candles[-1] = _candle(upper, len(closes) - 1)
    result = s.on_candle(candles, _portfolio(cash=5_000.0, held=0.0))
    # With no position, upper touch should not SELL
    assert result.action_type != "SELL"


# ---------------------------------------------------------------------------
# HOLD in neutral zone
# ---------------------------------------------------------------------------

def test_hold_when_price_between_bands() -> None:
    s = _strategy(window=10, num_std=2.0)
    closes = [100.0, 102.0, 98.0, 101.0, 99.0,
              100.0, 102.0, 98.0, 101.0, 99.0]
    lower, middle, upper = s._bands(closes)
    # Middle price is strictly between bands (when std > 0)
    candles = [_candle(closes[i], i) for i in range(len(closes))]
    candles[-1] = _candle(middle, len(closes) - 1)
    result = s.on_candle(candles, _portfolio())
    assert result.action_type == "HOLD"


# ---------------------------------------------------------------------------
# Action fields
# ---------------------------------------------------------------------------

def test_action_symbol_matches_strategy_symbol() -> None:
    s = _strategy(window=5)
    candles = _flat_candles(100.0, 5)
    result = s.on_candle(candles, _portfolio())
    assert result.symbol == SYMBOL


def test_action_reason_is_nonempty() -> None:
    s = _strategy(window=5)
    candles = _flat_candles(100.0, 3)
    result = s.on_candle(candles, _portfolio())
    assert result.reason
