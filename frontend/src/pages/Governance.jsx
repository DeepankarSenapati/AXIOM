import { useEffect, useState } from "react";
import { apiFetch } from "../auth.js";

const STAGE_NAMES = { 1: "Normal", 2: "Review", 3: "Community" };
const STAGE_COLORS = { 1: "badge-green", 2: "badge-yellow", 3: "badge-red" };

function StageBadge({ stage }) {
  return (
    <span className={`badge ${STAGE_COLORS[stage] ?? "badge-blue"}`}>
      Stage {stage} — {STAGE_NAMES[stage] ?? "Unknown"}
    </span>
  );
}

function PollHistoryTable({ polls }) {
  if (polls.length === 0) {
    return <p className="text-xs text-gray-500">No closed polls yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-gray-800">
            <th className="th">Quarter</th>
            <th className="th">Yes %</th>
            <th className="th">No %</th>
            <th className="th">Result</th>
            <th className="th">Stage Before Close</th>
            <th className="th">Closed</th>
          </tr>
        </thead>
        <tbody>
          {polls.map((p, i) => {
            const yesPct = (p.satisfaction_rate * 100).toFixed(1);
            const noPct = ((1 - p.satisfaction_rate) * 100).toFixed(1);
            const passed = p.satisfaction_rate >= 0.5;
            return (
              <tr key={i} className="border-b border-gray-800 hover:bg-gray-800/50">
                <td className="td font-mono">{p.quarter}</td>
                <td className="td text-emerald-400 font-medium">{yesPct}%</td>
                <td className="td text-red-400 font-medium">{noPct}%</td>
                <td className="td">
                  {passed
                    ? <span className="badge badge-green">Pass</span>
                    : <span className="badge badge-red">Fail</span>}
                </td>
                <td className="td"><StageBadge stage={p.stage_at_close} /></td>
                <td className="td text-gray-500">{new Date(p.closed_at).toLocaleDateString()}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const SEVERITY_COLORS = { low: "badge-green", medium: "badge-yellow", high: "badge-red" };

function currentQuarter() {
  const now = new Date();
  return `${now.getUTCFullYear()}-Q${Math.floor(now.getUTCMonth() / 3) + 1}`;
}

function BotGovernance({ bot, currentUser }) {
  const [stage, setStage] = useState(null);
  const [polls, setPolls] = useState([]);
  const [audits, setAudits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [voteForm, setVoteForm] = useState(() => ({ quarter: currentQuarter(), vote: "satisfied" }));
  const [voting, setVoting] = useState(false);
  const [voteMsg, setVoteMsg] = useState(null);
  const [holding, setHolding] = useState(null);
  const [holdingStatus, setHoldingStatus] = useState("loading");
  const [holdingError, setHoldingError] = useState(null);
  const [holdingsRevision, setHoldingsRevision] = useState(0);

  const [closeQuarter, setCloseQuarter] = useState(currentQuarter);
  const [closing, setClosing] = useState(false);
  const [closeResult, setCloseResult] = useState(null);

  const [auditForm, setAuditForm] = useState(() => ({ quarter: currentQuarter(), finding: "", recommendation: "", severity: "medium" }));
  const [submittingAudit, setSubmittingAudit] = useState(false);
  const [auditMsg, setAuditMsg] = useState(null);

  function fetchAll() {
    setLoading(true);
    Promise.all([
      apiFetch(`/governance/${bot.id}/stage`).then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
      apiFetch(`/governance/${bot.id}/polls`).then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
      apiFetch(`/governance/${bot.id}/audits`).then((r) => r.ok ? r.json() : []),
    ])
      .then(([s, p, a]) => {
        setStage(s);
        setPolls(Array.isArray(p) ? p : []);
        setAudits(Array.isArray(a) ? a : []);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { fetchAll(); }, [bot.id]);

  useEffect(() => {
    if (!currentUser?.email) {
      setHolding(null);
      setHoldingStatus("error");
      setHoldingError("Signed-in account is unavailable.");
      return undefined;
    }
    const controller = new AbortController();
    setHolding(null);
    setHoldingStatus("loading");
    setHoldingError(null);
    apiFetch("/tokenomics/my-holdings", { signal: controller.signal })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((data) => {
        if (!Array.isArray(data?.holdings)) throw new Error("Invalid holdings response.");
        const entry = data.holdings.find((item) => item.bot_id === bot.id);
        const amount = entry ? entry.amount : 0;
        if (typeof amount !== "number" || !Number.isFinite(amount) || amount < 0) throw new Error("Invalid holding amount.");
        if (!controller.signal.aborted) { setHolding(amount); setHoldingStatus("ready"); }
      })
      .catch((e) => {
        if (!controller.signal.aborted) { setHoldingError(e.message); setHoldingStatus("error"); }
      });
    return () => controller.abort();
  }, [bot.id, currentUser?.email, holdingsRevision]);

  function handleVote(e) {
    e.preventDefault();
    setVoting(true); setVoteMsg(null);
    apiFetch("/governance/vote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bot_id: bot.id, quarter: voteForm.quarter, vote: voteForm.vote }),
    })
      .then((r) => {
        if (r.status === 204) { setVoteMsg({ ok: true, text: "Simulated vote submitted." }); setHoldingsRevision((value) => value + 1); return; }
        return r.json().then((d) => { throw new Error(d.detail); });
      })
      .catch((e) => setVoteMsg({ ok: false, text: e.message }))
      .finally(() => setVoting(false));
  }

  function handleClosePoll(e) {
    e.preventDefault();
    setClosing(true); setCloseResult(null);
    apiFetch("/governance/poll/close", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bot_id: bot.id, quarter: closeQuarter }),
    })
      .then((r) => { if (!r.ok) return r.json().then((d) => { throw new Error(d.detail); }); return r.json(); })
      .then((data) => { setCloseResult(data); fetchAll(); })
      .catch((e) => setCloseResult({ error: e.message }))
      .finally(() => setClosing(false));
  }

  function handleAuditSubmit(e) {
    e.preventDefault();
    setSubmittingAudit(true); setAuditMsg(null);
    apiFetch(`/governance/${bot.id}/audit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(auditForm),
    })
      .then((r) => r.ok ? r.json() : r.json().then((d) => { throw new Error(d.detail); }))
      .then(() => {
        setAuditMsg({ ok: true, text: "Audit report submitted." });
        setAuditForm({ quarter: currentQuarter(), finding: "", recommendation: "", severity: "medium" });
        fetchAll();
      })
      .catch((e) => setAuditMsg({ ok: false, text: e.message }))
      .finally(() => setSubmittingAudit(false));
  }

  const isStage2Plus = stage && stage.current_stage >= 2;
  const canClose = currentUser?.role === "admin" || currentUser?.role === "governance_company";
  const voteId = `vote-${bot.id}`;

  return (
    <div className="card space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-100">{bot.name}</h3>
          <p className="text-xs text-gray-500">{bot.strategy_name}</p>
        </div>
        <button onClick={() => { fetchAll(); setHoldingsRevision((value) => value + 1); }} className="btn bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs">Refresh</button>
      </div>

      {loading && <p className="text-sm text-gray-500">Loading…</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}

      {/* Current stage */}
      {stage && (
        <div className="flex items-center gap-3 bg-gray-800/50 rounded-lg px-3 py-2">
          <StageBadge stage={stage.current_stage} />
          <span className="text-xs text-gray-500">Current governance stage</span>
        </div>
      )}

      {/* Stage 2+ review banner */}
      {isStage2Plus && (
        <div className="rounded-lg border border-amber-700 bg-amber-900/20 px-4 py-3 space-y-1">
          <p className="text-sm font-semibold text-amber-400">
            Stage {stage.current_stage} — Simulated Review
          </p>
          <p className="text-xs text-amber-300/70">
            This bot's poll history places it in a simulated review stage. You can submit findings and recommendations.
          </p>
        </div>
      )}

      {/* Submit vote */}
      <div className="border-t border-gray-800 pt-3 space-y-2">
        <h4 className="text-xs font-semibold text-gray-400">Submit Satisfaction Vote</h4>
        <p className="text-xs text-gray-400">Voting is simulated. Weight uses your balance at vote time; transferable tokens can be counted again after transfer. Displayed holdings reflect the last refresh.</p>
        <form onSubmit={handleVote} className="grid grid-cols-2 gap-2">
          <div>
            <label className="label" htmlFor={`${voteId}-quarter`}>Quarter (UTC)</label>
            <input id={`${voteId}-quarter`} className="input" pattern="[0-9]{4}-Q[1-4]" title="Use YYYY-Q1 through YYYY-Q4" required value={voteForm.quarter} onChange={(e) => setVoteForm({ ...voteForm, quarter: e.target.value })} />
          </div>
          <div>
            <span className="label">Signed in as</span>
            <p className="input" aria-label={`Signed in as ${currentUser?.email ?? "unavailable"}`}>{currentUser?.email ?? "Unavailable"}</p>
          </div>
          <div>
            <span className="label">Current holdings for this bot</span>
            <p className="input" role="status">{holdingStatus === "loading" ? "Loading…" : holdingStatus === "ready" ? `${holding} RST` : "Unavailable"}</p>
          </div>
          <div>
            <label className="label" htmlFor={`${voteId}-choice`}>Vote</label>
            <select id={`${voteId}-choice`} className="input" value={voteForm.vote} onChange={(e) => setVoteForm({ ...voteForm, vote: e.target.value })}>
              <option value="satisfied">Satisfied</option>
              <option value="unsatisfied">Not Satisfied</option>
            </select>
          </div>
          <div className="col-span-2">
            <button type="submit" className="btn-primary text-sm" disabled={voting || holdingStatus !== "ready" || !(holding > 0)}>
              {voting ? "Submitting…" : "Submit Vote"}
            </button>
          </div>
        </form>
        {holdingStatus === "ready" && holding === 0 && <p className="text-xs text-gray-400">A positive RST balance for this bot is required to vote.</p>}
        {holdingStatus === "error" && <p className="text-xs text-red-400" role="alert">Could not load holdings: {holdingError}. Use Refresh to retry.</p>}
        {voteMsg && <p role="status" className={`text-xs ${voteMsg.ok ? "text-green-400" : "text-red-400"}`}>{voteMsg.text}</p>}
      </div>

      {/* Close poll */}
      {canClose && <div className="border-t border-gray-800 pt-3 space-y-2">
        <h4 className="text-xs font-semibold text-gray-400">Close Poll</h4>
        <form onSubmit={handleClosePoll} className="flex gap-2">
          <label className="sr-only" htmlFor={`${voteId}-close-quarter`}>Quarter to close</label>
          <input id={`${voteId}-close-quarter`} className="input flex-1" pattern="[0-9]{4}-Q[1-4]" title="Use YYYY-Q1 through YYYY-Q4" required value={closeQuarter} onChange={(e) => setCloseQuarter(e.target.value)} placeholder={`e.g. ${currentQuarter()}`} />
          <button type="submit" disabled={closing} className="btn bg-amber-700 hover:bg-amber-600 text-white text-sm">
            {closing ? "Closing…" : "Close Poll"}
          </button>
        </form>
        {closeResult && !closeResult.error && (
          <div className="bg-gray-800 rounded p-3 text-xs space-y-1">
            <p className="text-gray-300 font-medium">Poll Closed — {closeResult.quarter}</p>
            <p className="text-gray-400">
              Satisfaction:{" "}
              <span className={closeResult.satisfaction_rate >= 0.5 ? "text-green-400" : "text-red-400"}>
                {(closeResult.satisfaction_rate * 100).toFixed(1)}%
              </span>
              {" "}· Weight: {closeResult.satisfied_weight} / {closeResult.total_weight}
            </p>
          </div>
        )}
        {closeResult?.error && <p className="text-xs text-red-400">{closeResult.error}</p>}
      </div>}

      {/* Audit form — Stage 2+ only */}
      {isStage2Plus && (
        <div className="border-t border-amber-800/50 pt-3 space-y-2">
          <h4 className="text-xs font-semibold text-amber-400">Submit Audit Report</h4>
          <form onSubmit={handleAuditSubmit} className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="label">Quarter</label>
                <input className="input" value={auditForm.quarter} onChange={(e) => setAuditForm({ ...auditForm, quarter: e.target.value })} required />
              </div>
              <div>
                <label className="label">Severity</label>
                <select className="input" value={auditForm.severity} onChange={(e) => setAuditForm({ ...auditForm, severity: e.target.value })}>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>
            </div>
            <div>
              <label className="label">Findings</label>
              <textarea className="input min-h-[64px] resize-y" placeholder="What issues were identified?" value={auditForm.finding} onChange={(e) => setAuditForm({ ...auditForm, finding: e.target.value })} required />
            </div>
            <div>
              <label className="label">Recommendations</label>
              <textarea className="input min-h-[56px] resize-y" placeholder="What corrective actions are recommended?" value={auditForm.recommendation} onChange={(e) => setAuditForm({ ...auditForm, recommendation: e.target.value })} required />
            </div>
            <button type="submit" className="btn bg-amber-700 hover:bg-amber-600 text-white text-sm" disabled={submittingAudit}>
              {submittingAudit ? "Submitting…" : "Submit Audit Report"}
            </button>
          </form>
          {auditMsg && <p className={`text-xs ${auditMsg.ok ? "text-green-400" : "text-red-400"}`}>{auditMsg.text}</p>}
        </div>
      )}

      {/* Audit history */}
      {audits.length > 0 && (
        <div className="border-t border-gray-800 pt-3 space-y-2">
          <h4 className="text-xs font-semibold text-gray-400">
            Audit Reports <span className="ml-1 text-gray-600">({audits.length})</span>
          </h4>
          <div className="space-y-2">
            {audits.map((a) => (
              <div key={a.id} className="bg-gray-800/60 rounded-lg px-3 py-2 space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`badge ${SEVERITY_COLORS[a.severity] ?? "badge-yellow"}`}>{a.severity}</span>
                  <span className="text-xs font-mono text-gray-400">{a.quarter}</span>
                  <span className="text-xs text-gray-600">by {a.submitted_by}</span>
                  <span className="text-xs text-gray-600 ml-auto">{new Date(a.created_at).toLocaleDateString()}</span>
                </div>
                <p className="text-xs text-gray-300"><span className="text-gray-500">Finding: </span>{a.finding}</p>
                <p className="text-xs text-gray-400"><span className="text-gray-500">Recommendation: </span>{a.recommendation}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Poll history */}
      <div className="border-t border-gray-800 pt-3 space-y-2">
        <h4 className="text-xs font-semibold text-gray-400">
          Poll History
          {polls.length > 0 && <span className="ml-2 text-gray-600">({polls.length} poll{polls.length !== 1 ? "s" : ""})</span>}
        </h4>
        <PollHistoryTable polls={polls} />
      </div>
    </div>
  );
}

export default function Governance() {
  const [bots, setBots] = useState([]);
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      apiFetch("/bots/").then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
      apiFetch("/auth/me").then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
    ])
      .then(([b, u]) => { setBots(b); setCurrentUser(u); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div className="page-heading"><div>
        <p className="page-kicker">Community oversight</p>
        <h1>Governance</h1>
        <p className="page-subtitle">
          Stage 1 Normal → Stage 2 Review → Stage 3 Community. These are simulated indicators; Stage 3 does not transfer control.
        </p>
      </div></div>
      {loading && <p className="text-sm text-gray-500">Loading bots…</p>}
      {error && <p className="text-sm text-red-400">Error: {error}</p>}
      {!loading && !error && bots.length === 0 && <p className="text-sm text-gray-500">No bots found.</p>}
      <div className="grid gap-4 md:grid-cols-2">
        {bots.map((bot) => <BotGovernance key={bot.id} bot={bot} currentUser={currentUser} />)}
      </div>
    </div>
  );
}
