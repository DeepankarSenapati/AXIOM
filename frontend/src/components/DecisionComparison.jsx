import { useMemo } from "react";
import { compareGuardDecisions } from "../decisionComparison.js";
import { formatEquityDelta } from "../worldsFormatting.js";
import "./DecisionComparison.css";

function displayNumber(value) {
  if (!Number.isFinite(value) || value <= 0) return "unavailable";
  if (value < 0.000001) return value.toPrecision(3);
  return value.toLocaleString("en-US", { maximumFractionDigits: 6 });
}

function UnguardedOutcome({ comparison }) {
  const candle = comparison.blocked.candle_index + 1;
  if (comparison.outcomeStatus === "no_signal") {
    return <p>No unguarded signal was recorded at candle {candle}.</p>;
  }
  if (comparison.outcomeStatus === "different_signal") {
    const action = ["HOLD", "SELL"].includes(comparison.signal.action) ? comparison.signal.action : "a different";
    return <p>At candle {candle} close, the unguarded path recorded {action === "a different" ? "a different signal" : `a ${action} signal`}, not a BUY.</p>;
  }
  const outcome = comparison.outcome;
  if (comparison.outcomeStatus === "fill") {
    return <><p>BUY signaled at candle {candle} close. At the next open, candle {outcome.candle_index + 1}, a BUY fill was recorded.</p><strong>{displayNumber(outcome.quantity)} units · {Number.isFinite(outcome.price) && outcome.price > 0 ? `$${displayNumber(outcome.price)} per unit` : "fill price unavailable"}</strong><small>{outcome.reason}</small></>;
  }
  if (comparison.outcomeStatus === "rejected") {
    return <><p>BUY signaled at candle {candle} close. The order was rejected at the next open, candle {outcome.candle_index + 1}.</p><small>{outcome.reason}</small></>;
  }
  if (comparison.outcomeStatus === "expired") {
    return <><p>BUY signaled at the final close, candle {candle}. It expired because there was no next candle.</p><small>{outcome.reason}</small></>;
  }
  return <p>BUY signaled at candle {candle} close. No linked fill, rejection, or expiry was recorded.</p>;
}

export default function DecisionComparison({ run, onInspect }) {
  const comparison = useMemo(() => compareGuardDecisions(run), [run]);
  return (
    <section className="decision-comparison" aria-labelledby="decision-comparison-title">
      <div className="decision-comparison-heading">
        <div><span>ONE DECISION / TWO PATHS</span><h4 id="decision-comparison-title">See the difference at the decision.</h4></div>
        <span className="decision-comparison-tag">SYNTHETIC SCENARIO</span>
      </div>
      {comparison.status === "guard_disabled" && <p className="decision-comparison-empty">The guard was disabled for this run.</p>}
      {comparison.status === "unavailable" && <p className="decision-comparison-empty">The recorded paths are unavailable for comparison.</p>}
      {comparison.status === "no_blocked_buy" && <p className="decision-comparison-empty">No blocked BUY signal was recorded in the guarded path.</p>}
      {comparison.status === "compared" && <>
        <p className="decision-comparison-intro">The first guarded blocked BUY and the unguarded signal at the same candle close:</p>
        <div className="decision-comparison-grid">
          <div className="decision-comparison-path">
            <span>GUARDED PATH</span><h5>BUY signal blocked</h5>
            <p>Candle {comparison.blocked.candle_index + 1}, at the close.</p>
            <small>{comparison.blocked.reason}</small>
          </div>
          <div className="decision-comparison-path">
            <span>UNGUARDED PATH</span><h5>Same-candle signal</h5>
            <UnguardedOutcome comparison={comparison} />
          </div>
        </div>
        {onInspect && <button type="button" className="decision-comparison-link" onClick={() => onInspect({
          candleIndex: comparison.blocked.candle_index, event: comparison.blocked, label: "BUY signal blocked",
        })}>Inspect the blocked signal <span aria-hidden="true">↗</span></button>}
      </>}
      {(comparison.status === "compared" || comparison.status === "no_blocked_buy") && <div className="decision-comparison-total">
        <span>WHOLE-RUN FINAL EQUITY · GUARDED − UNGUARDED</span>
        <strong>{comparison.difference == null ? "Unavailable" : formatEquityDelta(comparison.difference)}</strong>
        <small>{comparison.status === "compared" ? "Simulated USD. This difference reflects the entire run, not just this signal." : "Simulated USD. This is a whole-run comparison."}</small>
      </div>}
      <p className="decision-comparison-note">{comparison.status === "compared" ? "Later decisions may differ. The guard checks at the close; an order from an earlier close may have filled at that candle's open. " : ""}These synthetic outcomes are not predictions.</p>
    </section>
  );
}
