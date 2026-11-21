import test from "node:test";
import assert from "node:assert/strict";
import { formatPercent } from "../src/percentFormatting.js";

test("preserves small nonzero returns and drawdowns without displaying zero", () => {
  assert.equal(formatPercent(0.003580227, true), "+0.0036%");
  assert.equal(formatPercent(-0.003580227, true), "−0.0036%");
  assert.equal(formatPercent(0.0000001), "1.0e-7%");
  assert.equal(formatPercent(-0.0000001), "−1.0e-7%");
  assert.equal(formatPercent(0.004999, true), "+0.0050%");
});

test("ordinary percentages, exact zero and missing data remain unambiguous", () => {
  assert.equal(formatPercent(1.234, true), "+1.23%");
  assert.equal(formatPercent(-1.234, true), "−1.23%");
  assert.equal(formatPercent(0.0051, true), "+0.01%");
  assert.equal(formatPercent(0, true), "0.00%");
  assert.equal(formatPercent(-0, true), "0.00%");
  assert.equal(formatPercent(null), "—");
  assert.equal(formatPercent(NaN), "—");
  assert.equal(formatPercent(Infinity), "—");
});
