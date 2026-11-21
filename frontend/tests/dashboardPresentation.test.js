import test from "node:test";
import assert from "node:assert/strict";
import { observedPnlMaximum, simulatedAmount } from "../src/dashboardPresentation.js";

test("mixed or unknown market units cannot produce a cross-unit maximum", () => {
  assert.deepEqual(observedPnlMaximum([{ symbol: "BTC/USDT", final_pnl: 10 }, { symbol: "TCS.NS", final_pnl: 500 }]), { kind: "mixed" });
  assert.deepEqual(observedPnlMaximum([{ symbol: "BTC/USDT", final_pnl: 10 }, { symbol: "unknown", final_pnl: 500 }]), { kind: "mixed" });
});

test("same-unit maximum is explicitly a raw number from the supplied runs", () => {
  assert.deepEqual(observedPnlMaximum([{ symbol: "BTC/USDT", final_pnl: -5 }, { symbol: "ETH/USDT", final_pnl: 3 }]), { kind: "value", value: 3, unit: "USDT" });
  assert.equal(simulatedAmount(3, "USDT"), "+3.00 USDT");
  assert.equal(simulatedAmount(-3, "INR"), "-3.00 INR");
  assert.equal(simulatedAmount(0, "INR"), "0.00 INR");
});

test("empty and invalid results do not turn into zero-valued maxima", () => {
  assert.deepEqual(observedPnlMaximum([]), { kind: "empty" });
  assert.deepEqual(observedPnlMaximum([{ symbol: "TCS.NS", final_pnl: null }]), { kind: "unavailable" });
  assert.equal(simulatedAmount(NaN, "USDT"), "—");
});
