import math

import backend.config as settings
from backend.bots.strategies.base import BaseStrategy
from backend.engine.models import Action, Candle, Portfolio


class BollingerBandsStrategy(BaseStrategy):
    """
    Buys when price closes at or below the lower Bollinger Band.
    Sells the full position when price closes at or above the upper Bollinger Band.
    Holds otherwise or when the window has not yet been filled.
    """

    def __init__(
        self,
        symbol: str,
        window: int = 20,
        num_std: float = 2.0,
    ) -> None:
        if window < 2:
            raise ValueError(f"window must be >= 2, got {window}")
        if num_std <= 0:
            raise ValueError(f"num_std must be > 0, got {num_std}")
        self.symbol = symbol
        self.window = window
        self.num_std = num_std

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def on_candle(self, candles: list[Candle], portfolio: Portfolio) -> Action:
        if len(candles) <= self.window:
            return Action(
                action_type="HOLD",
                symbol=self.symbol,
                quantity=0.0,
                reason=f"Insufficient history: need {self.window} candles, have {len(candles)}",
            )

        closes = [c.close for c in candles]
        lower, middle, upper = self._bands(closes[:-1])
        price = closes[-1]
        held = portfolio.positions.get(self.symbol, 0.0)

        if price <= lower:
            quantity = (portfolio.cash * settings.MAX_POSITION_SIZE) / price
            if quantity <= 0:
                return Action(
                    action_type="HOLD",
                    symbol=self.symbol,
                    quantity=0.0,
                    reason="Lower band touch but insufficient cash to buy",
                )
            return Action(
                action_type="BUY",
                symbol=self.symbol,
                quantity=quantity,
                reason=f"Price {price:.4f} <= lower band {lower:.4f} (mid={middle:.4f})",
            )

        if price >= upper and held > 0:
            return Action(
                action_type="SELL",
                symbol=self.symbol,
                quantity=held,
                reason=f"Price {price:.4f} >= upper band {upper:.4f} (mid={middle:.4f})",
            )

        return Action(
            action_type="HOLD",
            symbol=self.symbol,
            quantity=0.0,
            reason=f"Price {price:.4f} within bands [{lower:.4f}, {upper:.4f}]",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _bands(self, closes: list[float]) -> tuple[float, float, float]:
        """Return (lower, middle, upper) using the last `window` closes."""
        window = closes[-self.window :]
        middle = sum(window) / self.window
        variance = sum((c - middle) ** 2 for c in window) / self.window
        std = math.sqrt(variance)
        band = self.num_std * std
        return middle - band, middle, middle + band
