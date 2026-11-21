from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.api.models import (
    ArenaResultResponse,
    BacktestRequest,
    BacktestResultResponse,
    BacktestRunResponse,
    LeaderboardEntryResponse,
    RunArenaRequest,
    TradeRecordResponse,
)
from backend.bots.registry import UnknownStrategyError, get_strategy_class
from backend.db.models import DBBacktestRun, DBBot
from backend.db.session import get_db
from backend.engine.backtester import Backtester
from backend.engine.bot_runner import BotRunner
from backend.engine.market_feed import CCXTFeed, MarketFeedError, MockMarketFeed, YFinanceFeed
from backend.engine.models import BacktestResult, Candle, TradeRecord

router = APIRouter(prefix="/arena", tags=["arena"])


def _is_indian_symbol(symbol: str) -> bool:
    """NSE stocks end with '.NS'; indices start with '^'."""
    return symbol.endswith(".NS") or symbol.startswith("^")


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


def _fetch_candles(payload: RunArenaRequest | BacktestRequest) -> list[Candle]:
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
    seed = getattr(payload, "seed", None)
    return MockMarketFeed().generate(
        symbol=payload.symbol,
        n=payload.num_candles,
        start_price=payload.start_price,
        seed=seed,
    )


def _calc_benchmark(candles: list, starting_cash: float) -> float:
    """Buy-and-hold PnL: invest all cash at first candle close, sell at last."""
    if len(candles) < 2:
        return 0.0
    first_price = candles[0].close
    last_price = candles[-1].close
    if first_price <= 0:
        return 0.0
    shares = starting_cash / first_price
    return round((last_price - first_price) * shares, 2)


def _compute_win_rate(result: BacktestResult) -> float:
    """Fraction of nonzero sell fills profitable versus weighted average entry.

    Legacy fills contain no commissions; this is not a cost-adjusted metric.
    Multiple buys and partial sells retain the remaining position's cost basis.
    """
    holdings: dict[str, tuple[float, float]] = {}
    profits: list[float] = []
    for trade in result.trade_records:
        if trade.quantity <= 0:
            continue
        quantity, cost_basis = holdings.get(trade.symbol, (0.0, 0.0))
        if trade.action_type == "BUY":
            holdings[trade.symbol] = (quantity + trade.quantity, cost_basis + trade.quantity * trade.price)
        elif trade.action_type == "SELL" and quantity > 0:
            sold = min(quantity, trade.quantity)
            average_entry = cost_basis / quantity
            profits.append((trade.price - average_entry) * sold)
            remaining = max(0.0, quantity - sold)
            holdings[trade.symbol] = (remaining, average_entry * remaining)
    return sum(profit > 0 for profit in profits) / len(profits) if profits else 0.0


