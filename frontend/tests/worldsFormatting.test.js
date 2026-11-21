import test from "node:test";
import assert from "node:assert/strict";
import { describeEquityDelta, formatEquityDelta } from "../src/worldsFormatting.js";

test("small final-equity differences retain their sign when returns round equally", () => {
  assert.equal(formatEquityDelta(-0.2526), "−$0.25");
  assert.equal(formatEquityDelta(-0.0000001), "−$1.00e-7");
  assert.equal(describeEquityDelta(-0.2526, 0.00001), "Lower");
  assert.equal(describeEquityDelta(-0.0000001, 0.00001), "Equal within tolerance");
});

test("a difference exactly on the tolerance boundary is equal", () => {
  assert.equal(describeEquityDelta(0.00001, 0.00001), "Equal within tolerance");
  assert.equal(describeEquityDelta(0.000011, 0.00001), "Higher");
  assert.equal(formatEquityDelta(0), "$0.00");
});
