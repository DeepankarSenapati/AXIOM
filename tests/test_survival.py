"""Behavioural tests for the local, simulated Survival Lab."""
from datetime import datetime, timedelta, timezone
import math

import pytest

from backend.bots.strategies.base import BaseStrategy
from backend.bots.strategies.bollinger_bands import BollingerBandsStrategy
from backend.bots.strategies.macd import MACDStrategy
from backend.bots.strategies.momentum import MomentumStrategy
from backend.bots.strategies.rsi import RSIStrategy
from backend.bots.strategies.simple_ma import SimpleMovingAverageStrategy
from backend.bots.registry import get_strategy_defaults
from backend.engine.models import Action, Candle, Portfolio
from backend.engine import survival
import backend.config as settings
from backend.engine.survival import (
    SurvivalRequest,
    run_survival,
    simulate_benchmark,
    simulate_strategy,
)


def tape(prices: list[tuple[float, float]]) -> list[Candle]:
    """Create an explicit, chronological tape of (open, close) prices."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            symbol="SIM",
            timestamp=start + timedelta(days=index),
            open=open_price,
            high=max(open_price, close_price) + 1.0,
            low=min(open_price, close_price) - 1.0,
            close=close_price,
            volume=1_000.0,
        )
        for index, (open_price, close_price) in enumerate(prices)
    ]


def request_for(count: int, **overrides: object) -> SurvivalRequest:
    values = {
        "strategy_key": "simple_ma",
        "seed": 42,
        "num_candles": count,
        "start_price": 100.0,
        "starting_cash": 1_000.0,
        "fee_bps": 0.0,
        "slippage_bps": 0.0,
        "shock_pct": 0.0,
        "shock_index": None,
        "guard_enabled": False,
        "guard_drawdown_pct": 10.0,
        "max_position_pct": 100.0,
    }
    values.update(overrides)
    return SurvivalRequest(**values)


class ScriptedStrategy(BaseStrategy):
    def __init__(self, signals: dict[int, tuple[str, float]]) -> None:
        self.signals = signals
        self.observed_closes: list[list[float]] = []

    def on_candle(self, candles: list[Candle], portfolio: Portfolio) -> Action:
        self.observed_closes.append([c.close for c in candles])
        action, quantity = self.signals.get(len(candles) - 1, ("HOLD", 0.0))
        return Action(
            action_type=action,
            symbol=candles[-1].symbol,
            quantity=quantity,
            reason="deterministic test signal",
        )


def events_of(run: object, kind: str) -> list:
    return [event for event in run.events if event.event_type == kind]


@pytest.mark.parametrize(
    ("strategy", "closes", "trigger"),
    [
        (RSIStrategy("SIM", period=14), list(range(100, 115)), "above overbought threshold"),
        (SimpleMovingAverageStrategy("SIM", short_window=2, long_window=3), [100, 100, 101, 90], "Death cross"),
        (BollingerBandsStrategy("SIM", window=3), [100, 100, 100, 105], "upper band"),
        (MACDStrategy("SIM", fast=2, slow=3, signal=2), [100, 101, 102, 103, 104, 105, 104], "Bearish crossover"),
    ],
)
def test_sell_trigger_reports_flat_position_without_changing_actions(
    strategy: BaseStrategy, closes: list[float], trigger: str,
) -> None:
    candles = tape([(price, price) for price in closes])
    flat = strategy.on_candle(candles, Portfolio(cash=1_000, positions={"SIM": 0.0}, pnl=0))
    held = strategy.on_candle(candles, Portfolio(cash=1_000, positions={"SIM": 2.0}, pnl=0))

    assert flat.action_type == "HOLD" and flat.quantity == 0
    assert trigger in flat.reason and "no position to sell" in flat.reason
    assert held.action_type == "SELL" and held.quantity == 2


def test_rsi_retains_simple_rolling_average_and_signal() -> None:
    # Fourteen +1 changes, then eleven -1 changes: the last fourteen changes
    # contain three gains and eleven losses, so the simple-window RSI is 3/14.
    closes = list(range(100, 115)) + list(range(113, 102, -1))
    strategy = RSIStrategy("SIM", period=14)
    action = strategy.on_candle(tape([(price, price) for price in closes]), Portfolio(cash=1_000, positions={}, pnl=0))

    assert strategy._compute_rsi(closes) == pytest.approx(100 * 3 / 14)
    assert action.action_type == "BUY"


def test_close_marked_drawdown_discloses_that_intrabar_losses_can_be_missed() -> None:
    candles = tape([(100, 100), (100, 100), (50, 100)])
    request = request_for(3, guard_enabled=True, guard_drawdown_pct=5)
    run = simulate_strategy(request, candles, ScriptedStrategy({0: ("BUY", 1.0)}), use_guard=True)

    assert run.equity_curve[1].cash + run.equity_curve[1].position * candles[2].open == pytest.approx(950)
    assert run.max_drawdown_pct == 0 and run.guard_trigger_index is None
    assert any("candle-close equity" in item and "between closes" in item for item in run_survival(request).assumptions)


def test_strategy_sees_only_prefix_and_fills_at_next_open() -> None:
    candles = tape([(10, 10), (20, 30), (40, 50)])
    strategy = ScriptedStrategy({0: ("BUY", 1.0), 1: ("SELL", 1.0)})

    run = simulate_strategy(request_for(3), candles, strategy)

    assert strategy.observed_closes == [[10], [10, 30], [10, 30, 50]]
    fills = events_of(run, "fill")
    assert [(e.candle_index, e.action, e.price, e.quantity) for e in fills] == [
        (1, "BUY", 20.0, 1.0),
        (2, "SELL", 40.0, 1.0),
    ]
    assert [event.signal_index for event in fills] == [0, 1]
    assert run.final_equity == pytest.approx(1_020.0)
    assert run.trade_count == 2


def test_final_close_signal_expires_without_a_phantom_fill() -> None:
    candles = tape([(100, 100), (100, 110), (110, 120)])
    strategy = ScriptedStrategy({2: ("BUY", 1.0)})

    run = simulate_strategy(request_for(3), candles, strategy)

    assert events_of(run, "fill") == []
    expired = events_of(run, "expired")
    assert len(expired) == 1
    assert expired[0].candle_index == 2
    assert expired[0].action == "BUY"
    assert run.final_equity == pytest.approx(1_000.0)


def test_fees_and_slippage_are_adverse_and_buy_is_affordable() -> None:
    candles = tape([(100, 100), (100, 100), (100, 100)])
    request = request_for(3, starting_cash=1_000.0, fee_bps=100.0, slippage_bps=100.0)
    strategy = ScriptedStrategy({0: ("BUY", 10.0)})

    run = simulate_strategy(request, candles, strategy)

    fill, = events_of(run, "fill")
    assert fill.price == pytest.approx(101.0)
    assert 0 < fill.quantity < 10.0
    assert fill.fee == pytest.approx(fill.quantity * fill.price * 0.01)
    assert fill.quantity * fill.price + fill.fee <= 1_000.0 + 1e-8
    assert run.ending_cash == pytest.approx(1_000.0 - fill.quantity * fill.price - fill.fee)
    assert run.ending_cash >= -1e-8
    assert run.total_fees == pytest.approx(fill.fee)


def test_sell_slippage_and_fees_reduce_proceeds() -> None:
    candles = tape([(100, 100), (100, 100), (100, 100)])
    request = request_for(3, fee_bps=100.0, slippage_bps=100.0)

    run = simulate_strategy(
        request, candles, ScriptedStrategy({0: ("BUY", 1.0), 1: ("SELL", 1.0)})
    )

    buy, sell = events_of(run, "fill")
    assert (buy.action, buy.price, buy.fee) == ("BUY", 101.0, pytest.approx(1.01))
    assert (sell.action, sell.price, sell.fee) == ("SELL", 99.0, pytest.approx(0.99))
    assert run.ending_cash == pytest.approx(996.0)
    assert run.total_fees == pytest.approx(2.0)
    assert run.total_slippage_cost == pytest.approx(2.0)


def test_position_cap_applies_to_post_cost_equity() -> None:
    candles = tape([(100, 100), (100, 100), (100, 100)])
    request = request_for(3, fee_bps=100.0, slippage_bps=100.0, max_position_pct=30.0)

    run = simulate_strategy(request, candles, ScriptedStrategy({0: ("BUY", 10.0)}))

    fill, = events_of(run, "fill")
    position_value = fill.quantity * candles[1].open
    equity_after_fill = run.equity_curve[1].equity
    assert fill.quantity < 10.0
    assert position_value / equity_after_fill == pytest.approx(0.30)
    assert run.ending_cash >= 0.0


def test_saturated_cap_rejects_float_residue_instead_of_counting_a_fill() -> None:
    candles = tape([(10, 10), (10, 10), (10, 10)])
    request = request_for(3, starting_cash=10_000, fee_bps=10, slippage_bps=5, max_position_pct=30)

    run = simulate_strategy(request, candles, ScriptedStrategy({0: ("BUY", 10_000), 1: ("BUY", 10_000)}))

    fills = events_of(run, "fill")
    assert len(fills) == run.trade_count == 1
    assert fills[0].quantity == pytest.approx(299.86501576315419)
    rejected, = events_of(run, "rejected")
    assert rejected.candle_index == 2 and rejected.action == "BUY"
    assert run.ending_position * 10 / run.final_equity == pytest.approx(0.30)


def test_minimum_cash_and_cap_allow_a_real_tiny_high_price_fill() -> None:
    candles = tape([(1_000_000_000, 1_000_000_000)] * 2)
    request = request_for(2, start_price=1_000_000_000, starting_cash=0.01, max_position_pct=0.0001)

    run = simulate_strategy(request, candles, ScriptedStrategy({0: ("BUY", 1.0)}))

    fill, = events_of(run, "fill")
    assert fill.quantity > 0
    assert fill.quantity * candles[1].open == pytest.approx(1e-8)
    assert 100 * run.ending_position * candles[1].close / run.final_equity == pytest.approx(0.0001)


def test_phantom_cap_fill_cannot_replace_momentum_entry_and_trigger_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MAX_POSITION_SIZE", 0.30)
    first_quantity = 3_000 / 11
    first_cost = 10 * (1 + 5 / 10_000) * (1 + 10 / 10_000)
    cash_after_buy = 10_000 - first_quantity * first_cost
    cap_open = math.nextafter(0.30 * cash_after_buy / (0.70 * first_quantity), -math.inf)
    candles = tape([(10, 10), (10, 11), (10, 11.2), (cap_open, 10.2), (10.2, 10.2)])
    request = request_for(5, starting_cash=10_000, fee_bps=10, slippage_bps=5, max_position_pct=30)
    strategy = MomentumStrategy(symbol="SIM", window=2, threshold=0.01, stop_loss=0.10)

    run = simulate_strategy(request, candles, strategy)

    buy, = events_of(run, "fill")
    assert buy.action == "BUY" and buy.price == pytest.approx(10.005)
    assert any(event.candle_index == 3 and event.action == "BUY" for event in events_of(run, "rejected"))
    assert not any(event.action == "SELL" for event in run.events)
    assert strategy._entry_price == pytest.approx(10.005)
    assert run.final_equity == pytest.approx(cash_after_buy + first_quantity * 10.2)


def test_buy_and_hold_uses_the_same_entry_timing_and_costs() -> None:
    candles = tape([(100, 100), (100, 100), (100, 100)])
    request = request_for(3, fee_bps=100.0, slippage_bps=100.0)
    strategy = ScriptedStrategy({0: ("BUY", 1_000_000.0)})

    bot = simulate_strategy(request, candles, strategy)
    benchmark = simulate_benchmark(request, candles)

    bot_fill, = events_of(bot, "fill")
    benchmark_fill, = events_of(benchmark, "fill")
    assert benchmark_fill.candle_index == bot_fill.candle_index == 1
    assert benchmark_fill.price == pytest.approx(bot_fill.price)
    assert benchmark_fill.quantity == pytest.approx(bot_fill.quantity)
    assert benchmark_fill.fee == pytest.approx(bot_fill.fee)
    assert benchmark.total_fees == pytest.approx(bot.total_fees)
    assert benchmark.final_equity == pytest.approx(bot.final_equity)


def test_drawdown_guard_blocks_later_buys_but_does_not_force_a_sale() -> None:
    candles = tape([(100, 100), (100, 60), (60, 50), (50, 50)])
    request = request_for(
        4, starting_cash=200.0, guard_enabled=True, guard_drawdown_pct=15.0
    )
    signals = {0: ("BUY", 1.0), 1: ("BUY", 1.0), 2: ("SELL", 1.0)}

    guarded = simulate_strategy(request, candles, ScriptedStrategy(signals), use_guard=True)
    unguarded = simulate_strategy(request, candles, ScriptedStrategy(signals), use_guard=False)

    assert guarded.guard_trigger_index == 1
    assert guarded.equity_curve[1].position == pytest.approx(1.0)
    assert guarded.equity_curve[2].position == pytest.approx(1.0)
    guard_fills = events_of(guarded, "fill")
    assert not any(e.action == "BUY" and e.candle_index > 1 for e in guard_fills)
    assert any(e.action == "SELL" and e.candle_index == 3 for e in guard_fills)
    assert any(e.action == "BUY" and e.candle_index == 2 for e in events_of(unguarded, "fill"))


@pytest.mark.parametrize("scale", [0.001, 1.0, 1_000_000.0])
@pytest.mark.parametrize(("close_offset", "triggered"), [(0.0, True), (0.0001, False)])
def test_guard_rounding_at_threshold_is_scale_aware(scale: float, close_offset: float, triggered: bool) -> None:
    # A $107 account holding one unit bought at $100 reaches exactly 3%
    # drawdown at $96.79. The offset case is measurably above that price.
    close = (96.79 + close_offset) * scale
    candles = [c.model_copy(update={"low": min(c.open, c.close)}) for c in tape([
        (100 * scale, 100 * scale), (100 * scale, close), (close, close),
    ])]
    request = request_for(3, start_price=100 * scale, starting_cash=107 * scale,
                          guard_enabled=True, guard_drawdown_pct=3, max_position_pct=100)
    run = simulate_strategy(request, candles, ScriptedStrategy({0: ("BUY", 1.0), 1: ("BUY", 0.01)}), use_guard=True)

    assert (run.guard_trigger_index == 1) is triggered
    assert bool(events_of(run, "blocked")) is triggered
    assert len(events_of(run, "fill")) == (1 if triggered else 2)
    assert any("four floating-point ULPs" in item for item in run_survival(request).assumptions)


def test_momentum_stop_loss_uses_next_open_fill_not_signal_close() -> None:
    # The first momentum signal is at 110; the next open gaps to 200.
    # With 1% slippage the real simulated entry is 202. A close of 180
    # therefore breaches a 10% stop, despite being above the signal price.
    candles = tape([(100, 100), (100, 110), (200, 180), (180, 180)])
    strategy = MomentumStrategy(symbol="SIM", window=2, threshold=0.01, stop_loss=0.10)

    run = simulate_strategy(request_for(4, slippage_bps=100.0), candles, strategy)

    buys = [e for e in events_of(run, "fill") if e.action == "BUY"]
    sells = [e for e in events_of(run, "fill") if e.action == "SELL"]
    stop_signals = [e for e in events_of(run, "signal") if e.action == "SELL"]
    assert len(buys) == 1 and buys[0].candle_index == 2
    assert buys[0].price == pytest.approx(202.0)
    assert any(e.candle_index == 2 and "stop" in e.reason.lower() for e in stop_signals)
    assert len(sells) == 1 and sells[0].candle_index == 3


def test_momentum_repeated_entry_tracks_latest_executed_fill() -> None:
    candles = tape([(100, 100), (100, 110), (100, 120), (200, 180), (180, 180)])
    strategy = MomentumStrategy(symbol="SIM", window=2, threshold=0.01, stop_loss=0.10)

    run = simulate_strategy(request_for(5, slippage_bps=100.0), candles, strategy)

    buys = [e for e in events_of(run, "fill") if e.action == "BUY"]
    assert [e.candle_index for e in buys] == [2, 3]
    assert [e.price for e in buys] == pytest.approx([101.0, 202.0])
    assert any(
        e.candle_index == 3 and e.action == "SELL" and "stop" in e.reason.lower()
        for e in events_of(run, "signal")
    )
    assert any(e.candle_index == 4 and e.action == "SELL" for e in events_of(run, "fill"))


def test_expired_momentum_buy_does_not_create_a_fictitious_entry() -> None:
    candles = tape([(100, 100), (100, 110)])
    strategy = MomentumStrategy(symbol="SIM", window=2, threshold=0.01, stop_loss=0.10)

    run = simulate_strategy(request_for(2), candles, strategy)

    assert events_of(run, "fill") == []
    assert any(e.action == "BUY" for e in events_of(run, "expired"))
    assert strategy._entry_price is None


def test_guard_blocked_momentum_buy_does_not_replace_last_fill_price() -> None:
    candles = tape([(100, 100), (100, 110), (100, 60), (60, 130), (130, 130)])
    strategy = MomentumStrategy(symbol="SIM", window=2, threshold=0.01, stop_loss=0.90)
    request = request_for(5, guard_enabled=True, guard_drawdown_pct=5.0)

    run = simulate_strategy(request, candles, strategy, use_guard=True)

    buys = [e for e in events_of(run, "fill") if e.action == "BUY"]
    assert run.guard_trigger_index == 2
    assert len(buys) == 1 and buys[0].price == pytest.approx(100.0)
    assert strategy._entry_price == pytest.approx(100.0)
    assert not any(e.action == "BUY" and e.candle_index > 2 for e in buys)


def test_position_cap_rejected_momentum_buy_does_not_replace_last_fill_price() -> None:
    candles = tape([(100, 100), (100, 110), (110, 120), (120, 120)])
    strategy = MomentumStrategy(symbol="SIM", window=2, threshold=0.01, stop_loss=0.90)
    request = request_for(4, max_position_pct=30.0)

    run = simulate_strategy(request, candles, strategy)

    buys = [e for e in events_of(run, "fill") if e.action == "BUY"]
    assert len(buys) == 1 and buys[0].price == pytest.approx(110.0)
    assert strategy._entry_price == pytest.approx(110.0)
    assert any(e.event_type in ("blocked", "rejected") and e.action == "BUY" for e in run.events)


def test_equity_curve_and_events_are_aligned_to_candle_timestamps() -> None:
    candles = tape([(100, 100), (100, 110), (110, 105), (105, 95)])
    run = simulate_strategy(
        request_for(4), candles, ScriptedStrategy({0: ("BUY", 1.0)})
    )

    assert len(run.equity_curve) == len(candles)
    for index, point in enumerate(run.equity_curve):
        assert point.index == index
        assert point.timestamp == candles[index].timestamp
        assert math.isfinite(point.equity)
    for event in run.events:
        assert 0 <= event.candle_index < len(candles)
        assert event.timestamp == candles[event.candle_index].timestamp
    assert run.final_equity == pytest.approx(run.equity_curve[-1].equity)


@pytest.mark.parametrize("strategy_key", ["simple_ma", "rsi", "bollinger_bands", "macd", "momentum"])
def test_full_replay_reconciles_fills_to_cash_position_and_equity(strategy_key: str) -> None:
    request = request_for(
        160, strategy_key=strategy_key, seed=42, shock_pct=30.0, shock_index=80,
        fee_bps=100.0, slippage_bps=100.0, guard_enabled=True,
        guard_drawdown_pct=3.0, max_position_pct=100.0,
    )
    result = run_survival(request)

    # Rebuild the ledger from executed trades, independently of the engine's
    # reported balances. Verify each close, not just the ending balance.
    assert result.guarded is not None
    for run in (result.unguarded, result.guarded, result.benchmark):
        cash = request.starting_cash
        position = fees = slippage = 0.0
        fills = [event for event in run.events if event.event_type == "fill"]
        assert len(fills) == run.trade_count > 0
        for index, (point, candle) in enumerate(zip(run.equity_curve, result.candles)):
            for fill in (event for event in fills if event.candle_index == index):
                assert fill.signal_index == index - 1
                assert fill.quantity > 0 and fill.price is not None
                assert fill.fee == pytest.approx(fill.quantity * fill.price * request.fee_bps / 10_000)
                fees += fill.fee
                slippage += abs(fill.price - candle.open) * fill.quantity
                if fill.action == "BUY":
                    assert fill.price >= candle.open
                    cash -= fill.quantity * fill.price + fill.fee
                    position += fill.quantity
                else:
                    assert fill.action == "SELL" and fill.price <= candle.open
                    cash += fill.quantity * fill.price - fill.fee
                    position -= fill.quantity
            assert math.isfinite(point.equity)
            assert cash >= -1e-7 and position >= -1e-7
            assert point.cash == pytest.approx(cash, abs=1e-7)
            assert point.position == pytest.approx(position, abs=1e-7)
            assert point.equity == pytest.approx(cash + position * candle.close, abs=1e-7)
        assert run.total_fees == pytest.approx(fees)
        assert run.total_slippage_cost == pytest.approx(slippage)
        assert run.ending_cash == pytest.approx(cash, abs=1e-7)
        assert run.ending_position == pytest.approx(position, abs=1e-7)


def test_scenario_fingerprint_is_reproducible_and_captures_assumptions() -> None:
    request = request_for(50, seed=123, shock_pct=20.0, shock_index=25)
    original = run_survival(request)
    repeated = run_survival(request)
    changed_fee = run_survival(request_for(50, seed=123, shock_pct=20.0, shock_index=25, fee_bps=25.0))
    changed_seed = run_survival(request_for(50, seed=124, shock_pct=20.0, shock_index=25))

    assert original.scenario.source == "synthetic"
    assert original.scenario.seed == 123
    assert original.scenario.shock_index == 25
    assert original.scenario.shock_pct == pytest.approx(20.0)
    assert len(original.candles) == 50
    assert original.fingerprint
    assert original.fingerprint == repeated.fingerprint
    assert original.model_dump(mode="json") == repeated.model_dump(mode="json")
    assert original.fingerprint != changed_fee.fingerprint
    assert original.fingerprint != changed_seed.fingerprint


@pytest.mark.parametrize("strategy_key", ["simple_ma", "rsi", "bollinger_bands", "macd", "momentum"])
def test_passport_reports_strategy_parameters_and_engine_version(strategy_key: str) -> None:
    request = request_for(50, strategy_key=strategy_key)
    response = run_survival(request)
    assert response.strategy_parameters == get_strategy_defaults(strategy_key)
    assert response.strategy_key == strategy_key
    assert response.request == request
    assert response.engine_version == survival.ENGINE_VERSION
    assert response.engine_version


def test_fingerprint_changes_when_engine_version_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    request = request_for(30)
    original = run_survival(request)
    monkeypatch.setattr(survival, "ENGINE_VERSION", "test-version-change")

    changed = run_survival(request)

    assert changed.candles == original.candles
    assert changed.engine_version == "test-version-change"
    assert changed.fingerprint != original.fingerprint


def test_v4_fingerprint_differs_from_v3_for_the_same_request_and_tape(monkeypatch: pytest.MonkeyPatch) -> None:
    request = request_for(30, strategy_key="momentum", seed=123, shock_pct=20, shock_index=15)
    monkeypatch.setattr(survival, "ENGINE_VERSION", "survival-lab-v3")
    v3 = run_survival(request)
    monkeypatch.setattr(survival, "ENGINE_VERSION", "survival-lab-v4")
    v4 = run_survival(request)
    assert v3.candles == v4.candles
    assert v3.request == v4.request == request
    assert v3.strategy_key == v4.strategy_key == request.strategy_key
    assert v3.fingerprint != v4.fingerprint


def test_signal_sizing_configuration_is_reported_and_changes_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = request_for(
        120, strategy_key="rsi", seed=42, shock_pct=20.0,
        shock_index=80, max_position_pct=100.0,
    )
    monkeypatch.setattr(settings, "MAX_POSITION_SIZE", 0.30)
    full = run_survival(request)
    monkeypatch.setattr(settings, "MAX_POSITION_SIZE", 0.15)
    half = run_survival(request)
    full_first = next(
        e for e in full.unguarded.events if e.event_type == "signal" and e.action == "BUY"
    )
    half_first = next(
        e for e in half.unguarded.events if e.event_type == "signal" and e.action == "BUY"
    )

    assert full.signal_cash_fraction == pytest.approx(0.30)
    assert half.signal_cash_fraction == pytest.approx(0.15)
    assert full.candles == half.candles
    assert half_first.quantity == pytest.approx(full_first.quantity / 2)
    assert full.fingerprint != half.fingerprint


def test_synthetic_shock_preserves_prefix_and_changes_only_future_path() -> None:
    unshocked = run_survival(request_for(50, seed=7))
    shocked = run_survival(request_for(50, seed=7, shock_pct=20.0, shock_index=25))

    assert unshocked.scenario.shock_index is None
    assert shocked.scenario.shock_index == 25
    assert shocked.candles[:25] == unshocked.candles[:25]
    assert shocked.candles[25].open == pytest.approx(unshocked.candles[25].open * 0.8)
    assert shocked.candles[25].close == pytest.approx(unshocked.candles[25].close * 0.8)
    assert shocked.scenario.source == "synthetic"


@pytest.mark.parametrize(
    "bad_candle",
    [
        {"open": float("nan")},
        {"close": -1.0},
        {"high": 99.0},
        {"volume": -1.0},
        {"symbol": "OTHER"},
        {"timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc)},
    ],
)
def test_invalid_market_tapes_are_rejected(bad_candle: dict[str, object]) -> None:
    candles = tape([(100, 100), (100, 100), (100, 100)])
    candles[1] = candles[1].model_copy(update=bad_candle)

    with pytest.raises(ValueError):
        simulate_strategy(request_for(3), candles, ScriptedStrategy({}))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("num_candles", 1),
        ("num_candles", 601),
        ("starting_cash", 0.0),
        ("starting_cash", float("nan")),
        ("start_price", float("inf")),
        ("fee_bps", -1.0),
        ("fee_bps", 501.0),
        ("slippage_bps", float("nan")),
        ("shock_pct", 81.0),
        ("guard_drawdown_pct", 0.0),
        ("max_position_pct", 101.0),
    ],
)
def test_invalid_or_nonfinite_parameters_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        request_for(50, **{field: value})


@pytest.mark.parametrize("field", ["max_position_pct", "guard_drawdown_pct"])
def test_smallest_supported_percentage_is_inclusive(field: str) -> None:
    assert getattr(request_for(3, **{field: 0.0001}), field) == 0.0001


@pytest.mark.parametrize("field", ["max_position_pct", "guard_drawdown_pct"])
@pytest.mark.parametrize("value", [math.nextafter(0.0001, 0.0), math.ulp(0.0), 0.0])
def test_subminimum_percentages_are_rejected(field: str, value: float) -> None:
    with pytest.raises(ValueError):
        request_for(3, **{field: value})


def test_smallest_supported_position_cap_can_still_produce_a_real_fill() -> None:
    candles = tape([(100, 100), (100, 100)])
    request = request_for(2, max_position_pct=0.0001)
    run = simulate_strategy(request, candles, ScriptedStrategy({0: ("BUY", 1.0)}))
    fill, = events_of(run, "fill")
    assert fill.quantity > 0
    assert 100 * run.ending_position * candles[-1].close / run.final_equity == pytest.approx(0.0001)
