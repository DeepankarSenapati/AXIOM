// Parser for the "axiom-survival-lab-v1" JSON export.
//
// Only the request and the two fingerprints are extracted. Stored results,
// metrics and any other file contents are intentionally ignored and never
// returned. Fingerprints are NOT proof that the file, source code, outputs or
// execution are authentic; they are only values for comparison against a
// rerun performed through the API. The caller should check the file size
// before reading it.

const FORMAT = "axiom-survival-lab-v1";
const FINGERPRINT_RE = /^[0-9a-fA-F]{64}$/;
const STRATEGIES = ["simple_ma", "rsi", "momentum"];

const hasOwn = (o, k) => Object.prototype.hasOwnProperty.call(o, k);

function isPlainObject(v) {
  if (v === null || typeof v !== "object" || Array.isArray(v)) return false;
  const proto = Object.getPrototypeOf(v);
  return proto === Object.prototype || proto === null;
}

const isInt = (v, min, max) =>
  typeof v === "number" && Number.isInteger(v) && v >= min && v <= max;
const isExact = (expected) => (v) => typeof v === "number" && Number.isFinite(v) && v === expected;

// Same key order as INITIAL_INPUTS in SurvivalLab.jsx.
const REQUEST_SPEC = [
  ["strategy_key", (v) => typeof v === "string" && STRATEGIES.includes(v), "must be simple_ma, rsi or momentum"],
  ["seed", (v) => isInt(v, 0, 4294967295), "must be an integer from 0 to 4294967295"],
  ["num_candles", isExact(160), "must be 160"],
  ["start_price", isExact(100), "must be 100"],
  ["starting_cash", isExact(10000), "must be 10000"],
  ["fee_bps", (v) => isInt(v, 0, 50), "must be an integer from 0 to 50"],
  ["slippage_bps", (v) => isInt(v, 0, 30), "must be an integer from 0 to 30"],
  ["shock_pct", (v) => isInt(v, 0, 30), "must be an integer from 0 to 30"],
  ["shock_index", isExact(90), "must be 90"],
  ["guard_enabled", (v) => typeof v === "boolean", "must be true or false"],
  ["guard_drawdown_pct", (v) => isInt(v, 2, 20), "must be an integer from 2 to 20"],
  ["max_position_pct", isExact(30), "must be 30"],
];

function parseRequest(raw) {
  if (!isPlainObject(raw)) throw new Error("Passport request must be an object.");
  const known = new Set(REQUEST_SPEC.map(([k]) => k));
  for (const key of Object.keys(raw)) {
    if (!known.has(key)) throw new Error("Passport request contains unsupported fields.");
  }
  const request = {};
  for (const [key, valid, hint] of REQUEST_SPEC) {
    if (!hasOwn(raw, key)) throw new Error(`Passport request is missing ${key}.`);
    if (!valid(raw[key])) throw new Error(`Passport request ${key} ${hint}.`);
    request[key] = raw[key];
  }
  return request;
}

function parseFingerprint(section, name) {
  if (!isPlainObject(section)) throw new Error(`Passport ${name} section must be an object.`);
  const fp = hasOwn(section, "fingerprint") ? section.fingerprint : undefined;
  if (typeof fp !== "string" || !FINGERPRINT_RE.test(fp)) {
    throw new Error(`Passport ${name} fingerprint must be 64 hexadecimal characters.`);
  }
  return fp.toLowerCase();
}

export function parsePassport(text) {
  if (typeof text !== "string") throw new Error("Passport must be text.");
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("File is not valid JSON.");
  }
  if (!isPlainObject(data)) throw new Error("Passport must be a JSON object.");
  if (data.format !== FORMAT) throw new Error(`Unsupported passport format; expected ${FORMAT}.`);

  const request = parseRequest(hasOwn(data, "request") ? data.request : undefined);
  const baselineFingerprint = parseFingerprint(hasOwn(data, "baseline") ? data.baseline : undefined, "baseline");
  const shockedFingerprint = parseFingerprint(hasOwn(data, "shocked") ? data.shocked : undefined, "shocked");
  return { request, baselineFingerprint, shockedFingerprint };
}
