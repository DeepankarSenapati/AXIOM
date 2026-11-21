import { useEffect, useRef, useState } from "react";
import { authHeaders } from "../auth.js";
import { formatPercent } from "../percentFormatting.js";
import "./ShockLandscape.css";

function levels(current, maximum) {
  return current <= 0 || current >= maximum ? [0, maximum / 2, maximum] : [0, current, maximum];
}

const percent = (value, signed = false) => formatPercent(value, signed);

function errorMessage(data) {
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.detail)) return data.detail.map((item) => item.msg ?? "Invalid input").join("; ");
  return "The landscape could not be calculated. Check that the backend is running.";
}

export default function ShockLandscape({ scenario, otherBusy, onBusyChange, onSelectCell }) {
  const shockPcts = levels(scenario.shock_pct, 30);
  const fees = levels(scenario.fee_bps, 50);
  const [results, setResults] = useState(null);
  const [running, setRunning] = useState(false);
  const [path, setPath] = useState(scenario.guard_enabled ? "guarded" : "unguarded");
  const [error, setError] = useState("");
  const requestRef = useRef(null);
  const tooLong = scenario.num_candles > 160;

  useEffect(() => () => requestRef.current?.abort(), []);

  async function runLandscape() {
    const controller = new AbortController();
    requestRef.current = controller;
    setRunning(true);
    onBusyChange(true);
    setResults(null);
    setError("");
    try {
      const response = await fetch("/arena/lab/landscape", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ scenario, shock_pcts: shockPcts, fee_bps_values: fees }),
        signal: controller.signal,
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(errorMessage(data));
      setResults(data);
    } catch (err) {
      if (!controller.signal.aborted) setError(err.message || "The landscape could not be calculated.");
    } finally {
      if (!controller.signal.aborted) {
        setRunning(false);
        onBusyChange(false);
      }
    }
  }

  return <section className="landscape-panel" aria-labelledby="landscape-title">
    <header className="landscape-header">
      <div><p className="landscape-kicker">05 / SHOCK LANDSCAPE</p><h2 id="landscape-title">See the response to pressure.</h2><p>Vary one hypothetical shock and the per-fill fee while holding the last experiment's other settings fixed. Every cell is an actual simulation you can replay.</p></div>
      <div className="landscape-mark" aria-hidden="true"><span /><span /><span /><span /><span /><span /><span /><span /><span /></div>
    </header>
    <p className="landscape-disclosure">This is sensitivity to one artificial market, not a probability, forecast, safety rating, or real-market validation. Colors do not indicate safety.</p>
    <div className="landscape-action"><div><strong>Fixed: seed {scenario.seed} · {scenario.num_candles} candles · {scenario.slippage_bps} bps slippage</strong><small>The same generated random factors are used throughout. A shock is one downward gap; it changes the price path from that candle onward.</small></div><button type="button" onClick={runLandscape} disabled={running || otherBusy || tooLong}>{running ? "Calculating landscape…" : results ? "Run landscape again" : "Generate landscape"}<span aria-hidden="true"> ↗</span></button></div>
    {tooLong && <p className="landscape-error" role="alert">Shock Landscape supports at most 160 candles per experiment.</p>}
    {error && <p className="landscape-error" role="alert">{error}</p>}
    <p className="landscape-status" role="status">{running ? "Calculating shock and fee combinations using the last experiment's settings." : otherBusy ? "Waiting for the other simulation to finish." : results ? `${results.cells.length} shock and fee combinations calculated.` : "Uses the last completed experiment, not unsaved changes in the controls above."}</p>
    {results && <>
      <div className="landscape-results-header"><div><span>THE OBSERVED COMBINATIONS</span><h3>Shock × fee</h3></div>{scenario.guard_enabled && <div className="landscape-switch" role="group" aria-label="Result path"><button type="button" aria-pressed={path === "unguarded"} onClick={() => setPath("unguarded")}>BOT</button><button type="button" aria-pressed={path === "guarded"} onClick={() => setPath("guarded")}>GUARDED</button></div>}</div>
      <p className="landscape-context">Showing {path === "guarded" ? "guarded" : "unguarded"} return, drawdown and exposure. Drawdown uses candle closes and can miss intrabar losses. Exposure is measured at the close before candle {results.shock_index + 1}; it excludes pending orders that may fill at the next open. The buy cap applies when a buy fills; exposure may later drift above it as prices change. A 0% shock applies no gap.</p>
      <p className="landscape-context">Changing the shock or fee can also change signals, fills and guard timing. Outcomes need not move in one direction as conditions change.</p>
      <p className="landscape-context">Loading a cell replaces unsaved experiment settings. Run the experiment afterward to replay the selected cell.</p>
      <p id="landscape-scroll-help" className="landscape-scroll-help"><span aria-hidden="true">↔</span> Scroll sideways if needed to see all fees.</p>
      <div className="landscape-table-scroll" role="region" aria-label="Shock and fee comparison" aria-describedby="landscape-scroll-help" tabIndex="0">
        <table className="landscape-table">
          <caption>Simulated results by downward shock and fee per fill; the last completed experiment is outlined.</caption>
          <thead><tr><th scope="col">SHOCK ↓<br />FEE →</th>{results.fee_bps_values.map((fee) => <th scope="col" key={fee}>{fee} bps</th>)}</tr></thead>
          <tbody>{results.shock_pcts.map((shock) => <tr key={shock}><th scope="row">{shock}%<small>{shock === 0 ? "No gap" : "Downward gap"}</small></th>{results.fee_bps_values.map((fee) => {
            const cell = results.cells.find((item) => item.shock_pct === shock && item.fee_bps === fee);
            if (!cell) return <td key={fee}>Unavailable</td>;
            const selected = cell[path] ?? cell.unguarded;
            const isCurrent = shock === scenario.shock_pct && fee === scenario.fee_bps;
            const guard = cell.guarded;
            return <td key={fee}><div className={`landscape-cell ${isCurrent ? "is-current" : ""}`}>
              {isCurrent && <span className="landscape-current">LAST COMPLETED RUN</span>}
              <dl><div><dt>Return</dt><dd>{percent(selected.total_return_pct, true)}</dd></div><div><dt>Max drawdown</dt><dd>{percent(selected.max_drawdown_pct)}</dd></div><div><dt>Prior-close exposure</dt><dd>{percent(selected.prior_close_exposure_pct)}</dd></div></dl>
              <p className="landscape-guard">{guard ? `${guard.guard_trigger_index == null ? "Guarded path: not triggered" : `Guarded path: triggered at candle ${guard.guard_trigger_index + 1}`} · ${guard.blocked_buy_count} blocked buy signal${guard.blocked_buy_count === 1 ? "" : "s"}` : "Guard disabled"}</p>
              <p className="landscape-fingerprint" title={cell.fingerprint} aria-label={`Run fingerprint ${cell.fingerprint}`}>ID / {cell.fingerprint.slice(0, 12)}…</p>
              <button type="button" disabled={running || otherBusy} onClick={() => onSelectCell(cell.request)} aria-label={`Load ${shock}% shock and ${fee} basis points fee into experiment controls`}>Load for replay <span aria-hidden="true">↗</span></button>
            </div></td>;
          })}</tr>)}</tbody>
        </table>
      </div>
      <details className="landscape-assumptions"><summary>About this landscape and its assumptions</summary><ul>{results.assumptions.map((assumption, index) => <li key={index}>{assumption}</li>)}</ul></details>
    </>}
  </section>;
}
