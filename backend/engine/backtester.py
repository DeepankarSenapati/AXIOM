from backend.engine.bot_runner import BotRunner
from backend.engine.models import BacktestResult, Candle


class Backtester:
    def __init__(self, runner: BotRunner) -> None:
        self.runner = runner

    def run(self, candles: list[Candle]) -> BacktestResult:
        records = self.runner.run(candles)

        start_cash = self.runner.starting_cash
        end_cash = records[-1].cash_after if records else start_cash
        final_pnl = records[-1].pnl if records else 0.0
        total_trades = sum(1 for r in records if r.action_type in ("BUY", "SELL"))

        return BacktestResult(
            bot_id=self.runner.bot_id,
            total_trades=total_trades,
            final_pnl=final_pnl,
            trade_records=records,
            start_cash=start_cash,
            end_cash=end_cash,
        )
