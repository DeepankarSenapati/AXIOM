import backend.config as settings
from backend.bots.strategies.base import BaseStrategy
from backend.engine.models import Action, Candle, Portfolio


class MACDStrategy(BaseStrategy):
    """
    Buys when the MACD line crosses above the signal line (bullish crossover).
    Sells the full position when the MACD line crosses below the signal line (bearish crossover).
    Uses standard EMA-based MACD: fast=12, slow=26, signal=9.
    Requires at least slow + signal - 1 candles before producing a signal.
    """

    def __init__(
        self,
        symbol: str,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> None:
        if fast >= slow:
            raise ValueError(f"fast ({fast}) must be less than slow ({slow})")
        if fast < 1 or slow < 1 or signal < 1:
            raise ValueError("fast, slow, and signal must all be >= 1")
        self.symbol = symbol
        self.fast = fast
        self.slow = slow
        self.signal = signal
        # Minimum candles: need slow candles for first MACD value,
        # then signal-1 more to compute the first signal EMA.
        self._min_candles = self.slow + self.signal - 1

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def on_candle(self, candles: list[Candle], portfolio: Portfolio) -> Action:
        if len(candles) < self._min_candles + 1:
            return Action(
                action_type="HOLD",
                symbol=self.symbol,
                quantity=0.0,
                reason=(
                    f"Insufficient history: need {self._min_candles + 1} candles, "
                    f"have {len(candles)}"
                ),
            )

        closes = [c.close for c in candles]
        macd_line = self._macd_series(closes)

        # Need at least signal+1 MACD values to detect a crossover
        if len(macd_line) < self.signal + 1:
            return Action(
                action_type="HOLD",
                symbol=self.symbol,
                quantity=0.0,
                reason="Building MACD signal line — not enough MACD values yet",
            )

        signal_line = self._ema(macd_line, self.signal)

        current_hist = macd_line[-1] - signal_line[-1]
        prev_hist = macd_line[-2] - signal_line[-2]

        price = candles[-1].close
        held = portfolio.positions.get(self.symbol, 0.0)

        # Bullish crossover: histogram flips from negative to positive
        if prev_hist <= 0 and current_hist > 0:
            quantity = (portfolio.cash * settings.MAX_POSITION_SIZE) / price
            if quantity <= 0:
                return Action(
                    action_type="HOLD",
                    symbol=self.symbol,
                    quantity=0.0,
                    reason="Bullish MACD crossover but insufficient cash to buy",
                )
            return Action(
                action_type="BUY",
                symbol=self.symbol,
                quantity=quantity,
                reason=(
                    f"Bullish crossover: MACD={macd_line[-1]:.4f} "
                    f"crossed above signal={signal_line[-1]:.4f}"
                ),
            )

        # Bearish crossover: histogram flips from positive to negative
        if prev_hist >= 0 and current_hist < 0:
            if held > 0:
                return Action(
                    action_type="SELL",
                    symbol=self.symbol,
                    quantity=held,
                    reason=(
                        f"Bearish crossover: MACD={macd_line[-1]:.4f} "
                        f"crossed below signal={signal_line[-1]:.4f}"
                    ),
                )
            return Action(
                action_type="HOLD",
                symbol=self.symbol,
                quantity=0.0,
                reason=(
                    f"Bearish crossover: MACD={macd_line[-1]:.4f} "
                    f"crossed below signal={signal_line[-1]:.4f} but no position to sell"
                ),
            )

        return Action(
            action_type="HOLD",
            symbol=self.symbol,
            quantity=0.0,
            reason=(
                f"No crossover: MACD={macd_line[-1]:.4f}, "
                f"signal={signal_line[-1]:.4f}, hist={current_hist:.4f}"
            ),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ema(values: list[float], period: int) -> list[float]:
        """Compute EMA for a series. Seeds with SMA of the first `period` values."""
        if len(values) < period:
            return []
        k = 2.0 / (period + 1)
        ema = sum(values[:period]) / period
        result = [ema]
        for v in values[period:]:
            ema = v * k + ema * (1 - k)
            result.append(ema)
        return result

    def _macd_series(self, closes: list[float]) -> list[float]:
        """Return the MACD line (fast EMA − slow EMA) aligned to the slow EMA series."""
        fast_ema = self._ema(closes, self.fast)
        slow_ema = self._ema(closes, self.slow)
        # Align: slow EMA starts later; trim fast EMA to match length
        offset = len(fast_ema) - len(slow_ema)
        return [f - s for f, s in zip(fast_ema[offset:], slow_ema)]
