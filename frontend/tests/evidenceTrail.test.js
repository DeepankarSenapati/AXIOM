import test from "node:test";
import assert from "node:assert/strict";
import { buildEvidenceTrail } from "../src/evidenceTrail.js";

const event = (candle_index, event_type, action, reason = event_type) => ({ candle_index, event_type, action, reason });
const makeRun = (events, shock = 4, guarded = true) => ({
  candles: Array.from({ length: 10 }, () => ({})),
  scenario: { shock_index: shock, shock_pct: shock == null ? 0 : 12 },
  guarded: guarded ? { events } : null,
  unguarded: { events: [event(0, "fill", "SELL", "unguarded path")] },
});

test("orders actual guarded events around the shock marker and retains event identity", () => {
  const events = [event(1, "fill", "BUY"), event(4, "fill", "BUY"), event(4, "guard", "HOLD"), event(4, "blocked", "BUY"), event(7, "fill", "SELL")];
  const trail = buildEvidenceTrail(makeRun(events));
  assert.deepEqual(trail.map((m) => m.id), ["event-0", "shock", "event-1", "event-2", "event-3", "event-4"]);
  assert.equal(trail[1].event, null);
  assert.match(trail[1].reason, /scenario marker/);
  assert.equal(trail[3].event, events[2]);
  assert.equal(trail[4].label, "BUY signal blocked");
});

test("chooses the unguarded path and omits a nonexistent shock", () => {
  const trail = buildEvidenceTrail(makeRun([event(3, "guard", "HOLD")], null, false));
  assert.deepEqual(trail.map((m) => m.label), ["SELL filled"]);
  assert.equal(trail[0].reason, "unguarded path");
});

test("reports rejected and expired orders without inventing fills and ignores invalid indices", () => {
  const events = [event(-1, "fill", "BUY"), event(2, "rejected", "BUY"), event(9, "expired", "SELL"), event(15, "guard", "HOLD")];
  const trail = buildEvidenceTrail(makeRun(events, null));
  assert.deepEqual(trail.map((m) => m.label), ["BUY order rejected", "SELL signal expired"]);
});

test("does not duplicate the first fill when it is also the first after the shock", () => {
  const trail = buildEvidenceTrail(makeRun([event(4, "fill", "BUY")], 4));
  assert.deepEqual(trail.map((m) => m.id), ["shock", "event-0"]);
});

test("includes pending fills before a same-candle guard even when an earlier fill was selected", () => {
  const events = [event(1, "fill", "BUY"), event(3, "fill", "BUY"), event(3, "guard", "HOLD"), event(3, "blocked", "BUY")];
  const trail = buildEvidenceTrail(makeRun(events, 4));
  assert.deepEqual(trail.map((m) => m.id), ["event-0", "event-1", "event-2", "event-3", "shock"]);
});
