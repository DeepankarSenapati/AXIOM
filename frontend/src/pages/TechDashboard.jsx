import { useEffect, useState } from "react";
import { authHeaders, getUser } from "../auth.js";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STRATEGIES = ["simple_ma", "rsi", "bollinger_bands", "macd", "momentum"];

const STRATEGY_PARAMS = {
  simple_ma: { short_window: 5, long_window: 20 },
  rsi: { period: 14, oversold: 30, overbought: 70 },
  bollinger_bands: { window: 20, num_std: 2.0 },
  macd: { fast: 12, slow: 26, signal: 9 },
  momentum: { window: 10, threshold: 0.02, stop_loss: 0.03 },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric", month: "short", day: "numeric",
  });
}

function StatusBadge({ status }) {
  const map = {
    pending_approval: "badge-yellow",
    approved: "badge-blue",
    live: "badge-green",
    rejected: "badge-red",
  };
  return (
    <span className={`badge ${map[status] ?? "bg-gray-700 text-gray-400"}`}>
      {status ?? "unknown"}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Section A — My Bots
// ---------------------------------------------------------------------------

function MyBots({ bots, loading, error }) {
  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">My Bots</h2>
      {loading && <p className="text-sm text-gray-500">Loading…</p>}
      {error && <p className="text-sm text-red-400">Error: {error}</p>}
      {!loading && !error && bots.length === 0 && (
        <p className="text-sm text-gray-500">You haven&#39;t submitted any bots yet</p>
      )}
      {bots.length > 0 && (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800">
              <th className="th">Name</th>
              <th className="th">Strategy</th>
              <th className="th">Status</th>
              <th className="th">Description</th>
              <th className="th">Created</th>
            </tr>
          </thead>
          <tbody>
            {bots.map(bot => (
              <tr key={bot.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                <td className="td font-medium text-gray-100">{bot.name}</td>
                <td className="td">
                  <span className="badge badge-blue">{bot.strategy_key ?? bot.strategy_name}</span>
                </td>
                <td className="td">
                  <StatusBadge status={bot.status} />
                </td>
                <td className="td text-gray-400 max-w-xs truncate">
                  {bot.description || <span className="text-gray-600">—</span>}
                </td>
                <td className="td text-gray-500">{fmt(bot.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section B — Submit New Bot
// ---------------------------------------------------------------------------

function SubmitBot({ onBotCreated }) {
  const [form, setForm] = useState({ name: "", strategy_key: "simple_ma", description: "" });
  const [botParams, setBotParams] = useState({ ...STRATEGY_PARAMS["simple_ma"] });
  const [paramErrors, setParamErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  function handleStrategyChange(newStrategy) {
    setForm(f => ({ ...f, strategy_key: newStrategy }));
    setBotParams({ ...STRATEGY_PARAMS[newStrategy] });
    setParamErrors({});
  }

  function handleParamChange(key, value) {
    const n = parseFloat(value);
    const invalid = isNaN(n) || n <= 0;
    setParamErrors(prev => ({ ...prev, [key]: invalid }));
    setBotParams(prev => ({ ...prev, [key]: invalid ? value : n }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSubmitting(true);
    setSubmitError(null);
    setSuccessMsg(null);

    try {
      const res = await fetch("/bots/", {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name.trim(),
          strategy_key: form.strategy_key,
          description: form.description.trim(),
          params: botParams,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setSubmitError(JSON.stringify(data.detail ?? data));
        return;
      }
      setSuccessMsg("Submitted! Awaiting admin approval.");
      setForm({ name: "", strategy_key: "simple_ma", description: "" });
      setBotParams({ ...STRATEGY_PARAMS["simple_ma"] });
      setParamErrors({});
      onBotCreated();
    } catch (e) {
      setSubmitError(e.message ?? "Network error");
    } finally {
      setSubmitting(false);
    }
  }

  const currentParams = STRATEGY_PARAMS[form.strategy_key] ?? {};

  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">Submit New Bot</h2>

      {successMsg && (
        <div className="mb-3 px-3 py-2 rounded bg-green-900/50 border border-green-700 text-green-300 text-sm">
          {successMsg}
        </div>
      )}
      {submitError && (
        <p className="mb-2 text-xs text-red-400">{submitError}</p>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Name + Strategy row */}
        <div className="flex gap-3 items-end flex-wrap">
          <div className="flex-1 min-w-[160px]">
            <label className="label">Bot Name</label>
            <input
              className="input"
              placeholder="e.g. Alpha-RSI"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              required
            />
          </div>
          <div className="w-44">
            <label className="label">Strategy</label>
            <select
              className="input"
              value={form.strategy_key}
              onChange={e => handleStrategyChange(e.target.value)}
            >
              {STRATEGIES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>

        {/* Description */}
        <div>
          <label className="label">Description</label>
          <textarea
            className="input min-h-[72px] resize-y"
            placeholder="What does this bot do?"
            value={form.description}
            onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
          />
        </div>

        {/* Strategy parameters */}
        {Object.keys(currentParams).length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
              Strategy Parameters
            </p>
            <div className="flex flex-wrap gap-3">
              {Object.entries(currentParams).map(([key]) => (
                <div key={key} className="flex flex-col gap-1">
                  <label className="label text-xs">{key}</label>
                  <input
                    type="number"
                    className={`input w-28 ${paramErrors[key] ? "border-red-500 focus:border-red-500" : ""}`}
                    step="any"
                    min="0"
                    value={botParams[key] ?? currentParams[key]}
                    onChange={e => handleParamChange(key, e.target.value)}
                  />
                  {paramErrors[key] && (
                    <p className="text-xs text-red-400">Must be &gt; 0</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <button type="submit" className="btn-primary" disabled={submitting}>
          {submitting ? "Submitting…" : "Submit Bot"}
        </button>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section C — Revenue Summary
// ---------------------------------------------------------------------------

function RevenueSummary({ bots }) {
  const [revenues, setRevenues] = useState({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (bots.length === 0) return;
    setLoading(true);
    const headers = authHeaders();

    Promise.all(
      bots.map(bot =>
        fetch(`/tokenomics/balances/${bot.id}`, { headers })
          .then(r => r.ok ? r.json() : null)
          .then(data => ({ id: bot.id, data }))
          .catch(() => ({ id: bot.id, data: null }))
      )
    ).then(results => {
      const map = {};
      for (const { id, data } of results) {
        map[id] = data;
      }
      setRevenues(map);
      setLoading(false);
    });
  }, [bots]);

  if (bots.length === 0) {
    return (
      <div className="card">
        <h2 className="text-sm font-semibold text-gray-300 mb-3">Revenue Summary</h2>
        <p className="text-sm text-gray-500">No revenue data yet</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-gray-300 mb-1">Revenue Summary</h2>
      <p className="text-xs text-gray-600 mb-3">Tech company share (15%) per bot</p>
      {loading && <p className="text-sm text-gray-500">Loading…</p>}
      {!loading && (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800">
              <th className="th">Bot Name</th>
              <th className="th">Revenue Earned</th>
            </tr>
          </thead>
          <tbody>
            {bots.map(bot => {
              const d = revenues[bot.id];
              const earned = d?.tech_balance ?? d?.tech_wallet ?? null;
              return (
                <tr key={bot.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                  <td className="td font-medium text-gray-100">{bot.name}</td>
                  <td className="td font-mono text-gray-300">
                    {earned !== null && earned !== undefined
                      ? `$${Number(earned).toFixed(2)}`
                      : <span className="text-gray-600">—</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function TechDashboard() {
  const [bots, setBots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  async function fetchBots() {
    setLoading(true);
    try {
      const res = await fetch("/bots/", { headers: authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setBots(await res.json());
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchBots(); }, []);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-100">Tech Dashboard</h1>
        <button
          onClick={fetchBots}
          className="btn bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm"
        >
          Refresh
        </button>
      </div>

      {/* A — My Bots */}
      <MyBots bots={bots} loading={loading} error={error} />

      {/* B — Submit New Bot */}
      <SubmitBot onBotCreated={fetchBots} />

      {/* C — Revenue Summary */}
      <RevenueSummary bots={bots} />
    </div>
  );
}
