# Investor demo notes

## A focused story

**Problem hypothesis:** people evaluating automated trading strategies often
see a performance curve without an easy way to understand what assumptions,
exposure, and decisions produced it. Ask potential users whether this is a
painful and expensive problem before treating it as a validated market.

**Prototype:** AXIOM Survival Lab lets someone run a rule-based bot on a
synthetic market, inject a hypothetical gap, account for basic simulated
fees and slippage, inspect individual decisions, and compare small samples of
seeded scenarios. It is a local demonstration, not a broker, investment
product, live performance record, or proven trading system.

**Potential positioning:** an explainable strategy-evaluation workspace for
teams who must understand failure modes before trusting automation. The
proposed audience and differentiation are hypotheses, not established demand
or a defensible moat. The most credible story is not that AXIOM predicts the
market; it is that AXIOM makes a strategy's assumptions and surprises easier
to interrogate.

## A three-minute demonstration

**Prepare:** start the local demo, sign in and open Survival Lab. Reload the
page to restore its default controls. This script's numbers use RSI, seed 42,
160 candles, a 12% shock at candle 91, a 3% drawdown guard, 10 bps fees and
5 bps slippage. Fees of 10 bps mean 0.1% per simulated fill. Set Synthetic
Worlds to 12 when asked; it initially defaults to 6.

1. **0:00–0:30 — The question and the boundary.** “What happens to an
   automated strategy when the market gaps down, and can we explain its
   decisions?” This local prototype has three built-in, rule-based
   strategies and synthetic prices; it does not accept a customer's strategy
   or trade real money.
2. **0:30–1:20 — One decision.** Run the default experiment and point to the
   scenario and guard results. Ask: “Why did a 3% buy-pause guard still see
   5.43% maximum close drawdown?” It checks at the close after the gap and
   leaves the existing position open; it is a trigger, not a loss limit. In
   **One decision / two paths**, show the BUY blocked at candle 91's close
   and the unguarded path's actual fill at candle
   92's open. Click **Inspect the blocked signal** to open its recorder entry.
   The shock happens at the open, while the guard checks at the close; an
   earlier pending order could fill before that check. The guard pauses new
   buys; it neither forces a sale nor guarantees a loss limit. The whole-run
   guarded-minus-unguarded final equity is about −$2.98 in simulated USD; do
   not attribute that entire difference to this one decision.
3. **1:20–2:20 — A small sample, not a promise.** Set Synthetic Worlds to
   12 and select **Generate worlds**. For these settings and seeds 42–53, the
   guarded final equity is higher in 3, lower in 8 and equal within the shown
   tolerance in 1. These are outcomes from one artificial generator, not
   probabilities, forecasts or evidence of real-market performance. They
   show that a guard can change outcomes in either direction.
4. **2:20–3:00 — The next milestone.** “We want to help people evaluating
   automated strategies understand assumptions and investigate failure
   modes.” Identify strategy researchers and risk reviewers as prospective
   users, then ask for introductions to interview them and for independent
   historical, out-of-sample validation. Demand and willingness to pay remain
   untested.

### If there is time for questions

- **A larger counterexample:** select Momentum and seed 10, keeping the
  remaining default controls, then run again. The buy-pause guard triggers
  at candle 86, before the gap, but leaves the existing position exposed.
  The strategy signals a stop-loss at candle 91 and fills it at candle 92.
  Later the guard blocks a new buy at candle 118. Final simulated equity is
  $9,531.35 with the guard versus $9,869.86 without it; the guarded maximum
  close drawdown is 7.89%. The $338.51 difference reflects the entire run,
  not only that buy. This example was selected after exploring synthetic
  seeds and is not representative evidence of real-world outcomes.
- **Shock Landscape:** compare shock and fee combinations on one artificial
  seed. Show exposure immediately before the gap; a run with no position at
  that point is not proof of crash resilience.
- **Passport:** download the JSON and replay it using **Replay a saved
  passport**. The page compares recorded and newly calculated fingerprints.
  A match is not proof of file contents, source code, execution, independent
  verification or real trading.
- **World replay:** load a seed, then run the experiment again. The replay
  compares its fingerprint with the one recorded for that world; expand the
  result to inspect both. The Worlds sample is replaced by the new run. As
  with the passport, a match is not independent verification or proof of
  execution.

## What already exists

These are reference points, not a complete competitive analysis:

- [QuantConnect](https://www.quantconnect.com/docs/v2/research-environment/meta-analysis/key-concepts)
  documents backtest analysis, optimization analysis and comparison of live
  trading with simulated results. Its [research guide](https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/research-guide)
  discusses overfitting and out-of-sample testing.
- [Composer](https://www.composer.trade/learn/how-do-backtests-work-in-composer)
  describes visual strategy backtesting with benchmarks, fees and slippage.
- [Alpaca](https://docs.alpaca.markets/us/docs/paper-trading) offers a
  real-time paper trading environment and documents differences between
  simulated and real trading.

Those products already provide substantial capabilities. AXIOM should not
claim it invented backtesting, explainability, or simulation. A possible
wedge is a focused, approachable workflow for examining how and why an
automated strategy fails; whether people value that enough to switch or pay
must be tested.

## Questions to validate next

- Interview strategy researchers, risk reviewers and educators separately.
  Ask them to show a recent evaluation workflow and a time an unexpected
  failure changed a decision; do not begin by pitching a solution.
- Test whether a user can explain a simulated result and its limitations
  unaided, then ask what evidence they would require before relying on it.
- Seek a small design-partner pilot only after defining its intended use,
  success criteria, data rights, security requirements and appropriate legal
  review. Measure repeat use and time to identify a material failure, not
  simulated returns alone.
- Before any claim of reliable performance: independently review the engine,
  support trustworthy historical datasets and realistic execution models,
  run out-of-sample evaluations, and make model and provenance limitations
  clear. A synthetic stress sweep is useful for demonstrating behavior but
  cannot establish financial viability.
