"""A bounded, descriptive sweep of the Survival Lab's artificial market generator.

Each outcome is produced by the normal single-world engine and may be replayed
there with the returned seed. Nothing here estimates real-market probabilities.
"""

from statistics import median

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.engine.survival import SurvivalRequest, SurvivalResponse, run_survival
from backend.engine.survival_models import SurvivalRun


MAX_SEED = 4_294_967_295
MAX_WORLD_CANDLES = 240
EQUALITY_RELATIVE_TOLERANCE = 1e-9


class SyntheticWorldsRequest(BaseModel):
    """Replay a scenario with consecutive seeds, preserving all other settings."""

    model_config = ConfigDict(extra="forbid")

    scenario: SurvivalRequest
    world_count: int = Field(default=12, ge=1, le=12)

    @model_validator(mode="after")
    def validate_sweep_bounds(self) -> "SyntheticWorldsRequest":
        if self.scenario.num_candles > MAX_WORLD_CANDLES:
            raise ValueError(f"Synthetic Worlds supports at most {MAX_WORLD_CANDLES} candles per world")
        if self.scenario.seed + self.world_count - 1 > MAX_SEED:
            raise ValueError("consecutive world seeds must fit in the 32-bit seed range")
        return self


class SyntheticWorldRunSummary(BaseModel):
    """Compact values from one actual replay; full traces are available by replay."""

    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    ending_cash: float
    ending_position: float
    total_fees: float
    total_slippage_cost: float
    trade_count: int
    guard_trigger_index: int | None


class SyntheticWorld(BaseModel):
    seed: int
    fingerprint: str
    unguarded: SyntheticWorldRunSummary
    guarded: SyntheticWorldRunSummary | None


class SyntheticWorldAggregate(BaseModel):
    median_total_return_pct: float
    worst_total_return_pct: float
    median_max_drawdown_pct: float
    worst_max_drawdown_pct: float


class SyntheticWorldComparison(BaseModel):
    guard_trigger_count: int
    improved_equity_count: int
    worsened_equity_count: int
    equal_equity_count: int
    equity_equality_tolerance: float


class SyntheticWorldsResponse(BaseModel):
    scenario: SurvivalRequest
    world_count: int
    engine_version: str
    strategy_parameters: dict[str, int | float]
    signal_cash_fraction: float
    worlds: list[SyntheticWorld]
    unguarded: SyntheticWorldAggregate
    guarded: SyntheticWorldAggregate | None
    comparison: SyntheticWorldComparison | None
    assumptions: list[str]


def _summarize(run: SurvivalRun) -> SyntheticWorldRunSummary:
    return SyntheticWorldRunSummary(
        final_equity=run.final_equity,
        total_return_pct=run.total_return_pct,
        max_drawdown_pct=run.max_drawdown_pct,
        ending_cash=run.ending_cash,
        ending_position=run.ending_position,
        total_fees=run.total_fees,
        total_slippage_cost=run.total_slippage_cost,
        trade_count=run.trade_count,
        guard_trigger_index=run.guard_trigger_index,
    )


def _aggregate(runs: list[SyntheticWorldRunSummary]) -> SyntheticWorldAggregate:
    return SyntheticWorldAggregate(
        median_total_return_pct=median(run.total_return_pct for run in runs),
        worst_total_return_pct=min(run.total_return_pct for run in runs),
        median_max_drawdown_pct=median(run.max_drawdown_pct for run in runs),
        worst_max_drawdown_pct=max(run.max_drawdown_pct for run in runs),
    )


def run_synthetic_worlds(request: SyntheticWorldsRequest) -> SyntheticWorldsResponse:
    """Describe a few deterministic samples of one synthetic generator, locally."""
    request = SyntheticWorldsRequest.model_validate(request.model_dump())
    worlds: list[SyntheticWorld] = []
    first: SurvivalResponse | None = None
    for offset in range(request.world_count):
        seed = request.scenario.seed + offset
        world_request = request.scenario.model_copy(update={"seed": seed})
        result = run_survival(world_request)
        if first is None:
            first = result
        elif (
            result.engine_version != first.engine_version
            or result.strategy_parameters != first.strategy_parameters
            or result.signal_cash_fraction != first.signal_cash_fraction
        ):
            raise RuntimeError("simulation implementation or signal sizing changed during the sweep")
        worlds.append(SyntheticWorld(
            seed=seed,
            fingerprint=result.fingerprint,
            unguarded=_summarize(result.unguarded),
            guarded=_summarize(result.guarded) if result.guarded is not None else None,
        ))

    # The request validator ensures at least one world.
    assert first is not None
    unguarded = _aggregate([world.unguarded for world in worlds])
    guarded: SyntheticWorldAggregate | None = None
    comparison: SyntheticWorldComparison | None = None
    tolerance = request.scenario.starting_cash * EQUALITY_RELATIVE_TOLERANCE
    if request.scenario.guard_enabled:
        guarded_runs = [world.guarded for world in worlds if world.guarded is not None]
        if len(guarded_runs) != len(worlds):
            raise RuntimeError("a guarded replay is missing from the sweep")
        guarded = _aggregate(guarded_runs)
        differences = [
            guarded_run.final_equity - world.unguarded.final_equity
            for world, guarded_run in zip(worlds, guarded_runs)
        ]
        comparison = SyntheticWorldComparison(
            guard_trigger_count=sum(run.guard_trigger_index is not None for run in guarded_runs),
            improved_equity_count=sum(difference > tolerance for difference in differences),
            worsened_equity_count=sum(difference < -tolerance for difference in differences),
            equal_equity_count=sum(abs(difference) <= tolerance for difference in differences),
            equity_equality_tolerance=tolerance,
        )

    return SyntheticWorldsResponse(
        scenario=request.scenario,
        world_count=len(worlds),
        engine_version=first.engine_version,
        strategy_parameters=first.strategy_parameters,
        signal_cash_fraction=first.signal_cash_fraction,
        worlds=worlds,
        unguarded=unguarded,
        guarded=guarded,
        comparison=comparison,
        assumptions=[
            "These are samples from one artificial generator, not probabilities, forecasts, independent evidence or real-market validation.",
            "Worlds use consecutive seeds; all other requested scenario, strategy, cost and guard settings remain the same.",
            "Medians, counts and worst values describe only these selected worlds; they do not predict unobserved scenarios.",
            f"Final equities count as equal when their absolute difference is at most {tolerance:g} cash units (1e-9 times starting cash).",
            "Each fingerprint can be reproduced by replaying its seed with the same scenario and implementation metadata; it is not an independent audit or proof of execution.",
            *first.assumptions,
        ],
    )
