# Experiment notes

These observations are from the local `survival-lab-v2` synthetic generator,
not market data or evidence of future performance. They are included to show
how to question a strategy, including when a safeguard hurts its outcome.

## A small, reproducible stress sweep

Each row uses seeds 42–53, 160 daily synthetic candles, a 12% gap at
zero-based candle index 90, $10,000 starting cash, a 10 bps fee and 5 bps
adverse slippage per fill, a 30% execution exposure cap, and 30% of available
cash as the built-in buy-signal size. Strategies use their registry defaults.
The guard stops new buys for the rest of the run after its threshold, but it
does not liquidate positions. Drawdowns below are positive magnitudes.

| Strategy / guard threshold | Median return, no guard → guard | Worst observed drawdown, no guard → guard | Guarded final equity: higher / lower / equal |
|---|---:|---:|---:|
| RSI / 3% | −6.21% → −6.25% | 9.10% → 8.77% | 3 / 8 / 1 |
| RSI / 6% | −6.21% → −6.24% | 9.10% → 9.06% | 0 / 8 / 4 |
| Moving average / 3% | +3.37% → +3.37% | 1.60% → 1.60% | 0 / 0 / 12 |
| Moving average / 6% | +3.37% → +3.37% | 1.60% → 1.60% | 0 / 0 / 12 |
| Momentum / 3% | +1.05% → −2.60% | 8.93% → 8.09% | 0 / 10 / 2 |
| Momentum / 6% | +1.05% → −0.36% | 8.93% → 8.09% | 0 / 5 / 7 |

Equality means a final-equity difference of at most $0.00001. The 3% guard
did not cap the momentum strategy's realized drawdown at 3%. For momentum at
seed 45, the guard blocked later buys and the simulated return changed from
+2.91% to −1.51%. The moving-average strategy happened to be flat immediately
before the shock in all 12 sampled worlds; that is not evidence it is generally
resilient. Changing conditions or the generator can change these results.

To reproduce, run the following from the project root with the virtual
environment activated:

```bash
python scripts/reproduce_survival_sweep.py
```

The underlying calls are equivalent to:

```python
from backend.engine.survival import SurvivalRequest
from backend.engine.survival_worlds import SyntheticWorldsRequest, run_synthetic_worlds

for strategy in ("rsi", "simple_ma", "momentum"):
    for threshold in (3, 6):
        scenario = SurvivalRequest(
            strategy_key=strategy, seed=42, num_candles=160,
            shock_pct=12, shock_index=90, starting_cash=10_000,
            fee_bps=10, slippage_bps=5, guard_enabled=True,
            guard_drawdown_pct=threshold, max_position_pct=30,
        )
        result = run_synthetic_worlds(SyntheticWorldsRequest(scenario=scenario, world_count=12))
        print(strategy, threshold, result.unguarded, result.guarded, result.comparison)
```

## Broader pre-declared sweep

A second experiment used **every seed from 0 through 39** for each of the
three strategies and each shock level below: 360 replays in total. Settings
were fixed before running: 160 candles, shock index 90, $10,000 starting cash,
$100 starting price, 10 bps fee, 5 bps slippage, 30% position cap, and a 3%
buy-pause guard. The engine's signal cash fraction was 30%. Values show
unguarded → guarded outcomes; equality uses the same $0.00001 tolerance.

| Strategy | Shock | Median return | Worst observed drawdown | Guarded equity higher / lower / equal | Guard triggered |
|---|---:|---:|---:|---:|---:|
| RSI | 0% | −1.91% → −1.98% | 8.05% → 7.74% | 3 / 20 / 17 | 23 / 40 |
| RSI | 12% | −5.45% → −5.51% | 11.36% → 10.65% | 12 / 25 / 3 | 37 / 40 |
| RSI | 30% | −10.74% → −10.79% | 16.31% → 15.01% | 12 / 25 / 3 | 37 / 40 |
| Moving average | 0% | +3.59% → +3.59% | 2.09% → 2.09% | 0 / 0 / 40 | 0 / 40 |
| Moving average | 12% | +3.62% → +3.62% | 5.33% → 5.00% | 0 / 2 / 38 | 2 / 40 |
| Moving average | 30% | +3.62% → +3.62% | 10.34% → 10.26% | 0 / 2 / 38 | 2 / 40 |
| Momentum | 0% | +2.34% → −1.07% | 6.65% → 6.65% | 0 / 23 / 17 | 33 / 40 |
| Momentum | 12% | +1.06% → −2.37% | 9.26% → 9.26% | 0 / 32 / 8 | 34 / 40 |
| Momentum | 30% | −3.70% → −8.05% | 14.31% → 14.31% | 0 / 33 / 7 | 34 / 40 |

These are descriptive results for a fixed synthetic generator and chosen
seeds. In particular, an apparently favorable moving-average median may
reflect its exposure and the generator's structure; it is not evidence of
real-world resilience. To rerun the full sweep locally:

```bash
python scripts/extended_survival_sweep.py
```

## Research informing the design

- Bailey and coauthors discuss how selecting strategies using backtests can
  overfit results; a small synthetic sweep does not solve this problem.
  [The Probability of Backtest Overfitting](https://escholarship.org/uc/item/4w1110bb)
- The CFTC describes limitations of hypothetical trading results and the
  importance of considering costs. [Commodity Trading Systems Sold on the Internet](https://www.cftc.gov/LearnAndProtect/AdvisoriesAndArticles/fraudadv_tradingsystem.html)
- The SEC, NASAA and FINRA warn against claims that AI can guarantee investment
  returns. [Artificial Intelligence and Investment Fraud](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-alerts/artificial-intelligence-fraud)

The product thesis is to make assumptions, decisions, and failure cases easy
to inspect. Before claiming value beyond a prototype, test that thesis with
potential users, add rigorous historical/out-of-sample evaluation, and obtain
independent technical and legal review appropriate to the intended product.
