from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.models import (
    ArenaResultResponse,
    BacktestRequest,
    BacktestResultResponse,
    BacktestRunResponse,
    RunArenaRequest,
    TradeRecordResponse,
)
from backend.bots.registry import UnknownStrategyError, get_strategy_class
from backend.db.models import DBBacktestRun, DBBot
from backend.db.session import get_db
from backend.engine.arena import Arena
from backend.engine.backtester import Backtester
from backend.engine.bot_runner import BotRunner
from backend.engine.market_feed import CCXTFeed, MarketFeedError, MockMarketFeed, YFinanceFeed


def _is_indian_symbol(symbol: str) -> bool:
    """NSE stocks end with '.NS'; indices start with '^'."""
    return symbol.endswith(".NS") or symbol.startswith("^")
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
    params: dict = bot.params if bot.params else {}
    strategy = strategy_cls(symbol=symbol, **params)
    return BotRunner(bot_id=bot.id, strategy=strategy, starting_cash=starting_cash)


def _fetch_candles(payload: RunArenaRequest | BacktestRequest) -> list:
    if payload.data_source == "live":
        try:
            if _is_indian_symbol(payload.symbol):
                return YFinanceFeed().fetch_historical(
                    symbol=payload.symbol,
                    timeframe=payload.timeframe,
                    limit=payload.num_candles,
                )
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


def _compute_win_rate(result: BacktestResult) -> float:
    """Return fraction of trades with pnl > 0, or 0.0 if no trades."""
    if result.total_trades == 0:
        return 0.0
    winning = sum(1 for r in result.trade_records if r.pnl > 0)
    return winning / result.total_trades


def _persist_run(
    db: Session,
    bot: DBBot,
    result: BacktestResult,
    payload: RunArenaRequest | BacktestRequest,
) -> None:
    """Insert one DBBacktestRun row for the given result. Append-only."""
    win_rate = _compute_win_rate(result)
    run = DBBacktestRun(
        id=str(uuid4()),
        bot_id=bot.id,
        bot_name=bot.name,
        strategy_key=bot.strategy_name,
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        data_source=payload.data_source,
        num_candles=payload.num_candles,
        starting_cash=payload.starting_cash,
        final_pnl=result.final_pnl,
        end_cash=result.end_cash,
        total_trades=result.total_trades,
        win_rate=win_rate,
        sharpe_ratio=result.sharpe_ratio,
        max_drawdown=result.max_drawdown,
        created_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()


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

    try:
        runners = [(bot.id, _build_runner(bot, payload.symbol, payload.starting_cash)) for bot in bots]
        arena = Arena(bots=runners)
        arena_result = arena.run(candles)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Arena run failed: {exc}") from exc

    bot_map: dict[str, DBBot] = {b.id: b for b in bots}
    for bot_id, result in arena_result.results.items():
        _persist_run(db, bot_map[bot_id], result, payload)

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

    try:
        runner = _build_runner(bot, payload.symbol, payload.starting_cash)
        backtester = Backtester(runner)
        result = backtester.run(candles)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {exc}") from exc

    _persist_run(db, bot, result, payload)
    return _to_response(result)


def _run_to_response(run: DBBacktestRun) -> BacktestRunResponse:
    return BacktestRunResponse(
        id=run.id,
        bot_id=run.bot_id,
        bot_name=run.bot_name,
        strategy_key=run.strategy_key,
        symbol=run.symbol,
        timeframe=run.timeframe,
        data_source=run.data_source,
        num_candles=run.num_candles,
        starting_cash=run.starting_cash,
        final_pnl=run.final_pnl,
        end_cash=run.end_cash,
        total_trades=run.total_trades,
        win_rate=run.win_rate,
        sharpe_ratio=run.sharpe_ratio,
        max_drawdown=run.max_drawdown,
        created_at=run.created_at,
    )


@router.get("/history", response_model=list[BacktestRunResponse])
def get_history(db: Session = Depends(get_db)) -> list[BacktestRunResponse]:
    """Return the last 50 backtest/arena runs ordered by created_at descending."""
    runs = (
        db.query(DBBacktestRun)
        .order_by(DBBacktestRun.created_at.desc())
        .limit(50)
        .all()
    )
    return [_run_to_response(r) for r in runs]


@router.get("/history/best", response_model=BacktestRunResponse)
def get_best_run(db: Session = Depends(get_db)) -> BacktestRunResponse:
    """Return the single best backtest run by final_pnl."""
    run = (
        db.query(DBBacktestRun)
        .order_by(DBBacktestRun.final_pnl.desc())
        .first()
    )
    if run is None:
        raise HTTPException(status_code=404, detail="No backtest runs recorded yet")
    return _run_to_response(run)
