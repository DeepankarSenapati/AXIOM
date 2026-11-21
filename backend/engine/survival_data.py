"""Deterministic, synthetic market data for a local simulation.

The scenario is generated from independent daily random factors, not retrieved
from an exchange. A shock is a single artificial downward gap at one open.
"""

import math
import random
from datetime import datetime, timedelta, timezone

from backend.engine.models import Candle
from backend.engine.survival_models import SurvivalRequest


SYNTHETIC_SYMBOL = "SYNTH/USD"
SYNTHETIC_START = datetime(2024, 1, 1, tzinfo=timezone.utc)
DAILY_RANDOM_RANGE = 0.012
TREND_AMPLITUDE = 0.0035
TREND_PERIOD = 17.0
WICK_MAX = 0.004
MIN_VOLUME = 500_000.0
MAX_VOLUME = 1_500_000.0
PERCENT_SCALE = 100.0


def resolved_shock_index(request: SurvivalRequest) -> int:
    """Return the configured shock location, or a valid default location."""
    return request.shock_index if request.shock_index is not None else max(1, request.num_candles * 2 // 3)


def build_synthetic_candles(request: SurvivalRequest) -> list[Candle]:
    """Produce identical random factors for both shocked and unshocked paths."""
    rng = random.Random(request.seed)
    shock_index = resolved_shock_index(request)
    previous_close = request.start_price
    candles: list[Candle] = []
    for index in range(request.num_candles):
        gap = (1.0 - request.shock_pct / PERCENT_SCALE) if index == shock_index else 1.0
        open_price = previous_close * gap
        change = rng.uniform(-DAILY_RANDOM_RANGE, DAILY_RANDOM_RANGE)
        change += TREND_AMPLITUDE * math.sin(index / TREND_PERIOD)
        close_price = open_price * (1.0 + change)
        upper_wick = rng.uniform(0.0, WICK_MAX)
        lower_wick = rng.uniform(0.0, WICK_MAX)
        volume = rng.uniform(MIN_VOLUME, MAX_VOLUME)
        candles.append(Candle(
            symbol=SYNTHETIC_SYMBOL,
            timestamp=SYNTHETIC_START + timedelta(days=index),
            open=open_price,
            high=max(open_price, close_price) * (1.0 + upper_wick),
            low=min(open_price, close_price) * (1.0 - lower_wick),
            close=close_price,
            volume=volume,
        ))
        previous_close = close_price
    return candles
