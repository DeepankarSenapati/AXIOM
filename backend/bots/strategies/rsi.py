import backend.config as settings
from backend.bots.strategies.base import BaseStrategy
from backend.engine.models import Action, Candle, Portfolio


class RSIStrategy(BaseStrategy):
    """
    Buys when RSI drops below the oversold threshold.
    Sells when RSI rises above the overbought threshold.
    Holds otherwise.
    """

    def __init__(
        self,
        symbol: str,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
    ) -> None:
        self.symbol = symbol
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def on_candle(self, candles: list[Candle], portfolio: Portfolio) -> Action:
        # Need at least period + 1 candles to compute one RSI value
        if len(candles) < self.period + 1:
            return Action(
                action_type="HOLD",
                symbol=self.symbol,
                quantity=0.0,
                reason=f"Insufficient history: need {self.period + 1} candles, have {len(candles)}",
            )

        rsi = self._compute_rsi([c.close for c in candles])
        held = portfolio.positions.get(self.symbol, 0.0)

        if rsi < self.oversold:
            quantity = (portfolio.cash * settings.MAX_POSITION_SIZE) / candles[-1].close
            if quantity <= 0:
                return Action(
                    action_type="HOLD",
                    symbol=self.symbol,
                    quantity=0.0,
                    reason=f"RSI={rsi:.2f} oversold signal but insufficient cash to buy",
                )
            return Action(
                action_type="BUY",
                symbol=self.symbol,
                quantity=quantity,
                reason=f"RSI={rsi:.2f} below oversold threshold {self.oversold}",
            )

        if rsi > self.overbought:
            if held > 0:
                return Action(
                    action_type="SELL",
                    symbol=self.symbol,
                    quantity=held,
                    reason=f"RSI={rsi:.2f} above overbought threshold {self.overbought}",
                )
            return Action(
                action_type="HOLD",
                symbol=self.symbol,
                quantity=0.0,
                reason=f"RSI={rsi:.2f} above overbought threshold {self.overbought} but no position to sell",
            )

        return Action(
            action_type="HOLD",
            symbol=self.symbol,
            quantity=0.0,
            reason=f"RSI={rsi:.2f} within neutral range [{self.oversold}, {self.overbought}]",
        )

    def _compute_rsi(self, closes: list[float]) -> float:
        """RSI using simple mean gains and losses over the latest period."""
        window = closes[-(self.period + 1) :]
        gains: list[float] = []
        losses: list[float] = []

        for i in range(1, len(window)):
            delta = window[i] - window[i - 1]
            if delta >= 0:
                gains.append(delta)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(delta))

        avg_gain = sum(gains) / self.period
        avg_loss = sum(losses) / self.period

        if avg_loss == 0.0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))
