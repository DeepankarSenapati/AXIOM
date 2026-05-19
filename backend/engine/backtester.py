import math

from backend.engine.bot_runner import BotRunner
from backend.engine.models import BacktestResult, Candle, TradeRecord


def _sharpe_ratio(records: list[TradeRecord], start_cash: float) -> float:
    """Annualised Sharpe ratio from the per-tick equity series (252 trading days)."""
    if len(records) < 2:
        return 0.0
    equities = [start_cash + r.pnl for r in records]
    raw_returns = [
        (equities[i] - equities[i - 1]) / equities[i - 1]
        for i in range(1, len(equities))
        if equities[i - 1] != 0
    ]
    returns = [0.0 if math.isnan(r) or math.isinf(r) else r for r in raw_returns]
    if len(returns) < 2:
        return 0.0
    n = len(returns)
    mean = sum(returns) / n
    variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
    std = math.sqrt(variance)
    if std == 0:
        return 0.0
    return (mean / std) * math.sqrt(252)


def _max_drawdown(records: list[TradeRecord], start_cash: float) -> float:
    """Largest peak-to-trough decline in equity, returned as a negative fraction."""
    if not records:
        return 0.0
    peak = start_cash
    max_dd = 0.0
    for r in records:
        equity = start_cash + r.pnl
        if math.isnan(equity) or math.isinf(equity):
            continue
        if equity > peak:
            peak = equity
        if peak > 0:
            dd = (equity - peak) / peak
            if dd < max_dd:
                max_dd = dd
    return max_dd


class Backtester:
    def __init__(self, runner: BotRunner) -> None:
        self.runner = runner

    def run(self, candles: list[Candle]) -> BacktestResult:
        all_records = self.runner.run(candles)
        trade_records = [r for r in all_records if r.action_type in ("BUY", "SELL")]

        start_cash = self.runner.starting_cash
        end_cash = all_records[-1].cash_after if all_records else start_cash
        final_pnl = all_records[-1].pnl if all_records else 0.0
        total_trades = len(trade_records)

        return BacktestResult(
            bot_id=self.runner.bot_id,
            total_trades=total_trades,
            final_pnl=final_pnl,
            trade_records=trade_records,
            start_cash=start_cash,
            end_cash=end_cash,
            sharpe_ratio=_sharpe_ratio(all_records, start_cash),
            max_drawdown=_max_drawdown(all_records, start_cash),
        )
