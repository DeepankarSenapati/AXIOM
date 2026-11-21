import { useMemo } from "react";
import { buildEvidenceTrail } from "../evidenceTrail.js";
import "./EvidenceTrail.css";

export default function EvidenceTrail({ run, onNavigate }) {
  const moments = useMemo(() => buildEvidenceTrail(run), [run]);
  return (
    <section className="evidence-trail" aria-labelledby="evidence-trail-title">
      <div className="evidence-trail-heading">
        <div><span>THE EVIDENCE TRAIL</span><h4 id="evidence-trail-title">Follow what happened.</h4></div>
        <span className="evidence-trail-path">TESTED SCENARIO / {run.guarded ? "GUARDED" : "UNGUARDED"}</span>
      </div>
      <p>Selected moments from the completed simulation, not a complete event log. Choose one to inspect it in the replay.</p>
      {moments.length ? (
        <ol className="evidence-trail-list">
          {moments.map((moment) => (
            <li key={moment.id}>
              <button type="button" onClick={() => onNavigate(moment)}>
                <span className="evidence-trail-candle">CANDLE {moment.candleIndex + 1}</span>
                <strong>{moment.label}</strong>
                <small>{moment.reason}</small>
                <span className="evidence-trail-arrow" aria-hidden="true">↗</span>
              </button>
            </li>
          ))}
        </ol>
      ) : <p>No selected moments were recorded for this path. Use the replay to inspect its signals.</p>}
    </section>
  );
}
