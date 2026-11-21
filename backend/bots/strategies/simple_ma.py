import backend.config as settings
from backend.bots.strategies.base import BaseStrategy
from backend.engine.models import Action, Candle, Portfolio


class SimpleMovingAverageStrategy(BaseStrategy):
    """
    Buys when the short-period MA crosses above the long-period MA (golden cross).
    Sells when the short-period MA crosses below the long-period MA (death cross).
    Holds otherwise.
    """

    def __init__(
        self,
        symbol: str,
        short_window: int = 5,
        long_window: int = 20,
    ) -> None:
        self.symbol = symbol
        self.short_window = short_window
        self.long_window = long_window

    def on_candle(self, candles: list[Candle], portfolio: Portfolio) -> Action:
        if len(candles) < self.long_window:
            return Action(
                action_type="HOLD",
                symbol=self.symbol,
                quantity=0.0,
                reason=f"Insufficient history: need {self.long_window} candles, have {len(candles)}",
            )

        closes = [c.close for c in candles]
        short_ma = sum(closes[-self.short_window :]) / self.short_window
        long_ma = sum(closes[-self.long_window :]) / self.long_window

        # Previous MAs (one candle back) to detect crossover
        if len(candles) >= self.long_window + 1:
            prev_closes = closes[:-1]
            prev_short_ma = sum(prev_closes[-self.short_window :]) / self.short_window
            prev_long_ma = sum(prev_closes[-self.long_window :]) / self.long_window
        else:
            prev_short_ma = short_ma
            prev_long_ma = long_ma

        held = portfolio.positions.get(self.symbol, 0.0)

        # Golden cross: short crosses above long
        if prev_short_ma <= prev_long_ma and short_ma > long_ma:
            quantity = (portfolio.cash * settings.MAX_POSITION_SIZE) / candles[-1].close
            if quantity <= 0:
                return Action(
                    action_type="HOLD",
                    symbol=self.symbol,
                    quantity=0.0,
                    reason="Golden cross signal but insufficient cash to buy",
                )
            return Action(
                action_type="BUY",
                symbol=self.symbol,
                quantity=quantity,
                reason=f"Golden cross: short_ma={short_ma:.4f} crossed above long_ma={long_ma:.4f}",
            )

        # Death cross: short crosses below long
        if prev_short_ma >= prev_long_ma and short_ma < long_ma:
            if held > 0:
                return Action(
                    action_type="SELL",
                    symbol=self.symbol,
                    quantity=held,
                    reason=f"Death cross: short_ma={short_ma:.4f} crossed below long_ma={long_ma:.4f}",
                )
            return Action(
                action_type="HOLD",
                symbol=self.symbol,
                quantity=0.0,
                reason=f"Death cross: short_ma={short_ma:.4f} crossed below long_ma={long_ma:.4f} but no position to sell",
            )

        return Action(
            action_type="HOLD",
            symbol=self.symbol,
            quantity=0.0,
            reason=f"No crossover: short_ma={short_ma:.4f}, long_ma={long_ma:.4f}",
        )
