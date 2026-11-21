import test from "node:test";
import assert from "node:assert/strict";
import { compareGuardDecisions } from "../src/decisionComparison.js";

const event = (candle, kind, action, signal = candle, extra = {}) => ({
  candle_index: candle, event_type: kind, action, signal_index: signal, reason: kind, ...extra,
});
const run = (guardedEvents, unguardedEvents, count = 6) => ({
  candles: Array.from({ length: count }, () => ({})),
  guarded: { events: guardedEvents, final_equity: 9900 },
  unguarded: { events: unguardedEvents, final_equity: 9950 },
});

test("links the first blocked BUY to its own unguarded next-open fill", () => {
  const blocked = event(3, "blocked", "BUY");
  const signal = event(3, "signal", "BUY");
  const unrelatedEarlierFill = event(3, "fill", "BUY", 2);
  const unrelatedNextOpen = event(4, "fill", "BUY", 1);
  const actualFill = event(4, "fill", "BUY", 3, { quantity: 2.31282, price: 93.1078 });
  const result = compareGuardDecisions(run(
    [event(5, "blocked", "BUY"), blocked, event(2, "blocked", "SELL")],
    [unrelatedEarlierFill, signal, unrelatedNextOpen, actualFill],
  ));
  assert.equal(result.status, "compared");
  assert.equal(result.blocked, blocked); // preserved for the recorder callback
  assert.equal(result.signal, signal);
  assert.equal(result.outcome, actualFill);
  assert.equal(result.outcomeStatus, "fill");
  assert.equal(result.difference, -50);
});

test("guard disabled, unavailable paths, and no blocked BUY are distinct", () => {
  assert.deepEqual(compareGuardDecisions({ guarded: null }), { status: "guard_disabled" });
  assert.equal(compareGuardDecisions({}).status, "unavailable");
  const noBlocked = compareGuardDecisions(run([event(2, "guard", "HOLD"), event(4, "blocked", "SELL")], []));
  assert.equal(noBlocked.status, "no_blocked_buy");
  assert.equal(noBlocked.difference, -50);
});

test("reports a missing or different unguarded signal without inventing a BUY", () => {
  const blocked = event(2, "blocked", "BUY");
  assert.equal(compareGuardDecisions(run([blocked], [])).outcomeStatus, "no_signal");
  for (const action of ["HOLD", "SELL"]) {
    const signal = event(2, "signal", action);
    const result = compareGuardDecisions(run([blocked], [signal, event(3, "fill", "BUY", 2)]));
    assert.equal(result.outcomeStatus, "different_signal");
    assert.equal(result.signal, signal);
    assert.equal(result.outcome, null);
  }
});

test("distinguishes a next-open rejection from a fill", () => {
  const rejection = event(4, "rejected", "BUY", 3, { reason: "Position cap" });
  const result = compareGuardDecisions(run(
    [event(3, "blocked", "BUY")], [event(3, "signal", "BUY"), rejection],
  ));
  assert.equal(result.outcomeStatus, "rejected");
  assert.equal(result.outcome, rejection);
});

test("reports final-candle expiry only when the recorded unguarded signal expired", () => {
  const blocked = event(5, "blocked", "BUY");
  const expired = event(5, "expired", "BUY", 5);
  const result = compareGuardDecisions(run([blocked], [event(5, "signal", "BUY"), expired]));
  assert.equal(result.outcomeStatus, "expired");
  assert.equal(result.outcome, expired);
  const incomplete = compareGuardDecisions(run([blocked], [event(5, "signal", "BUY")]));
  assert.equal(incomplete.outcomeStatus, "no_outcome");
  assert.equal(incomplete.outcome, null);
});

test("does not link fills from other signals, wrong candles, or invalid indices", () => {
  const blocked = event(2, "blocked", "BUY");
  const signal = event(2, "signal", "BUY");
  const result = compareGuardDecisions(run([blocked], [
    signal, event(2, "fill", "BUY", 2), event(3, "fill", "BUY", 1),
    event(4, "fill", "BUY", 2), event(3, "fill", "SELL", 2), event(2, "expired", "BUY", 2),
  ]));
  assert.equal(result.outcomeStatus, "no_outcome");
  assert.equal(result.outcome, null);
  assert.equal(compareGuardDecisions(run([event(-1, "blocked", "BUY"), event(9, "blocked", "BUY")], [])).status, "no_blocked_buy");
  assert.equal(compareGuardDecisions(run([blocked], [{ ...signal, signal_index: null }, event(3, "fill", "BUY", 2)])).outcomeStatus, "no_outcome");
});

test("non-finite equity is unavailable rather than shown as a numeric difference", () => {
  const scenario = run([event(2, "blocked", "BUY")], [event(2, "signal", "BUY")]);
  scenario.guarded.final_equity = Number.NaN;
  assert.equal(compareGuardDecisions(scenario).difference, null);
});
