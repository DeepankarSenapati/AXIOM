import assert from "node:assert/strict";
import test from "node:test";
import { parsePassport } from "../src/passport.js";

const request = {
  strategy_key: "rsi", seed: 42, num_candles: 160, start_price: 100,
  starting_cash: 10000, fee_bps: 10, slippage_bps: 5, shock_pct: 12,
  shock_index: 90, guard_enabled: true, guard_drawdown_pct: 3, max_position_pct: 30,
};

const makePassport = () => ({
  format: "axiom-survival-lab-v1",
  request: { ...request },
  baseline: { fingerprint: "A".repeat(64), final_equity: 999999999 },
  shocked: { fingerprint: "b".repeat(64), events: [{ reason: "untrusted" }] },
  ignored: "untrusted",
});

test("extracts only supported settings and recorded fingerprints", () => {
  const parsed = parsePassport(JSON.stringify(makePassport()));
  assert.deepEqual(parsed, {
    request, baselineFingerprint: "a".repeat(64), shockedFingerprint: "b".repeat(64),
  });
});

test("accepts the limits offered by the UI", () => {
  const data = makePassport();
  Object.assign(data.request, {
    strategy_key: "momentum", seed: 4294967295, fee_bps: 50, slippage_bps: 30,
    shock_pct: 0, guard_enabled: false, guard_drawdown_pct: 20,
  });
  assert.deepEqual(parsePassport(JSON.stringify(data)).request, data.request);
});

test("rejects invalid JSON, formats and fingerprint shapes", () => {
  assert.throws(() => parsePassport("{"), /valid JSON/);
  const data = makePassport();
  data.format = "axiom-survival-lab-v2";
  assert.throws(() => parsePassport(JSON.stringify(data)), /Unsupported passport format/);
  data.format = "axiom-survival-lab-v1";
  data.baseline.fingerprint = "z".repeat(64);
  assert.throws(() => parsePassport(JSON.stringify(data)), /fingerprint/);
});

test("rejects missing, unknown and unsupported settings without clamping", () => {
  const data = makePassport();
  delete data.request.seed;
  assert.throws(() => parsePassport(JSON.stringify(data)), /missing seed/);
  data.request.seed = 42;
  data.request.unexpected = true;
  assert.throws(() => parsePassport(JSON.stringify(data)), /unsupported fields/);
  delete data.request.unexpected;
  data.request.strategy_key = "macd";
  assert.throws(() => parsePassport(JSON.stringify(data)), /strategy_key/);
  data.request.strategy_key = "rsi";
  data.request.shock_pct = 31;
  assert.throws(() => parsePassport(JSON.stringify(data)), /shock_pct/);
});

test("rejects coerced, non-finite and non-object inputs", () => {
  const data = makePassport();
  data.request.seed = "42";
  assert.throws(() => parsePassport(JSON.stringify(data)), /seed/);
  data.request.seed = 42;
  data.request.guard_enabled = 1;
  assert.throws(() => parsePassport(JSON.stringify(data)), /guard_enabled/);
  const json = JSON.stringify(makePassport()).replace('"seed":42', '"seed":1e400');
  assert.throws(() => parsePassport(json), /seed/);
  assert.throws(() => parsePassport("[]"), /JSON object/);
});
