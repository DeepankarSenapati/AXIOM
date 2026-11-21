import test from "node:test";
import assert from "node:assert/strict";
import { buildArenaCsv, buildBacktestCsv, compareMarkets, isIndian, marketUnit, nseFourHourUnsupported, resultMarket, sharedStartingCash } from "../src/arenaPresentation.js";

test("market labels distinguish crypto quotes, NSE shares, and synthetic index points", () => {
  assert.equal(marketUnit("BTC/USDT"), "USDT");
  assert.equal(marketUnit("RELIANCE.NS"), "INR");
  assert.equal(marketUnit("^NSEI"), "synthetic index-point units");
  assert.equal(marketUnit("unknown"), "simulated units");
  assert.equal(isIndian("RELIANCE.NS"), true);
  assert.equal(isIndian("^NSEI"), true);
  assert.equal(isIndian("BTC/USDT"), false);
});

test("completed market is taken from recorded candles, falling back to the submitted request", () => {
  assert.equal(resultMarket({ equity_records: [{ symbol: "TCS.NS" }] }, "BTC/USDT"), "TCS.NS");
  assert.equal(resultMarket({ equity_records: [] }, "ETH/USDT"), "ETH/USDT");
  assert.equal(resultMarket({}, null), "Unknown");
});

test("mixed or unknown units are not ranked while same-unit markets are identified", () => {
  assert.deepEqual(compareMarkets(["BTC/USDT", "ETH/USDT"]), {
    comparable: true, sharedUnit: "USDT", mixedMarkets: true,
  });
  assert.equal(compareMarkets(["BTC/USDT", "RELIANCE.NS"]).comparable, false);
  assert.equal(compareMarkets(["RELIANCE.NS", "^NSEI"]).comparable, false);
  assert.equal(compareMarkets(["^NSEI", "^NSEBANK"]).comparable, false);
  assert.equal(compareMarkets(["^NSEI", "^NSEI"]).comparable, true);
  assert.equal(compareMarkets(["BTC/USDT", "Unknown"]).comparable, false);
  assert.equal(compareMarkets(["Unknown"]).comparable, false);
});

test("starting reference line is sourced from completed responses and only when shared", () => {
  assert.equal(sharedStartingCash({ a: { start_cash: 1000 }, b: { start_cash: 1000 } }), 1000);
  assert.equal(sharedStartingCash({ a: { start_cash: 1000 }, b: { start_cash: 2000 } }), null);
  assert.equal(sharedStartingCash({ a: { start_cash: NaN } }), null);
  assert.equal(sharedStartingCash({}), null);
});

test("4-hour historical NSE data is rejected even when only an override is Indian", () => {
  assert.equal(nseFourHourUnsupported("live", "4h", ["BTC/USDT", "TCS.NS"]), true);
  assert.equal(nseFourHourUnsupported("live", "4h", ["^NSEI"]), true);
  assert.equal(nseFourHourUnsupported("live", "1d", ["TCS.NS"]), false);
  assert.equal(nseFourHourUnsupported("mock", "4h", ["TCS.NS"]), false);
  assert.equal(nseFourHourUnsupported("live", "4h", ["BTC/USDT"]), false);
});

test("arena CSV includes each market and unit, omits mixed-unit rank and escapes text", () => {
  const summary = [{
    name: '=HYPERLINK("bad")', strategy: "rsi", symbol: "BTC/USDT", unit: "USDT",
    finalPnl: 1, benchmarkPnl: 2, alpha: -1, endCash: 1001, trades: 3, winRate: null,
    sharpe: 0.2, maxDrawdown: -0.04,
  }];
  const csv = buildArenaCsv(summary, false);
  assert.match(csv, /Market,Simulated Unit/);
  assert.match(csv, /,"BTC\/USDT","USDT",/);
  assert.match(csv, /\n,"'=HYPERLINK\(""bad""\)"/);
  assert.match(buildArenaCsv(summary, true), /\n1,/);
});

test("backtest CSV records market, quote units, and safe text", () => {
  const csv = buildBacktestCsv([{
    timestamp: "2026-01-01T00:00:00Z", symbol: "TCS.NS", action_type: "BUY",
    price: 100, quantity: 2, pnl: 0, cash_after: 9800, reason: "=untrusted",
  }]);
  assert.match(csv, /Market,Simulated Unit/);
  assert.match(csv, /"TCS\.NS","INR","BUY"/);
  assert.match(csv, /"'=untrusted"/);
});
