import test from "node:test";
import assert from "node:assert/strict";
import { resolveWarRoomEvidence, validateWarRoomResponse } from "../src/warRoomEvidence.js";

const entry = (overrides = {}) => ({
  id: "guard-block", label: "Blocked buy", value: "BUY", detail: "Recorded at the close",
  path: "guarded", candle_index: 2, event_type: "blocked", ...overrides,
});

function fixture() {
  const blocked = { candle_index: 2, event_type: "blocked", action: "BUY", reason: "paused" };
  const fill = { candle_index: 1, event_type: "fill", action: "BUY", reason: "filled" };
  const run = {
    candles: [{}, {}, {}], scenario: { shock_pct: 12, shock_index: 2 },
    guarded: { events: [blocked] }, unguarded: { events: [fill] },
  };
  const evidence = [entry(),
    entry({ id: "fill", label: "Buy fill", path: "unguarded", candle_index: 1, event_type: "fill" }),
    entry({ id: "shock", label: "Shock", path: "scenario", candle_index: 2, event_type: null }),
    entry({ id: "metric", label: "Final equity", path: "guarded", candle_index: null, event_type: null }),
  ];
  const messages = [
    { role: "challenger", headline: "Challenge", body: "Examine the shock.", evidence_ids: ["shock"] },
    { role: "defender", headline: "Decision", body: "Inspect the fill.", evidence_ids: ["fill"] },
    { role: "auditor", headline: "Scope", body: "Inspect the block.", evidence_ids: ["guard-block", "metric"] },
  ];
  return { run, blocked, fill, data: { fingerprint: "recorded-fingerprint", mode: "scripted", evidence, messages } };
}

test("valid review returns the response without asserting whether its text is true", () => {
  const { data } = fixture();
  assert.equal(validateWarRoomResponse(data, "recorded-fingerprint", "scripted"), data);
  const claude = { ...data, mode: "claude" };
  assert.equal(validateWarRoomResponse(claude, "recorded-fingerprint", "claude"), claude);
});

test("rejects missing, stale, or mismatched fingerprint and mode", () => {
  const { data } = fixture();
  for (const args of [
    [{ ...data, fingerprint: "other" }, "recorded-fingerprint", "scripted"],
    [data, "", "scripted"], [data, "recorded-fingerprint", "claude"],
    [{ ...data, mode: "other" }, "recorded-fingerprint", "other"],
  ]) assert.throws(() => validateWarRoomResponse(...args), /incomplete or did not match/);
});

test("rejects malformed evidence and duplicate or unknown citations", () => {
  for (const mutate of [
    (d) => { d.evidence = []; },
    (d) => { d.evidence.push({ ...d.evidence[0] }); },
    (d) => { d.evidence[0].id = " "; },
    (d) => { d.evidence[0].value = null; },
    (d) => { d.evidence[0].detail = " "; },
    (d) => { d.evidence[0].path = "other"; },
    (d) => { d.evidence[0].candle_index = -1; },
    (d) => { d.evidence[0].candle_index = 1.5; },
    (d) => { d.evidence[0].candle_index = "2"; },
    (d) => { delete d.evidence[0].event_type; },
    (d) => { d.evidence[0].event_type = "invented"; },
    (d) => { d.evidence[0].candle_index = null; },
    (d) => { d.evidence[0].path = "scenario"; },
    (d) => { d.messages[0].evidence_ids = ["missing"]; },
    (d) => { d.messages[0].evidence_ids = ["shock", "shock"]; },
    (d) => { d.messages[0].evidence_ids = []; },
  ]) {
    const { data } = fixture();
    mutate(data);
    assert.throws(() => validateWarRoomResponse(data, "recorded-fingerprint", "scripted"));
  }
});

test("requires three ordered roles with nonempty message text and references", () => {
  for (const mutate of [
    (d) => { d.messages = []; },
    (d) => { d.messages.reverse(); },
    (d) => { d.messages[1].role = "challenger"; },
    (d) => { d.messages[0].headline = " "; },
    (d) => { d.messages[1].body = null; },
    (d) => { d.messages[2].evidence_ids = null; },
  ]) {
    const { data } = fixture();
    mutate(data);
    assert.throws(() => validateWarRoomResponse(data, "recorded-fingerprint", "scripted"));
  }
});

test("event references resolve to the exact recorded object on the selected path", () => {
  const { run, blocked, fill, data } = fixture();
  const guarded = resolveWarRoomEvidence(data.evidence[0], run);
  assert.deepEqual(guarded, { candleIndex: 2, event: blocked, label: "Blocked buy", path: "guarded" });
  assert.equal(guarded.event, blocked);
  const unguarded = resolveWarRoomEvidence(data.evidence[1], run);
  assert.equal(unguarded.event, fill);
  assert.equal(unguarded.path, "unguarded");
  assert.deepEqual(resolveWarRoomEvidence(entry({ event_type: null }), run), {
    candleIndex: 2, event: null, label: "Blocked buy", path: "guarded",
  });
});

test("scenario marker navigates only to the actual nonzero shock", () => {
  const { run, data } = fixture();
  const shock = data.evidence[2];
  assert.deepEqual(resolveWarRoomEvidence(shock, run), { candleIndex: 2, event: null, label: "Shock", path: "scenario" });
  assert.equal(resolveWarRoomEvidence({ ...shock, candle_index: 1 }, run), null);
  assert.equal(resolveWarRoomEvidence(shock, { ...run, scenario: { shock_pct: 0, shock_index: 2 } }), null);
  assert.equal(resolveWarRoomEvidence({ ...shock, event_type: "fill" }, run), null);
});

test("missing, ambiguous, or invalid references never navigate", () => {
  const { run, data, blocked } = fixture();
  for (const bad of [
    { ...data.evidence[0], candle_index: null }, { ...data.evidence[0], candle_index: -1 },
    { ...data.evidence[0], candle_index: 3 }, { ...data.evidence[0], candle_index: "2" },
    { ...data.evidence[0], path: "unknown" }, { ...data.evidence[0], event_type: "fill" },
    { ...data.evidence[0], event_type: undefined }, { ...data.evidence[0], label: " " },
  ]) assert.equal(resolveWarRoomEvidence(bad, run), null);
  assert.equal(resolveWarRoomEvidence(data.evidence[0], { ...run, guarded: null }), null);
  assert.equal(resolveWarRoomEvidence(data.evidence[0], { ...run, guarded: {} }), null);
  assert.equal(resolveWarRoomEvidence(data.evidence[0], { ...run, candles: null }), null);
  assert.equal(resolveWarRoomEvidence(data.evidence[0], { ...run, guarded: { events: [blocked, { ...blocked }] } }), null);
});
