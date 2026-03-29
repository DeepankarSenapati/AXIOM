"""
Central registry mapping strategy keys to their classes.

Any new strategy must be added here to be usable via the API and arena.
"""
from backend.bots.strategies.base import BaseStrategy
from backend.bots.strategies.bollinger_bands import BollingerBandsStrategy
from backend.bots.strategies.macd import MACDStrategy
from backend.bots.strategies.momentum import MomentumStrategy
from backend.bots.strategies.rsi import RSIStrategy
from backend.bots.strategies.simple_ma import SimpleMovingAverageStrategy

STRATEGY_MAP: dict[str, type[BaseStrategy]] = {
    "simple_ma": SimpleMovingAverageStrategy,
    "rsi": RSIStrategy,
    "bollinger_bands": BollingerBandsStrategy,
    "macd": MACDStrategy,
    "momentum": MomentumStrategy,
}

STRATEGY_PARAMS: dict[str, dict] = {
    "simple_ma": {"short_window": 5, "long_window": 20},
    "rsi": {"period": 14, "oversold": 30, "overbought": 70},
    "bollinger_bands": {"window": 20, "num_std": 2.0},
    "macd": {"fast": 12, "slow": 26, "signal": 9},
    "momentum": {"window": 10, "threshold": 0.02, "stop_loss": 0.03},
}


class UnknownStrategyError(Exception):
    pass


def get_strategy_class(key: str) -> type[BaseStrategy]:
    cls = STRATEGY_MAP.get(key)
    if cls is None:
        raise UnknownStrategyError(
            f"Unknown strategy '{key}'. Available: {sorted(STRATEGY_MAP)}"
        )
    return cls


def get_strategy_defaults(strategy_name: str) -> dict:
    """Return a copy of the default parameter dict for the given strategy.

    Raises UnknownStrategyError if strategy_name is not registered.
    """
    if strategy_name not in STRATEGY_PARAMS:
        raise UnknownStrategyError(
            f"Unknown strategy '{strategy_name}'. Available: {sorted(STRATEGY_PARAMS)}"
        )
    return STRATEGY_PARAMS[strategy_name].copy()
