import { useEffect, useMemo, useRef, useState } from "react";
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { authHeaders } from "../auth.js";
import { buildExperimentBrief } from "../experimentBrief.js";
import { formatPercent } from "../percentFormatting.js";
import { parseSeedInput } from "../seedInput.js";
import LabRobot from "../components/LabRobot.jsx";
import DecisionComparison from "../components/DecisionComparison.jsx";
import EvidenceTrail from "../components/EvidenceTrail.jsx";
import SyntheticWorlds from "../components/SyntheticWorlds.jsx";
import ShockLandscape from "../components/ShockLandscape.jsx";
import PassportReplay from "../components/PassportReplay.jsx";
import WarRoom from "../components/WarRoom.jsx";
import "./SurvivalLab.css";

const STRATEGIES = [
  { key: "simple_ma", callsign: "VECTOR", label: "Moving average", number: "01", description: "Follows moving-average crossovers.", color: "#c8f37b" },
  { key: "rsi", callsign: "PULSE", label: "RSI", number: "02", description: "Responds to relative strength thresholds.", color: "#7bded6" },
  { key: "momentum", callsign: "MOMENTUM", label: "Momentum", number: "03", description: "Responds to price momentum and a stop-loss rule.", color: "#f2ba8c" },
];

const INITIAL_INPUTS = {
  strategy_key: "rsi",
  seed: 42,
  num_candles: 160,
  start_price: 100,
  starting_cash: 10000,
  fee_bps: 10,
  slippage_bps: 5,
  shock_pct: 12,
  shock_index: 90,
  guard_enabled: true,
  guard_drawdown_pct: 3,
  max_position_pct: 30,
};

const money = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "—";
};
const pct = (value) => formatPercent(value, true);
const drawdown = (value) => typeof value === "number" ? formatPercent(-Math.abs(value)) : "—";
const number = (value, digits = 3) => {
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString("en-US", { maximumFractionDigits: digits }) : "—";
};

const axisCurrency = new Intl.NumberFormat("en-US", {
  style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2,
});

function equityAxis(points) {
  const values = points.flatMap((point) => [point.baseline, point.shock, point.guarded, point.benchmark])
    .filter((value) => typeof value === "number" && Number.isFinite(value));
  if (!values.length) return { domain: [0, 1], ticks: [0, 0.25, 0.5, 0.75, 1] };

  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const rawStep = Math.max((maximum - minimum) / 4, 0.01);
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const step = ([1, 2, 5, 10].find((factor) => factor * magnitude >= rawStep) ?? 10) * magnitude;
  let first = Math.floor(minimum / step);
  let last = Math.ceil(maximum / step);
  if (first === last) { first -= 1; last += 1; }
  const ticks = Array.from({ length: last - first + 1 }, (_, index) =>
    Number(((first + index) * step).toFixed(2)),
  );
  return { domain: [ticks[0], ticks[ticks.length - 1]], ticks };
}

function eventName(event) {
  if (event.event_type === "fill") return `${event.action} filled`;
  if (event.event_type === "guard") return "Buy guard";
  if (event.event_type === "expired") return "Order expired";
  if (event.event_type === "blocked") return "Buy blocked";
  if (event.event_type === "rejected") return "Order rejected";
  if (event.event_type === "signal") return `${event.action} signal`;
  return event.event_type;
}

function apiError(data) {
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((entry) => entry.msg ?? "Invalid input").join("; ");
  return "The simulation could not be run. Check that the backend is running.";
}

async function runLab(payload, signal) {
  const response = await fetch("/arena/lab/paired", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
    signal,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(apiError(data));
  const validRun = (run) => run && typeof run.fingerprint === "string" && run.scenario &&
    Array.isArray(run.candles) && run.candles.length > 0 && Array.isArray(run.assumptions) &&
    [run.unguarded, run.benchmark, ...(run.guarded ? [run.guarded] : [])].every((path) =>
      path && Array.isArray(path.equity_curve) && Array.isArray(path.events),
    );
  if (!validRun(data?.baseline) || !validRun(data?.shock)) throw new Error("The engine returned an incomplete result. Previous results are still shown.");
  return data;
}

function Slider({ id, label, value, min, max, step = 1, suffix, description, onChange }) {
  const spokenUnit = suffix === "%" ? "percent" : suffix === " bps" ? "basis points" : (suffix ?? "").trim();
  return (
    <div className="lab-slider">
      <div className="lab-control-label"><label htmlFor={id}>{label}</label><output htmlFor={id}>{value}{suffix}</output></div>
      <input id={id} type="range" min={min} max={max} step={step} value={value} aria-valuetext={`${value}${spokenUnit ? ` ${spokenUnit}` : ""}`} aria-describedby={`${id}-help`} onChange={(event) => onChange(Number(event.target.value))} />
      <p id={`${id}-help`}>{description}</p>
    </div>
  );
}

function Legend({ guarded }) {
  return (
    <div className="lab-chart-legend" role="group" aria-label="Chart legend">
      <span><i className="lab-key baseline" /> Baseline bot · no guard</span>
      <span><i className="lab-key shock" /> Scenario bot</span>
      {guarded && <span><i className="lab-key guarded" /> Scenario + guard</span>}
      <span><i className="lab-key benchmark" /> Scenario buy &amp; hold</span>
    </div>
  );
}

function LabTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="lab-tooltip">
      <strong>CANDLE {Number(label) + 1}</strong>
      {payload.map((entry) => <p key={entry.dataKey}><span style={{ color: entry.color }}>{entry.name}</span><b>{money(entry.value)}</b></p>)}
    </div>
  );
}

