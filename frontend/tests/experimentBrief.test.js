import assert from "node:assert/strict";
import test from "node:test";
import { buildExperimentBrief } from "../src/experimentBrief.js";

function makeRun(equities, startingCash, guardTrigger = null) {
  let peak = startingCash;
  let drawdown = 0;
  for (const value of equities) {
    peak = Math.max(peak, value);
    drawdown = Math.max(drawdown, (peak - value) / peak * 100);
  }
  const last = equities.at(-1);
  return {
    final_equity: last,
    total_return_pct: (last / startingCash - 1) * 100,
    max_drawdown_pct: drawdown,
    guard_trigger_index: guardTrigger,
    equity_curve: equities.map((equity, index) => ({ index, equity })),
  };
}

function fixture(startingCash = 10000) {
  const request = {
    strategy_key: "rsi", seed: 42, num_candles: 3, start_price: 100,
    starting_cash: startingCash, fee_bps: 10, slippage_bps: 5, shock_pct: 12,
    shock_index: 1, guard_enabled: true, guard_drawdown_pct: 3, max_position_pct: 30,
  };
  const run = (ratios, trigger = null) => makeRun(ratios.map((value) => value * startingCash), startingCash, trigger);
  const response = (baseline) => ({
    fingerprint: (baseline ? "a" : "b").repeat(64), engine_version: "survival-lab-v3",
    strategy_key: "rsi", request: { ...request, shock_pct: baseline ? 0 : 12 },
    strategy_parameters: { period: 14, oversold: 30, overbought: 70 }, signal_cash_fraction: 0.3,
    scenario: { source: "synthetic", symbol: "SYNTH/USD", timeframe: "1d", seed: 42,
      candle_count: 3, shock_pct: baseline ? 0 : 12, shock_index: baseline ? null : 1 },
    unguarded: run(baseline ? [1, 0.99, 0.98] : [1, 0.9, 0.95]),
    guarded: run(baseline ? [1, 0.99, 0.98] : [1, 0.95, 0.97], baseline ? null : 1),
    benchmark: run(baseline ? [1, 1, 1] : [1, 0.8, 0.9]),
  });
  return { request, baseline: response(true), shock: response(false) };
}

test("renders calculated curves, metrics, provenance, and limitations without scripts", () => {
  const html = buildExperimentBrief(fixture());
  assert.match(html, /Synthetic stress-test result/);
  assert.match(html, /Shock · candle 2/);
  assert.match(html, /Shocked buy-and-hold/);
  assert.match(html, /post-cost equity at execution/);
  assert.match(html, /not risk-matched/);
  assert.match(html, /not source hashes or independent proof/);
  assert.match(html, /Baseline <code>a{64}<\/code>/);
  assert.match(html, /Scenario <code>b{64}<\/code>/);
  assert.doesNotMatch(html, /<script\b/i);
  assert.doesNotMatch(html, /NaN|Infinity|undefined/);
});

test("rejects mixed strategies, requests, shocks, or guard states", () => {
  for (const mutate of [
    (data) => { data.shock.strategy_key = "momentum"; },
    (data) => { data.shock.request.fee_bps = 11; },
    (data) => { data.request.shock_pct = 5; },
    (data) => { data.shock.guarded = null; },
    (data) => { data.shock.strategy_parameters.period = 15; },
    (data) => { data.shock.signal_cash_fraction = 0.2; },
    (data) => { data.shock.scenario.source = "historical"; },
  ]) {
    const data = fixture();
    mutate(data);
    assert.throws(() => buildExperimentBrief(data), /Experiment brief:/);
  }
});

test("rejects metrics that disagree with the plotted equity curves", () => {
  for (const mutate of [
    (data) => { data.shock.unguarded.total_return_pct = 99; },
    (data) => { data.shock.unguarded.max_drawdown_pct = 0; },
    (data) => { data.shock.unguarded.final_equity = 10000; },
    (data) => { data.shock.unguarded.equity_curve[1].equity = NaN; },
    (data) => { data.shock.unguarded.equity_curve[1].index = 7; },
  ]) {
    const data = fixture();
    mutate(data);
    assert.throws(() => buildExperimentBrief(data), /Experiment brief:/);
  }
});

test("escapes untrusted dynamic text in the static document", () => {
  const data = fixture();
  const hostile = 'v3</style><script>alert("x")</script>';
  data.baseline.engine_version = hostile;
  data.shock.engine_version = hostile;
  const html = buildExperimentBrief(data);
  assert.doesNotMatch(html, /<script\b/i);
  assert.match(html, /&lt;script&gt;alert\(&quot;x&quot;\)&lt;\/script&gt;/);
});

test("labels no-shock and disabled-guard runs accurately", () => {
  const data = fixture();
  data.request.shock_pct = 0;
  data.request.guard_enabled = false;
  data.baseline.request = { ...data.request };
  data.shock.request = { ...data.request };
  data.baseline.guarded = null;
  data.shock.guarded = null;
  data.shock.scenario.shock_pct = 0;
  data.shock.scenario.shock_index = null;
  const html = buildExperimentBrief(data);
  assert.match(html, /No shock in this run/);
  assert.match(html, /Scenario \(no shock\) buy-and-hold/);
  assert.match(html, /Guard was not enabled/);
  assert.doesNotMatch(html, /Shock · candle/);
});

test("reserves enough chart space for large dollar labels", () => {
  const html = buildExperimentBrief(fixture(1_000_000_000_000));
  const match = html.match(/<rect x="(\d+)" y="14"[^>]*class="frame"/);
  assert.ok(match);
  assert.ok(Number(match[1]) > 100);
});

test("uses distinct currency ticks for nearly flat curves", () => {
  const data = fixture();
  const values = [10000, 10000.0001, 10000.0002];
  for (const response of [data.baseline, data.shock]) {
    response.unguarded = makeRun(values, 10000);
    response.guarded = makeRun(values, 10000);
    response.benchmark = makeRun(values, 10000);
  }
  const html = buildExperimentBrief(data);
  const ticks = [...html.matchAll(/text-anchor="end" class="tick">([^<]+)<\/text>/g)].map((match) => match[1]);
  assert.equal(ticks.length, 5);
  assert.equal(new Set(ticks).size, 5);
});

test("the brief preserves small positive and negative returns and drawdown", () => {
  const data = fixture();
  data.baseline.unguarded = makeRun([10000, 10000, 10000.358], 10000);
  data.shock.unguarded = makeRun([10000, 9999.642, 9999.642], 10000);
  const html = buildExperimentBrief(data);
  assert.match(html, /Baseline return<\/span><b>\+0\.0036%<\/b>/);
  assert.match(html, /Shocked return<\/span><b>−0\.0036%<\/b>/);
  assert.match(html, /Max close drawdown, unguarded<\/span><b>0\.0036%<\/b>/);
});
