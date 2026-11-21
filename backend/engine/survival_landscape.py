"""Bounded, paired sensitivity experiments on one synthetic price generator."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.engine.survival import SurvivalRequest, SurvivalResponse, run_survival
from backend.engine.survival_data import resolved_shock_index
from backend.engine.survival_models import SurvivalRun


MAX_LANDSCAPE_CANDLES = 160
ShockPercent = Annotated[float, Field(ge=0.0, le=80.0, allow_inf_nan=False)]
FeeBps = Annotated[float, Field(ge=0.0, le=500.0, allow_inf_nan=False)]


class ShockLandscapeRequest(BaseModel):
    """Vary just the shock and per-fill fee, preserving every other input."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    scenario: SurvivalRequest
    shock_pcts: list[ShockPercent] = Field(default_factory=lambda: [0.0, 12.0, 20.0], min_length=2, max_length=3)
    fee_bps_values: list[FeeBps] = Field(default_factory=lambda: [0.0, 10.0, 50.0], min_length=2, max_length=3)

    @model_validator(mode="after")
    def validate_landscape_bounds(self) -> "ShockLandscapeRequest":
        if self.scenario.num_candles > MAX_LANDSCAPE_CANDLES:
            raise ValueError(f"Shock Landscape supports at most {MAX_LANDSCAPE_CANDLES} candles per cell")
        for name, values in (("shock_pcts", self.shock_pcts), ("fee_bps_values", self.fee_bps_values)):
            if values[0] != 0.0 or any(first >= second for first, second in zip(values, values[1:])):
                raise ValueError(f"{name} must start at zero and be strictly increasing")
        return self


class ShockLandscapeRun(BaseModel):
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    ending_cash: float
    ending_position: float
    total_fees: float
    total_slippage_cost: float
    fill_count: int
    blocked_buy_count: int
    guard_trigger_index: int | None
    prior_close_exposure_pct: float


class ShockLandscapeCell(BaseModel):
    shock_pct: float
    fee_bps: float
    request: SurvivalRequest
    fingerprint: str
    unguarded: ShockLandscapeRun
    guarded: ShockLandscapeRun | None


class ShockLandscapeResponse(BaseModel):
    scenario: SurvivalRequest
    shock_pcts: list[float]
    fee_bps_values: list[float]
    shock_index: int
    engine_version: str
    strategy_parameters: dict[str, int | float]
    signal_cash_fraction: float
    cells: list[ShockLandscapeCell]
    assumptions: list[str]


def _summarize(result: SurvivalResponse, run: SurvivalRun, shock_index: int) -> ShockLandscapeRun:
    prior = run.equity_curve[shock_index - 1]
    if prior.equity <= 0:
        raise ValueError("Prior-close equity must be positive to calculate exposure")
    exposure_pct = 100.0 * prior.position * result.candles[shock_index - 1].close / prior.equity
    return ShockLandscapeRun(
        final_equity=run.final_equity,
        total_return_pct=run.total_return_pct,
        max_drawdown_pct=run.max_drawdown_pct,
        ending_cash=run.ending_cash,
        ending_position=run.ending_position,
        total_fees=run.total_fees,
        total_slippage_cost=run.total_slippage_cost,
        fill_count=run.trade_count,
        blocked_buy_count=sum(event.event_type == "blocked" and event.action == "BUY" for event in run.events),
        guard_trigger_index=run.guard_trigger_index,
        prior_close_exposure_pct=exposure_pct,
    )


def run_shock_landscape(request: ShockLandscapeRequest) -> ShockLandscapeResponse:
    """Replay the exact same synthetic scenario with bounded shock/fee axes."""
    request = ShockLandscapeRequest.model_validate(request.model_dump())
    shock_index = resolved_shock_index(request.scenario)
    cells: list[ShockLandscapeCell] = []
    first: SurvivalResponse | None = None
    for shock_pct in request.shock_pcts:
        for fee_bps in request.fee_bps_values:
            cell_request = request.scenario.model_copy(update={"shock_pct": shock_pct, "fee_bps": fee_bps})
            result = run_survival(cell_request)
            if first is None:
                first = result
            elif (
                result.engine_version != first.engine_version
                or result.strategy_parameters != first.strategy_parameters
                or result.signal_cash_fraction != first.signal_cash_fraction
            ):
                raise RuntimeError("simulation implementation or signal sizing changed during the landscape")
            cells.append(ShockLandscapeCell(
                shock_pct=shock_pct,
                fee_bps=fee_bps,
                request=cell_request,
                fingerprint=result.fingerprint,
                unguarded=_summarize(result, result.unguarded, shock_index),
                guarded=_summarize(result, result.guarded, shock_index) if result.guarded is not None else None,
            ))

    # Axis validation ensures at least four cells.
    assert first is not None
    return ShockLandscapeResponse(
        scenario=request.scenario,
        shock_pcts=request.shock_pcts,
        fee_bps_values=request.fee_bps_values,
        shock_index=shock_index,
        engine_version=first.engine_version,
        strategy_parameters=first.strategy_parameters,
        signal_cash_fraction=first.signal_cash_fraction,
        cells=cells,
        assumptions=[
            "These correlated cells vary one synthetic generator and seed; they are not probabilities, forecasts, independent evidence or real-market validation.",
            f"At candle index {shock_index}, a nonzero shock applies one downward open gap and permanently rescales subsequent synthetic prices; zero shock applies no gap.",
            "Cells share the same random factors; their prices differ after the shock. No dedicated recovery dynamics or historical crash is modeled.",
            "The fee axis is commission in basis points per fill; zero fee does not remove the separately configured slippage.",
            f"Each fill has {request.scenario.slippage_bps:g} bps adverse slippage; fills assume unlimited liquidity and exclude taxes, market impact, dividends and intrabar movement.",
            "Strategies see only current and earlier candles; eligible signals may fill at the next open, and final-bar signals cannot fill.",
            "Open positions are marked at the last close without liquidation or estimated exit costs.",
            f"Long-only without leverage; fill exposure is capped at {request.scenario.max_position_pct:g}% of post-cost equity.",
            f"Built-in buy signals request {first.signal_cash_fraction * 100:g}% of available cash at the signal close, separate from the execution position cap.",
            "The guard, when enabled, pauses new buys at the close that reaches its drawdown threshold; it does not liquidate positions or guarantee a loss limit.",
            "Prior-close exposure is the position value divided by equity immediately before the hypothetical shock gap; an earlier pending order may fill at that open and change exposure afterward.",
            "Blocked-buy counts are blocked signals, including any final-bar signal that could not have filled regardless.",
            "Momentum's stop-loss reference is its latest actual simulated buy fill, not average cost.",
            "Fingerprints hash each request, generated candles, declared strategy defaults, signal cash fraction and manual engine version, not source code; they are not signatures, independent audits or proof of execution.",
        ],
    )
