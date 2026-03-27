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


class UnknownStrategyError(Exception):
    pass


def get_strategy_class(key: str) -> type[BaseStrategy]:
    cls = STRATEGY_MAP.get(key)
    if cls is None:
        raise UnknownStrategyError(
            f"Unknown strategy '{key}'. Available: {sorted(STRATEGY_MAP)}"
        )
    return cls
