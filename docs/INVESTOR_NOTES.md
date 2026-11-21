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

1. **Ask a question:** “What happens to this bot if the market gaps down?”
2. Run the default RSI experiment. Show the baseline and shocked paths, fees,
   drawdown and guard. The decision comparison shows the blocked buy at candle
   91 alongside the unguarded path's recorded next-open fill. Use the evidence
   trail to inspect the block. The shock is at the open, while the guard is
   checked at the close; a pending order could fill before that guard check.
3. Set Synthetic Worlds to 12 and run it. Point to both better and worse
   guarded outcomes; load one seed, rerun it and match its fingerprint.
   Explain that the guard does not guarantee a loss limit.
4. Generate Shock Landscape to compare shock and fee combinations on the same
   artificial seed. Highlight exposure before the gap so that a strategy that
   happened to hold no position is not mistaken for proven crash resilience.
5. Download the passport and replay it. Compare the recorded fingerprints with
   the new calculation, then explain what is reproducible—and what is not:
   this is generated data and a self-reported fingerprint, not proof of the
   file contents, source code or execution, independent verification, or
   evidence of real trading.
6. Close with the next milestone: interviews and independent validation on
   historical, out-of-sample data before any claim of product-market fit.

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
