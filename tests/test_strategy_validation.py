"""Reject un-runnable strategy parameters before they become a broken bot."""
from datetime import datetime, timezone
import math

import pytest
from sqlalchemy.orm import Session

from backend.bots.registry import get_strategy_defaults
from backend.bots.validation import normalize_strategy_params
from backend.db.models import DBBacktestRun, DBBot
from tests.test_governance_api import local_governance  # authenticated in-memory ASGI fixture


@pytest.mark.parametrize("strategy", ["simple_ma", "rsi", "bollinger_bands", "macd", "momentum"])
def test_empty_parameters_resolve_to_each_registered_strategy_default(strategy: str) -> None:
    assert normalize_strategy_params(strategy, {}) == get_strategy_defaults(strategy)


@pytest.mark.parametrize(
    ("strategy", "partial", "key", "expected"),
    [("simple_ma", {"short_window": "3.0"}, "short_window", 3),
     ("rsi", {"period": 20}, "period", 20),
     ("bollinger_bands", {"num_std": 1.5}, "num_std", 1.5),
     ("macd", {"fast": 9}, "fast", 9),
     ("momentum", {"stop_loss": 0.05}, "stop_loss", 0.05)],
)
def test_valid_partial_parameters_keep_other_defaults(
    strategy: str, partial: dict, key: str, expected: float,
) -> None:
    original = dict(partial)
    normalized = normalize_strategy_params(strategy, partial)
    assert normalized == {**get_strategy_defaults(strategy), key: expected}
    assert partial == original
    if key in ("short_window", "period", "fast"):
        assert type(normalized[key]) is int


@pytest.mark.parametrize(
    ("strategy", "params"),
    [("simple_ma", {"short_window": 5.5}),
     ("simple_ma", {"long_window": True}),
     ("rsi", {"period": math.nan}),
     ("rsi", {"period": 0}),
     ("bollinger_bands", {"window": 4.5}),
     ("bollinger_bands", {"num_std": math.inf}),
     ("macd", {"slow": "25.5"}),
     ("momentum", {"window": False}),
     ("momentum", {"stop_loss": -0.01}),
     ("simple_ma", {"short_window": 20, "long_window": 20}),
     ("simple_ma", {"short_window": 21}),
     ("rsi", {"oversold": 70, "overbought": 30}),
     ("macd", {"fast": 26, "slow": 12}),
     ("simple_ma", {"unknown": 1}),
     ("simple_ma", {"symbol": "override"}),
     ("unregistered", {})],
)
def test_invalid_parameters_and_unknown_strategies_are_rejected(strategy: str, params: dict) -> None:
    with pytest.raises(ValueError):
        normalize_strategy_params(strategy, params)


@pytest.mark.parametrize(
    ("strategy", "params"),
    [("simple_ma", {"short_window": 5.5}), ("rsi", {"period": True}),
     ("bollinger_bands", {"window": math.nan}), ("macd", {"fast": 30, "slow": 12}),
     ("momentum", {"unexpected": 1}), ("unregistered", {})],
)
def test_create_endpoint_returns_422_without_saving_invalid_bot(local_governance, strategy: str, params: dict) -> None:
    post, engine = local_governance
    status, response = post("/bots/", {"name": "Bad bot", "strategy_key": strategy, "params": params}, "tech")
    assert status == 422 and response["detail"]
    with Session(engine) as db:
        assert db.query(DBBot).filter_by(name="Bad bot").count() == 0


def test_valid_partial_parameters_are_normalized_when_a_bot_is_created(local_governance) -> None:
    post, engine = local_governance
    status, response = post("/bots/", {
        "name": "Working bot", "strategy_key": "simple_ma", "params": {"short_window": "3.0"},
    }, "tech")
    assert status == 201
    with Session(engine) as db:
        bot = db.get(DBBot, response["id"])
        assert bot.params == {"short_window": 3, "long_window": 20}
        assert type(bot.params["short_window"]) is int


@pytest.mark.parametrize("arena_mode", [False, True])
def test_old_invalid_saved_bot_returns_422_not_500(local_governance, arena_mode: bool) -> None:
    post, engine = local_governance
    with Session(engine) as db:
        db.add(DBBot(
            id="invalid-old", name="Old invalid bot", strategy_name="simple_ma",
            params={"short_window": 5.5, "long_window": 20},
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc), is_active=True, status="approved",
        ))
        db.commit()
    if arena_mode:
        path = "/arena/run"
        payload = {"bot_ids": ["invalid-old"], "symbol": "SIM", "num_candles": 40, "seed": 42}
    else:
        path = "/arena/backtest/invalid-old"
        payload = {"symbol": "SIM", "num_candles": 40, "seed": 42}
    status, response = post(path, payload, "tech")
    assert status == 422 and response["detail"]
    with Session(engine) as db:
        assert db.query(DBBacktestRun).filter_by(bot_id="invalid-old").count() == 0
