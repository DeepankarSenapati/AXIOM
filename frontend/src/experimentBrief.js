// Pure builder for a printable, offline, script-free investor demo brief.
// Input: an already completed Survival Lab run ({ request, baseline, shock }).
// Output: a complete standalone HTML string. No I/O, no network, no randomness.

import { formatPercent } from "./percentFormatting.js";

const STRATEGY_LABELS = {
  simple_ma: "Simple moving average",
  rsi: "RSI",
  bollinger_bands: "Bollinger bands",
  macd: "MACD",
  momentum: "Momentum",
};

const CHART = { w: 640, h: 230, right: 14, top: 14, bottom: 30 };
const REQUEST_FIELDS = [
  "strategy_key", "seed", "num_candles", "start_price", "starting_cash",
  "fee_bps", "slippage_bps", "shock_pct", "shock_index", "guard_enabled",
  "guard_drawdown_pct", "max_position_pct",
];

function fail(message) {
  throw new Error(`Experiment brief: ${message}`);
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function finite(value, label) {
  if (typeof value !== "number" || !Number.isFinite(value)) fail(`${label} must be a finite number.`);
  return value;
}

function nonNegInt(value, label) {
  if (!Number.isInteger(value) || value < 0) fail(`${label} must be a non-negative integer.`);
  return value;
}

function text(value, label) {
  if (typeof value !== "string" || value.length === 0) fail(`${label} must be a non-empty string.`);
  return value;
}

export function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

const esc = escapeHtml;

function fmt(value, digits) {
  const out = value.toFixed(digits);
  return out === "-0" || /^-0\.0*$/.test(out) ? out.slice(1) : out;
}

function money(value) {
  const sign = value < 0 ? "-" : "";
  const [whole, frac] = Math.abs(value).toFixed(2).split(".");
  return `${sign}$${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${frac}`;
}

function validateRun(run, label, count, startingCash) {
  if (!isObject(run)) fail(`${label} is missing.`);
  if (!Array.isArray(run.equity_curve) || run.equity_curve.length !== count) {
    fail(`${label} equity curve must contain exactly ${count} points.`);
  }
  const values = run.equity_curve.map((point, i) => {
    if (!isObject(point)) fail(`${label} equity curve point ${i} is invalid.`);
    if (point.index !== i) fail(`${label} equity curve index mismatch at point ${i}.`);
    const equity = finite(point.equity, `${label} equity at point ${i}`);
    if (equity < 0 || equity >= 1e21) fail(`${label} equity is outside the supported chart range.`);
    return equity;
  });
  const finalEquity = finite(run.final_equity, `${label} final equity`);
  const reportedReturn = finite(run.total_return_pct, `${label} total return`);
  const reportedDrawdown = finite(run.max_drawdown_pct, `${label} max drawdown`);
  const last = values[values.length - 1];
  const cashTolerance = Math.max(1e-8, 32 * Number.EPSILON * Math.max(1, Math.abs(startingCash), Math.abs(last)));
  if (Math.abs(finalEquity - last) > cashTolerance) fail(`${label} final equity does not match its curve.`);
  const expectedReturn = (last / startingCash - 1) * 100;
  let peak = startingCash;
  let expectedDrawdown = 0;
  for (const value of values) {
    peak = Math.max(peak, value);
    expectedDrawdown = Math.max(expectedDrawdown, ((peak - value) / peak) * 100);
  }
  const closePercent = (actual, expected) => Math.abs(actual - expected) <=
    1e-9 + 64 * Number.EPSILON * Math.max(1, Math.abs(actual), Math.abs(expected));
  if (!closePercent(reportedReturn, expectedReturn)) fail(`${label} return does not match its curve.`);
  if (!closePercent(reportedDrawdown, expectedDrawdown)) fail(`${label} drawdown does not match its curve.`);
  const trig = run.guard_trigger_index;
  if (trig !== null && trig !== undefined && (!Number.isInteger(trig) || trig < 0 || trig >= count)) {
    fail(`${label} guard trigger index is out of range.`);
  }
  return values;
}

function validateResponse(res, label, startingCash) {
  if (!isObject(res)) fail(`${label} run is missing.`);
  if (!/^[0-9a-f]{64}$/i.test(text(res.fingerprint, `${label} fingerprint`))) fail(`${label} fingerprint is invalid.`);
  text(res.engine_version, `${label} engine version`);
  text(res.strategy_key, `${label} strategy`);
  if (!isObject(res.request)) fail(`${label} effective request is missing; rerun with the current engine.`);
  if (!isObject(res.strategy_parameters)) fail(`${label} strategy parameters are missing.`);
  for (const value of Object.values(res.strategy_parameters)) finite(value, `${label} strategy parameter`);
  const signalCashFraction = finite(res.signal_cash_fraction, `${label} signal cash fraction`);
  if (signalCashFraction < 0 || signalCashFraction > 1) fail(`${label} signal cash fraction is invalid.`);
  if (!isObject(res.scenario)) fail(`${label} scenario is missing.`);
  if (res.scenario.source !== "synthetic") fail(`${label} must use synthetic data.`);
  const count = nonNegInt(res.scenario.candle_count, `${label} candle count`);
  if (count < 2 || count > 600) fail(`${label} candle count must be between 2 and 600.`);
  nonNegInt(res.scenario.seed, `${label} seed`);
  finite(res.scenario.shock_pct, `${label} shock percent`);
  const si = res.scenario.shock_index;
  if (si !== null && si !== undefined && (!Number.isInteger(si) || si < 0 || si >= count)) {
    fail(`${label} shock index is out of range.`);
  }
  const unguarded = validateRun(res.unguarded, `${label} unguarded`, count, startingCash);
  const benchmark = validateRun(res.benchmark, `${label} buy-and-hold`, count, startingCash);
  const guardedRun = res.guarded === null || res.guarded === undefined ? null : res.guarded;
  const guarded = guardedRun ? validateRun(guardedRun, `${label} guarded`, count, startingCash) : null;
  return { count, unguarded, benchmark, guarded };
}

function buildChart(series, count, shockIndex) {
  const { w, h, right, top, bottom } = CHART;
  let min = Infinity;
  let max = -Infinity;
  for (const s of series) {
    for (const v of s.values) {
      if (v < min) min = v;
      if (v > max) max = v;
    }
  }
  // Keep cent-formatted ticks distinct even when all curves are nearly flat.
  if (max - min < 0.08) {
    const center = (max + min) / 2;
    min = Math.max(0, center - 0.04);
    max = min + 0.08;
  }
  const span = max - min;
  min = Math.max(0, min - span * 0.05);
  max += span * 0.05;
  // Reserve enough room for the longest actual dollar tick, including large balances.
  const left = Math.max(62, Math.ceil(Math.max(money(min).length, money(max).length) * 5.6 + 12));
  const pw = w - left - right;
  const ph = h - top - bottom;
  const x = (i) => left + (pw * i) / (count - 1);
  const y = (v) => top + ph * (1 - (v - min) / (max - min));
  const r = (n) => {
    if (!Number.isFinite(n)) fail("chart coordinate is not finite.");
    return n.toFixed(2);
  };

  const parts = [];
  for (let t = 0; t <= 4; t += 1) {
    const v = min + ((max - min) * t) / 4;
    const yy = r(y(v));
    parts.push(`<line x1="${left}" y1="${yy}" x2="${w - right}" y2="${yy}" class="grid"/>`);
    parts.push(`<text x="${left - 6}" y="${r(y(v) + 3)}" text-anchor="end" class="tick">${esc(money(v))}</text>`);
  }
  const xt = count >= 5 ? [0, 0.25, 0.5, 0.75, 1] : [0, 1];
  for (const f of xt) {
    const i = Math.round((count - 1) * f);
    parts.push(`<text x="${r(x(i))}" y="${h - 12}" text-anchor="middle" class="tick">${i + 1}</text>`);
  }
  parts.push(`<text x="${r(left + pw / 2)}" y="${h - 1}" text-anchor="middle" class="tick">Candle</text>`);
  parts.push(`<rect x="${left}" y="${top}" width="${pw}" height="${ph}" class="frame"/>`);

  if (shockIndex !== null) {
    const sx = r(x(shockIndex));
    const anchor = shockIndex > count * 0.7 ? "end" : "start";
    const tx = r(x(shockIndex) + (anchor === "end" ? -4 : 4));
    parts.push(`<line x1="${sx}" y1="${top}" x2="${sx}" y2="${top + ph}" class="shockline"/>`);
    parts.push(`<text x="${tx}" y="${top + 10}" text-anchor="${anchor}" class="shocklabel">Shock · candle ${shockIndex + 1}</text>`);
  }
  for (const s of series) {
    const pts = s.values.map((v, i) => `${r(x(i))},${r(y(v))}`).join(" ");
    parts.push(`<polyline points="${pts}" fill="none" class="${s.cls}"/>`);
  }
  return `<svg viewBox="0 0 ${w} ${h}" role="img" aria-labelledby="chart-title chart-desc" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet"><title id="chart-title">Simulated equity curves</title><desc id="chart-desc">${esc(series.map((s) => `${s.name}: from ${money(s.values[0])} to ${money(s.values[s.values.length - 1])}`).join("; "))}. Synthetic data.</desc>${parts.join("")}</svg>`;
}

const CSS = `
*{box-sizing:border-box}
@page{size:auto;margin:9mm}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;background:#eef1f4;color:#111827;font:12px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.page{max-width:1000px;margin:16px auto;background:#fff;border:1px solid #cbd2da;border-top:5px solid #0f172a;padding:18px 22px}
header{display:flex;justify-content:space-between;gap:12px;align-items:flex-end;border-bottom:1px solid #0f172a;padding-bottom:8px}
.eyebrow{font:600 10px/1 ui-monospace,Menlo,Consolas,monospace;letter-spacing:.14em;text-transform:uppercase;color:#334155}
h1{margin:5px 0 0;font-size:22px;line-height:1.1;letter-spacing:-.01em}
.badge{border:1.5px solid #111827;padding:4px 8px;font:700 10px/1.2 ui-monospace,Menlo,Consolas,monospace;letter-spacing:.08em;text-transform:uppercase;white-space:nowrap}
.notice{margin:10px 0;border:1.5px solid #111827;background:#f1f5f9;padding:8px 10px}
.notice strong{display:block;font-size:13px;margin-bottom:3px}
.notice ul{margin:3px 0 0;padding-left:16px}
.notice li{margin:1px 0}
.grid2{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(0,1fr);gap:12px;align-items:start}
h2{margin:0 0 5px;font:700 10px/1.2 ui-monospace,Menlo,Consolas,monospace;letter-spacing:.12em;text-transform:uppercase;color:#334155}
.panel{border:1px solid #cbd2da;padding:8px 10px}
svg{display:block;width:100%;height:auto}
.grid{stroke:#d5dbe2;stroke-width:.6}
.frame{fill:none;stroke:#64748b;stroke-width:.8}
.tick{font:9px ui-monospace,Menlo,Consolas,monospace;fill:#475569}
.shockline{stroke:#111827;stroke-width:1;stroke-dasharray:1 3}
.shocklabel{font:700 9px ui-monospace,Menlo,Consolas,monospace;fill:#111827}
.s-base{stroke:#64748b;stroke-width:1.6;stroke-linejoin:round}
.s-shock{stroke:#b91c1c;stroke-width:1.8;stroke-dasharray:7 4;stroke-linejoin:round}
.s-guard{stroke:#0f172a;stroke-width:2.2;stroke-dasharray:1.5 3;stroke-linecap:round;stroke-linejoin:round}
.s-benchmark{stroke:#04746c;stroke-width:1.8;stroke-dasharray:10 3 2 3;stroke-linejoin:round}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;margin-top:4px;font-size:10.5px}
.legend span{display:inline-flex;align-items:center;gap:5px}
.legend svg{width:30px;height:8px;display:inline-block}
.metrics{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.m{border:1px solid #cbd2da;padding:5px 7px;min-width:0}
.m span{display:block;font:600 8.5px/1.2 ui-monospace,Menlo,Consolas,monospace;letter-spacing:.08em;text-transform:uppercase;color:#475569}
.m b{display:block;font-size:17px;line-height:1.2;font-variant-numeric:tabular-nums}
.m small{display:block;color:#475569;font-size:9.5px;line-height:1.25}
dl{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;margin:0}
dt{color:#475569}
dd{margin:0;font-weight:600;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.fp{margin-top:8px;border:1px solid #cbd2da;padding:6px 10px}
code{display:block;font:10.5px/1.35 ui-monospace,Menlo,Consolas,monospace;word-break:break-all;overflow-wrap:anywhere}
.limits{margin:8px 0 0;padding-left:16px;font-size:10.5px}
.limits li{margin:1px 0}
footer{margin-top:8px;border-top:1px solid #cbd2da;padding-top:5px;font-size:9.5px;color:#475569}
@media (max-width:760px){.page{margin:0;border-left:0;border-right:0;padding:14px}.grid2{grid-template-columns:1fr}header{flex-direction:column;align-items:flex-start}}
@media print{
body{background:#fff;font-size:10.5px;line-height:1.3}
.page{margin:0;max-width:none;border:0;border-top:4px solid #000;padding:0 0 0}
.grid2{grid-template-columns:minmax(0,1.5fr) minmax(0,1fr)}
h1{font-size:19px}
.m b{font-size:14px}
.notice,.panel,.m,.fp{break-inside:avoid;page-break-inside:avoid}
.notice{background:#fff}
}
`;

export function buildExperimentBrief({ request, baseline, shock } = {}) {
  if (!isObject(request)) fail("request is missing.");
  const strategyKey = text(request.strategy_key, "strategy");
  if (!Object.prototype.hasOwnProperty.call(STRATEGY_LABELS, strategyKey)) fail("strategy is unsupported.");
  const seed = nonNegInt(request.seed, "request seed");
  const startingCash = finite(request.starting_cash, "starting cash");
  const startPrice = finite(request.start_price, "starting price");
  if (startingCash <= 0 || startPrice <= 0) fail("starting cash and price must be positive.");
  const feeBps = finite(request.fee_bps, "fee");
  const slipBps = finite(request.slippage_bps, "slippage");
  const cap = finite(request.max_position_pct, "position cap");
  const requestedShock = finite(request.shock_pct, "shock percent");
  if (feeBps < 0 || slipBps < 0) fail("fee and slippage must not be negative.");
  if (cap <= 0 || cap > 100) fail("position cap must be in (0, 100].");
  if (requestedShock < 0 || requestedShock > 80) fail("shock percent is out of range.");
  if (typeof request.guard_enabled !== "boolean") fail("guard setting must be true or false.");
  const guardDrawdown = request.guard_enabled ? finite(request.guard_drawdown_pct, "guard drawdown") : null;
  if (guardDrawdown !== null && (guardDrawdown <= 0 || guardDrawdown > 90)) fail("guard drawdown is out of range.");

  const b = validateResponse(baseline, "baseline", startingCash);
  const s = validateResponse(shock, "shocked", startingCash);
  const matchesRequest = (actual, expected) => isObject(actual) &&
    Object.keys(actual).length === REQUEST_FIELDS.length &&
    REQUEST_FIELDS.every((key) => Object.prototype.hasOwnProperty.call(actual, key) && actual[key] === expected[key]);
  if (!matchesRequest(request, request) || !matchesRequest(shock.request, request) ||
      !matchesRequest(baseline.request, { ...request, shock_pct: 0 })) {
    fail("effective requests do not match the completed experiment.");
  }
  if (baseline.strategy_key !== strategyKey || shock.strategy_key !== strategyKey) fail("strategy metadata differs between runs.");
  const sortedParams = (params) => JSON.stringify(Object.entries(params).sort(([a], [b]) => a.localeCompare(b)));
  if (sortedParams(baseline.strategy_parameters) !== sortedParams(shock.strategy_parameters) ||
      baseline.signal_cash_fraction !== shock.signal_cash_fraction) fail("strategy settings differ between runs.");
  if (b.count !== s.count) fail("baseline and shocked candle counts differ.");
  if (baseline.scenario.seed !== shock.scenario.seed) fail("baseline and shocked seeds differ.");
  if (shock.scenario.seed !== seed) fail("request seed does not match the run.");
  if (!isObject(shock.scenario) || shock.scenario.candle_count !== s.count) fail("candle count mismatch.");
  if (request.num_candles !== undefined && request.num_candles !== s.count) fail("request candle count does not match the run.");
  if (baseline.scenario.shock_index !== null && baseline.scenario.shock_index !== undefined) {
    fail("baseline must not contain a shock.");
  }
  if (baseline.scenario.shock_pct !== 0 || shock.scenario.shock_pct !== requestedShock) fail("shock metadata does not match the request.");
  if (baseline.scenario.symbol !== shock.scenario.symbol || baseline.scenario.timeframe !== shock.scenario.timeframe) {
    fail("market metadata differs between runs.");
  }
  if (baseline.engine_version !== shock.engine_version) fail("engine versions differ between runs.");
  if (Boolean(b.guarded) !== request.guard_enabled || Boolean(s.guarded) !== request.guard_enabled) {
    fail("guarded results do not match the requested guard setting.");
  }

  const shockIndex = shock.scenario.shock_index === undefined ? null : shock.scenario.shock_index;
  const shockPct = shock.scenario.shock_pct;
  const hasShock = shockIndex !== null;
  const expectedShockIndex = request.shock_index == null ? Math.max(1, Math.floor(s.count * 2 / 3)) : request.shock_index;
  if ((requestedShock > 0 && shockIndex !== expectedShockIndex) || (requestedShock === 0 && hasShock)) {
    fail("shock location does not match the request.");
  }
  const guardedRun = s.guarded ? shock.guarded : null;
  const count = s.count;
  const scenarioLabel = hasShock ? "Shocked" : "Scenario (no shock)";

  const series = [
    { name: "Baseline, unguarded", cls: "s-base", values: b.unguarded },
    { name: `${scenarioLabel}, unguarded`, cls: "s-shock", values: s.unguarded },
  ];
  if (guardedRun) series.push({ name: `${scenarioLabel}, guarded`, cls: "s-guard", values: s.guarded });
  series.push({ name: `${scenarioLabel} buy-and-hold`, cls: "s-benchmark", values: s.benchmark });
  const chart = buildChart(series, count, hasShock ? shockIndex : null);

  const swatch = (cls) => `<svg viewBox="0 0 30 8" aria-hidden="true"><line x1="1" y1="4" x2="29" y2="4" class="${cls}"/></svg>`;
  const legend = series.map((x) => `<span>${swatch(x.cls)}${esc(x.name)}</span>`).join("");

  const metric = (label, value, sub) => `<div class="m"><span>${esc(label)}</span><b>${esc(value)}</b><small>${esc(sub)}</small></div>`;
  const metrics = [
    metric("Baseline return", formatPercent(baseline.unguarded.total_return_pct, true), "Same seed, no shock, unguarded"),
    metric(`${scenarioLabel} return`, formatPercent(shock.unguarded.total_return_pct, true), hasShock ? "Unguarded bot after shock" : "No shock in this run"),
    guardedRun
      ? metric(`${scenarioLabel} + guard return`, formatPercent(guardedRun.total_return_pct, true), hasShock ? "Guarded bot after shock" : "Guarded bot, no shock")
      : metric(`${scenarioLabel} + guard return`, "No guard", "Guard was not enabled"),
    metric(`${scenarioLabel} buy-and-hold`, formatPercent(shock.benchmark.total_return_pct, true), "All cash invested; not risk-matched"),
    metric("Max close drawdown, unguarded", formatPercent(shock.unguarded.max_drawdown_pct), hasShock ? "Shocked scenario" : "No shock"),
    guardedRun
      ? metric("Max close drawdown, guarded", formatPercent(guardedRun.max_drawdown_pct), hasShock ? "Shocked scenario" : "No shock")
      : metric("Max close drawdown, guarded", "No guard", "Guard was not enabled"),
  ].join("");

  let triggerText = "No guard";
  if (guardedRun) {
    const t = guardedRun.guard_trigger_index;
    triggerText = t === null || t === undefined ? "No trigger" : `Candle ${t + 1}`;
  }
  const strategyLabel = Object.prototype.hasOwnProperty.call(STRATEGY_LABELS, strategyKey)
    ? STRATEGY_LABELS[strategyKey]
    : strategyKey;

  const params = [
    ["Strategy", strategyLabel],
    ["Strategy parameters", Object.entries(shock.strategy_parameters).map(([key, value]) => `${key}: ${value}`).join(" · ")],
    ["Buy signal size", `${fmt(shock.signal_cash_fraction * 100, 2)}% of available cash`],
    ["Seed", String(seed)],
    ["Candles", String(count)],
    ["Starting cash", money(startingCash)],
    ["Starting price", money(startPrice)],
    ["Shock", hasShock ? `${fmt(shockPct, 2)}% at candle ${shockIndex + 1}` : "No shock"],
    ["Fee per fill", `${fmt(feeBps, 2)} bps`],
    ["Slippage per fill", `${fmt(slipBps, 2)} bps`],
    ["Buy cap", `${fmt(cap, 2)}% of post-cost equity at execution`],
    ["Guard", guardedRun ? `Pause buys at ${fmt(guardDrawdown, 2)}% drawdown at close` : "No guard"],
    ["Guard trigger", triggerText],
    ["Engine version", shock.engine_version],
  ].map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("");

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>AXIOM Survival Lab experiment brief (synthetic)</title>
<style>${CSS}</style>
</head>
<body>
<main class="page">
<header>
<div><div class="eyebrow">AXIOM · Survival Lab · Investor demo brief</div><h1>Synthetic stress-test result</h1></div>
<div class="badge">Synthetic data · Not a forecast</div>
</header>
<section class="notice" aria-label="Important disclosures">
<strong>All figures come from simulated, synthetic market data. They are not forecasts and not evidence of real trading.</strong>
<ul>
<li>Buy-and-hold invests all cash and is not risk-matched to the position-capped bot.</li>
<li>Drawdown uses closes and can miss intrabar losses. The guard only pauses new buys; it cannot guarantee a loss limit.</li>
<li>Final open positions are marked to market without future exit costs.</li>
<li>The fingerprint and engine version are not source hashes or independent proof.</li>
</ul>
</section>
<div class="grid2">
<section class="panel" aria-label="Equity chart">
<h2>Equity, simulated USD</h2>
${chart}
<div class="legend">${legend}</div>
</section>
<section class="panel" aria-label="Run parameters">
<h2>Run parameters</h2>
<dl>${params}</dl>
</section>
</div>
<section style="margin-top:10px" aria-label="Results">
<h2>Final simulated results</h2>
<div class="metrics" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr))">${metrics}</div>
</section>
<section class="fp" aria-label="Fingerprint">
<h2>Run fingerprints (not source hashes or independent proof)</h2>
<div>Baseline <code>${esc(baseline.fingerprint)}</code></div>
<div>Scenario <code>${esc(shock.fingerprint)}</code></div>
</section>
<footer>Generated from one completed Survival Lab run only. Synthetic Worlds and Shock Landscape results are excluded. To save a PDF, use your browser's Print command.</footer>
</main>
</body>
</html>
`;
  return html;
}
