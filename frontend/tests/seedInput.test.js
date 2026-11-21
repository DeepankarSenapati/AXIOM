import test from "node:test";
import assert from "node:assert/strict";
import { parseSeedInput } from "../src/seedInput.js";
import { parsePassport } from "../src/passport.js";

test("valid seed text becomes an exact number, including both bounds", () => {
  for (const [text, expected] of [["0", 0], ["00042", 42], ["4294967295", 4294967295]]) {
    assert.deepEqual(parseSeedInput(text), { value: expected, error: "" });
  }
});

test("empty, non-integer and out-of-range text remains visible and invalid", () => {
  for (const input of ["", " ", "-1", "1.5", "1e3", "abc", "4294967296", "9007199254740993"]) {
    const parsed = parseSeedInput(input);
    assert.equal(parsed.value, input);
    assert.match(parsed.error, /whole number from 0 to 4,294,967,295/);
  }
});

test("the largest seed remains numeric through passport JSON export and import", () => {
  const seed = parseSeedInput("4294967295").value;
  const passport = {
    format: "axiom-survival-lab-v1",
    request: {
      strategy_key: "rsi", seed, num_candles: 160, start_price: 100, starting_cash: 10000,
      fee_bps: 10, slippage_bps: 5, shock_pct: 12, shock_index: 90,
      guard_enabled: true, guard_drawdown_pct: 3, max_position_pct: 30,
    },
    baseline: { fingerprint: "a".repeat(64) },
    shocked: { fingerprint: "b".repeat(64) },
  };
  const imported = parsePassport(JSON.stringify(passport));
  assert.equal(imported.request.seed, 4294967295);
  assert.equal(typeof imported.request.seed, "number");
});
