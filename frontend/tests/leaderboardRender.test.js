import test, { before, after } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

let vite;
let RawAggregates;
before(async () => {
  vite = await createServer({ root: fileURLToPath(new URL("..", import.meta.url)),
    server: { middlewareMode: true, watch: { ignored: ["**/*"] } }, appType: "custom", logLevel: "silent" });
  ({ RawAggregates } = await vite.ssrLoadModule("/src/pages/Leaderboard.jsx"));
});
after(async () => { await vite?.close(); });

test("raw mixed-unit aggregates are disclosed in a closed section without dollar labels", () => {
  const html = renderToStaticMarkup(React.createElement(RawAggregates, { entries: [
    { strategy_key: "rsi", avg_pnl: 130, avg_alpha: -2, best_pnl: 200 },
  ] }));
  assert.match(html, /<details class=/);
  assert.doesNotMatch(html, /<details[^>]*\sopen(?:=|\s|>)/);
  assert.match(html, /may combine different market quote units/);
  assert.match(html, /cannot be treated as comparable currency amounts or identify the best performer/);
  assert.match(html, /Raw maximum PnL/);
  assert.match(html, /\+130\.00/);
  assert.doesNotMatch(html, /\$130\.00|Best PnL/);
});
