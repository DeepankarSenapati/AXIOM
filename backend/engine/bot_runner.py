from backend.bots.strategies.base import BaseStrategy
from backend.engine.models import Action, Candle, Portfolio, TradeRecord


class InsufficientFundsError(Exception):
    pass


class BotRunner:
    def __init__(self, bot_id: str, strategy: BaseStrategy, starting_cash: float) -> None:
        self.bot_id = bot_id
        self.strategy = strategy
        self.starting_cash = starting_cash

    def run(self, candles: list[Candle]) -> list[TradeRecord]:
        portfolio = Portfolio(cash=self.starting_cash, positions={}, pnl=0.0)
        records: list[TradeRecord] = []

        for i in range(len(candles)):
            # Strategy receives history up to now — never future candles
            window = candles[: i + 1]
            action: Action = self.strategy.on_candle(window, portfolio)

            candle = candles[i]
            portfolio, record = self._execute(action, candle, portfolio)
            records.append(record)

        return records

    def _execute(
        self,
        action: Action,
        candle: Candle,
        portfolio: Portfolio,
    ) -> tuple[Portfolio, TradeRecord]:
        cash = portfolio.cash
        positions = dict(portfolio.positions)
        symbol = action.symbol or candle.symbol
        price = candle.close

        executed_qty = action.quantity

        if action.action_type == "BUY":
            cost = price * action.quantity
            if cost > cash:
                raise InsufficientFundsError(
                    f"Bot '{self.bot_id}' cannot BUY {action.quantity} of {symbol} "
                    f"at {price}: cost {cost:.2f} exceeds cash {cash:.2f}"
                )
            cash -= cost
            positions[symbol] = positions.get(symbol, 0.0) + action.quantity

        elif action.action_type == "SELL":
            held = positions.get(symbol, 0.0)
            executed_qty = min(action.quantity, held)
            cash += price * executed_qty
            positions[symbol] = held - executed_qty

        # Compute unrealised PnL: sum of (current_price * qty) for all positions minus starting cash offset
        position_value = sum(positions.get(s, 0.0) * price for s in positions)
        pnl = (cash + position_value) - self.starting_cash

        new_portfolio = Portfolio(cash=cash, positions=positions, pnl=pnl)
        record = TradeRecord(
            bot_id=self.bot_id,
            symbol=symbol,
            action_type=action.action_type,
            quantity=executed_qty,
            price=price,
            timestamp=candle.timestamp,
            reason=action.reason,
            cash_after=cash,
            pnl=pnl,
        )
        return new_portfolio, record
