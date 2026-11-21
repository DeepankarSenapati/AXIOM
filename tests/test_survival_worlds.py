"""Synthetic Worlds only summarises actual deterministic local replays."""
from statistics import median

import pytest

from backend.engine.survival import SurvivalRequest, run_survival
from backend.engine.survival_worlds import SyntheticWorldsRequest, run_synthetic_worlds


def scenario(**overrides: object) -> SurvivalRequest:
    values = {
        "strategy_key": "momentum",
        "seed": 1,
        "num_candles": 100,
        "shock_pct": 30.0,
        "shock_index": 60,
        "guard_enabled": True,
        "guard_drawdown_pct": 1.0,
        "max_position_pct": 100.0,
    }
    values.update(overrides)
    return SurvivalRequest(**values)


def test_worlds_match_replayed_results_and_derive_paired_aggregates() -> None:
    initial = scenario()
    request = SyntheticWorldsRequest(scenario=initial, world_count=5)
    batch = run_synthetic_worlds(request)
    repeated = run_synthetic_worlds(request)

    assert batch.model_dump(mode="json") == repeated.model_dump(mode="json")
    assert [world.seed for world in batch.worlds] == [1, 2, 3, 4, 5]
    assert batch.world_count == 5
    for world in batch.worlds:
        replay = run_survival(initial.model_copy(update={"seed": world.seed}))
        assert world.fingerprint == replay.fingerprint
        assert world.unguarded.final_equity == pytest.approx(replay.unguarded.final_equity)
        assert world.unguarded.total_fees == pytest.approx(replay.unguarded.total_fees)
        assert world.unguarded.max_drawdown_pct == pytest.approx(replay.unguarded.max_drawdown_pct)
        assert world.guarded is not None and replay.guarded is not None
        assert world.guarded.final_equity == pytest.approx(replay.guarded.final_equity)
        assert world.guarded.guard_trigger_index == replay.guarded.guard_trigger_index

    assert batch.unguarded.median_total_return_pct == pytest.approx(
        median(world.unguarded.total_return_pct for world in batch.worlds)
    )
    assert batch.unguarded.worst_total_return_pct == pytest.approx(
        min(world.unguarded.total_return_pct for world in batch.worlds)
    )
    assert batch.unguarded.worst_max_drawdown_pct == pytest.approx(
        max(world.unguarded.max_drawdown_pct for world in batch.worlds)
    )
    assert batch.guarded is not None
    assert batch.comparison is not None
    comparison = batch.comparison
    tolerance = initial.starting_cash * 1e-9
    differences = [world.guarded.final_equity - world.unguarded.final_equity for world in batch.worlds]
    assert comparison.equity_equality_tolerance == pytest.approx(tolerance)
    assert comparison.improved_equity_count == sum(value > tolerance for value in differences)
    assert comparison.worsened_equity_count == sum(value < -tolerance for value in differences)
    assert comparison.equal_equity_count == sum(abs(value) <= tolerance for value in differences)
    assert comparison.guard_trigger_count == sum(
        world.guarded.guard_trigger_index is not None for world in batch.worlds
    )
    # This deterministic sample deliberately includes both directions, so a
    # dashboard cannot silently present the guard as invariably beneficial.
    assert comparison.improved_equity_count > 0
    assert comparison.worsened_equity_count > 0
    assert comparison.equal_equity_count > 0


def test_guard_disabled_has_no_guarded_results_or_comparison() -> None:
    result = run_synthetic_worlds(SyntheticWorldsRequest(
        scenario=scenario(guard_enabled=False), world_count=2
    ))
    assert result.guarded is None
    assert result.comparison is None
    assert all(world.guarded is None for world in result.worlds)
    assert all(world.unguarded.guard_trigger_index is None for world in result.worlds)


@pytest.mark.parametrize("world_count", [0, 13])
def test_world_count_bounds(world_count: int) -> None:
    with pytest.raises(ValueError):
        SyntheticWorldsRequest(scenario=scenario(), world_count=world_count)


def test_sweep_rejects_too_many_candles_and_seed_overflow() -> None:
    with pytest.raises(ValueError):
        SyntheticWorldsRequest(scenario=scenario(num_candles=241), world_count=1)
    with pytest.raises(ValueError):
        SyntheticWorldsRequest(scenario=scenario(seed=4_294_967_295), world_count=2)
