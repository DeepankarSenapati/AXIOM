"""Historical provider failures must not become successful empty simulations."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.api import arena
from backend.api.models import BacktestRequest
from backend.db.models import DBBacktestRun, DBBot
from backend.engine import market_feed


def yahoo_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {"Open": [100.0, 101.0], "High": [102.0, 103.0], "Low": [99.0, 100.0],
         "Close": [101.0, 102.0], "Volume": [1000.0, 1000.0]},
        index=pd.date_range("2026-01-01", periods=2, tz="UTC"),
    )


def mock_yahoo(monkeypatch: pytest.MonkeyPatch, frame: pd.DataFrame) -> Mock:
    ticker = Mock()
    ticker.history.return_value = frame
    factory = Mock(return_value=ticker)
    monkeypatch.setattr(market_feed.yf, "Ticker", factory)
    return factory


def test_nse_4h_rejected_before_fetch_with_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = mock_yahoo(monkeypatch, yahoo_frame())
    request = BacktestRequest(symbol="RELIANCE.NS", data_source="live", timeframe="4h")
    with pytest.raises(HTTPException) as exc:
        arena._fetch_candles(request)
    assert exc.value.status_code == 422
    assert "1 Hour or 1 Day" in exc.value.detail
    factory.assert_not_called()


def test_binance_4h_remains_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    exchange = SimpleNamespace(fetch_ohlcv=Mock(return_value=[
        [0, 100, 102, 99, 101, 1000], [14_400_000, 101, 103, 100, 102, 1000],
    ]))
    monkeypatch.setattr(market_feed.ccxt, "binance", lambda _: exchange)
    request = BacktestRequest(symbol="BTC/USDT", data_source="live", timeframe="4h")
    candles = arena._fetch_candles(request)
    exchange.fetch_ohlcv.assert_called_once_with("BTC/USDT", "4h", limit=100)
    assert len(candles) == 2
    assert (candles[1].timestamp - candles[0].timestamp).total_seconds() == 4 * 60 * 60


@pytest.mark.parametrize("problem", ["one_bar", "zero", "nan", "infinite", "invalid_range", "negative_volume", "missing_time", "duplicate_time"])
def test_yahoo_invalid_or_insufficient_bars_do_not_create_a_run(
    problem: str, monkeypatch: pytest.MonkeyPatch, db_session: Session,
) -> None:
    frame = yahoo_frame()
    if problem == "one_bar":
        frame = frame.iloc[:1]
    elif problem == "zero":
        frame.loc[:, ["Open", "High", "Low", "Close"]] = 0.0
    elif problem == "nan":
        frame.iloc[1, frame.columns.get_loc("Close")] = float("nan")
    elif problem == "infinite":
        frame.iloc[1, frame.columns.get_loc("Open")] = float("inf")
    elif problem == "invalid_range":
        frame.iloc[1, frame.columns.get_loc("High")] = 90.0
    elif problem == "negative_volume":
        frame.iloc[1, frame.columns.get_loc("Volume")] = -1.0
    elif problem == "missing_time":
        frame.index = [pd.NaT, frame.index[1]]
    else:
        frame.index = [frame.index[0], frame.index[0]]
    mock_yahoo(monkeypatch, frame)
    db_session.add(DBBot(id="test", name="Test", strategy_name="simple_ma", params={}, is_active=True,
                         created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    db_session.commit()
    request = BacktestRequest(symbol="RELIANCE.NS", data_source="live", timeframe="1d")
    with pytest.raises(HTTPException) as exc:
        arena.backtest_bot("test", request, db_session)
    assert exc.value.status_code == 502
    assert "Historical data" in exc.value.detail
    assert db_session.query(DBBacktestRun).count() == 0


@pytest.mark.parametrize("rows", [
    [[0, 100, 102, 99, 101, 1000]],
    [[0, 100, 102, 99, 101, 1000], [3_600_000, 101, 103, 100, float("nan"), 1000]],
    [[0, 100, 102, 99, 101, 1000], [0, 101, 103, 100, 102, 1000]],
])
def test_binance_invalid_or_insufficient_bars_are_rejected(
    rows: list[list[float]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    exchange = SimpleNamespace(fetch_ohlcv=Mock(return_value=rows))
    monkeypatch.setattr(market_feed.ccxt, "binance", lambda _: exchange)
    with pytest.raises(HTTPException) as exc:
        arena._fetch_candles(BacktestRequest(symbol="BTC/USDT", data_source="live", timeframe="1h"))
    assert exc.value.status_code == 502
    assert "Historical data" in exc.value.detail


def test_short_valid_history_records_the_actual_count(
    monkeypatch: pytest.MonkeyPatch, db_session: Session,
) -> None:
    mock_yahoo(monkeypatch, yahoo_frame())
    db_session.add(DBBot(id="test", name="Test", strategy_name="simple_ma", params={}, is_active=True,
                         created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    db_session.commit()
    request = BacktestRequest(symbol="RELIANCE.NS", data_source="live", timeframe="1d", num_candles=100)
    result = arena.backtest_bot("test", request, db_session)
    assert len(result.equity_records) == 2
    assert db_session.query(DBBacktestRun).one().num_candles == 2
