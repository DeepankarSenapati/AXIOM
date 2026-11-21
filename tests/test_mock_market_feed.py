"""Mock prices should be reproducible without misrepresenting their interval."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import random

import pytest

from backend.api.arena import _fetch_candles
from backend.api.models import BacktestRequest, RunArenaRequest
from backend.engine.market_feed import MarketFeedError, MockMarketFeed


@pytest.mark.parametrize(
    ("timeframe", "interval"),
    [("1h", timedelta(hours=1)), ("4h", timedelta(hours=4)), ("1d", timedelta(days=1))],
)
def test_requested_interval_matches_mock_candle_timestamps(timeframe: str, interval: timedelta) -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = MockMarketFeed().generate("SIM", 4, 100, start_time=start, seed=42, timeframe=timeframe)
    assert [candle.timestamp for candle in candles] == [start + interval * i for i in range(4)]


def test_default_interval_remains_one_hour() -> None:
    candles = MockMarketFeed().generate("SIM", 2, 100, seed=42)
    assert candles[1].timestamp - candles[0].timestamp == timedelta(hours=1)


@pytest.mark.parametrize("timeframe", ["5m", "weekly", ""])
def test_invalid_interval_is_rejected(timeframe: str) -> None:
    with pytest.raises(MarketFeedError):
        MockMarketFeed().generate("SIM", 3, 100, seed=42, timeframe=timeframe)


def test_seeded_generation_is_deterministic_and_does_not_touch_global_rng() -> None:
    before = random.getstate()
    first = MockMarketFeed().generate("SIM", 50, 100, seed=42, timeframe="1d")
    after_seeded = random.getstate()
    second = MockMarketFeed().generate("SIM", 50, 100, seed=42, timeframe="1d")
    different = MockMarketFeed().generate("SIM", 50, 100, seed=43, timeframe="1d")
    MockMarketFeed().generate("SIM", 3, 100, timeframe="1d")
    assert first == second and first != different
    assert before == after_seeded == random.getstate()


def test_seeded_mock_prices_preserve_the_previous_hourly_fixture() -> None:
    candles = MockMarketFeed().generate("SIM", 3, 100, seed=42)
    assert [(c.open, c.high, c.low, c.close, c.volume) for c in candles] == [
        (100.0, 100.5829, 99.275, 100.5577, 23097.86),
        (100.5577, 102.1958, 100.4493, 101.5089, 9606.94),
        (101.5089, 101.5391, 100.4012, 101.1919, 51030.17),
    ]


def test_concurrent_seeded_generation_matches_serial_runs() -> None:
    seeds = [1, 2, 3, 4, 5, 6, 7, 8]

    def generate(seed: int):
        return MockMarketFeed().generate("SIM", 1_000, 100, seed=seed, timeframe="4h")

    expected = [generate(seed) for seed in seeds]
    with ThreadPoolExecutor(max_workers=4) as pool:
        concurrent = list(pool.map(generate, seeds))
    assert concurrent == expected


@pytest.mark.parametrize(
    ("timeframe", "interval"),
    [("1h", timedelta(hours=1)), ("4h", timedelta(hours=4)), ("1d", timedelta(days=1))],
)
@pytest.mark.parametrize("arena_mode", [False, True])
def test_arena_forwards_requested_timeframe_to_mock_feed(
    timeframe: str, interval: timedelta, arena_mode: bool
) -> None:
    kwargs = {"symbol": "SIM", "num_candles": 3, "timeframe": timeframe, "seed": 42}
    request = RunArenaRequest(bot_ids=["bot"], **kwargs) if arena_mode else BacktestRequest(**kwargs)
    candles = _fetch_candles(request)
    assert candles[1].timestamp - candles[0].timestamp == interval
