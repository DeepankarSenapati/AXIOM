import test, { before, after } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

let vite;
let ArenaComparison;

before(async () => {
  vite = await createServer({
    root: fileURLToPath(new URL("..", import.meta.url)),
    server: { middlewareMode: true, watch: { ignored: ["**/*"] } },
    appType: "custom", logLevel: "silent",
  });
  ({ ArenaComparison } = await vite.ssrLoadModule("/src/pages/BotArena.jsx"));
});
after(async () => { await vite?.close(); });

const result = (symbol, pnl) => ({
  start_cash: 1000, end_cash: 1000 + pnl, final_pnl: pnl, benchmark_pnl: 0, alpha: pnl,
  total_trades: 0, trade_records: [], win_rate: 0, sharpe_ratio: 0, max_drawdown: 0,
  equity_records: [{ symbol, timestamp: "2026-01-01T00:00:00Z", pnl }],
});
const bots = [{ id: "a", name: "First", strategy_name: "rsi" }, { id: "b", name: "Second", strategy_name: "rsi" }];
function render(results) {
  return renderToStaticMarkup(React.createElement(ArenaComparison, {
    results, bots, submittedSymbols: { a: "UNKNOWN", b: "UNKNOWN" },
  }));
}

test("mixed-unit runs show actual markets but no shared chart or ranking", () => {
  const html = render({ a: result("BTC/USDT", 1), b: result("TCS.NS", 100) });
  assert.match(html, /BTC\/USDT/);
  assert.match(html, /TCS\.NS/);
  assert.match(html, /USDT/);
  assert.match(html, /INR/);
  assert.match(html, /shared equity chart and PnL ranking are not shown/);
  assert.doesNotMatch(html, /Equity Curve Comparison/);
  assert.doesNotMatch(html, />#1</);
});

test("same-unit markets retain comparison with explicit caveats", () => {
  const html = render({ a: result("BTC/USDT", 1), b: result("ETH/USDT", 2) });
  assert.match(html, /Equity Curve Comparison/);
  assert.match(html, /different markets and may cover different dates/);
  assert.match(html, /not risk-matched/);
  assert.match(html, /No currency conversion/);
  assert.match(html, />#1</);
});
