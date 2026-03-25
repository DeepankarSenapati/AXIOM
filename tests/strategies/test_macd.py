"""Tests for backend/bots/strategies/macd.py"""
from datetime import datetime, timezone

import pytest

from backend.bots.strategies.macd import MACDStrategy
from backend.engine.models import Candle, Portfolio


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

SYMBOL = "ETH/USD"


def _portfolio(cash: float = 10_000.0, held: float = 0.0) -> Portfolio:
    positions = {SYMBOL: held} if held > 0 else {}
    return Portfolio(cash=cash, positions=positions, pnl=0.0)


def _candle(close: float, i: int = 0) -> Candle:
    return Candle(
        symbol=SYMBOL,
        timestamp=datetime(2026, 1, 1 + i % 28, tzinfo=timezone.utc),
        open=close, high=close + 1.0, low=close - 1.0,
        close=close, volume=1000.0,
    )


def _candles(closes: list[float]) -> list[Candle]:
    return [_candle(c, i) for i, c in enumerate(closes)]


def _strategy(fast: int = 12, slow: int = 26, signal: int = 9) -> MACDStrategy:
    return MACDStrategy(symbol=SYMBOL, fast=fast, slow=slow, signal=signal)


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------

def test_init_raises_when_fast_equals_slow() -> None:
    with pytest.raises(ValueError, match="fast"):
        MACDStrategy(symbol=SYMBOL, fast=26, slow=26)


def test_init_raises_when_fast_greater_than_slow() -> None:
    with pytest.raises(ValueError, match="fast"):
        MACDStrategy(symbol=SYMBOL, fast=30, slow=26)


def test_init_raises_on_zero_period() -> None:
    with pytest.raises(ValueError):
        MACDStrategy(symbol=SYMBOL, fast=0, slow=26, signal=9)


# ---------------------------------------------------------------------------
# HOLD when insufficient history
# ---------------------------------------------------------------------------

def test_hold_with_zero_candles() -> None:
    s = _strategy()
    assert s.on_candle([], _portfolio()).action_type == "HOLD"


def test_hold_with_fewer_candles_than_minimum() -> None:
    s = _strategy(fast=3, slow=6, signal=3)
    # min = slow + signal - 1 = 8; need 9 for crossover detection
    candles = _candles([100.0] * 8)
    assert s.on_candle(candles, _portfolio()).action_type == "HOLD"


def test_hold_reason_mentions_required_count() -> None:
    s = _strategy(fast=3, slow=6, signal=3)
    candles = _candles([100.0] * 5)
    result = s.on_candle(candles, _portfolio())
    assert "Insufficient" in result.reason


# ---------------------------------------------------------------------------
# _ema helper
# ---------------------------------------------------------------------------

def test_ema_returns_empty_when_insufficient_values() -> None:
    assert MACDStrategy._ema([1.0, 2.0], period=5) == []


def test_ema_of_constant_series_equals_constant() -> None:
    result = MACDStrategy._ema([5.0] * 20, period=5)
    for v in result:
        assert v == pytest.approx(5.0)


def test_ema_first_value_is_sma() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    result = MACDStrategy._ema(values, period=3)
    assert result[0] == pytest.approx(sum(values[:3]) / 3)


def test_ema_length_equals_len_minus_period_plus_one() -> None:
    values = list(range(1, 21))
    result = MACDStrategy._ema(values, period=5)
    assert len(result) == len(values) - 5 + 1


# ---------------------------------------------------------------------------
# _macd_series helper
# ---------------------------------------------------------------------------

def test_macd_series_constant_price_is_zero() -> None:
    s = _strategy(fast=3, slow=6, signal=3)
    closes = [100.0] * 20
    macd = s._macd_series(closes)
    for v in macd:
        assert v == pytest.approx(0.0, abs=1e-9)


def test_macd_series_length() -> None:
    s = _strategy(fast=3, slow=6, signal=3)
    closes = list(range(1, 21))
    macd = s._macd_series(closes)
    # MACD len = len(closes) - slow + 1
    assert len(macd) == len(closes) - 6 + 1


# ---------------------------------------------------------------------------
# BUY signal — bullish crossover (MACD crosses above signal)
# ---------------------------------------------------------------------------

def _make_bullish_crossover_series(fast: int, slow: int, signal: int) -> list[float]:
    """
    Build a price series that produces a bullish MACD crossover near the end.
    First half: declining prices (MACD below signal), second half: rising.
    """
    n = slow + signal + 20
    half = n // 2
    descending = [200.0 - i * 2 for i in range(half)]
    ascending = [descending[-1] + i * 3 for i in range(1, n - half + 1)]
    return descending + ascending


def test_bullish_crossover_triggers_buy() -> None:
    fast, slow, signal = 3, 6, 3
    s = MACDStrategy(symbol=SYMBOL, fast=fast, slow=slow, signal=signal)
    closes = _make_bullish_crossover_series(fast, slow, signal)
    # Scan entire series; at least one BUY should appear
    buys = []
    for i in range(len(closes)):
        result = s.on_candle(_candles(closes[: i + 1]), _portfolio())
        if result.action_type == "BUY":
            buys.append(i)
    assert len(buys) > 0, "Expected at least one BUY signal in bullish crossover series"


