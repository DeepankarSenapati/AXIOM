import { useEffect, useRef, useState } from "react";
import { authHeaders } from "../auth.js";
import { formatPercent } from "../percentFormatting.js";
import { describeEquityDelta, formatEquityDelta } from "../worldsFormatting.js";
import "./SyntheticWorlds.css";

const MAX_SEED = 4_294_967_295;

const percent = (value, sign = true) => formatPercent(value, sign);

function errorMessage(data) {
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.detail)) return data.detail.map((item) => item.msg ?? "Invalid input").join("; ");
  return "The worlds could not be calculated. Check that the backend is running.";
}

function Aggregate({ label, values }) {
  return (
    <div className="worlds-aggregate">
      <span>{label}</span>
      <div><strong>{percent(values.median_total_return_pct)}</strong><small>median return</small></div>
      <div><strong>{percent(values.worst_max_drawdown_pct, false)}</strong><small>worst observed drawdown</small></div>
      <div><strong>{percent(values.worst_total_return_pct)}</strong><small>worst observed return</small></div>
    </div>
  );
}

export default function SyntheticWorlds({ scenario, experimentRunning, onBusyChange, onSelectSeed }) {
  const maximumWorlds = Math.min(12, MAX_SEED - scenario.seed + 1);
  const [worldCount, setWorldCount] = useState(Math.min(6, maximumWorlds));
  const [results, setResults] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const requestRef = useRef(null);

  useEffect(() => () => requestRef.current?.abort(), []);

  async function runWorlds(event) {
    event.preventDefault();
    const controller = new AbortController();
    requestRef.current = controller;
    setRunning(true);
    onBusyChange(true);
    setResults(null);
    setError("");
    try {
      const response = await fetch("/arena/lab/worlds", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ scenario, world_count: Number(worldCount) }),
        signal: controller.signal,
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(errorMessage(data));
      setResults(data);
    } catch (err) {
      if (!controller.signal.aborted) setError(err.message || "The worlds could not be calculated.");
    } finally {
      if (!controller.signal.aborted) {
        setRunning(false);
        onBusyChange(false);
      }
    }
  }

  return (
    <section className="worlds-panel" aria-labelledby="worlds-title">
      <header className="worlds-header">
        <div>
          <p className="worlds-kicker">04 / SYNTHETIC WORLDS</p>
          <h2 id="worlds-title">One question. More worlds.</h2>
          <p>Keep the last experiment's settings and explore consecutive market seeds. Load any world to restore those settings and its seed, then run the experiment again to replay it.</p>
        </div>
        <div className="worlds-header-mark" aria-hidden="true"><i /><i /><i /><span>AX<br />∴</span></div>
      </header>
      <p className="worlds-disclosure">These are samples from one artificial generator, not probabilities, forecasts, independent evidence, or real-market validation. Drawdown uses candle closes and can miss intrabar losses.</p>
      <form className="worlds-form" onSubmit={runWorlds}>
        <div className="worlds-count"><label htmlFor="worlds-count">Number of worlds</label><small id="worlds-count-help">Consecutive seeds starting at {scenario.seed}. Maximum {maximumWorlds}.</small></div>
        <input id="worlds-count" type="number" min="1" max={maximumWorlds} step="1" required disabled={running || experimentRunning} aria-describedby="worlds-count-help" value={worldCount} onChange={(event) => setWorldCount(event.target.value === "" ? "" : Number(event.target.value))} />
        <button type="submit" disabled={running || experimentRunning}>{running ? "Calculating worlds…" : results ? "Run worlds again" : "Generate worlds"}<span aria-hidden="true"> ↗</span></button>
      </form>
      {error && <p className="worlds-error" role="alert">{error}</p>}
      <p className="worlds-status" role="status">{running ? "Calculating synthetic worlds using the last experiment's settings." : results ? `${results.world_count} synthetic worlds calculated.` : "Uses the last completed experiment, not unsaved changes in the controls above."}</p>
      {results && <>
        <div className="worlds-results-head"><div><span>THE OBSERVED SAMPLE</span><h3>{results.world_count === 1 ? "What happened in this world?" : "What changed across these seeds?"}</h3></div><span>{results.world_count} / WORLD{results.world_count === 1 ? "" : "S"}</span></div>
        <div className="worlds-aggregates">
          <Aggregate label="BOT / NO GUARD" values={results.unguarded} />
          {results.guarded && <Aggregate label="BOT / GUARD ENABLED" values={results.guarded} />}
        </div>
        {results.comparison && <p className="worlds-comparison">Guarded final equity was higher in <strong>{results.comparison.improved_equity_count}</strong>, lower in <strong>{results.comparison.worsened_equity_count}</strong>, and equal in <strong>{results.comparison.equal_equity_count}</strong> of {results.world_count === 1 ? "this 1 world" : `these ${results.world_count} worlds`}. The guard triggered in {results.comparison.guard_trigger_count}. Equal means a difference of at most ${results.comparison.equity_equality_tolerance.toExponential(1)}. Each world shows guarded minus unguarded final equity; positive means the guarded path ended higher.</p>}
        <div className="worlds-list-heading"><span>EVERY WORLD / ACTUAL SIMULATED RESULTS</span><span>Loading a world replaces unsaved settings in the experiment controls.</span></div>
        <ul className="worlds-list">
          {results.worlds.map((world, index) => <li key={world.seed} className="worlds-card">
            <div className="worlds-card-top"><span>WORLD {String(index + 1).padStart(2, "0")}</span><span className="worlds-orbit" aria-hidden="true"><i /></span></div>
            <h4>Seed {world.seed}</h4>
            <dl>
              <div><dt>Bot return</dt><dd>{percent(world.unguarded.total_return_pct)}</dd></div>
              <div><dt>Bot drawdown</dt><dd>{percent(world.unguarded.max_drawdown_pct, false)}</dd></div>
              <div><dt>Bot fills</dt><dd>{world.unguarded.trade_count}</dd></div>
              {world.guarded && <><div><dt>Guarded return</dt><dd>{percent(world.guarded.total_return_pct)}</dd></div><div><dt>Guarded drawdown</dt><dd>{percent(world.guarded.max_drawdown_pct, false)}</dd></div><div><dt>Guard triggered</dt><dd>{world.guarded.guard_trigger_index == null ? "No" : `Candle ${world.guarded.guard_trigger_index + 1}`}</dd></div><div><dt>Guard − bot equity</dt><dd>{formatEquityDelta(world.guarded.final_equity - world.unguarded.final_equity)}<br /><small>{describeEquityDelta(world.guarded.final_equity - world.unguarded.final_equity, results.comparison?.equity_equality_tolerance)}</small></dd></div></>}
            </dl>
            <p className="worlds-fingerprint" title={world.fingerprint} aria-label={`Run fingerprint ${world.fingerprint}`}>ID / {world.fingerprint.slice(0, 12)}…</p>
            <button type="button" disabled={experimentRunning} onClick={() => onSelectSeed(world.seed)} aria-label={`Load seed ${world.seed} and the last experiment settings into the controls`}>Load world for replay <span aria-hidden="true">↗</span></button>
          </li>)}
        </ul>
        <details className="worlds-assumptions"><summary>About this sample and its assumptions</summary><ul>{results.assumptions.map((assumption, index) => <li key={index}>{assumption}</li>)}</ul></details>
      </>}
    </section>
  );
}
