import test, { before, after } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

let vite;
let ProfilePerformance;

before(async () => {
  vite = await createServer({
    root: fileURLToPath(new URL("..", import.meta.url)),
    server: { middlewareMode: true, watch: { ignored: ["**/*"] } },
    appType: "custom", logLevel: "silent",
  });
  ({ ProfilePerformance } = await vite.ssrLoadModule("/src/pages/MarketDashboard.jsx"));
});
after(async () => { await vite?.close(); });

const run = (id, symbol, final_pnl) => ({
  id, symbol, final_pnl, created_at: "2026-01-01T00:00:00Z", data_source: "mock",
  sharpe_ratio: 0.5, win_rate: 0.3, max_drawdown: -0.1,
});
const render = (profile) => renderToStaticMarkup(React.createElement(ProfilePerformance, { profile }))
  .replace(/<[^>]*>/g, "").replace(/\s+/g, " ");

test("individual recorded PnLs retain their own simulated market units", () => {
  const text = render({
    run_count: 4, avg_sharpe: 0.5, avg_pnl: 98765, best_pnl: 123456,
    recent_runs: [run("a", "BTC/USDT", 25), run("b", "TCS.NS", -30),
      run("c", "^NSEI", 0), run("d", "UNKNOWN", 5)],
  });
  assert.match(text, /BTC\/USDT.*\+25\.00 USDT/);
  assert.match(text, /TCS\.NS.*-30\.00 INR/);
  assert.match(text, /\^NSEI.*0\.00 synthetic index-point units/);
  assert.match(text, /UNKNOWN.*\+5\.00 simulated units/);
  assert.match(text, /No currency conversion is applied/);
  assert.doesNotMatch(text, /\$/);
  assert.doesNotMatch(text, /98,765|123,456/);
});

test("aggregate PnL stays hidden even if the recent subset uses one unit", () => {
  const text = render({
    run_count: 6, avg_sharpe: null, avg_pnl: 99999, best_pnl: 88888,
    recent_runs: [run("a", "BTC/USDT", 25)],
  });
  assert.match(text, /Average and best PnL are not shown/);
  assert.match(text, /Avg Sharpe\s*—/);
  assert.doesNotMatch(text, /99,999|88,888/);
});

test("empty profiles explain how to generate performance data", () => {
  const text = render({ run_count: 0, avg_sharpe: null, recent_runs: [] });
  assert.match(text, /No backtest runs yet/);
  assert.doesNotMatch(text, /Recent Backtest Runs/);
});