def _persist_run(
    db: Session,
    bot: DBBot,
    result: BacktestResult,
    payload: RunArenaRequest | BacktestRequest,
    symbol: str | None = None,
    benchmark_pnl: float = 0.0,
) -> None:
    """Insert one DBBacktestRun row for the given result. Append-only."""
    effective_symbol = symbol if symbol is not None else payload.symbol
    win_rate = _compute_win_rate(result)
    run = DBBacktestRun(
        id=str(uuid4()),
        bot_id=bot.id,
        bot_name=bot.name,
        strategy_key=bot.strategy_name,
        symbol=effective_symbol,
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
        benchmark_pnl=benchmark_pnl,
        created_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()


def _trade_to_response(record: TradeRecord) -> TradeRecordResponse:
    return TradeRecordResponse(
        bot_id=record.bot_id,
        symbol=record.symbol,
        action_type=record.action_type,
        quantity=record.quantity,
        price=record.price,
        timestamp=record.timestamp,
        reason=record.reason,
        cash_after=record.cash_after,
        pnl=record.pnl,
    )


def _to_response(result: BacktestResult, win_rate: float = 0.0, benchmark_pnl: float = 0.0) -> BacktestResultResponse:
    alpha = round(result.final_pnl - benchmark_pnl, 2)
    return BacktestResultResponse(
        bot_id=result.bot_id,
        total_trades=result.total_trades,
        final_pnl=result.final_pnl,
        start_cash=result.start_cash,
        end_cash=result.end_cash,
        win_rate=win_rate,
        sharpe_ratio=result.sharpe_ratio,
        max_drawdown=result.max_drawdown,
        benchmark_pnl=benchmark_pnl,
        alpha=alpha,
        trade_records=[_trade_to_response(record) for record in result.trade_records],
        equity_records=[_trade_to_response(record) for record in result.equity_records],
    )


@router.post("/run", response_model=ArenaResultResponse)
def run_arena(payload: RunArenaRequest, db: Session = Depends(get_db)) -> ArenaResultResponse:
    bots = db.query(DBBot).filter(DBBot.id.in_(payload.bot_ids), DBBot.is_active == True).all()  # noqa: E712

    missing = set(payload.bot_ids) - {b.id for b in bots}
    if missing:
        raise HTTPException(status_code=404, detail=f"Bots not found or inactive: {sorted(missing)}")

    # A symbol override must change the market data, not merely the action label.
    # Fetch each distinct symbol once so bots on the same market see identical bars.
    candles_by_symbol: dict[str, list[Candle]] = {}
    benchmarks_by_symbol: dict[str, float] = {}
    for bot in bots:
        symbol = payload.bot_symbols.get(bot.id, payload.symbol)
        if symbol not in candles_by_symbol:
            symbol_payload = payload.model_copy(update={"symbol": symbol})
            candles = _fetch_candles(symbol_payload)
            candles_by_symbol[symbol] = candles
            benchmarks_by_symbol[symbol] = _calc_benchmark(candles, payload.starting_cash)

    results: dict[str, BacktestResult] = {}
    for bot in bots:
        symbol = payload.bot_symbols.get(bot.id, payload.symbol)
        try:
            runner = _build_runner(bot, symbol, payload.starting_cash)
            results[bot.id] = Backtester(runner).run(candles_by_symbol[symbol])
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Arena run failed: {exc}") from exc

    for bot in bots:
        symbol = payload.bot_symbols.get(bot.id, payload.symbol)
        _persist_run(db, bot, results[bot.id], payload, symbol=symbol, benchmark_pnl=benchmarks_by_symbol[symbol])

    return ArenaResultResponse(
        results={
            bot.id: _to_response(
                results[bot.id], _compute_win_rate(results[bot.id]),
                benchmarks_by_symbol[payload.bot_symbols.get(bot.id, payload.symbol)],
            )
            for bot in bots
        }
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
    benchmark_pnl = _calc_benchmark(candles, payload.starting_cash)

    try:
        runner = _build_runner(bot, payload.symbol, payload.starting_cash)
        backtester = Backtester(runner)
        result = backtester.run(candles)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Backtest failed: {exc}") from exc

    _persist_run(db, bot, result, payload, benchmark_pnl=benchmark_pnl)
    return _to_response(result, _compute_win_rate(result), benchmark_pnl)


def _run_to_response(run: DBBacktestRun) -> BacktestRunResponse:
    benchmark_pnl = run.benchmark_pnl if run.benchmark_pnl is not None else 0.0
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
        benchmark_pnl=benchmark_pnl,
        alpha=round(run.final_pnl - benchmark_pnl, 2),
        created_at=run.created_at,
    )


@router.get("/history", response_model=list[BacktestRunResponse])
def get_history(
    bot_id: str | None = None,
    symbol: str | None = None,
    strategy_key: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[BacktestRunResponse]:
    """Return backtest/arena runs ordered by created_at descending, with optional filters."""
    q = db.query(DBBacktestRun)
    if bot_id:
        q = q.filter(DBBacktestRun.bot_id == bot_id)
    if symbol:
        q = q.filter(DBBacktestRun.symbol == symbol)
    if strategy_key:
        q = q.filter(DBBacktestRun.strategy_key == strategy_key)
    runs = q.order_by(DBBacktestRun.created_at.desc()).limit(limit).all()
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


@router.get("/history/{run_id}", response_model=BacktestRunResponse)
def get_history_run(run_id: str, db: Session = Depends(get_db)) -> BacktestRunResponse:
    """Return a single backtest/arena run by its ID."""
    run = db.query(DBBacktestRun).filter(DBBacktestRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return _run_to_response(run)


@router.get("/leaderboard", response_model=list[LeaderboardEntryResponse])
def get_leaderboard(db: Session = Depends(get_db)) -> list[LeaderboardEntryResponse]:
    """Return per-strategy aggregated stats ranked by average Sharpe ratio."""
    rows = (
        db.query(
            DBBacktestRun.strategy_key,
            func.count(DBBacktestRun.id).label("total_runs"),
            func.avg(DBBacktestRun.sharpe_ratio).label("avg_sharpe"),
            func.avg(DBBacktestRun.final_pnl).label("avg_pnl"),
            func.max(DBBacktestRun.final_pnl).label("best_pnl"),
            func.avg(DBBacktestRun.win_rate).label("avg_win_rate"),
            func.avg(DBBacktestRun.final_pnl - DBBacktestRun.benchmark_pnl).label("avg_alpha"),
        )
        .group_by(DBBacktestRun.strategy_key)
        .order_by(func.avg(DBBacktestRun.sharpe_ratio).desc())
        .all()
    )
    return [
        LeaderboardEntryResponse(
            rank=i + 1,
            strategy_key=r.strategy_key,
            total_runs=r.total_runs,
            avg_sharpe=round(float(r.avg_sharpe or 0), 3),
            avg_pnl=round(float(r.avg_pnl or 0), 2),
            best_pnl=round(float(r.best_pnl or 0), 2),
            avg_win_rate=round(float(r.avg_win_rate or 0), 3),
            avg_alpha=round(float(r.avg_alpha or 0), 2),
        )
        for i, r in enumerate(rows)
    ]