function ResultMetric({ label, value, sub, tone }) {
  return <div className="lab-metric"><span>{label}</span><strong className={tone ?? ""}>{value}</strong><small>{sub}</small></div>;
}

export default function SurvivalLab() {
  const [inputs, setInputs] = useState(INITIAL_INPUTS);
  const [applied, setApplied] = useState(null);
  const [results, setResults] = useState(null);
  const [running, setRunning] = useState(false);
  const [worldsRunning, setWorldsRunning] = useState(false);
  const [landscapeRunning, setLandscapeRunning] = useState(false);
  const [passportRunning, setPassportRunning] = useState(false);
  const [warRoomRunning, setWarRoomRunning] = useState(false);
  const [passportComparison, setPassportComparison] = useState(null);
  const [briefError, setBriefError] = useState("");
  const [error, setError] = useState("");
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [replayMode, setReplayMode] = useState("shock");
  const [replayGuarded, setReplayGuarded] = useState(true);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [navigationTarget, setNavigationTarget] = useState(null);
  const [loadedNotice, setLoadedNotice] = useState(null);
  const [pendingWorld, setPendingWorld] = useState(null);
  const [worldComparison, setWorldComparison] = useState(null);
  const passportAbortRef = useRef(null);
  const recorderRef = useRef(null);
  const seedInputRef = useRef(null);

  useEffect(() => () => passportAbortRef.current?.abort(), []);

  const seedValidation = parseSeedInput(inputs.seed);
  useEffect(() => {
    seedInputRef.current?.setCustomValidity(seedValidation.error);
  }, [seedValidation.error]);

  const dirty = Boolean(applied && JSON.stringify(inputs) !== JSON.stringify(applied));
  const selectedStrategy = STRATEGIES.find((strategy) => strategy.key === inputs.strategy_key) ?? STRATEGIES[0];
  const displayedStrategy = STRATEGIES.find((strategy) => strategy.key === applied?.strategy_key) ?? selectedStrategy;
  const lastIndex = Math.max(0, (results?.shock?.candles?.length ?? 1) - 1);

  useEffect(() => {
    if (!playing || !results) return undefined;
    const timer = window.setInterval(() => setCursor((current) => Math.min(current + 1, lastIndex)), 110);
    return () => window.clearInterval(timer);
  }, [playing, lastIndex, results]);

  useEffect(() => {
    if (playing && cursor >= lastIndex) setPlaying(false);
  }, [playing, cursor, lastIndex]);

  useEffect(() => { setSelectedEvent(null); setNavigationTarget(null); }, [results]);
  useEffect(() => { setBriefError(""); }, [results]);

  const timeline = useMemo(() => {
    if (!results) return [];
    const { baseline, shock } = results;
    return shock.candles.map((candle, index) => ({
      index,
      price: candle.close,
      baseline: baseline.unguarded.equity_curve[index]?.equity,
      shock: shock.unguarded.equity_curve[index]?.equity,
      guarded: shock.guarded?.equity_curve[index]?.equity,
      benchmark: shock.benchmark.equity_curve[index]?.equity,
    }));
  }, [results]);

  const displayedRun = results ? (replayMode === "baseline" ? results.baseline : results.shock) : null;
  const displayedPath = replayGuarded && displayedRun?.guarded ? displayedRun.guarded : displayedRun?.unguarded;
  const displayedPoint = displayedPath?.equity_curve?.[cursor];
  const currentCandle = displayedRun?.candles[cursor];
  const currentEvents = displayedPath?.events.filter((event) => event.candle_index === cursor) ?? [];
  const currentSignal = currentEvents.find((event) => event.event_type === "signal");
  const robotAction = currentSignal?.action ?? "READY";
  const detailEvent = currentEvents.includes(selectedEvent) ? selectedEvent : currentEvents.find((event) => event.event_type === "signal") ?? currentEvents[0];
  const shockRun = results?.shock;
  const guarded = shockRun?.guarded;
  const shockIndex = shockRun?.scenario.shock_index;
  const hasShock = shockRun?.scenario.shock_pct > 0 && Number.isInteger(shockIndex) && shockIndex >= 0 && shockIndex < shockRun.candles.length;
  const configuredShockIndex = inputs.shock_index ?? Math.max(1, Math.floor(inputs.num_candles * 2 / 3));
  const controlId = "survival-lab";
  const chartData = useMemo(() => timeline.slice(0, cursor + 1), [timeline, cursor]);
  const chartAxis = useMemo(() => equityAxis(chartData), [chartData]);
  const chartPoint = timeline[cursor];
  const navigationNotice = navigationTarget && replayMode === "shock" && replayGuarded === navigationTarget.guarded &&
    cursor === navigationTarget.candleIndex && (!navigationTarget.event || detailEvent === navigationTarget.event)
    ? `Opened ${navigationTarget.label} at candle ${cursor + 1} in the tested ${navigationTarget.guarded ? "guarded" : "unguarded"} path.` : "";

  function updateInput(key, value) {
    setLoadedNotice(null);
    setPendingWorld(null);
    setInputs((current) => ({ ...current, [key]: value }));
  }

  function focusSeed() {
    const input = document.getElementById(`${controlId}-seed`);
    input?.focus({ preventScroll: true });
    input?.scrollIntoView({ block: "center" });
  }

  function loadWorldSeed(seed, fingerprint) {
    setInputs({ ...applied, seed });
    setPendingWorld({ seed, fingerprint });
    setWorldComparison(null);
    setLoadedNotice(`Seed ${seed} and the experiment settings are loaded. Run the experiment to compare its fingerprint.`);
    focusSeed();
  }

  function loadLandscapeCell(request) {
    setInputs({ ...request });
    setPendingWorld(null);
    setLoadedNotice(`Shock ${request.shock_pct}% and fee ${request.fee_bps} bps are loaded. Run the experiment to replay.`);
    focusSeed();
  }

  async function handleRun(event) {
    event.preventDefault();
    const parsedSeed = parseSeedInput(inputs.seed);
    if (parsedSeed.error) {
      seedInputRef.current?.setCustomValidity(parsedSeed.error);
      seedInputRef.current?.reportValidity();
      return;
    }
    setRunning(true);
    setError("");
    setWorldComparison(null);
    setPassportComparison(null);
    setPlaying(false);
    const payload = { ...inputs, seed: parsedSeed.value };
    try {
      const { baseline, shock } = await runLab(payload);
      setResults({ baseline, shock });
      setApplied({ ...payload });
      setLoadedNotice(null);
      setWorldComparison(pendingWorld ? {
        seed: pendingWorld.seed, recorded: pendingWorld.fingerprint, calculated: shock.fingerprint,
      } : null);
      setPendingWorld(null);
      setPassportComparison(null);
      setCursor(Math.max(0, shock.candles.length - 1));
      setReplayMode("shock");
      setReplayGuarded(Boolean(shock.guarded));
    } catch (err) {
      setError(err.message || "The simulation could not be run.");
    } finally {
      setRunning(false);
    }
  }

  async function replayPassport(passport) {
    if (running || worldsRunning || landscapeRunning || passportRunning || warRoomRunning || passportAbortRef.current) return;
    const controller = new AbortController();
    passportAbortRef.current = controller;
    setPassportRunning(true);
    setWorldComparison(null);
    setPassportComparison(null);
    setPlaying(false);
    try {
      const { baseline, shock } = await runLab(passport.request, controller.signal);
      if (controller.signal.aborted || passportAbortRef.current !== controller) return;
      setInputs({ ...passport.request });
      setApplied({ ...passport.request });
      setResults({ baseline, shock });
      setCursor(Math.max(0, shock.candles.length - 1));
      setReplayMode("shock");
      setReplayGuarded(Boolean(shock.guarded));
      setLoadedNotice(null);
      setPendingWorld(null);
      setWorldComparison(null);
      setError("");
      setPassportComparison({
        baseline: { recorded: passport.baselineFingerprint, calculated: baseline.fingerprint },
        shock: { recorded: passport.shockedFingerprint, calculated: shock.fingerprint },
      });
    } finally {
      if (passportAbortRef.current === controller) passportAbortRef.current = null;
      if (!controller.signal.aborted) setPassportRunning(false);
    }
  }

  function toggleReplay() {
    if (playing) {
      setPlaying(false);
      return;
    }
    if (cursor >= lastIndex) setCursor(0);
    setPlaying(true);
  }

  function jumpToShock() {
    if (!hasShock) return;
    setPlaying(false);
    setReplayMode("shock");
    setCursor(shockIndex);
  }

  function navigateEvidence(moment) {
    const guardedPath = moment.path === "guarded" ? true : moment.path === "unguarded" ? false : Boolean(shockRun.guarded);
    setPlaying(false);
    setReplayMode("shock");
    setReplayGuarded(guardedPath);
    setCursor(moment.candleIndex);
    setSelectedEvent(moment.event);
    setNavigationTarget({ ...moment, guarded: guardedPath });
    recorderRef.current?.focus({ preventScroll: true });
    recorderRef.current?.scrollIntoView({ block: "center" });
  }

  function downloadPassport() {
    if (!results || !applied) return;
    const passport = {
      format: "axiom-survival-lab-v1",
      description: "Synthetic simulation. Not a prediction or independent audit. Engine version is a manually maintained label, not a source hash or proof of execution.",
      request: applied,
      baseline: results.baseline,
      shocked: results.shock,
    };
    const blob = new Blob([JSON.stringify(passport, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = window.document.createElement("a");
    link.href = url;
    link.download = `axiom-lab-${applied.strategy_key}-${String(results.shock.fingerprint).slice(0, 12)}.json`;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function downloadBriefing() {
    if (!results || !applied) return;
    setBriefError("");
    let url;
    try {
      const html = buildExperimentBrief({ request: applied, baseline: results.baseline, shock: results.shock });
      if (typeof html !== "string") throw new Error("The briefing could not be generated.");
      url = URL.createObjectURL(new Blob([html], { type: "text/html;charset=utf-8" }));
      const link = window.document.createElement("a");
      link.href = url;
      link.download = `axiom-briefing-${applied.strategy_key}-${String(results.shock.fingerprint).slice(0, 12)}.html`;
      link.click();
    } catch (err) {
      setBriefError(err.message || "The briefing could not be generated.");
    } finally {
      if (url) window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
  }

  return (
    <div className="lab-page">
      <div className="lab-topline">
        <span><i /> AXIOM / EXPERIMENT 01</span>
        <span>SYNTHETIC MARKET · NO REAL ORDERS</span>
      </div>
      <header className="lab-hero">
        <div>
          <p className="lab-eyebrow"><span /> AN OPEN QUESTION, NOT A PROMISE</p>
          <h1>What is your strategy<br /><em>really made of?</em></h1>
          <p>Run a controlled market simulation. Add friction, introduce a shock, and follow every decision—one candle at a time.</p>
          <div className="lab-hero-meta"><span><b>01</b> SELECT A STRATEGY</span><span><b>02</b> SET CONDITIONS</span><span><b>03</b> EXAMINE THE EVIDENCE</span></div>
        </div>
        <div className="lab-hero-visual" aria-hidden="true">
          <div className="lab-orb lab-orb-outer" />
          <div className="lab-orb lab-orb-inner" />
          <LabRobot strategy={inputs.strategy_key} action={results && applied?.strategy_key === inputs.strategy_key ? robotAction : "READY"} selected />
          <span className="lab-hero-coordinate top">AX / 01</span>
          <span className="lab-hero-coordinate bottom">RULE-BASED STRATEGIES</span>
        </div>
      </header>

      <PassportReplay disabled={running || worldsRunning || landscapeRunning || passportRunning || warRoomRunning} replaying={passportRunning} comparison={passportComparison} onClearComparison={() => setPassportComparison(null)} onReplay={replayPassport} />

      <div className="lab-war-room-teaser">
        <div><span>NEW / AXIOM WAR ROOM</span><strong>Three perspectives. One strategy on trial.</strong><p>Run an experiment to open an evidence-linked review with the Challenger, Defender and Auditor.</p></div>
        <a href={results ? "#war-room" : "#lab-control-room"}>{results ? "Enter the War Room" : "Set up the case"} <span aria-hidden="true">↗</span></a>
      </div>

      <div className="lab-section-title" id="lab-control-room"><div><span>THE CONTROL ROOM</span><h2>Design your experiment</h2></div><p>One strategy. Two scenarios. The same synthetic market.</p></div>

      <div className="lab-layout">
        <form className="lab-controls" onSubmit={handleRun}>
          <div className="lab-panel-heading"><div><span>01 / STRATEGY</span><h3>Choose your bot</h3></div><span className="lab-panel-code">3 AVAILABLE</span></div>
          <div className="lab-picks" role="group" aria-label="Choose strategy">
            {STRATEGIES.map((strategy) => (
              <button type="button" key={strategy.key} className={`lab-pick ${inputs.strategy_key === strategy.key ? "is-selected" : ""}`} aria-pressed={inputs.strategy_key === strategy.key} onClick={() => updateInput("strategy_key", strategy.key)} disabled={running || passportRunning || warRoomRunning}>
                <span className="lab-pick-icon"><LabRobot strategy={strategy.key} /></span>
                <span className="lab-pick-copy"><strong>{strategy.callsign}</strong><small>{strategy.label}</small></span>
                <span className="lab-pick-number">{strategy.number}</span>
              </button>
            ))}
          </div>
          <p className="lab-strategy-description">{selectedStrategy.description}</p>

          <div className="lab-control-divider" />
          <div className="lab-panel-heading"><div><span>02 / CONDITIONS</span><h3>Change the environment</h3></div></div>
          <fieldset disabled={running || passportRunning || warRoomRunning} className="lab-fieldset">
            <Slider id={`${controlId}-shock`} label="Price shock" value={inputs.shock_pct} min={0} max={30} suffix="%" description={inputs.shock_pct === 0 ? "No shock will be injected." : `A hypothetical downward shock at candle ${configuredShockIndex + 1}.`} onChange={(value) => updateInput("shock_pct", value)} />
            <Slider id={`${controlId}-fee`} label="Trading fee" value={inputs.fee_bps} min={0} max={50} suffix=" bps" description="Applied to each simulated fill." onChange={(value) => updateInput("fee_bps", value)} />
            <Slider id={`${controlId}-slippage`} label="Slippage" value={inputs.slippage_bps} min={0} max={30} suffix=" bps" description="An assumed adverse price adjustment." onChange={(value) => updateInput("slippage_bps", value)} />
            <div className="lab-seed-row">
              <div>
                <label htmlFor={`${controlId}-seed`}>Market seed</label>
                <small id={`${controlId}-seed-help`} aria-live="polite">{loadedNotice ?? "The same seed reproduces the random factors; changing the shock changes the price path. Enter a whole number from 0 to 4,294,967,295."}</small>
                {seedValidation.error && <small id={`${controlId}-seed-error`} className="lab-seed-error" role="alert">{seedValidation.error}</small>}
              </div>
              <input ref={seedInputRef} id={`${controlId}-seed`} type="text" inputMode="numeric" pattern="[0-9]+" required aria-invalid={seedValidation.error ? true : undefined} aria-describedby={`${controlId}-seed-help${seedValidation.error ? ` ${controlId}-seed-error` : ""}`} value={inputs.seed} onChange={(event) => {
                const parsed = parseSeedInput(event.target.value);
                event.target.setCustomValidity(parsed.error);
                updateInput("seed", parsed.value);
              }} />
            </div>
            <div className="lab-guard">
              <div className="lab-guard-top"><div><strong>Drawdown guard</strong><small>Pause new buys after a threshold.</small></div><label className="lab-switch"><input type="checkbox" checked={inputs.guard_enabled} onChange={(event) => updateInput("guard_enabled", event.target.checked)} aria-label="Enable drawdown guard" /><span /></label></div>
              {inputs.guard_enabled && <Slider id={`${controlId}-guard`} label="Pause buys at drawdown" value={inputs.guard_drawdown_pct} min={2} max={20} suffix="%" description="Checked at candle closes. The guard does not force a sell or guarantee a loss limit." onChange={(value) => updateInput("guard_drawdown_pct", value)} />}
            </div>
          </fieldset>

          <button className="lab-run" type="submit" disabled={running || worldsRunning || landscapeRunning || passportRunning || warRoomRunning}>
            <span>{running ? "Running experiment…" : worldsRunning || landscapeRunning || passportRunning || warRoomRunning ? "Waiting for calculation…" : results ? "Run experiment again" : "Run the experiment"}</span><span aria-hidden="true">↗</span>
          </button>
          <p className="lab-control-foot">SIMULATION ONLY · RESULTS ARE NOT PREDICTIONS</p>
          {error && <p className="lab-error" role="alert">{error}</p>}
        </form>

        <div className="lab-stage">
          <div className="lab-stage-header">
            <div><span>03 / THE EVIDENCE</span><h3>Market replay</h3></div>
            <span className="lab-status" role="status"><i /> {running || passportRunning ? "CALCULATING" : results ? "SIMULATION COMPLETE" : "AWAITING EXPERIMENT"}</span>
          </div>
          {dirty && <div className="lab-stale" role="status">Settings changed. You’re viewing the previous run until you run the experiment again.</div>}
          {results && <a className="lab-war-room-link" href="#war-room">Open the War Room <span aria-hidden="true">↗</span></a>}
          {worldComparison && <div className={`lab-world-comparison ${worldComparison.recorded === worldComparison.calculated ? "is-match" : "is-mismatch"}`} role="status">
            <strong>WORLD {worldComparison.seed} / REPLAY {worldComparison.recorded === worldComparison.calculated ? "MATCHED" : "DIFFERED"}</strong>
            <p>The recorded and rerun fingerprints {worldComparison.recorded === worldComparison.calculated ? "match" : "do not match"}. This is not independent verification or proof of execution.</p>
            <details><summary>View both fingerprints</summary><dl><div><dt>Recorded</dt><dd><code>{worldComparison.recorded}</code></dd></div><div><dt>Rerun</dt><dd><code>{worldComparison.calculated}</code></dd></div></dl></details>
          </div>}

          {!results ? (
            <div className="lab-empty">
              <div className="lab-empty-radar"><span /><span /><span /><LabRobot strategy={inputs.strategy_key} selected /></div>
              <p className="lab-empty-code">EXPERIMENT / READY</p>
              <h4>The market is yours to challenge.</h4>
              <p>Select a bot and run the experiment to reveal its decisions, simulated performance, and comparison.</p>
              <div><span>●</span> DETERMINISTIC SYNTHETIC DATA <span>●</span> SAME-MARKET BENCHMARK</div>
            </div>
          ) : (
            <>
              <div className="lab-stage-overview">
                <div className="lab-stage-bot">
                  <div className="lab-stage-avatar"><LabRobot strategy={displayedStrategy.key} action={robotAction} selected /></div>
                  <div><span>STRATEGY IN REVIEW</span><strong>{displayedStrategy.callsign}</strong><small>{displayedStrategy.label} · rule-based</small></div>
                </div>
                <div className="lab-stage-now"><span>RECORDED SIGNAL</span><strong className={`signal-${robotAction.toLowerCase()}`}>{robotAction}</strong><small>{currentSignal ? `Candle ${cursor + 1} of ${displayedRun.candles.length}` : "No signal at this candle"}</small></div>
              </div>

              <div className="lab-chart-head"><div><span>EQUITY / SIMULATED USD</span><h4>One market. Different outcomes.</h4></div><span className="lab-chart-timestamp">{cursor + 1} / {shockRun.candles.length} CANDLES</span></div>
              {dirty && <p className="lab-stale lab-chart-stale">Chart and results show the completed {displayedStrategy.label} run: seed {applied.seed}, {applied.shock_pct === 0 ? "no injected shock" : `${applied.shock_pct}% shock`}, {applied.fee_bps} bps fee. Run again to apply the changed controls.</p>}
              <Legend guarded={Boolean(guarded)} />
              <div className="lab-chart" role="img" aria-label="Simulated equity curves for the unguarded baseline, scenario, buy-and-hold, and optional guard. Use the replay slider and the current candle values below to inspect each point.">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 15, right: 8, left: 4, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="#ffffff" strokeOpacity={0.06} strokeDasharray="3 7" />
                    <XAxis dataKey="index" tickFormatter={(value) => value + 1} stroke="#647d6b" tick={{ fill: "#82958a", fontSize: 10 }} tickLine={false} axisLine={false} minTickGap={30} />
                    <YAxis domain={chartAxis.domain} ticks={chartAxis.ticks} interval={0} tickFormatter={(value) => axisCurrency.format(value)} stroke="#647d6b" tick={{ fill: "#82958a", fontSize: 10 }} tickLine={false} axisLine={false} width={86} />
                    <Tooltip content={<LabTooltip />} />
                    {cursor >= shockRun.scenario.shock_index && applied.shock_pct > 0 && <ReferenceLine x={shockRun.scenario.shock_index} stroke="#f2ba8c" strokeOpacity={0.7} strokeDasharray="3 5" label={{ value: "SHOCK", fill: "#f2ba8c", fontSize: 9, position: "insideTopRight" }} />}
                    <Line type="linear" dataKey="baseline" name="Baseline bot · no guard" stroke="#c7d7bd" strokeWidth={1.7} dot={false} isAnimationActive={false} />
                    <Line type="linear" dataKey="shock" name="Scenario bot" stroke="#f28f87" strokeWidth={2} strokeDasharray="8 3" dot={false} isAnimationActive={false} />
                    {guarded && <Line type="linear" dataKey="guarded" name="Scenario + guard" stroke="#c8f37b" strokeWidth={2.5} strokeDasharray="2 4" strokeLinecap="round" dot={false} isAnimationActive={false} />}
                    <Line type="linear" dataKey="benchmark" name="Scenario buy & hold" stroke="#7bded6" strokeWidth={1.6} strokeDasharray="8 3 2 3" dot={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="lab-playback">
                <button type="button" className="lab-play" onClick={toggleReplay} aria-label={playing ? "Pause replay" : "Play replay"}>{playing ? "Ⅱ" : "▶"}</button>
                <div className="lab-timeline-control"><label htmlFor={`${controlId}-timeline`}>Replay candle {cursor + 1} of {lastIndex + 1}</label><input id={`${controlId}-timeline`} type="range" min="0" max={lastIndex} value={cursor} aria-valuetext={`Candle ${cursor + 1} of ${lastIndex + 1}`} onChange={(event) => { setPlaying(false); setCursor(Number(event.target.value)); }} /></div>
                <div className="lab-replay-switch" role="group" aria-label="Scenario for decision recorder"><button type="button" className={replayMode === "baseline" ? "is-active" : ""} aria-pressed={replayMode === "baseline"} onClick={() => setReplayMode("baseline")}>BASE</button><button type="button" className={replayMode === "shock" ? "is-active" : ""} aria-pressed={replayMode === "shock"} onClick={() => setReplayMode("shock")}>TEST</button></div>
                {guarded && <div className="lab-replay-switch" role="group" aria-label="Strategy path for decision recorder"><button type="button" className={!replayGuarded ? "is-active" : ""} aria-pressed={!replayGuarded} onClick={() => setReplayGuarded(false)}>BOT</button><button type="button" className={replayGuarded ? "is-active" : ""} aria-pressed={replayGuarded} onClick={() => setReplayGuarded(true)}>GUARD</button></div>}
              </div>
              <div className="lab-shock-navigation">
                <button type="button" onClick={jumpToShock} disabled={!hasShock} aria-describedby={`${controlId}-shock-jump-help`}><span aria-hidden="true">↗</span> Jump to shock {hasShock && <strong>CANDLE {shockIndex + 1}</strong>}</button>
                <p id={`${controlId}-shock-jump-help`}>{hasShock ? `Pauses at candle ${shockIndex + 1} in the tested scenario.` : "This completed run has no injected shock."}</p>
              </div>
              <div className="lab-candle-values" role="group" aria-label={`Simulated equity at replay candle ${cursor + 1}`}>
                <span>CURRENT CANDLE / {cursor + 1}</span>
                <dl><div><dt>Baseline bot · no guard</dt><dd>{money(chartPoint?.baseline)}</dd></div><div><dt>Scenario bot</dt><dd>{money(chartPoint?.shock)}</dd></div>{guarded && <div><dt>Scenario + guard</dt><dd>{money(chartPoint?.guarded)}</dd></div>}<div><dt>Scenario buy &amp; hold</dt><dd>{money(chartPoint?.benchmark)}</dd></div></dl>
              </div>
              <p className="lab-chart-note">Curves reveal as you replay. Buy &amp; hold uses all starting cash; bot buys are capped at {applied.max_position_pct}% of equity at execution, so they are not risk-matched. Drawdown and the guard use candle closes and can miss intrabar losses. The guard pauses new buys and does not guarantee protection.</p>

              <div className="lab-metrics-heading">FINAL RESULTS / END OF {dirty ? "PREVIOUS " : ""}RUN <span>Replay candle: {cursor + 1}</span></div>
              <div className="lab-metrics">
                <ResultMetric label="BASELINE BOT RETURN" value={pct(results.baseline.unguarded.total_return_pct)} sub="Same seed, no shock or guard" />
                <ResultMetric label="SCENARIO BOT RETURN" value={pct(shockRun.unguarded.total_return_pct)} sub="Without the drawdown guard" />
                <ResultMetric label={guarded ? "SCENARIO + GUARD" : "BUY & HOLD RETURN"} value={pct((guarded ?? shockRun.benchmark).total_return_pct)} sub={guarded ? guarded.guard_trigger_index == null ? "Guard did not trigger" : `Guard triggered at candle ${guarded.guard_trigger_index + 1}` : "Same scenario"} tone="is-accent" />
                <ResultMetric label="BOT MAX CLOSE DRAWDOWN" value={drawdown(shockRun.unguarded.max_drawdown_pct)} sub="Scenario bot · no guard" />
                {guarded && <ResultMetric label="GUARDED MAX CLOSE DRAWDOWN" value={drawdown(guarded.max_drawdown_pct)} sub="Scenario + guard" />}
                <ResultMetric label="SIMULATED FRICTION" value={money(Number(shockRun.unguarded.total_fees) + Number(shockRun.unguarded.total_slippage_cost))} sub="Fees + slippage for scenario bot" />
              </div>

              <section className="lab-recorder" ref={recorderRef} tabIndex={-1} aria-labelledby="lab-recorder-title">
                <div className="lab-subhead"><div><span>DECISION RECORDER / {replayMode === "shock" ? "SCENARIO" : "BASELINE"} / {replayGuarded && guarded ? "GUARDED" : "UNGUARDED"}</span><h4 id="lab-recorder-title">Inside the strategy</h4></div><span>CANDLE {cursor + 1}</span></div>
                <p className="lab-navigation-notice" role="status" aria-live="polite">{navigationNotice}</p>
                {navigationNotice && !navigationTarget.event && <p className="lab-inspect-context">Showing {navigationTarget.label} at this candle. The events below are separate recorded decisions.</p>}
                <div className="lab-recorder-grid">
                  <div className="lab-recorder-context"><span>CANDLE CLOSE</span><strong>{money(currentCandle?.close)}</strong><small>Synthetic price · {displayedRun.scenario.symbol}</small><span>CLOSE DRAWDOWN</span><strong>{formatPercent(displayedPoint?.drawdown_pct)}</strong><small>Selected path · peak-to-trough magnitude</small></div>
                  <div className="lab-recorder-content">
                    {currentEvents.length ? (
                      <>
                        <div className="lab-event-tabs" role="group" aria-label="Recorded events">{currentEvents.map((event, index) => <button type="button" key={`${event.event_type}-${index}`} onClick={() => setSelectedEvent(event)} aria-pressed={detailEvent === event} className={detailEvent === event ? "is-active" : ""}>{eventName(event)}</button>)}</div>
                        {detailEvent && <><p>{detailEvent.reason}</p><div className="lab-event-details"><span>TYPE <b>{detailEvent.event_type.toUpperCase()}</b></span><span>ACTION <b>{detailEvent.action}</b></span>{detailEvent.event_type === "fill" && <><span>PRICE <b>{money(detailEvent.price)}</b></span><span>QTY <b>{number(detailEvent.quantity, 6)}</b></span><span>FEE <b>{money(detailEvent.fee)}</b></span></>}</div></>}
                      </>
                    ) : <p>No event was recorded for this candle.</p>}
                  </div>
                </div>
              </section>
              <DecisionComparison run={shockRun} onInspect={navigateEvidence} />
              <EvidenceTrail run={shockRun} onNavigate={navigateEvidence} />
            </>
          )}
        </div>
      </div>

      {results && <WarRoom key={`war-room-${shockRun.fingerprint}`} scenario={applied} run={shockRun} dirty={dirty} otherBusy={running || worldsRunning || landscapeRunning || passportRunning} onBusyChange={setWarRoomRunning} onInspect={navigateEvidence} />}
      {results && <SyntheticWorlds key={`worlds-${shockRun.fingerprint}`} scenario={applied} experimentRunning={running || landscapeRunning || passportRunning || warRoomRunning} onBusyChange={setWorldsRunning} onSelectSeed={loadWorldSeed} />}
      {results && <ShockLandscape key={`landscape-${shockRun.fingerprint}`} scenario={applied} otherBusy={running || worldsRunning || passportRunning || warRoomRunning} onBusyChange={setLandscapeRunning} onSelectCell={loadLandscapeCell} />}

      {results && (
        <section className="lab-passport">
          <div className="lab-passport-heading"><div><span>06 / REPRODUCIBILITY PASSPORT</span><h2>A result you can inspect.</h2><p>These files cover the last completed synthetic run. Synthetic Worlds and Shock Landscape are separate calculations. Open the briefing HTML to print it to PDF.</p></div><div className="lab-passport-actions"><button type="button" className="lab-export" onClick={downloadPassport}>Download JSON <span aria-hidden="true">↓</span></button><button type="button" className="lab-export" onClick={downloadBriefing}>Download briefing <span aria-hidden="true">↓</span></button></div></div>
          {briefError && <p className="lab-error" role="alert">{briefError}</p>}
          <div className="lab-passport-grid">
            <div><span>STRATEGY</span><strong>{displayedStrategy.label}</strong><small>{displayedStrategy.callsign} · rule-based</small></div>
            <div><span>MARKET</span><strong>Synthetic · {shockRun.scenario.candle_count} candles</strong><small>Seed {shockRun.scenario.seed}</small></div>
            <div><span>FRICTION</span><strong>{applied.fee_bps} bps fee / {applied.slippage_bps} bps slip</strong><small>Assumptions per simulated fill</small></div>
            <div><span>SCENARIO</span><strong>{shockRun.scenario.shock_index == null ? "No injected shock" : `${applied.shock_pct}% hypothetical shock`}</strong><small>{shockRun.scenario.shock_index == null ? "Baseline conditions" : `Candle ${shockRun.scenario.shock_index + 1}`}</small></div>
          </div>
          <div className="lab-passport-implementation"><span>ENGINE VERSION <b>{shockRun.engine_version ?? "—"}</b></span><span>STRATEGY PARAMETERS <b>{shockRun.strategy_parameters ? Object.entries(shockRun.strategy_parameters).map(([key, value]) => `${key}: ${value}`).join(" · ") : "—"}</b></span><span>BUY SIGNAL SIZE <b>{shockRun.signal_cash_fraction == null ? "—" : `${shockRun.signal_cash_fraction * 100}% of available cash`}</b></span></div>
          <p className="lab-version-note">Engine version is a manually maintained label, not a source hash or proof of execution.</p>
          <div className="lab-passport-fingerprint"><span>RUN FINGERPRINT</span><code>{shockRun.fingerprint}</code></div>
          <details className="lab-assumptions"><summary>View simulation assumptions and limitations <span>+</span></summary><ul>{shockRun.assumptions.map((assumption, index) => <li key={index}>{assumption}</li>)}<li>This is synthetic data, not evidence of a profitable strategy or a forecast. The fingerprint is not an independent audit.</li><li>The engine version is a manually maintained label, not a source hash or proof of execution.</li></ul></details>
        </section>
      )}
      <div className="lab-footer"><span>AXIOM / SURVIVAL LAB</span><span>BUILT TO EXAMINE, NOT TO PREDICT.</span></div>
    </div>
  );
}
