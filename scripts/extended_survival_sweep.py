#!/usr/bin/env python3
"""Predeclared extended synthetic stress experiment for the Survival Lab.

Run from the project root:  python scripts/extended_survival_sweep.py

3 strategies x 3 shocks x seeds 0-39 (360 runs), all printed. Offline, no file
writes, no subprocess. Exits nonzero if a guarded result is missing or if
run metadata varies inside the experiment.
"""

import statistics
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.engine.survival import run_survival  # noqa: E402
from backend.engine.survival_models import SurvivalRequest  # noqa: E402

# Predeclared design: do not tune after seeing results.
STRATEGIES = ("rsi", "simple_ma", "momentum")
SHOCKS = (0, 12, 30)
SEEDS = range(40)
NUM_CANDLES = 160
START_PRICE = 100
STARTING_CASH = 10_000
FEE_BPS = 10
SLIPPAGE_BPS = 5
SHOCK_INDEX = 90
GUARD_DRAWDOWN_PCT = 3
MAX_POSITION_PCT = 30
EQUALITY_TOLERANCE = 1e-9 * STARTING_CASH


class ExperimentError(RuntimeError):
    pass


def run_row(strategy: str, shock: float) -> dict:
    unguarded_returns, guarded_returns = [], []
    unguarded_dd, guarded_dd = [], []
    higher = lower = equal = triggers = 0
    meta = None
    for seed in SEEDS:
        request = SurvivalRequest(
            strategy_key=strategy, seed=seed, num_candles=NUM_CANDLES,
            start_price=START_PRICE, starting_cash=STARTING_CASH,
            fee_bps=FEE_BPS, slippage_bps=SLIPPAGE_BPS,
            shock_pct=shock, shock_index=SHOCK_INDEX, guard_enabled=True,
            guard_drawdown_pct=GUARD_DRAWDOWN_PCT, max_position_pct=MAX_POSITION_PCT,
        )
        result = run_survival(request)
        label = f"{strategy}/shock {shock}%/seed {seed}"
        if result.guarded is None:
            raise ExperimentError(f"guarded result missing for {label}")
        scenario = result.scenario
        observed_meta = (
            result.engine_version,
            result.signal_cash_fraction,
            tuple(sorted(result.strategy_parameters.items())),
            scenario.candle_count, scenario.shock_index, scenario.shock_pct,
            scenario.source, scenario.symbol, scenario.timeframe,
            tuple(result.assumptions),
        )
        if scenario.seed != seed:
            raise ExperimentError(f"scenario seed {scenario.seed} != requested seed for {label}")
        if scenario.candle_count != NUM_CANDLES or len(result.candles) != NUM_CANDLES:
            raise ExperimentError(f"candle count differs from {NUM_CANDLES} for {label}")
        expected_shock_index = SHOCK_INDEX if shock > 0 else None
        if scenario.shock_index != expected_shock_index or scenario.shock_pct != shock:
            raise ExperimentError(f"shock metadata differs from declaration for {label}")
        if meta is None:
            meta = observed_meta
        elif observed_meta != meta:
            raise ExperimentError(f"metadata varies within row for {label}")

        u, g = result.unguarded, result.guarded
        unguarded_returns.append(u.total_return_pct)
        guarded_returns.append(g.total_return_pct)
        unguarded_dd.append(u.max_drawdown_pct)
        guarded_dd.append(g.max_drawdown_pct)
        diff = g.final_equity - u.final_equity
        if abs(diff) <= EQUALITY_TOLERANCE:
            equal += 1
        elif diff > 0:
            higher += 1
        else:
            lower += 1
        if g.guard_trigger_index is not None:
            triggers += 1

    return {
        "meta": meta,
        "u_med": statistics.median(unguarded_returns),
        "g_med": statistics.median(guarded_returns),
        "u_dd": max(unguarded_dd),
        "g_dd": max(guarded_dd),
        "higher": higher, "lower": lower, "equal": equal, "triggers": triggers,
    }


def main() -> int:
    n = len(SEEDS)
    print("Extended synthetic survival sweep (predeclared, offline, deterministic)")
    print("DISCLAIMER: these are selected synthetic samples from an artificial generator.")
    print("  They are NOT probabilities, forecasts, or real-world evidence.")
    print(f"Design: strategies {', '.join(STRATEGIES)}; shocks {SHOCKS} %; seeds {SEEDS[0]}-{SEEDS[-1]} ({n} per row);")
    print(f"  candles {NUM_CANDLES}, start price {START_PRICE}, cash {STARTING_CASH}, fee {FEE_BPS} bps, slippage {SLIPPAGE_BPS} bps,")
    print(f"  shock index {SHOCK_INDEX}, guard drawdown {GUARD_DRAWDOWN_PCT}%, max position {MAX_POSITION_PCT}%.")
    print(f"Equality tolerance on final equity: {EQUALITY_TOLERANCE:g}. Drawdowns are positive magnitudes.\n")

    header = (f"{'strategy':<10}{'shock%':>7} | {'med ret% unG':>13}{'med ret% G':>12} | "
              f"{'max DD% unG':>12}{'max DD% G':>11} | {'G higher':>9}{'lower':>7}{'equal':>7} | {'triggers':>8}")
    print(header)
    print("-" * len(header))

    global_meta = None
    engine_version = None
    for strategy in STRATEGIES:
        for shock in SHOCKS:
            row = run_row(strategy, shock)
            # engine_version and signal_cash_fraction must be identical across the whole experiment.
            shared = row["meta"][:2]
            if global_meta is None:
                global_meta = shared
                engine_version = row["meta"][0]
            elif shared != global_meta:
                raise ExperimentError(f"engine metadata varies across rows at {strategy}/{shock}%")
            print(
                f"{strategy:<10}{shock:>7} | {row['u_med']:>+13.2f}{row['g_med']:>+12.2f} | "
                f"{row['u_dd']:>12.2f}{row['g_dd']:>11.2f} | "
                f"{row['higher']:>9}{row['lower']:>7}{row['equal']:>7} | {row['triggers']:>3}/{n:<4}"
            )

    print(f"\nEngine version: {engine_version}; signal cash fraction: {global_meta[1]:g}.")
    print("Reminder: all 9 rows are shown; figures describe only these sampled synthetic worlds.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - fail clearly with nonzero exit
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
