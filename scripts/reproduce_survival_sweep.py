#!/usr/bin/env python3
"""Reproduce the six illustrative synthetic sweeps in docs/EXPERIMENT_NOTES.md.

Run from the project root:  python scripts/reproduce_survival_sweep.py

Everything is computed locally by the Survival Lab's artificial market
generator. Values describe 12 selected synthetic worlds only; they are not
forecasts, probabilities, or real-market evidence. No network or file writes.
"""

import sys
from pathlib import Path

# Allow running as a plain script from the project root (or elsewhere).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.engine.survival import SurvivalRequest  # noqa: E402
from backend.engine.survival_worlds import (  # noqa: E402
    SyntheticWorldsRequest,
    run_synthetic_worlds,
)

STRATEGIES = ("rsi", "simple_ma", "momentum")
THRESHOLDS = (3, 6)
WORLD_COUNT = 12

# Counts (improved, worsened, equal) as documented in docs/EXPERIMENT_NOTES.md.
DOCUMENTED_COUNTS = {
    ("rsi", 3): (3, 8, 1),
    ("rsi", 6): (0, 8, 4),
    ("simple_ma", 3): (0, 0, 12),
    ("simple_ma", 6): (0, 0, 12),
    ("momentum", 3): (0, 10, 2),
    ("momentum", 6): (0, 5, 7),
}


def main() -> int:
    print("Synthetic sweep reproduction (survival-lab generator, local only)")
    print("Illustrative samples of an artificial generator; NOT forecasts or real-market evidence.")
    print(f"Fixed settings: seeds 42-53 ({WORLD_COUNT} worlds), 160 candles, 12% shock at index 90,")
    print("  starting cash 10000, fee 10 bps, slippage 5 bps, max position 30%, guard enabled.")
    print("Drawdowns are positive magnitudes. Guarded counts compare final equity vs unguarded.\n")

    mismatches = []
    for strategy in STRATEGIES:
        for threshold in THRESHOLDS:
            scenario = SurvivalRequest(
                strategy_key=strategy, seed=42, num_candles=160,
                shock_pct=12, shock_index=90, starting_cash=10_000,
                fee_bps=10, slippage_bps=5, guard_enabled=True,
                guard_drawdown_pct=threshold, max_position_pct=30,
            )
            result = run_synthetic_worlds(
                SyntheticWorldsRequest(scenario=scenario, world_count=WORLD_COUNT)
            )
            if result.guarded is None or result.comparison is None:
                raise RuntimeError(f"missing guarded results for {strategy}/{threshold}%")

            u, g, c = result.unguarded, result.guarded, result.comparison
            print(f"== Strategy: {strategy} | guard threshold: {threshold}% | engine: {result.engine_version}")
            print(f"   worlds: {result.world_count}")
            print(f"   median total return %   no guard: {u.median_total_return_pct:+.2f}   guard: {g.median_total_return_pct:+.2f}")
            print(f"   worst total return %    no guard: {u.worst_total_return_pct:+.2f}   guard: {g.worst_total_return_pct:+.2f}")
            print(f"   median max drawdown %   no guard: {u.median_max_drawdown_pct:.2f}   guard: {g.median_max_drawdown_pct:.2f}")
            print(f"   worst max drawdown %    no guard: {u.worst_max_drawdown_pct:.2f}   guard: {g.worst_max_drawdown_pct:.2f}")
            print(f"   guard triggered in {c.guard_trigger_count} of {result.world_count} worlds")
            print(
                "   guarded final equity: "
                f"higher {c.improved_equity_count} / lower {c.worsened_equity_count} / equal {c.equal_equity_count}"
                f"  (equality tolerance {c.equity_equality_tolerance:g})"
            )

            observed = (c.improved_equity_count, c.worsened_equity_count, c.equal_equity_count)
            documented = DOCUMENTED_COUNTS[(strategy, threshold)]
            status = "matches" if observed == documented else "DIFFERS from"
            print(f"   comparison counts {status} documented {documented}\n")
            if observed != documented:
                mismatches.append((strategy, threshold, observed, documented))

    print("Reminder: these figures describe only the sampled synthetic worlds above.")
    if mismatches:
        print("\nReproduction mismatch (generator or settings may have changed):", file=sys.stderr)
        for strategy, threshold, observed, documented in mismatches:
            print(f"  {strategy}/{threshold}%: observed {observed}, documented {documented}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - report any failure with nonzero exit
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
