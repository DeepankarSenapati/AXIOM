"""Causal, single-asset local replay with disclosed execution assumptions."""

import math
from datetime import datetime, timezone

from backend.bots.strategies.base import BaseStrategy
from backend.bots.strategies.momentum import MomentumStrategy
from backend.engine.models import Action, Candle, Portfolio
from backend.engine.survival_models import (
    SurvivalEquityPoint,
    SurvivalEvent,
    SurvivalRequest,
    SurvivalRun,
)


PERCENT_SCALE = 100.0
BPS_SCALE = 10_000.0


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def validate_candles(request: SurvivalRequest, candles: list[Candle]) -> None:
    """Reject malformed prices, mixed symbols and non-increasing timestamps."""
    if len(candles) != request.num_candles:
        raise ValueError("Candle count must match num_candles")
    symbol = candles[0].symbol
    if not symbol:
        raise ValueError("Candle symbol must not be empty")
    previous: datetime | None = None
    for candle in candles:
        current = _utc(candle.timestamp)
        if previous is not None and current <= previous:
            raise ValueError("Candle timestamps must be strictly increasing")
        previous = current
        if candle.symbol != symbol:
            raise ValueError("All candles must have the same symbol")
        values = (candle.open, candle.high, candle.low, candle.close, candle.volume)
        if any(not math.isfinite(v) for v in values):
            raise ValueError("OHLCV values must be finite")
        if min(candle.open, candle.high, candle.low, candle.close) <= 0 or candle.volume < 0:
            raise ValueError("OHLC prices must be positive and volume nonnegative")
        if candle.low > min(candle.open, candle.close) or candle.high < max(candle.open, candle.close):
            raise ValueError("Candle low/high must contain its open and close")


def _buy_quantity(
    request: SurvivalRequest, cash: float, position: float, open_price: float, desired: float
) -> float:
    """Cap both cash use and position share of post-cost equity at the open."""
    fee_rate = request.fee_bps / BPS_SCALE
    execution = open_price * (1.0 + request.slippage_bps / BPS_SCALE)
    unit_cost = execution * (1.0 + fee_rate)
    affordable = cash / unit_cost
    fraction = request.max_position_pct / PERCENT_SCALE
    equity_before = cash + position * open_price
    cap_value = fraction * equity_before
    position_value = position * open_price
    numerator = cap_value - position_value
    # When the position is already at the cap, subtraction can leave a few
    # floating-point ULPs of spurious headroom. Reject only that numerical
    # residue; an absolute quantity cutoff would discard legitimate small buys.
    tolerance = 4 * max(math.ulp(cap_value), math.ulp(position_value), fraction * math.ulp(equity_before))
    if numerator <= tolerance:
        return 0.0
    denominator = open_price - fraction * (open_price - unit_cost)
    capped = max(0.0, numerator / denominator)
    return max(0.0, min(desired, affordable, capped))


def _guard_reached(peak: float, equity: float, threshold_pct: float) -> bool:
    """Compare close-marked loss to the threshold, allowing rounding at the boundary."""
    threshold_loss = peak * (threshold_pct / PERCENT_SCALE)
    # Peak and equity can each contain rounding from mark-to-market arithmetic;
    # use their scale (and the computed threshold) rather than a fixed percent.
    tolerance = 4 * max(math.ulp(peak), math.ulp(equity), math.ulp(threshold_loss))
    return peak - equity >= threshold_loss - tolerance


def _event(
    index: int, candle: Candle, event_type: str, action: str, quantity: float,
    price: float | None, fee: float, reason: str, signal_index: int | None = None,
) -> SurvivalEvent:
    return SurvivalEvent(
        candle_index=index, timestamp=candle.timestamp, event_type=event_type,
        action=action, quantity=quantity, price=price, fee=fee, reason=reason,
        signal_index=signal_index,
    )


def _finish(
    request: SurvivalRequest, cash: float, position: float, fees: float,
    slippage: float, trades: int, trigger: int | None,
    curve: list[SurvivalEquityPoint], events: list[SurvivalEvent],
) -> SurvivalRun:
    final_equity = curve[-1].equity
    return SurvivalRun(
        final_equity=final_equity,
        total_return_pct=(final_equity / request.starting_cash - 1.0) * PERCENT_SCALE,
        max_drawdown_pct=max(point.drawdown_pct for point in curve),
        ending_cash=cash, ending_position=position, total_fees=fees,
        total_slippage_cost=slippage, trade_count=trades,
        guard_trigger_index=trigger, equity_curve=curve, events=events,
    )


