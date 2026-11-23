import test from "node:test";
import assert from "node:assert/strict";
import { buildWarRoomCase } from "../src/warRoomCase.js";

const evidence = [{ id: "fact", label: "Scenario", value: "Synthetic", detail: "A recorded case.",
  path: "scenario", candle_index: null, event_type: null }];
const messages = ["challenger", "defender", "auditor"].map((role) => ({ role, headline: role, body: "A perspective.", evidence_ids: ["fact"] }));
const review = { fingerprint: "a".repeat(64), mode: "scripted", model: null, engine_version: "v4", evidence, messages, limitations: ["Synthetic."] };
const scenario = { strategy_key: "rsi", seed: 42, shock_pct: 12 };

test("case file retains evidence and the user's local decision without inventing verification", () => {
  const note = "Investigate <script> as plain text";
  const result = buildWarRoomCase(scenario, review, "investigate", note);
  assert.equal(result.fingerprint, review.fingerprint);
  assert.deepEqual(result.evidence, evidence);
  assert.deepEqual(result.human_review, { outcome: "investigate", notes: note });
  assert.match(result.notice, /not an independent audit/);
  assert.equal(JSON.parse(JSON.stringify(result)).human_review.notes, note);
});

test("invalid outcomes, oversized notes and broken citations cannot be exported", () => {
  assert.throws(() => buildWarRoomCase(scenario, review, "approve_trading", ""));
  assert.throws(() => buildWarRoomCase(scenario, review, "undecided", "x".repeat(501)));
  const bad = { ...review, messages: [{ ...messages[0], evidence_ids: ["missing"] }, ...messages.slice(1)] };
  assert.throws(() => buildWarRoomCase(scenario, bad, "undecided", ""));
});
