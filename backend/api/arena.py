from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.models import (
    ArenaResultResponse,
    BacktestRequest,
    BacktestResultResponse,
    RunArenaRequest,
    TradeRecordResponse,
)
from backend.bots.registry import UnknownStrategyError, get_strategy_class
from backend.db.models import DBBot
from backend.db.session import get_db
from backend.engine.arena import Arena
from backend.engine.backtester import Backtester
from backend.engine.bot_runner import BotRunner
from backend.engine.market_feed import CCXTFeed, MarketFeedError, MockMarketFeed
from backend.engine.models import BacktestResult

router = APIRouter(prefix="/arena", tags=["arena"])


def _build_runner(bot: DBBot, symbol: str, starting_cash: float) -> BotRunner:
    try:
        strategy_cls = get_strategy_class(bot.strategy_name)
    except UnknownStrategyError:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown strategy '{bot.strategy_name}' for bot '{bot.id}'",
        )
    strategy = strategy_cls(symbol=symbol)
    return BotRunner(bot_id=bot.id, strategy=strategy, starting_cash=starting_cash)


def _fetch_candles(payload: RunArenaRequest | BacktestRequest) -> list:
    if payload.data_source == "live":
        try:
            return CCXTFeed().fetch_historical(
                symbol=payload.symbol,
                timeframe=payload.timeframe,
                limit=payload.num_candles,
            )
        except MarketFeedError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
    return MockMarketFeed().generate(
        symbol=payload.symbol,
        n=payload.num_candles,
        start_price=payload.start_price,
    )


def _to_response(result: BacktestResult) -> BacktestResultResponse:
    return BacktestResultResponse(
        bot_id=result.bot_id,
        total_trades=result.total_trades,
        final_pnl=result.final_pnl,
        start_cash=result.start_cash,
        end_cash=result.end_cash,
        sharpe_ratio=result.sharpe_ratio,
        max_drawdown=result.max_drawdown,
        trade_records=[
            TradeRecordResponse(
                bot_id=r.bot_id,
                symbol=r.symbol,
                action_type=r.action_type,
                quantity=r.quantity,
                price=r.price,
                timestamp=r.timestamp,
                reason=r.reason,
                cash_after=r.cash_after,
                pnl=r.pnl,
            )
            for r in result.trade_records
        ],
    )


@router.post("/run", response_model=ArenaResultResponse)
def run_arena(payload: RunArenaRequest, db: Session = Depends(get_db)) -> ArenaResultResponse:
    bots = db.query(DBBot).filter(DBBot.id.in_(payload.bot_ids), DBBot.is_active == True).all()  # noqa: E712

    missing = set(payload.bot_ids) - {b.id for b in bots}
    if missing:
        raise HTTPException(status_code=404, detail=f"Bots not found or inactive: {sorted(missing)}")

    candles = _fetch_candles(payload)

    runners = [(bot.id, _build_runner(bot, payload.symbol, payload.starting_cash)) for bot in bots]
    arena = Arena(bots=runners)
    arena_result = arena.run(candles)

    return ArenaResultResponse(
        results={bot_id: _to_response(result) for bot_id, result in arena_result.results.items()}
    )


@router.post("/backtest/{bot_id}", response_model=BacktestResultResponse)
def backtest_bot(
    bot_id: str,
    payload: BacktestRequest,
    db: Session = Depends(get_db),
) -> BacktestResultResponse:
    bot = db.query(DBBot).filter(DBBot.id == bot_id, DBBot.is_active == True).first()  # noqa: E712
    if bot is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found or inactive")

    candles = _fetch_candles(payload)

    runner = _build_runner(bot, payload.symbol, payload.starting_cash)
    backtester = Backtester(runner)
    result = backtester.run(candles)
    return _to_response(result)
