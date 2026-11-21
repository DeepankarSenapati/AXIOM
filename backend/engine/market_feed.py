import csv
import logging
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Literal

import ccxt
import yfinance as yf

from backend.engine.models import Candle

logger = logging.getLogger(__name__)

# yfinance uses different interval strings than our internal timeframe labels
_YF_INTERVAL_MAP: dict[str, str] = {
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}

VALID_TIMEFRAMES = ("1h", "4h", "1d")
_MOCK_TIMEFRAME_STEPS = {
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
}


class MarketFeedError(Exception):
    pass


class MockMarketFeed:
    def generate(
        self,
        symbol: str,
        n: int,
        start_price: float,
        start_time: datetime | None = None,
        seed: int | None = None,
        timeframe: Literal["1h", "4h", "1d"] = "1h",
    ) -> list[Candle]:
        if timeframe not in VALID_TIMEFRAMES:
            raise MarketFeedError(
                f"Invalid timeframe '{timeframe}'. Must be one of {VALID_TIMEFRAMES}."
            )
        rng = random.Random(seed)
        step = _MOCK_TIMEFRAME_STEPS[timeframe]
        if start_time is None:
            start_time = datetime(2026, 1, 1, 0, 0, 0)

        candles: list[Candle] = []
        price = start_price

        for i in range(n):
            change = rng.uniform(-0.02, 0.02)  # ±2% random walk
            close = round(price * (1 + change), 4)
            high = round(max(price, close) * rng.uniform(1.0, 1.01), 4)
            low = round(min(price, close) * rng.uniform(0.99, 1.0), 4)
            open_ = round(price, 4)
            volume = round(rng.uniform(1_000, 100_000), 2)

            candles.append(
                Candle(
                    symbol=symbol,
                    timestamp=start_time + step * i,
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )
            price = close

        return candles

    def from_csv(self, filepath: str) -> list[Candle]:
        candles: list[Candle] = []
        with open(filepath, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                candles.append(
                    Candle(
                        symbol=row.get("symbol", "UNKNOWN"),
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]),
                    )
                )
        return candles


class YFinanceFeed:
    """Fetches public read-only historical OHLCV data via yfinance.

    Supports Indian NSE stocks (e.g. 'RELIANCE.NS', 'TCS.NS') and
    indices (e.g. '^NSEI'). No API keys required. Phase 1 safe.
    """

    def fetch_historical(
        self,
        symbol: str,
        timeframe: Literal["1h", "4h", "1d"] = "1d",
        limit: int = 100,
    ) -> list[Candle]:
        if timeframe not in VALID_TIMEFRAMES:
            raise MarketFeedError(
                f"Invalid timeframe '{timeframe}'. Must be one of {VALID_TIMEFRAMES}."
            )
        interval = _YF_INTERVAL_MAP[timeframe]
        period_map = {"1h": "60d", "4h": "60d", "1d": "2y"}
        period = period_map[timeframe]
        logger.info("Fetching %d %s candles for %s from yfinance", limit, timeframe, symbol)
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
        except Exception as exc:
            logger.exception("yfinance error fetching '%s': %s", symbol, exc)
            raise MarketFeedError(f"yfinance error fetching '{symbol}': {exc}") from exc

        if df is None or df.empty:
            logger.error("No data returned for symbol '%s' timeframe '%s'", symbol, timeframe)
            raise MarketFeedError(
                f"No data returned for symbol '{symbol}' timeframe '{timeframe}'. "
                "Check the symbol is valid (e.g. 'RELIANCE.NS', '^NSEI')."
            )

        df = df.tail(limit)

        candles: list[Candle] = []
        for ts, row in df.iterrows():
            if hasattr(ts, "to_pydatetime"):
                dt = ts.to_pydatetime()
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
            else:
                dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
            candles.append(
                Candle(
                    symbol=symbol,
                    timestamp=dt,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row.get("Volume", 0.0)),
                )
            )
        candles = [
            c for c in candles
            if not any(math.isnan(v) or v == 0 for v in [c.open, c.high, c.low, c.close])
        ]
        logger.info("Fetched %d candles successfully", len(candles))
        return candles


class CCXTFeed:
    """Fetches public read-only historical OHLCV data from Binance via CCXT.

    No API keys required. No orders. No real money. Phase 1 safe.
    """

    def __init__(self) -> None:
        self._exchange = ccxt.binance({"enableRateLimit": True})

    def fetch_historical(
        self,
        symbol: str = "BTC/USDT",
        timeframe: Literal["1h", "4h", "1d"] = "1d",
        limit: int = 100,
    ) -> list[Candle]:
        if timeframe not in VALID_TIMEFRAMES:
            raise MarketFeedError(
                f"Invalid timeframe '{timeframe}'. Must be one of {VALID_TIMEFRAMES}."
            )
        logger.info("Fetching %d %s candles for %s from Binance", limit, timeframe, symbol)
        try:
            raw: list[list] = self._exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        except ccxt.BadSymbol as exc:
            logger.error("Unknown symbol '%s': %s", symbol, exc)
            raise MarketFeedError(f"Unknown symbol '{symbol}': {exc}") from exc
        except ccxt.NetworkError as exc:
            logger.exception("Network error fetching '%s': %s", symbol, exc)
            raise MarketFeedError(f"Network error fetching '{symbol}': {exc}") from exc
        except ccxt.BaseError as exc:
            logger.exception("CCXT error fetching '%s': %s", symbol, exc)
            raise MarketFeedError(f"CCXT error fetching '{symbol}': {exc}") from exc

        if not raw:
            logger.error("No data returned for symbol '%s' timeframe '%s'", symbol, timeframe)
            raise MarketFeedError(
                f"No data returned for symbol '{symbol}' timeframe '{timeframe}'."
            )

        candles: list[Candle] = []
        for row in raw:
            ts_ms, open_, high, low, close, volume = row
            candles.append(
                Candle(
                    symbol=symbol,
                    timestamp=datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc),
                    open=float(open_),
                    high=float(high),
                    low=float(low),
                    close=float(close),
                    volume=float(volume),
                )
            )
        logger.info("Fetched %d candles successfully", len(candles))
        return candles
