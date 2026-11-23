// Structural checks connect review cards to a completed simulation; they do
// not establish that the reviewers' prose is accurate or independently verified.
const PATHS = new Set(["guarded", "unguarded", "scenario"]);
const EVENT_TYPES = new Set(["signal", "fill", "guard", "blocked", "rejected", "expired"]);
const ROLES = ["challenger", "defender", "auditor"];
const MODES = new Set(["scripted", "claude"]);

const isObject = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
const nonempty = (value) => typeof value === "string" && value.trim().length > 0;
const validIndex = (value) => Number.isSafeInteger(value) && value >= 0;

/** Check response structure and citation references, not the truth of the prose. */
export function validateWarRoomResponse(data, expectedFingerprint, requestedMode) {
  const invalid = () => { throw new Error("The War Room response was incomplete or did not match this experiment."); };
  if (!isObject(data) || !nonempty(expectedFingerprint) || data.fingerprint !== expectedFingerprint ||
      !MODES.has(requestedMode) || data.mode !== requestedMode ||
      !Array.isArray(data.evidence) || data.evidence.length === 0 ||
      !Array.isArray(data.messages) || data.messages.length !== ROLES.length) invalid();

  const ids = new Set();
  for (const item of data.evidence) {
    if (!isObject(item) || !nonempty(item.id) || ids.has(item.id) ||
        !nonempty(item.label) || !nonempty(item.value) || !nonempty(item.detail) ||
        !PATHS.has(item.path) ||
        !(item.candle_index === null || validIndex(item.candle_index)) ||
        !(item.event_type === null || EVENT_TYPES.has(item.event_type)) ||
        (item.event_type !== null && (item.candle_index === null || item.path === "scenario"))) invalid();
    ids.add(item.id);
  }

  data.messages.forEach((message, index) => {
    if (!isObject(message) || message.role !== ROLES[index] ||
        !nonempty(message.headline) || !nonempty(message.body) ||
        !Array.isArray(message.evidence_ids) || message.evidence_ids.length === 0) invalid();
    const cited = new Set();
    for (const id of message.evidence_ids) {
      if (!nonempty(id) || !ids.has(id) || cited.has(id)) invalid();
      cited.add(id);
    }
  });
  return data;
}

/** Locate a reference on the original completed shock run, or decline navigation. */
export function resolveWarRoomEvidence(entry, run) {
  if (!isObject(entry) || !isObject(run) || !nonempty(entry.label) || !PATHS.has(entry.path) ||
      !Array.isArray(run.candles) || !validIndex(entry.candle_index) || entry.candle_index >= run.candles.length) return null;
  const candleIndex = entry.candle_index;

  if (entry.path === "scenario") {
    // A scenario marker is navigable only to an actual injected shock.
    if (entry.event_type !== null || !Number.isFinite(run.scenario?.shock_pct) ||
        run.scenario.shock_pct <= 0 || run.scenario.shock_index !== candleIndex) return null;
    return { candleIndex, event: null, label: entry.label, path: entry.path };
  }

  const path = run[entry.path];
  if (!isObject(path) || !Array.isArray(path.events)) return null;
  if (entry.event_type === null) return { candleIndex, event: null, label: entry.label, path: entry.path };
  if (!EVENT_TYPES.has(entry.event_type)) return null;
  const matches = path.events.filter((event) => isObject(event) &&
    event.candle_index === candleIndex && event.event_type === entry.event_type);
  // A type and candle must identify exactly one event, not an arbitrary first match.
  if (matches.length !== 1) return null;
  return { candleIndex, event: matches[0], label: entry.label, path: entry.path };
}
