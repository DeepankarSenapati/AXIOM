from backend.engine.backtester import Backtester
from backend.engine.bot_runner import BotRunner
from backend.engine.models import ArenaResult, Candle


class Arena:
    def __init__(self, bots: list[tuple[str, BotRunner]]) -> None:
        # bots: list of (bot_id, BotRunner) — bot_id must match runner.bot_id
        self.bots = bots

    def run(self, candles: list[Candle]) -> ArenaResult:
        results = {}
        for bot_id, runner in self.bots:
            backtester = Backtester(runner)
            results[bot_id] = backtester.run(candles)
        return ArenaResult(results=results)
