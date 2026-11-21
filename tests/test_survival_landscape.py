"""The shock/fee grid must describe real, individually reproducible runs."""
import math

import pytest

from backend.engine.survival import SurvivalRequest, run_survival
from backend.engine.survival_landscape import ShockLandscapeRequest, run_shock_landscape


def scenario(**overrides: object) -> SurvivalRequest:
    values = {
        "strategy_key": "momentum", "seed": 1, "num_candles": 100,
        "shock_index": 60, "shock_pct": 12, "fee_bps": 10, "slippage_bps": 5,
        "guard_enabled": True, "guard_drawdown_pct": 1, "max_position_pct": 100,
    }
    values.update(overrides)
    return SurvivalRequest(**values)


def test_each_cell_is_an_exact_individually_replayable_experiment() -> None:
    initial = scenario()
    request = ShockLandscapeRequest(
        scenario=initial, shock_pcts=[0, 12, 20], fee_bps_values=[0, 10, 50]
    )
    grid = run_shock_landscape(request)
    assert grid.model_dump(mode="json") == run_shock_landscape(request).model_dump(mode="json")
    assert grid.shock_index == 60
    assert [(cell.shock_pct, cell.fee_bps) for cell in grid.cells] == [
        (shock, fee) for shock in (0, 12, 20) for fee in (0, 10, 50)
    ]

    for cell in grid.cells:
        expected = initial.model_copy(update={"shock_pct": cell.shock_pct, "fee_bps": cell.fee_bps})
        assert cell.request == expected
        replay = run_survival(expected)
        assert cell.fingerprint == replay.fingerprint
        assert grid.engine_version == replay.engine_version
        assert grid.strategy_parameters == replay.strategy_parameters
        assert grid.signal_cash_fraction == replay.signal_cash_fraction
        assert cell.guarded is not None and replay.guarded is not None
        for summary, run in ((cell.unguarded, replay.unguarded), (cell.guarded, replay.guarded)):
            assert summary.final_equity == pytest.approx(run.final_equity)
            assert summary.total_return_pct == pytest.approx(run.total_return_pct)
            assert summary.max_drawdown_pct == pytest.approx(run.max_drawdown_pct)
            assert summary.ending_cash == pytest.approx(run.ending_cash)
            assert summary.ending_position == pytest.approx(run.ending_position)
            assert summary.total_fees == pytest.approx(run.total_fees)
            assert summary.total_slippage_cost == pytest.approx(run.total_slippage_cost)
            assert summary.fill_count == run.trade_count
            assert summary.guard_trigger_index == run.guard_trigger_index
            assert summary.blocked_buy_count == sum(
                event.event_type == "blocked" and event.action == "BUY" for event in run.events
            )
            prior = run.equity_curve[grid.shock_index - 1]
            assert summary.prior_close_exposure_pct == pytest.approx(
                100 * prior.position * replay.candles[grid.shock_index - 1].close / prior.equity
            )
            if cell.fee_bps == 0:
                assert summary.total_fees == 0

    assert any(cell.guarded.blocked_buy_count for cell in grid.cells)
    assert any("pending order" in item.lower() for item in grid.assumptions)
    assert any("blocked" in item.lower() and "final-bar" in item.lower() for item in grid.assumptions)


def test_paired_tapes_are_identical_until_the_shock_and_fee_does_not_change_prices() -> None:
    initial = scenario()
    grid = run_shock_landscape(ShockLandscapeRequest(
        scenario=initial, shock_pcts=[0, 20], fee_bps_values=[0, 50]
    ))
    replays = {(cell.shock_pct, cell.fee_bps): run_survival(cell.request) for cell in grid.cells}
    no_shock = replays[(0, 0)]
    shocked = replays[(20, 0)]
    assert no_shock.candles == replays[(0, 50)].candles
    assert shocked.candles == replays[(20, 50)].candles
    assert no_shock.candles[:60] == shocked.candles[:60]
    for index in range(60, initial.num_candles):
        for field in ("open", "high", "low", "close"):
            assert getattr(shocked.candles[index], field) == pytest.approx(
                0.8 * getattr(no_shock.candles[index], field)
            )
    for unshocked_run, shocked_run in (
        (no_shock.unguarded, shocked.unguarded), (no_shock.guarded, shocked.guarded)
    ):
        assert unshocked_run is not None and shocked_run is not None
        assert unshocked_run.equity_curve[:60] == shocked_run.equity_curve[:60]
        assert [e for e in unshocked_run.events if e.candle_index < 60] == [
            e for e in shocked_run.events if e.candle_index < 60
        ]
    # The no-fee control still pays adverse slippage when a trade occurs.
    assert no_shock.unguarded.trade_count > 0
    assert no_shock.unguarded.total_fees == 0
    assert no_shock.unguarded.total_slippage_cost > 0


