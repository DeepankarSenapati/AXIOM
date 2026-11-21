"""Public entry point for the deterministic, local-only Survival Lab."""

import hashlib
import json
import math

import backend.config as settings
from backend.bots.registry import get_strategy_class, get_strategy_defaults
from backend.engine.survival_data import SYNTHETIC_SYMBOL, build_synthetic_candles, resolved_shock_index
from backend.engine.survival_execution import simulate_benchmark, simulate_strategy
from backend.engine.survival_models import SurvivalRequest, SurvivalResponse, SurvivalRun, SurvivalScenario


# Bump this when replay, fixture, strategy assumptions, or output semantics change.
ENGINE_VERSION = "survival-lab-v2"


def _assumptions(request: SurvivalRequest, signal_cash_fraction: float) -> list[str]:
    shock = (
        f"A single hypothetical {request.shock_pct:g}% downward gap is applied at bar {resolved_shock_index(request)}."
        if request.shock_pct > 0 else "No synthetic shock is applied."
    )
    return [
        "Synthetic seeded daily candles on a continuous calendar; not historical market data, a forecast, or live trading.",
        shock,
        "The strategy receives only current and prior candles, decides at the close, and may fill at the next open.",
        f"Built-in buy signals request {signal_cash_fraction * 100:g}% of available cash at the signal close; this is separate from the position cap applied at execution.",
        "A signal at the final close expires; open positions are marked at the last close without liquidation or estimated exit costs.",
        f"Long-only, no leverage; buys are capped at {request.max_position_pct:g}% of post-cost equity at execution.",
        f"Each fill uses {request.fee_bps:g} bps commission and {request.slippage_bps:g} bps adverse slippage.",
        "Fills assume unlimited available liquidity; taxes, market impact, dividends, intrabar movement and other costs are excluded.",
        "Guard, when enabled, permanently pauses new buys after the close reaches its drawdown threshold; sells remain allowed.",
        "The guard does not force liquidation and cannot guarantee a loss limit, especially through gaps.",
        "Buy-and-hold deploys all cash at the first eligible next open with the same entry costs; its exposure can differ from the strategy.",
        "Momentum's stop-loss reference is its latest actual simulated buy fill, not average cost.",
        "The fingerprint hashes the request, generated candles, declared strategy defaults, signal cash fraction and manual engine version, not source code; it is not a signature, independent audit or proof of execution.",
    ]


def run_survival(request: SurvivalRequest) -> SurvivalResponse:
    """Run the same deterministic tape through fresh unguarded/guarded bots."""
    request = SurvivalRequest.model_validate(request.model_dump())
    signal_cash_fraction = settings.MAX_POSITION_SIZE
    if isinstance(signal_cash_fraction, bool) or not isinstance(signal_cash_fraction, (int, float)):
        raise ValueError("MAX_POSITION_SIZE must be a finite cash fraction from 0 to 1")
    try:
        signal_cash_fraction = float(signal_cash_fraction)
    except OverflowError as exc:
        raise ValueError("MAX_POSITION_SIZE must be a finite cash fraction from 0 to 1") from exc
    if not math.isfinite(signal_cash_fraction) or not 0 <= signal_cash_fraction <= 1:
        raise ValueError("MAX_POSITION_SIZE must be a finite cash fraction from 0 to 1")
    candles = build_synthetic_candles(request)
    strategy_type = get_strategy_class(request.strategy_key)
    strategy_parameters = get_strategy_defaults(request.strategy_key)
    unguarded: SurvivalRun = simulate_strategy(
        request, candles, strategy_type(symbol=SYNTHETIC_SYMBOL, **strategy_parameters), use_guard=False,
    )
    guarded: SurvivalRun | None = (
        simulate_strategy(request, candles, strategy_type(symbol=SYNTHETIC_SYMBOL, **strategy_parameters), use_guard=True)
        if request.guard_enabled else None
    )
    benchmark = simulate_benchmark(request, candles)
    if settings.MAX_POSITION_SIZE != signal_cash_fraction:
        raise RuntimeError("MAX_POSITION_SIZE changed while the simulation was running")
    canonical = json.dumps(
        {
            "request": request.model_dump(mode="json"),
            "candles": [candle.model_dump(mode="json") for candle in candles],
            "strategy_parameters": strategy_parameters,
            "signal_cash_fraction": signal_cash_fraction,
            "engine_version": ENGINE_VERSION,
        },
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    return SurvivalResponse(
        fingerprint=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        engine_version=ENGINE_VERSION,
        strategy_parameters=strategy_parameters,
        signal_cash_fraction=signal_cash_fraction,
        scenario=SurvivalScenario(
            symbol=SYNTHETIC_SYMBOL, seed=request.seed, candle_count=len(candles),
            shock_index=resolved_shock_index(request) if request.shock_pct > 0 else None,
            shock_pct=request.shock_pct,
        ),
        assumptions=_assumptions(request, signal_cash_fraction),
        candles=candles, unguarded=unguarded, guarded=guarded, benchmark=benchmark,
    )
