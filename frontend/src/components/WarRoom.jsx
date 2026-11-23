import { useEffect, useRef, useState } from "react";
import { authHeaders } from "../auth.js";
import { resolveWarRoomEvidence, validateWarRoomResponse } from "../warRoomEvidence.js";
import { buildWarRoomCase, REVIEW_DECISIONS } from "../warRoomCase.js";
import LabRobot from "./LabRobot.jsx";
import "./WarRoom.css";

const REVIEWERS = [
  { role: "challenger", number: "01", name: "Challenger", mission: "Find the pressure point", robot: "momentum" },
  { role: "defender", number: "02", name: "Defender", mission: "Explain the rule", robot: "rsi" },
  { role: "auditor", number: "03", name: "Auditor", mission: "Separate fact from inference", robot: "simple_ma" },
];

function responseError(data, fallback) {
  return typeof data?.detail === "string" && data.detail.length < 400 ? data.detail : fallback;
}

export default function WarRoom({ scenario, run, dirty, otherBusy, onBusyChange, onInspect }) {
  const [mode, setMode] = useState("scripted");
  const [capabilities, setCapabilities] = useState(null);
  const [capabilityError, setCapabilityError] = useState(false);
  const [review, setReview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [focusedEvidence, setFocusedEvidence] = useState(null);
  const [decision, setDecision] = useState("undecided");
  const [notes, setNotes] = useState("");
  const [downloadError, setDownloadError] = useState("");
  const requestRef = useRef(null);
  const evidenceRefs = useRef(new Map());

  useEffect(() => {
    const controller = new AbortController();
    fetch("/arena/war-room/capabilities", { headers: authHeaders(), signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Capabilities unavailable");
        return response.json();
      })
      .then((data) => {
        if (typeof data.claude_configured !== "boolean" || !Number.isInteger(data.max_claude_reviews) ||
            !Number.isInteger(data.claude_reviews_remaining)) throw new Error("Invalid capabilities");
        setCapabilities(data);
      })
      .catch(() => { if (!controller.signal.aborted) setCapabilityError(true); });
    return () => {
      controller.abort();
      requestRef.current?.abort();
      onBusyChange(false);
    };
  }, [onBusyChange]);

  async function openReview() {
    if (busy || otherBusy) return;
    const controller = new AbortController();
    requestRef.current = controller;
    setBusy(true);
    onBusyChange(true);
    setError("");
    try {
      const response = await fetch("/arena/war-room/review", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ scenario, expected_fingerprint: run.fingerprint, mode }),
        signal: controller.signal,
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(responseError(data, "The review could not be generated."));
      validateWarRoomResponse(data, run.fingerprint, mode);
      if (!controller.signal.aborted) {
        setFocusedEvidence(null);
        setDownloadError("");
        setReview(data);
      }
    } catch (err) {
      if (!controller.signal.aborted) setError(err.message || "The review could not be generated.");
    } finally {
      if (!controller.signal.aborted && mode === "claude") {
        try {
          const response = await fetch("/arena/war-room/capabilities", { headers: authHeaders(), signal: controller.signal });
          const data = response.ok ? await response.json() : null;
          if (typeof data?.claude_configured === "boolean" && Number.isInteger(data.max_claude_reviews) &&
              Number.isInteger(data.claude_reviews_remaining)) setCapabilities(data);
          else setCapabilityError(true);
        } catch {
          if (!controller.signal.aborted) setCapabilityError(true);
        }
      }
      if (requestRef.current === controller) requestRef.current = null;
      if (!controller.signal.aborted) {
        setBusy(false);
        onBusyChange(false);
      }
    }
  }

  function selectMode(nextMode) {
    if (nextMode === mode) return;
    setMode(nextMode);
    setError("");
  }

  function showEvidence(id) {
    setFocusedEvidence(id);
    const node = evidenceRefs.current.get(id);
    node?.focus({ preventScroll: true });
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    node?.scrollIntoView({ block: "center", behavior: reduceMotion ? "auto" : "smooth" });
  }

  function downloadCase() {
    try {
      const caseFile = buildWarRoomCase(scenario, review, decision, notes);
      const url = URL.createObjectURL(new Blob([JSON.stringify(caseFile, null, 2)], { type: "application/json" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `axiom-war-room-${run.fingerprint.slice(0, 12)}.json`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setDownloadError("");
    } catch (err) {
      setDownloadError(err.message || "The case file could not be prepared.");
    }
  }

  return (
    <section id="war-room" className="war-room" aria-labelledby="war-room-title">
      <header className="war-room-hero">
        <div className="war-room-hero-copy">
          <div className="war-room-eyebrow"><span /> AXIOM / WAR ROOM <span className="war-room-index">CASE 01</span></div>
          <h2 id="war-room-title">Put the strategy <em>on trial.</em></h2>
          <p>Three review perspectives. One recorded simulation. Follow the evidence before deciding what to test next.</p>
          <div className="war-room-hero-tags"><span>SYNTHETIC SCENARIO</span><span>NO REAL TRADES</span><span>HUMAN DECISION</span></div>
        </div>
        <div className="war-room-constellation" aria-hidden="true">
          <div className="war-room-orbit war-room-orbit-outer" /><div className="war-room-orbit war-room-orbit-inner" />
          <div className="war-room-orbit-core"><span>AX</span><small>REVIEW</small></div>
          <i className="war-room-satellite one" /><i className="war-room-satellite two" /><i className="war-room-satellite three" />
        </div>
      </header>

      <div className="war-room-body">
        <div className="war-room-case">
          <div><span>THE CASE / LAST COMPLETED EXPERIMENT</span><strong>{scenario.strategy_key.replaceAll("_", " ")}</strong></div>
          <div><span>MARKET</span><strong>Seed {scenario.seed}</strong></div>
          <div><span>SCENARIO</span><strong>{scenario.shock_pct ? `${scenario.shock_pct}% gap` : "No shock"}</strong></div>
          <div><span>FRICTION</span><strong>{scenario.fee_bps} bps fee · {scenario.slippage_bps} bps slip</strong></div>
          <div><span>BUY GUARD</span><strong>{scenario.guard_enabled ? `${scenario.guard_drawdown_pct}% trigger` : "Off"}</strong></div>
          <div className="war-room-case-id"><span>RUN FINGERPRINT</span><strong title={run.fingerprint}>{run.fingerprint.slice(0, 12)}…</strong></div>
        </div>
        {dirty && <p className="war-room-stale" role="status">Controls have changed. This review uses the last completed experiment shown above.</p>}

        <div className="war-room-panel-head"><div><span>THE REVIEW PANEL</span><h3>Three lenses. One case.</h3></div><p>Every perspective should point you back to the recorded evidence.</p></div>
        <div className="war-room-reviewers">
          {REVIEWERS.map((reviewer) => <article key={reviewer.role} className={`war-room-reviewer is-${reviewer.role}`}>
            <div className="war-room-reviewer-top"><span>{reviewer.number} / {reviewer.role.toUpperCase()}</span><i aria-hidden="true" /></div>
            <div className="war-room-reviewer-avatar"><LabRobot strategy={reviewer.robot} selected /></div>
            <h4>{reviewer.name}</h4><p>{reviewer.mission}</p>
          </article>)}
        </div>

        <div className="war-room-controls">
          <div className="war-room-controls-heading"><div><span>REVIEW MODE</span><h3>Choose how to open the case.</h3></div></div>
          <div className="war-room-modes" role="group" aria-label="Review mode">
            <button type="button" className={`war-room-mode ${mode === "scripted" ? "is-selected" : ""}`} aria-pressed={mode === "scripted"} disabled={busy} onClick={() => selectMode("scripted")}>
              <span className="war-room-mode-dot" aria-hidden="true" /><span><strong>Offline walkthrough</strong><small>Rule-generated perspectives · no AI calls</small></span>
            </button>
            <button type="button" className={`war-room-mode ${mode === "claude" ? "is-selected" : ""}`} aria-pressed={mode === "claude"} disabled={busy || !capabilities?.claude_configured || capabilities.claude_reviews_remaining <= 0} onClick={() => selectMode("claude")}>
              <span className="war-room-mode-dot" aria-hidden="true" /><span><strong>Claude perspectives</strong><small>{capabilities?.claude_configured ? capabilities.claude_reviews_remaining > 0 ? "Three model calls · network required" : "Local review limit reached" : "Requires a server-side Anthropic API key"}</small></span>
            </button>
          </div>
          <p className="war-room-mode-note">{mode === "claude" ? `Opening the review sends synthetic scenario evidence to Anthropic and makes up to three paid API calls. This local server allows ${capabilities?.max_claude_reviews} reviews per launch (${capabilities?.claude_reviews_remaining} remaining); failures can count and be billed. Restarting resets the local limit; it is not an account-wide spending cap. All perspectives use the same configured model, and citations are not proof of accuracy.` : "The offline walkthrough uses rules and recorded results. It does not call an AI model."} {capabilityError ? "Model availability could not be checked." : ""}</p>
          {!capabilities?.claude_configured && <details className="war-room-setup"><summary>How to enable Claude perspectives</summary><p>Set <code>AXIOM_ANTHROPIC_API_KEY</code> in the backend environment and restart the demo. An Anthropic API key is separate from a Claude Code login; API calls can incur charges. The offline walkthrough remains available without a key.</p></details>}
          <button type="button" className="war-room-open" disabled={busy || otherBusy || (mode === "claude" && (!capabilities?.claude_configured || capabilities.claude_reviews_remaining <= 0))} onClick={openReview}>
            {busy ? "Preparing the review…" : review?.mode === mode ? "Run review again" : "Open the review"}<span aria-hidden="true">↗</span>
          </button>
          <p className="war-room-status" role="status" aria-live="polite">{busy ? `${mode === "claude" ? "Requesting the three model perspectives." : "Preparing the offline walkthrough."}${review ? " The previous review remains visible." : ""}` : error && review ? "The previous review and your notes remain available." : review && review.mode !== mode ? "Showing the previous review until the selected mode is run." : review ? "Review ready. Explore each reference below." : "Uses the last completed experiment and its recorded fingerprint."}</p>
          {error && <p className="war-room-error" role="alert">{error}</p>}
        </div>

        {review && <div className="war-room-results">
          <div className="war-room-results-head"><div><span>REVIEW / COMPLETED</span><h3>Follow the argument.</h3></div><strong>{review.mode === "claude" ? "MODEL-GENERATED" : "RULE-GENERATED · NO LIVE AI"}</strong></div>
          <p className="war-room-results-intro">{review.mode === "claude" ? `Unverified model output from ${review.model || "the configured model"}: statements may be wrong or inappropriate. Review every claim against the record; these perspectives are not trading advice. A reference is not independent verification.` : "These perspectives are generated by rules from this simulation, not by independent AI agents."}</p>
          <div className="war-room-transcript">
            {review.messages.map((message) => {
              const role = REVIEWERS.find((item) => item.role === message.role);
              return <article className={`war-room-message is-${message.role}`} key={message.role}>
                <div className="war-room-message-meta"><div className="war-room-message-avatar"><LabRobot strategy={role.robot} /></div><div><span>{role.number} / {role.name.toUpperCase()}</span><small>{role.mission}</small></div></div>
                <div className="war-room-message-content"><h4>{message.headline}</h4><p>{message.body}</p><div className="war-room-citations" aria-label={`${role.name} evidence references`}>
                  {message.evidence_ids.map((id) => <button key={id} type="button" onClick={() => showEvidence(id)}>{review.evidence.find((item) => item.id === id).label} ↗</button>)}
                </div></div>
              </article>;
            })}
          </div>
          <div className="war-room-evidence-heading"><div><span>THE EVIDENCE DESK</span><h3>Inspect the record.</h3></div><p>References point to this run, not to an independent audit.</p></div>
          <div className="war-room-evidence-grid">
            {review.evidence.map((entry, index) => {
              const moment = resolveWarRoomEvidence(entry, run);
              const headingId = `war-room-evidence-${entry.id}`;
              return <article key={entry.id} ref={(node) => node ? evidenceRefs.current.set(entry.id, node) : evidenceRefs.current.delete(entry.id)} tabIndex={-1} aria-labelledby={headingId} className={`war-room-evidence ${focusedEvidence === entry.id ? "is-focused" : ""}`}>
                <div><span>EVIDENCE {String(index + 1).padStart(2, "0")}</span><small>{entry.path.toUpperCase()} {Number.isInteger(entry.candle_index) ? `· CANDLE ${entry.candle_index + 1}` : ""}</small></div>
                <h4 id={headingId}>{entry.label}</h4><strong>{entry.value}</strong><p>{entry.detail}</p>
                {moment && <button type="button" aria-label={`Inspect ${entry.label} in the ${entry.path} replay at candle ${entry.candle_index + 1}`} onClick={() => onInspect(moment)}>Inspect in replay <span aria-hidden="true">↗</span></button>}
              </article>;
            })}
          </div>
          <div className="war-room-open-question"><span>THE NEXT QUESTION</span><p>Would this behavior hold on independent historical data and under more realistic execution assumptions?</p><small>These perspectives are a starting point for human review, not a forecast or trading recommendation.</small></div>
          <section className="war-room-decision" aria-labelledby="war-room-decision-title">
            <div><span>THE HUMAN REVIEW</span><h3 id="war-room-decision-title">What happens next is your call.</h3><p>Record a next step for this case. This does not approve a strategy for trading.</p></div>
            <div className="war-room-decision-choices" role="group" aria-label="Review outcome">
              {REVIEW_DECISIONS.map((item) => <button type="button" key={item.value} aria-pressed={decision === item.value} className={decision === item.value ? "is-selected" : ""} onClick={() => setDecision(item.value)}>{item.label}</button>)}
            </div>
            <label htmlFor="war-room-notes">Optional review notes</label>
            <textarea id="war-room-notes" rows="3" maxLength="500" value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="What would you want to investigate next?" />
            <p>Notes stay on this device and are not sent to the model. Download the case to keep them; an experiment with different settings replaces this case.</p>
            <button type="button" className="war-room-download" onClick={downloadCase}>Download case file <span aria-hidden="true">↓</span></button>
            {downloadError && <p className="war-room-error" role="alert">{downloadError}</p>}
          </section>
          {Array.isArray(review.limitations) && review.limitations.length > 0 && <details className="war-room-limitations"><summary>Review assumptions and limitations <span>+</span></summary><ul>{review.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></details>}
        </div>}
      </div>
    </section>
  );
}