def test_zero_prior_exposure_does_not_hide_a_pending_next_open_buy() -> None:
    initial = scenario(strategy_key="simple_ma", seed=1, num_candles=65, shock_index=47, guard_enabled=False)
    grid = run_shock_landscape(ShockLandscapeRequest(
        scenario=initial, shock_pcts=[0, 20], fee_bps_values=[0, 10]
    ))
    assert all(cell.guarded is None for cell in grid.cells)
    shocked = next(cell for cell in grid.cells if cell.shock_pct == 20 and cell.fee_bps == 10)
    replay = run_survival(shocked.request)
    assert shocked.unguarded.prior_close_exposure_pct == 0
    fills_at_gap = [
        event for event in replay.unguarded.events
        if event.event_type == "fill" and event.action == "BUY" and event.candle_index == 47
    ]
    assert fills_at_gap and fills_at_gap[0].signal_index == 46
    assert replay.unguarded.equity_curve[47].position > 0


def test_flat_before_shock_does_not_imply_monotonic_returns() -> None:
    initial = scenario(
        strategy_key="simple_ma", seed=48, num_candles=160, shock_index=90,
        guard_drawdown_pct=3, max_position_pct=30,
    )
    lower = run_shock_landscape(ShockLandscapeRequest(
        scenario=initial, shock_pcts=[0, 5, 10], fee_bps_values=[0, 10]
    ))
    upper = run_shock_landscape(ShockLandscapeRequest(
        scenario=initial, shock_pcts=[0, 10, 20], fee_bps_values=[0, 10]
    ))
    cells = {
        cell.shock_pct: cell for cell in [*lower.cells, *upper.cells]
        if cell.fee_bps == 10
    }
    assert all(cell.unguarded.prior_close_exposure_pct == 0 for cell in cells.values())
    assert cells[5].unguarded.total_return_pct < cells[10].unguarded.total_return_pct
    assert cells[20].unguarded.total_return_pct < cells[10].unguarded.total_return_pct
    entry_bars = []
    for shock in (5, 10, 20):
        replay = run_survival(cells[shock].request)
        entry_bars.append(next(
            event.candle_index for event in replay.unguarded.events
            if event.event_type == "fill" and event.action == "BUY" and event.candle_index > 90
        ))
    assert entry_bars == [106, 107, 109]


@pytest.mark.parametrize(
    ("field", "values"),
    [
        ("shock_pcts", []), ("shock_pcts", [0]),
        ("shock_pcts", [0, 1, 2, 3]), ("shock_pcts", [1, 2]),
        ("shock_pcts", [0, 0]), ("shock_pcts", [0, 10, 5]),
        ("shock_pcts", [0, 81]), ("shock_pcts", [0, math.nan]),
        ("fee_bps_values", []), ("fee_bps_values", [0]),
        ("fee_bps_values", [0, 1, 2, 3]), ("fee_bps_values", [1, 2]),
        ("fee_bps_values", [0, 0]), ("fee_bps_values", [0, 10, 5]),
        ("fee_bps_values", [0, 501]), ("fee_bps_values", [0, math.inf]),
    ],
)
def test_rejects_invalid_axes(field: str, values: list[float]) -> None:
    with pytest.raises(ValueError):
        ShockLandscapeRequest(scenario=scenario(), **{field: values})


def test_rejects_too_many_candles_and_unrecognised_fields() -> None:
    with pytest.raises(ValueError):
        ShockLandscapeRequest(scenario=scenario(num_candles=161))
    with pytest.raises(ValueError):
        ShockLandscapeRequest(scenario=scenario(), unexpected=True)
    # The stated endpoints are inclusive.
    assert ShockLandscapeRequest(
        scenario=scenario(num_candles=160), shock_pcts=[0, 80], fee_bps_values=[0, 500]
    )


def test_default_hypothetical_shock_index_is_valid_for_two_bars() -> None:
    grid = run_shock_landscape(ShockLandscapeRequest(
        scenario=scenario(num_candles=2, shock_index=None),
        shock_pcts=[0, 20], fee_bps_values=[0, 10],
    ))
    assert grid.shock_index == 1
    assert all(math.isfinite(cell.unguarded.prior_close_exposure_pct) for cell in grid.cells)
