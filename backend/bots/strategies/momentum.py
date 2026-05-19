import logging

import backend.config as settings
from backend.bots.strategies.base import BaseStrategy
from backend.engine.models import Action, Candle, Portfolio

logger = logging.getLogger(__name__)


class MomentumStrategy(BaseStrategy):
    """
    Buys when price has risen at least `threshold` % over the last `window` candles.
    Sells when price falls `stop_loss` % below the recorded entry price.
    Holds otherwise or when insufficient history.
    """

    def __init__(
        self,
        symbol: str,
        window: int = 10,
        threshold: float = 0.02,
        stop_loss: float = 0.03,
    ) -> None:
        if window < 2:
            raise ValueError(f"window must be >= 2, got {window}")
        if threshold <= 0:
            raise ValueError(f"threshold must be > 0, got {threshold}")
        if stop_loss <= 0:
            raise ValueError(f"stop_loss must be > 0, got {stop_loss}")
        self.symbol = symbol
        self.window = window
        self.threshold = threshold
        self.stop_loss = stop_loss
        self._entry_price: float | None = None

    def on_candle(self, candles: list[Candle], portfolio: Portfolio) -> Action:
        if len(candles) < self.window:
            return Action(
                action_type="HOLD",
                symbol=self.symbol,
                quantity=0.0,
                reason=f"Insufficient history: need {self.window} candles, have {len(candles)}",
            )

        price = candles[-1].close
        base_price = candles[-self.window].close
        held = portfolio.positions.get(self.symbol, 0.0)

        # Stop loss: sell if price has dropped stop_loss % below entry
        if held > 0 and self._entry_price is None:
            logger.warning(
                "Bot holding %s but _entry_price is None — skipping stop-loss this candle",
                self.symbol,
            )
        if held > 0 and self._entry_price is not None:
            entry = self._entry_price
            drop = (price - entry) / entry
            if drop <= -self.stop_loss:
                self._entry_price = None
                return Action(
                    action_type="SELL",
                    symbol=self.symbol,
                    quantity=held,
                    reason=(
                        f"Stop loss triggered: price {price:.4f} is "
                        f"{drop * 100:.2f}% below entry {entry:.4f} "
                        f"(limit -{self.stop_loss * 100:.1f}%)"
                    ),
                )

        # Momentum buy: price rose >= threshold % over the window
        if base_price > 0:
            gain = (price - base_price) / base_price
        else:
            gain = 0.0

        if gain >= self.threshold:
            quantity = (portfolio.cash * settings.MAX_POSITION_SIZE) / price
            if quantity <= 0:
                return Action(
                    action_type="HOLD",
                    symbol=self.symbol,
                    quantity=0.0,
                    reason=(
                        f"Momentum signal (+{gain * 100:.2f}% over {self.window} candles) "
                        f"but insufficient cash to buy"
                    ),
                )
            self._entry_price = price
            return Action(
                action_type="BUY",
                symbol=self.symbol,
                quantity=quantity,
                reason=(
                    f"Momentum: price rose {gain * 100:.2f}% over {self.window} candles "
                    f"(base={base_price:.4f} → now={price:.4f}, "
                    f"threshold={self.threshold * 100:.1f}%)"
                ),
            )

        return Action(
            action_type="HOLD",
            symbol=self.symbol,
            quantity=0.0,
            reason=(
                f"No signal: {gain * 100:.2f}% change over {self.window} candles "
                f"(threshold={self.threshold * 100:.1f}%)"
            ),
        )
