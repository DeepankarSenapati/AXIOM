import csv
import random
from datetime import datetime, timedelta

from backend.engine.models import Candle


class MockMarketFeed:
    def generate(
        self,
        symbol: str,
        n: int,
        start_price: float,
        start_time: datetime | None = None,
    ) -> list[Candle]:
        if start_time is None:
            start_time = datetime(2026, 1, 1, 0, 0, 0)

        candles: list[Candle] = []
        price = start_price

        for i in range(n):
            change = random.uniform(-0.02, 0.02)  # ±2% random walk
            close = round(price * (1 + change), 4)
            high = round(max(price, close) * random.uniform(1.0, 1.01), 4)
            low = round(min(price, close) * random.uniform(0.99, 1.0), 4)
            open_ = round(price, 4)
            volume = round(random.uniform(1_000, 100_000), 2)

            candles.append(
                Candle(
                    symbol=symbol,
                    timestamp=start_time + timedelta(hours=i),
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
