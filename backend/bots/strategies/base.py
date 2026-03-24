from abc import ABC, abstractmethod

from backend.engine.models import Action, Candle, Portfolio


class BaseStrategy(ABC):
    @abstractmethod
    def on_candle(self, candles: list[Candle], portfolio: Portfolio) -> Action:
        """
        Called on every tick. `candles` is the full history up to and including
        the current candle (candles[-1] is the latest). Future candles are never
        included — the strategy is always blind to what comes next.
        """
        raise NotImplementedError
