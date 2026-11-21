import test, { before, after } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

let vite;
let DecisionComparison;

before(async () => {
  vite = await createServer({
    root: fileURLToPath(new URL("..", import.meta.url)),
    server: { middlewareMode: true, watch: { ignored: ["**/*"] } },
    appType: "custom", logLevel: "silent",
  });
  ({ default: DecisionComparison } = await vite.ssrLoadModule("/src/components/DecisionComparison.jsx"));
});

after(async () => { await vite?.close(); });

const event = (candle, event_type, action, signal_index = candle, extra = {}) => ({
  candle_index: candle, event_type, action, signal_index, reason: event_type, ...extra,
});
const makeRun = (guarded, unguarded) => ({
  candles: Array.from({ length: 4 }, () => ({})),
  guarded: { events: guarded, final_equity: 9_900 },
  unguarded: { events: unguarded, final_equity: 9_950 },
});
const render = (run) => renderToStaticMarkup(React.createElement(DecisionComparison, { run, onInspect: () => {} }));

test("renders actual next-open fill and separates the whole-run difference", () => {
  const html = render(makeRun(
    [event(1, "blocked", "BUY")],
    [event(1, "signal", "BUY"), event(2, "fill", "BUY", 1, { quantity: 2.31282, price: 93.1078 })],
  ));
  assert.match(html, /candle 3/);
  assert.match(html, /2\.31282 units/);
  assert.match(html, /\$93\.1078/);
  assert.match(html, /−\$50\.00/);
  assert.match(html, /entire run, not just this signal/);
  assert.match(html, /Inspect the blocked signal/);
  assert.match(html, /order from an earlier close may have filled/);
});

test("a final-bar expiry is not rendered as a prevented fill", () => {
  const html = render(makeRun(
    [event(3, "blocked", "BUY")], [event(3, "signal", "BUY"), event(3, "expired", "BUY")],
  ));
  assert.match(html, /expired because there was no next candle/);
  assert.doesNotMatch(html, /BUY fill was recorded/);
});

test("disabled guard and different signals are stated without a fabricated trade", () => {
  const disabled = render({ guarded: null });
  assert.match(disabled, /guard was disabled/);
  assert.doesNotMatch(disabled, /WHOLE-RUN FINAL EQUITY/);
  const divergent = render(makeRun([event(1, "blocked", "BUY")], [event(1, "signal", "SELL")]));
  assert.match(divergent, /a SELL signal, not a BUY/);
  assert.doesNotMatch(divergent, /BUY fill was recorded/);
});
