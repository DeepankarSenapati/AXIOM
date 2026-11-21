import { useEffect, useRef, useState } from "react";
import { parsePassport } from "../passport.js";
import "./PassportReplay.css";

const MAX_PASSPORT_BYTES = 5 * 1024 * 1024;

function FingerprintComparison({ label, values }) {
  const matches = values.recorded.toLowerCase() === values.calculated.toLowerCase();
  return <div className="passport-compare-item">
    <strong>{label}</strong>
    <p>Recorded fingerprint {matches ? "matches" : "does not match"} this rerun.</p>
    <dl><div><dt>Recorded in file</dt><dd><code>{values.recorded}</code></dd></div><div><dt>Calculated on rerun</dt><dd><code>{values.calculated}</code></dd></div></dl>
  </div>;
}

export default function PassportReplay({ disabled, replaying, comparison, onClearComparison, onReplay }) {
  const [selected, setSelected] = useState(null);
  const [reading, setReading] = useState(false);
  const [error, setError] = useState("");
  const active = useRef(false);
  const readSequence = useRef(0);
  const fileInput = useRef(null);

  useEffect(() => {
    active.current = true;
    return () => { active.current = false; readSequence.current += 1; };
  }, []);

  async function chooseFile(event) {
    const file = event.target.files?.[0];
    const currentRead = ++readSequence.current;
    setSelected(null);
    setError("");
    onClearComparison();
    if (!file) { setReading(false); return; }
    if (file.size > MAX_PASSPORT_BYTES) {
      setReading(false);
      if (fileInput.current) fileInput.current.value = "";
      setError("Choose a passport no larger than 5 MiB.");
      return;
    }
    setReading(true);
    try {
      const text = await file.text();
      if (!active.current || currentRead !== readSequence.current) return;
      setSelected({ name: file.name, ...parsePassport(text) });
    } catch (err) {
      if (active.current && currentRead === readSequence.current) {
        if (fileInput.current) fileInput.current.value = "";
        setError(err.message || "This passport could not be read.");
      }
    } finally {
      if (active.current && currentRead === readSequence.current) setReading(false);
    }
  }

  function clearFile() {
    readSequence.current += 1;
    if (fileInput.current) fileInput.current.value = "";
    setReading(false);
    setSelected(null);
    setError("");
    onClearComparison();
  }

  async function replay() {
    if (!selected || disabled || reading) return;
    setError("");
    try {
      await onReplay(selected);
    } catch (err) {
      if (active.current && err.name !== "AbortError") setError(err.message || "The passport could not be replayed.");
    }
  }

  return <details className="passport-import">
    <summary className="passport-import-summary"><span><span className="passport-import-kicker">REPRODUCIBILITY / LOCAL REPLAY</span><span className="passport-import-title">Replay a saved passport.</span></span><span className="passport-import-mark" aria-hidden="true" /></summary>
    <p className="passport-import-description">Choose a previously exported AXIOM Survival Lab JSON file, then run its recorded settings again.</p>
    <div className="passport-import-controls">
      <div><label htmlFor="passport-file">Passport JSON file</label><small id="passport-file-help">Maximum 5 MiB. The file is read locally; only its validated simulation settings are sent to the local engine.</small><div className="passport-file-row"><input ref={fileInput} id="passport-file" type="file" accept=".json,application/json" aria-describedby="passport-file-help" disabled={disabled || reading} onChange={chooseFile} />{selected && <button type="button" disabled={disabled || reading} onClick={clearFile}>Clear file</button>}</div></div>
      <button type="button" disabled={disabled || reading || !selected} onClick={replay}>{replaying ? "Replaying passport…" : "Replay passport"}<span aria-hidden="true"> ↗</span></button>
    </div>
    <p className="passport-import-status" role="status">{reading ? "Reading passport…" : replaying ? "Calculating a fresh replay…" : selected ? `${selected.name} is ready. Replay to calculate new results.` : "No passport selected."}</p>
    {error && <p className="passport-import-error" role="alert">{error}</p>}
    {comparison && <section className="passport-comparison" aria-label="Fingerprint comparison" aria-live="polite">
      <p className="passport-comparison-note">A matching fingerprint is not proof of the file's contents, source code, outputs, or execution.</p>
      <div className="passport-comparison-grid"><FingerprintComparison label="BASELINE" values={comparison.baseline} /><FingerprintComparison label="SHOCKED SCENARIO" values={comparison.shock} /></div>
    </section>}
  </details>;
}