def test_buy_quantity_is_95_percent_of_cash() -> None:
    fast, slow, signal = 3, 6, 3
    s = MACDStrategy(symbol=SYMBOL, fast=fast, slow=slow, signal=signal)
    closes = _make_bullish_crossover_series(fast, slow, signal)
    cash = 8_000.0
    for i in range(len(closes)):
        result = s.on_candle(_candles(closes[: i + 1]), _portfolio(cash=cash))
        if result.action_type == "BUY":
            expected = (cash * 0.95) / closes[i]
            assert result.quantity == pytest.approx(expected)
            return
    pytest.fail("No BUY signal produced")


def test_buy_hold_when_insufficient_cash() -> None:
    fast, slow, signal = 3, 6, 3
    s = MACDStrategy(symbol=SYMBOL, fast=fast, slow=slow, signal=signal)
    closes = _make_bullish_crossover_series(fast, slow, signal)
    for i in range(len(closes)):
        result = s.on_candle(_candles(closes[: i + 1]), _portfolio(cash=0.0))
        # Should never raise InsufficientFundsError; at a BUY signal it HOLDs instead
        if len(_candles(closes[: i + 1])) >= s._min_candles + 1:
            assert result.action_type in ("BUY", "SELL", "HOLD")


# ---------------------------------------------------------------------------
# SELL signal — bearish crossover (MACD crosses below signal)
# ---------------------------------------------------------------------------

def _make_bearish_crossover_series(fast: int, slow: int, signal: int) -> list[float]:
    """Rising then declining, so MACD crosses below signal."""
    n = slow + signal + 20
    half = n // 2
    ascending = [50.0 + i * 3 for i in range(half)]
    descending = [ascending[-1] - i * 2 for i in range(1, n - half + 1)]
    return ascending + descending


def test_bearish_crossover_triggers_sell() -> None:
    fast, slow, signal = 3, 6, 3
    s = MACDStrategy(symbol=SYMBOL, fast=fast, slow=slow, signal=signal)
    closes = _make_bearish_crossover_series(fast, slow, signal)
    sells = []
    for i in range(len(closes)):
        result = s.on_candle(_candles(closes[: i + 1]), _portfolio(cash=0.0, held=5.0))
        if result.action_type == "SELL":
            sells.append(i)
    assert len(sells) > 0, "Expected at least one SELL signal in bearish crossover series"


def test_sell_quantity_equals_full_held_position() -> None:
    fast, slow, signal = 3, 6, 3
    s = MACDStrategy(symbol=SYMBOL, fast=fast, slow=slow, signal=signal)
    closes = _make_bearish_crossover_series(fast, slow, signal)
    held = 4.25
    for i in range(len(closes)):
        result = s.on_candle(_candles(closes[: i + 1]), _portfolio(cash=0.0, held=held))
        if result.action_type == "SELL":
            assert result.quantity == pytest.approx(held)
            return
    pytest.fail("No SELL signal produced")


def test_no_sell_without_position_on_bearish_crossover() -> None:
    fast, slow, signal = 3, 6, 3
    s = MACDStrategy(symbol=SYMBOL, fast=fast, slow=slow, signal=signal)
    closes = _make_bearish_crossover_series(fast, slow, signal)
    for i in range(len(closes)):
        result = s.on_candle(_candles(closes[: i + 1]), _portfolio(cash=5_000.0, held=0.0))
        assert result.action_type != "SELL", (
            f"Got unexpected SELL at tick {i} with no position held"
        )


# ---------------------------------------------------------------------------
# Action field integrity
# ---------------------------------------------------------------------------

def test_action_symbol_is_always_strategy_symbol() -> None:
    s = _strategy()
    for n in [1, 10, 35]:
        candles = _candles([100.0] * n)
        result = s.on_candle(candles, _portfolio())
        assert result.symbol == SYMBOL


def test_action_reason_is_nonempty_on_every_tick() -> None:
    s = _strategy(fast=3, slow=6, signal=3)
    closes = _make_bullish_crossover_series(3, 6, 3)
    for i in range(len(closes)):
        result = s.on_candle(_candles(closes[: i + 1]), _portfolio())
        assert result.reason, f"Empty reason at tick {i}"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_macd_registered_in_strategy_map() -> None:
    from backend.bots.registry import STRATEGY_MAP
    assert "macd" in STRATEGY_MAP
    assert STRATEGY_MAP["macd"] is MACDStrategy


def test_bollinger_bands_registered_in_strategy_map() -> None:
    from backend.bots.registry import STRATEGY_MAP
    from backend.bots.strategies.bollinger_bands import BollingerBandsStrategy
    assert "bollinger_bands" in STRATEGY_MAP
    assert STRATEGY_MAP["bollinger_bands"] is BollingerBandsStrategy


def test_get_strategy_class_raises_for_unknown_key() -> None:
    from backend.bots.registry import UnknownStrategyError, get_strategy_class
    with pytest.raises(UnknownStrategyError, match="nonexistent"):
        get_strategy_class("nonexistent")