def simulate_strategy(
    request: SurvivalRequest, candles: list[Candle], strategy: BaseStrategy, *, use_guard: bool = False
) -> SurvivalRun:
    """Run one strategy causally; a signal can fill only at the next bar open.

    The drawdown guard permanently blocks new BUY signals from the close where
    it triggers. It does not liquidate existing positions or guarantee a loss
    limit. The supplied strategy is stateful and must be fresh for each run.
    """
    request = SurvivalRequest.model_validate(request.model_dump())
    validate_candles(request, candles)
    symbol = candles[0].symbol
    cash, position = request.starting_cash, 0.0
    fees, slippage = 0.0, 0.0
    trades = 0
    peak = request.starting_cash
    trigger: int | None = None
    pending: tuple[int, Action] | None = None
    curve: list[SurvivalEquityPoint] = []
    events: list[SurvivalEvent] = []

    for index, candle in enumerate(candles):
        if pending is not None:
            signal_index, order = pending
            pending = None
            side = order.action_type
            price = candle.open * (1.0 + request.slippage_bps / BPS_SCALE * (1 if side == "BUY" else -1))
            qty = (
                _buy_quantity(request, cash, position, candle.open, order.quantity)
                if side == "BUY" else min(position, order.quantity)
            )
            if qty > 0.0:
                commission = qty * price * request.fee_bps / BPS_SCALE
                if side == "BUY":
                    cash = max(0.0, cash - qty * price - commission)
                    position += qty
                    if isinstance(strategy, MomentumStrategy):
                        strategy._entry_price = price
                else:
                    cash += qty * price - commission
                    position = max(0.0, position - qty)
                    if isinstance(strategy, MomentumStrategy) and position == 0.0:
                        strategy._entry_price = None
                fees += commission
                slippage += abs(price - candle.open) * qty
                trades += 1
                detail = "Next-open fill"
                if qty < order.quantity:
                    detail += "; quantity reduced by available cash, holdings, or position cap"
                events.append(_event(index, candle, "fill", side, qty, price, commission, detail, signal_index))
            else:
                events.append(_event(
                    index, candle, "rejected", side, 0.0, None, 0.0,
                    "No fill: insufficient cash, holdings, or position capacity.", signal_index,
                ))

        equity = cash + position * candle.close
        peak = max(peak, equity)
        drawdown = (peak - equity) / peak * PERCENT_SCALE
        curve.append(SurvivalEquityPoint(
            index=index, timestamp=candle.timestamp, equity=equity, cash=cash,
            position=position, drawdown_pct=drawdown,
        ))
        if use_guard and trigger is None and _guard_reached(peak, equity, request.guard_drawdown_pct):
            trigger = index
            events.append(_event(
                index, candle, "guard", "HOLD", 0.0, candle.close, 0.0,
                "Drawdown threshold reached at this close; new buys are paused for the remainder of this run.",
            ))

        portfolio = Portfolio(cash=cash, positions={symbol: position}, pnl=equity - request.starting_cash)
        history = [bar.model_copy(deep=True) for bar in candles[:index + 1]]
        # Momentum mutates its entry on signal. Only actual fills may update it
        # in this next-open model; preserve the prior fill state until then.
        entry_before = strategy._entry_price if isinstance(strategy, MomentumStrategy) else None
        action = strategy.on_candle(history, portfolio)
        if isinstance(strategy, MomentumStrategy):
            strategy._entry_price = entry_before
        if action.symbol != symbol:
            raise ValueError("Strategy action symbol must match the single-symbol candle series")
        if not math.isfinite(action.quantity) or action.quantity < 0:
            raise ValueError("Strategy action quantity must be finite and nonnegative")
        events.append(_event(
            index, candle, "signal", action.action_type, action.quantity,
            candle.close, 0.0, action.reason, index,
        ))
        if action.action_type == "HOLD":
            continue
        if action.action_type == "BUY" and trigger is not None:
            events.append(_event(
                index, candle, "blocked", "BUY", 0.0, None, 0.0,
                "New buy blocked by the drawdown guard; existing positions remain open.", index,
            ))
        elif index == len(candles) - 1:
            events.append(_event(
                index, candle, "expired", action.action_type, 0.0, None, 0.0,
                "No next candle exists, so this signal cannot fill.", index,
            ))
        else:
            pending = (index, action.model_copy(deep=True))

    return _finish(request, cash, position, fees, slippage, trades, trigger, curve, events)


def simulate_benchmark(request: SurvivalRequest, candles: list[Candle]) -> SurvivalRun:
    """Buy-and-hold uses the first eligible next open, costs, and full cash."""
    request = SurvivalRequest.model_validate(request.model_dump())
    validate_candles(request, candles)
    cash, position = request.starting_cash, 0.0
    fees, slippage = 0.0, 0.0
    peak = request.starting_cash
    curve: list[SurvivalEquityPoint] = []
    events: list[SurvivalEvent] = []
    for index, candle in enumerate(candles):
        if index == 0:
            events.append(_event(
                index, candle, "signal", "BUY", 0.0, candle.close, 0.0,
                "Allocate all available cash at the next bar open.", index,
            ))
        elif index == 1:
            price = candle.open * (1.0 + request.slippage_bps / BPS_SCALE)
            position = cash / (price * (1.0 + request.fee_bps / BPS_SCALE))
            fees = position * price * request.fee_bps / BPS_SCALE
            slippage = (price - candle.open) * position
            cash = max(0.0, cash - position * price - fees)
            events.append(_event(
                index, candle, "fill", "BUY", position, price, fees,
                "Buy-and-hold deploys available cash at the next open.", 0,
            ))
        equity = cash + position * candle.close
        peak = max(peak, equity)
        curve.append(SurvivalEquityPoint(
            index=index, timestamp=candle.timestamp, equity=equity, cash=cash,
            position=position, drawdown_pct=(peak - equity) / peak * PERCENT_SCALE,
        ))
    return _finish(request, cash, position, fees, slippage, 1, None, curve, events)
